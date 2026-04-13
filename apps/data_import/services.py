import logging

from django.utils import timezone

from apps.counterparties.models import Counterparty
from apps.counterparties.services import find_duplicates

from .models import DuplicateCandidate, ImportLog, ImportSession

logger = logging.getLogger("apps.data_import")


def process_import(session_id):
    """Основной процесс импорта данных."""
    session = ImportSession.objects.get(pk=session_id)
    session.status = ImportSession.Status.PROCESSING
    session.started_at = timezone.now()
    session.save(update_fields=["status", "started_at"])

    try:
        # Парсинг файла
        if session.file_format == ImportSession.FileFormat.EXCEL:
            from .parsers.excel_parser import parse_excel_counterparties
            parsed = parse_excel_counterparties(session.uploaded_file)
        else:
            from .parsers.xml_parser import parse_xml_counterparties
            parsed = parse_xml_counterparties(session.uploaded_file)

        session.total_records = len(parsed)
        session.status = ImportSession.Status.VALIDATING
        session.save(update_fields=["total_records", "status"])

        # Обработка записей
        for entry in parsed:
            session.processed_records += 1

            if "error" in entry:
                session.error_records += 1
                ImportLog.objects.create(
                    session=session,
                    level=ImportLog.Level.ERROR,
                    message=entry["error"],
                    row_number=entry["row"],
                )
                continue

            data = entry["data"]

            # Проверка дублей
            dupes = find_duplicates(inn=data.get("inn"), name=data.get("name"))
            if dupes:
                session.duplicates_found += 1
                for dupe in dupes:
                    DuplicateCandidate.objects.create(
                        session=session,
                        existing_counterparty=dupe["counterparty"],
                        new_counterparty_data=data,
                        match_field=dupe["match_field"],
                        match_confidence=dupe["confidence"],
                    )
                ImportLog.objects.create(
                    session=session,
                    level=ImportLog.Level.WARNING,
                    message=f"Найден дубль по {dupes[0]['match_field']}: {data.get('name', '')}",
                    row_number=entry["row"],
                    object_type="Counterparty",
                    object_data=data,
                )
                continue

            # Создание или обновление
            cp, created = Counterparty.objects.update_or_create(
                code_1c=data["code_1c"],
                defaults={
                    "name": data.get("name", ""),
                    "full_name": data.get("full_name", ""),
                    "inn": data.get("inn", ""),
                    "kpp": data.get("kpp", ""),
                    "phone": data.get("phone", ""),
                    "email": data.get("email", ""),
                    "contact_person": data.get("contact_person", ""),
                },
            )

            if created:
                session.created_records += 1
            else:
                session.updated_records += 1

            ImportLog.objects.create(
                session=session,
                level=ImportLog.Level.INFO,
                message=f"{'Создан' if created else 'Обновлён'}: {cp.name}",
                row_number=entry["row"],
                object_type="Counterparty",
                object_data=data,
            )

        # Финализация
        if session.error_records > 0 or session.duplicates_found > 0:
            session.status = ImportSession.Status.COMPLETED_WITH_WARNINGS
        else:
            session.status = ImportSession.Status.COMPLETED

        session.completed_at = timezone.now()
        session.save()

        logger.info(
            "Импорт #%d завершён: создано=%d, обновлено=%d, ошибок=%d, дублей=%d",
            session.pk,
            session.created_records,
            session.updated_records,
            session.error_records,
            session.duplicates_found,
        )

    except Exception as e:
        session.status = ImportSession.Status.FAILED
        session.error_message = str(e)
        session.completed_at = timezone.now()
        session.save()
        logger.exception("Ошибка импорта #%d: %s", session.pk, e)
        raise
