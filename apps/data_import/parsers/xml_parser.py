import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger("apps.data_import")


def parse_xml_counterparties(file_obj):
    """Парсинг контрагентов из XML."""
    file_obj.seek(0)
    tree = ET.parse(file_obj)
    root = tree.getroot()

    section = root.find("Контрагенты")
    if section is None:
        return []

    results = []
    for i, elem in enumerate(section, start=1):
        try:
            data = {
                "code_1c": elem.findtext("Код", "").strip(),
                "name": elem.findtext("Наименование", "").strip(),
                "full_name": elem.findtext("ПолноеНаименование", "").strip(),
                "inn": elem.findtext("ИНН", "").strip(),
                "kpp": elem.findtext("КПП", "").strip(),
                "phone": elem.findtext("Телефон", "").strip(),
                "email": elem.findtext("Email", "").strip(),
                "contact_person": elem.findtext("КонтактноеЛицо", "").strip(),
            }
            results.append({"row": i, "data": data})
        except Exception as e:
            logger.warning("Ошибка парсинга элемента %d: %s", i, e)
            results.append({"row": i, "error": str(e)})

    return results


def parse_xml_contracts(file_obj):
    """Парсинг договоров из XML."""
    file_obj.seek(0)
    tree = ET.parse(file_obj)
    root = tree.getroot()

    section = root.find("Договоры")
    if section is None:
        return []

    results = []
    for i, elem in enumerate(section, start=1):
        try:
            data = {
                "code_1c": elem.findtext("Код", "").strip(),
                "counterparty_code": elem.findtext("КодКонтрагента", "").strip(),
                "number": elem.findtext("Номер", "").strip(),
                "date": elem.findtext("Дата", "").strip(),
                "kind": elem.findtext("Вид", "supply").strip(),
                "payment_days": int(elem.findtext("СрокОплаты", "30").strip()),
            }
            results.append({"row": i, "data": data})
        except Exception as e:
            logger.warning("Ошибка парсинга элемента %d: %s", i, e)
            results.append({"row": i, "error": str(e)})

    return results
