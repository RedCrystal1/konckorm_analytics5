import hashlib
import logging

logger = logging.getLogger("apps.data_import")


def calculate_checksum(file_obj):
    """Вычисление контрольной суммы файла (SHA-256)."""
    sha256 = hashlib.sha256()
    file_obj.seek(0)
    for chunk in file_obj.chunks():
        sha256.update(chunk)
    file_obj.seek(0)
    return sha256.hexdigest()


def validate_xml_structure(file_obj):
    """Валидация структуры XML-файла."""
    import xml.etree.ElementTree as ET

    errors = []
    try:
        file_obj.seek(0)
        tree = ET.parse(file_obj)
        root = tree.getroot()

        # Проверяем наличие обязательных элементов
        required_tags = {"Контрагенты", "Договоры", "Документы"}
        found_tags = {child.tag for child in root}
        missing = required_tags - found_tags

        if missing:
            errors.append(f"Отсутствуют обязательные секции: {', '.join(missing)}")

    except ET.ParseError as e:
        errors.append(f"Ошибка парсинга XML: {e}")
    finally:
        file_obj.seek(0)

    return errors


def validate_excel_structure(file_obj):
    """Валидация структуры Excel-файла."""
    errors = []
    try:
        import openpyxl

        file_obj.seek(0)
        wb = openpyxl.load_workbook(file_obj, read_only=True)

        required_sheets = {"Контрагенты", "Договоры"}
        found_sheets = set(wb.sheetnames)
        missing = required_sheets - found_sheets

        if missing:
            errors.append(f"Отсутствуют обязательные листы: {', '.join(missing)}")

        wb.close()
    except Exception as e:
        errors.append(f"Ошибка чтения Excel: {e}")
    finally:
        file_obj.seek(0)

    return errors
