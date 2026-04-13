"""
ПОЛНОЕ НАПОЛНЕНИЕ ДЕМО-ДАННЫМИ — РАСШИРЕННАЯ ВЕРСИЯ

Этот скрипт создаёт реалистичные данные для всех 21 таблицы проекта.
Каждый блок объяснён комментариями.

Использование:
    python manage.py shell
    exec(open("scripts/seed_demo_data.py", encoding="utf-8").read())
    run()
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

random.seed(42)  # Фиксированный seed — данные воспроизводимы


def run():
    from apps.accounts.models import ActivityLog, User, UserCounterpartyAccess
    from apps.analytics.models import AnalyticsSnapshot
    from apps.counterparties.models import Contract, Counterparty, CounterpartyHistorySnapshot
    from apps.data_import.models import ImportSession, ImportLog
    from apps.directories.models import Department, Nomenclature
    from apps.documents.models import AccountBalance, GoodsReceipt, GoodsReceiptItem, Invoice, PaymentOrder
    from apps.notifications.models import Notification
    from apps.payments.models import CashBalance, CashGapAlert
    from apps.reconciliation.models import Discrepancy, ReconciliationAct
    from apps.registers.models import ContractConditionHistory, DebtByTerms, PlannedPayment, ProcurementVolume

    today = timezone.now().date()
    print("=" * 70)
    print("  ПОЛНОЕ НАПОЛНЕНИЕ ДЕМО-ДАННЫМИ (расширенная версия)")
    print("=" * 70)

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 1: ПОДРАЗДЕЛЕНИЯ
    # ══════════════════════════════════════════════════════════════════
    # Создаём иерархию подразделений предприятия.
    # parent — ссылка на вышестоящее подразделение (древовидная структура).
    # Это нужно для аналитики задолженности в разрезе подразделений.

    root, _ = Department.objects.get_or_create(code="HQ", defaults={"name": "АО Концкорма"})
    dept_data = [
        ("ADM", "Администрация"), ("FIN", "Финансовый отдел"), ("BUH", "Бухгалтерия"),
        ("PROC", "Отдел закупок"), ("PROD", "Производство"), ("LOG", "Логистика"),
        ("SKLAD", "Складской комплекс"), ("QC", "Контроль качества"),
        ("SALES", "Отдел продаж"), ("IT", "Информационные технологии"),
    ]
    departments = {"HQ": root}
    for code, name in dept_data:
        d, _ = Department.objects.get_or_create(code=code, defaults={"name": name, "parent": root})
        departments[code] = d
    print(f"  [1/17] Подразделения: {Department.objects.count()}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 2: ПОЛЬЗОВАТЕЛИ
    # ══════════════════════════════════════════════════════════════════
    # 4 роли: admin, accountant, manager, procurement.
    # Каждый пользователь привязан к подразделению, имеет должность.
    # Настройки уведомлений: кто о чём хочет получать уведомления.
    # admin — суперпользователь Django (is_staff + is_superuser), может в Django Admin.

    users_data = [
        ("admin",    "Иванов",   "Петр",    "Сергеевич",  "admin",       "ADM",  "Генеральный директор",   "+7(495)111-11-11"),
        ("buhgalter","Сидорова", "Анна",    "Викторовна", "accountant",  "BUH",  "Главный бухгалтер",      "+7(495)222-22-22"),
        ("buh2",     "Кравцова", "Мария",   "Андреевна",  "accountant",  "BUH",  "Бухгалтер расчётного отдела", "+7(495)222-33-33"),
        ("buh3",     "Тихонова", "Ольга",   "Сергеевна",  "accountant",  "FIN",  "Финансовый аналитик",    "+7(495)222-44-44"),
        ("rukovod",  "Козлов",   "Дмитрий", "Алексеевич", "manager",     "ADM",  "Финансовый директор",    "+7(495)333-33-33"),
        ("rukovod2", "Белова",   "Екатерина","Павловна",  "manager",     "PROC", "Начальник отдела закупок","+7(495)333-44-44"),
        ("zakupki1", "Петрова",  "Елена",   "Ивановна",  "procurement", "PROC", "Менеджер по закупкам (сырьё)", "+7(495)444-44-44"),
        ("zakupki2", "Волков",   "Алексей", "Дмитриевич", "procurement", "PROC", "Менеджер по закупкам (материалы)", "+7(495)555-55-55"),
        ("zakupki3", "Соколова", "Наталья", "Олеговна",  "procurement", "PROC", "Менеджер по закупкам (услуги)", "+7(495)666-66-66"),
    ]
    users = {}
    for username, last, first, patron, role, dept_code, position, phone in users_data:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "last_name": last, "first_name": first, "patronymic": patron,
                "role": role, "department": departments[dept_code],
                "position": position, "phone": phone,
                "email": f"{username}@konckorm.ru", "is_active": True,
                "notify_overdue": role in ("admin", "accountant", "manager"),
                "notify_cash_gap": role in ("admin", "accountant", "manager"),
                "notify_import": role == "accountant",
            },
        )
        if created:
            user.set_password("demo12345!")
            if role == "admin":
                user.is_staff = True
                user.is_superuser = True
            user.save()
        users[username] = user
    mgr1, mgr2, mgr3 = users["zakupki1"], users["zakupki2"], users["zakupki3"]
    print(f"  [2/17] Пользователи: {User.objects.count()}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 3: НОМЕНКЛАТУРА
    # ══════════════════════════════════════════════════════════════════
    # Классификация по видам: raw (сырьё), material (материалы), service (услуги), goods (товары).
    # Это нужно для отчёта «Структура закупок по видам».

    nom_data = [
        ("NOM-001", "Комбикорм ПК-1 (куры-несушки)", "raw", "кг"),
        ("NOM-002", "Комбикорм ПК-2 (цыплята-бройлеры)", "raw", "кг"),
        ("NOM-003", "Комбикорм ПК-5 (свиньи на откорме)", "raw", "кг"),
        ("NOM-004", "Премикс витаминный П-5-1", "raw", "кг"),
        ("NOM-005", "Премикс минеральный ПМ-2", "raw", "кг"),
        ("NOM-006", "Зерно пшеничное фуражное (3 класс)", "raw", "т"),
        ("NOM-007", "Зерно ячменное фуражное", "raw", "т"),
        ("NOM-008", "Жмых подсолнечный", "raw", "т"),
        ("NOM-009", "Соевый шрот (протеин 46%)", "raw", "т"),
        ("NOM-010", "Кукуруза фуражная", "raw", "т"),
        ("NOM-011", "Рыбная мука (протеин 65%)", "raw", "кг"),
        ("NOM-012", "Мел кормовой (CaCO3)", "raw", "кг"),
        ("NOM-013", "Соль поваренная (помол №1)", "raw", "кг"),
        ("NOM-014", "Мешки полипропиленовые 50кг", "material", "шт"),
        ("NOM-015", "Мешки бумажные крафт 25кг", "material", "шт"),
        ("NOM-016", "Этикетки самоклеящиеся", "material", "рулон"),
        ("NOM-017", "Запчасти для грануляторной линии", "material", "комплект"),
        ("NOM-018", "Фильтры для аспирации", "material", "шт"),
        ("NOM-019", "ГСМ дизельное топливо (ДТ-Л)", "material", "л"),
        ("NOM-020", "Транспортные услуги (доставка сырья)", "service", "рейс"),
        ("NOM-021", "Аренда склада 200 м²", "service", "мес"),
        ("NOM-022", "Сертификация продукции ГОСТ", "service", "усл"),
        ("NOM-023", "Лабораторный анализ кормов", "service", "анализ"),
        ("NOM-024", "Ремонт промышленного оборудования", "service", "усл"),
        ("NOM-025", "Масло подсолнечное (добавка)", "raw", "л"),
    ]
    noms = {}
    for code, name, kind, unit in nom_data:
        n, _ = Nomenclature.objects.get_or_create(code=code, defaults={"name": name, "kind": kind, "unit": unit})
        noms[code] = n
    print(f"  [3/17] Номенклатура: {Nomenclature.objects.count()}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 4: КОНТРАГЕНТЫ
    # ══════════════════════════════════════════════════════════════════
    # Полные реквизиты: ИНН, КПП, юр/факт адрес, телефон, email, контакт.
    # is_key_supplier — признак «ключевой поставщик» (обеспечивает 80% закупок).
    # responsible_manager — менеджер по закупкам, ответственный за этого контрагента.
    # code_1c — идентификатор для синхронизации с 1С.

    cp_data = [
        ("1C-001", "ООО АгроКорм",        "Общество с ограниченной ответственностью АгроКорм",       "7701234567", "770101001", True,  mgr1, "г. Москва, ул. Зерновая, д. 15, стр. 2",   "+7(495)600-11-11", "agro@agrokorm.ru",      "Смирнов Иван Петрович"),
        ("1C-002", "ЗАО ЗерноТрейд",      "Закрытое акционерное общество ЗерноТрейд",               "7702345678", "770201001", True,  mgr1, "г. Москва, Ленинский пр., д. 42, оф. 310", "+7(495)600-22-22", "trade@zernotrade.ru",   "Козлова Ольга Анатольевна"),
        ("1C-003", "ИП Семёнов А.В.",      "Индивидуальный предприниматель Семёнов Андрей Викторович","772099887766","",         False, mgr2, "г. Москва, ул. Частная, д. 3, кв. 15",     "+7(903)111-22-33", "semenov@mail.ru",       "Семёнов А.В."),
        ("1C-004", "ООО ПремиксПро",       "Общество с ограниченной ответственностью ПремиксПро",    "7703456789", "770301001", True,  mgr1, "г. Рязань, пр. Кормовой, д. 22",           "+7(491)333-44-55", "sale@premixpro.ru",     "Новиков Дмитрий Сергеевич"),
        ("1C-005", "АО Логистика-М",       "Акционерное общество Логистика-М",                       "7704567890", "770401001", False, mgr3, "г. Москва, ш. Энтузиастов, д. 50, корп. 3","+7(495)600-55-66", "log@logistika-m.ru",    "Белов Сергей Константинович"),
        ("1C-006", "ООО Упаковка Плюс",    "Общество с ограниченной ответственностью Упаковка Плюс", "7705678901", "770501001", False, mgr2, "г. Тула, ул. Промышленная, д. 12, лит. А",  "+7(487)444-55-66", "pack@upakovka.ru",      "Жукова Лариса Михайловна"),
        ("1C-007", "КФХ Нива",             "Крестьянское фермерское хозяйство Нива",                 "7706789012", "770601001", True,  mgr1, "с. Троицкое, ул. Полевая, д. 1",            "+7(496)777-88-99", "niva@farm.ru",          "Соколов Виктор Николаевич"),
        ("1C-008", "ООО СоевыйМир",        "Общество с ограниченной ответственностью СоевыйМир",    "7707890123", "770701001", False, mgr2, "г. Краснодар, ул. Южная, д. 45, оф. 201",   "+7(861)888-99-00", "soy@soyworld.ru",       "Попов Андрей Геннадьевич"),
        ("1C-009", "ИП Кузнецов Б.Г.",     "Индивидуальный предприниматель Кузнецов Борис Григорьевич","773011223344","",       False, mgr3, "г. Москва, ул. Лесная, д. 7, кв. 42",      "+7(926)333-44-55", "kuznetsov@inbox.ru",    "Кузнецов Б.Г."),
        ("1C-010", "ООО ТехноСервис",       "Общество с ограниченной ответственностью ТехноСервис",  "7708901234", "770801001", False, mgr3, "г. Воронеж, пр. Индустриальный, д. 3",      "+7(473)555-66-77", "service@tehnoserv.ru",  "Орлов Константин Борисович"),
        ("1C-011", "ООО РусЗерно",          "Общество с ограниченной ответственностью РусЗерно",     "7709123456", "770901001", True,  mgr1, "г. Ростов-на-Дону, ул. Аграрная, д. 18",   "+7(863)700-11-22", "info@ruszerno.ru",      "Морозов Алексей Павлович"),
        ("1C-012", "АО КормПром",            "Акционерное общество КормПром",                          "7710234567", "771001001", False, mgr2, "г. Самара, ул. Заводская, д. 55",           "+7(846)700-33-44", "sale@kormprom.ru",      "Лебедева Ирина Сергеевна"),
        ("1C-013", "ООО ГрануляторСервис",   "Общество с ограниченной ответственностью ГрануляторСервис","7711345678","771101001",False, mgr3, "г. Калуга, ул. Механиков, д. 8",            "+7(484)700-55-66", "service@granserv.ru",   "Титов Владимир Дмитриевич"),
        ("1C-014", "КФХ Урожай",             "Крестьянское фермерское хозяйство Урожай",              "7712456789", "771201001", False, mgr1, "с. Петровское, ул. Центральная, д. 1А",     "+7(496)800-77-88", "urozhay@farm.ru",       "Егоров Михаил Константинович"),
        ("1C-015", "ООО Витакорм",           "Общество с ограниченной ответственностью Витакорм",     "7713567890", "771301001", False, mgr2, "г. Брянск, пр. Станке Димитрова, д. 67",    "+7(483)700-88-99", "vita@vitakorm.ru",      "Федорова Людмила Анатольевна"),
    ]
    counterparties = []
    for code, name, full, inn, kpp, is_key, mgr, address, phone, email, contact in cp_data:
        cp, _ = Counterparty.objects.get_or_create(
            code_1c=code,
            defaults={
                "name": name, "full_name": full, "inn": inn, "kpp": kpp,
                "is_key_supplier": is_key, "responsible_manager": mgr, "is_active": True,
                "legal_address": address, "actual_address": address,
                "phone": phone, "email": email, "contact_person": contact,
                "notes": f"Контрагент {name}. Код 1С: {code}. Договор действует.",
            },
        )
        counterparties.append(cp)
        # Привязка менеджера к контрагенту (для фильтрации по роли procurement)
        UserCounterpartyAccess.objects.get_or_create(user=cp.responsible_manager, counterparty=cp)
    print(f"  [4/17] Контрагенты: {Counterparty.objects.count()}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 5: ДОГОВОРЫ
    # ══════════════════════════════════════════════════════════════════
    # Каждый контрагент имеет договор с условиями:
    # - kind: supply/service/work/lease
    # - payment_days: сколько дней на оплату после поступления
    # - credit_limit: максимальная допустимая сумма задолженности
    # - penalty_rate: процент пени за каждый день просрочки
    # ContractConditionHistory хранит историю изменений условий.

    contracts = []
    for i, cp in enumerate(counterparties):
        kinds = ["supply","supply","service","supply","service","supply","supply","supply","work","service","supply","supply","service","supply","supply"]
        pay_days_list = [30, 45, 14, 30, 60, 30, 45, 30, 14, 30, 30, 45, 21, 60, 30]
        limits = [5000000,3000000,None,1500000,2000000,500000,4000000,1500000,None,800000,6000000,1200000,None,2000000,1000000]
        penalties = [Decimal("0.1"),Decimal("0.05"),None,Decimal("0.1"),Decimal("0.03"),None,Decimal("0.1"),Decimal("0.05"),None,Decimal("0.1"),Decimal("0.05"),Decimal("0.1"),None,Decimal("0.03"),Decimal("0.1")]

        contract_date = date(2024, 1, 1) + timedelta(days=i * 20)
        contract, _ = Contract.objects.get_or_create(
            counterparty=cp, number=f"D-2024-{i+1:03d}",
            defaults={
                "code_1c": f"1C-D-{i+1:03d}", "name": f"Договор с {cp.name}",
                "date": contract_date, "kind": kinds[i], "currency": "RUB",
                "payment_term_type": "deferred", "payment_days": pay_days_list[i],
                "credit_limit": limits[i], "penalty_rate": penalties[i],
                "valid_from": contract_date, "valid_to": contract_date + timedelta(days=730),
                "is_active": True,
            },
        )
        contracts.append(contract)

        # История условий — фиксируем текущие условия
        ContractConditionHistory.objects.get_or_create(
            counterparty=cp, contract=contract, valid_from=contract_date,
            defaults={
                "payment_term_type": "deferred", "payment_days": pay_days_list[i],
                "credit_limit": limits[i],
                "penalty_info": f"Пени {penalties[i]}% за каждый день просрочки" if penalties[i] else "Штрафные санкции не предусмотрены",
                "changed_by": users["buhgalter"],
            },
        )
    print(f"  [5/17] Договоры: {Contract.objects.count()}, история условий: {ContractConditionHistory.objects.count()}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 6: ПОСТУПЛЕНИЯ (GoodsReceipt + GoodsReceiptItem)
    # ══════════════════════════════════════════════════════════════════
    # Главный документ системы — основание кредиторской задолженности.
    # Каждое поступление имеет товарные строки (GoodsReceiptItem).
    # payment_due_date рассчитывается от даты документа + срок оплаты из договора.
    # is_paid / paid_amount — статус и факт оплаты.
    # Распределяем по 6 месяцам для реалистичных графиков.

    receipts = []
    for i in range(120):
        cp = counterparties[i % len(counterparties)]
        contract = contracts[counterparties.index(cp)]
        # Даты от 180 дней назад до 5 дней вперёд (для будущих поступлений)
        doc_date = today - timedelta(days=random.randint(-5, 180))
        amount = Decimal(random.randint(50000, 12000000)) / 100
        due = doc_date + timedelta(days=contract.payment_days)

        # Статусы: 30% оплачены, 15% частично, 55% не оплачены
        roll = random.random()
        if roll < 0.30:
            is_paid, paid_amount = True, amount
        elif roll < 0.45:
            is_paid = False
            paid_amount = (amount * Decimal(str(random.uniform(0.15, 0.85)))).quantize(Decimal("0.01"))
        else:
            is_paid, paid_amount = False, Decimal("0")

        # Выбираем номенклатуру по виду контрагента
        kind = contract.kind
        if kind == "supply":
            nom_pool = [n for c, n in noms.items() if "NOM-0" in c and int(c[-2:]) <= 13]
        elif kind == "service":
            nom_pool = [n for c, n in noms.items() if int(c.split("-")[1]) >= 20]
        else:
            nom_pool = [n for c, n in noms.items() if 14 <= int(c.split("-")[1]) <= 19]

        receipt, created = GoodsReceipt.objects.get_or_create(
            number=f"PTU-{i+1:04d}",
            defaults={
                "code_1c": f"1C-PTU-{i+1:04d}", "date": doc_date,
                "counterparty": cp, "contract": contract,
                "amount": amount, "currency": "RUB",
                "payment_due_date": due, "is_paid": is_paid,
                "paid_amount": paid_amount, "created_by": users["buhgalter"],
            },
        )
        if created and nom_pool:
            items_count = random.randint(1, 5)
            remaining = amount
            for j in range(items_count):
                nom = random.choice(nom_pool)
                item_amount = remaining if j == items_count - 1 else (amount / items_count).quantize(Decimal("0.01"))
                remaining -= item_amount if j < items_count - 1 else Decimal("0")
                qty = Decimal(str(random.randint(10, 5000)))
                price = (item_amount / qty).quantize(Decimal("0.01")) if qty > 0 else Decimal("0")
                vat = (item_amount * Decimal("0.2") / Decimal("1.2")).quantize(Decimal("0.01"))
                GoodsReceiptItem.objects.create(
                    receipt=receipt, nomenclature=nom,
                    quantity=qty, price=price, amount=item_amount,
                    vat_rate=Decimal("20"), vat_amount=vat,
                )
        receipts.append(receipt)
    print(f"  [6/17] Поступления: {GoodsReceipt.objects.count()} (строк: {GoodsReceiptItem.objects.count()})")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 7: ПЛАТЁЖНЫЕ ПОРУЧЕНИЯ
    # ══════════════════════════════════════════════════════════════════
    # Факт оплаты — связывается с поступлением через related_receipt.
    # Дата платежа = дата поступления + случайное количество дней.

    pay_count = 0
    for receipt in receipts:
        if receipt.paid_amount > 0:
            pay_date = receipt.date + timedelta(days=random.randint(3, 55))
            PaymentOrder.objects.get_or_create(
                number=f"PP-{receipt.number[-4:]}",
                defaults={
                    "code_1c": f"1C-PP-{receipt.number[-4:]}", "date": pay_date,
                    "counterparty": receipt.counterparty, "contract": receipt.contract,
                    "amount": receipt.paid_amount, "related_receipt": receipt,
                    "payment_purpose": f"Оплата по дог. {receipt.contract.number} за пост. №{receipt.number}",
                    "created_by": users["buhgalter"],
                },
            )
            pay_count += 1
    print(f"  [7/17] Платёжные поручения: {pay_count}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 8: СЧЕТА НА ОПЛАТУ
    # ══════════════════════════════════════════════════════════════════
    inv_count = 0
    for i, receipt in enumerate(receipts[:50]):
        Invoice.objects.get_or_create(
            number=f"SCH-{i+1:04d}",
            defaults={
                "date": receipt.date - timedelta(days=random.randint(1, 7)),
                "counterparty": receipt.counterparty, "contract": receipt.contract,
                "amount": receipt.amount, "direction": "incoming",
                "payment_due_date": receipt.payment_due_date,
                "is_paid": receipt.is_paid, "created_by": users["buhgalter"],
            },
        )
        inv_count += 1
    print(f"  [8/17] Счета на оплату: {inv_count}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 9: ОСТАТКИ ПО СЧЕТАМ БУХУЧЁТА
    # ══════════════════════════════════════════════════════════════════
    # Остатки по счетам 60.01, 60.02, 60.21, 62, 76 на 1-е число каждого месяца.
    # Это данные из 1С — показывают состояние расчётов на дату.

    bal_count = 0
    accounts = ["60.01", "60.02", "76", "62"]
    for cp in counterparties:
        contract = contracts[counterparties.index(cp)]
        for month_offset in range(7):
            bal_date = (today.replace(day=1) - timedelta(days=30 * month_offset))
            base = Decimal(random.randint(50000, 3000000))
            factor = Decimal(str(1 - month_offset * 0.08))
            for acc in ["60.01"]:
                AccountBalance.objects.get_or_create(
                    account=acc, counterparty=cp, balance_date=bal_date,
                    defaults={
                        "contract": contract,
                        "debit": (base * Decimal("0.4") * factor).quantize(Decimal("0.01")),
                        "credit": (base * factor).quantize(Decimal("0.01")),
                        "balance": (base * Decimal("0.6") * factor).quantize(Decimal("0.01")),
                    },
                )
                bal_count += 1
        # 60.02 (авансы) — у 30% контрагентов
        if random.random() < 0.3:
            advance = Decimal(random.randint(50000, 800000))
            AccountBalance.objects.get_or_create(
                account="60.02", counterparty=cp, balance_date=today,
                defaults={"contract": contract, "debit": advance, "credit": Decimal("0"), "balance": advance},
            )
            bal_count += 1
        # 76 — у 20%
        if random.random() < 0.2:
            misc = Decimal(random.randint(10000, 200000))
            AccountBalance.objects.get_or_create(
                account="76", counterparty=cp, balance_date=today,
                defaults={"contract": contract, "debit": Decimal("0"), "credit": misc, "balance": -misc},
            )
            bal_count += 1
        # 62 — у 15%
        if random.random() < 0.15:
            buyers = Decimal(random.randint(30000, 500000))
            AccountBalance.objects.get_or_create(
                account="62", counterparty=cp, balance_date=today,
                defaults={"contract": contract, "debit": buyers, "credit": Decimal("0"), "balance": buyers},
            )
            bal_count += 1
    print(f"  [9/17] Остатки по счетам: {bal_count}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 10: РЕГИСТР ЗАДОЛЖЕННОСТИ
    # ══════════════════════════════════════════════════════════════════
    # Автоматический расчёт: берёт все неоплаченные поступления,
    # определяет статус (текущая/30/60/90/90+) по количеству дней просрочки.

    from apps.registers.services import update_debt_statuses
    debt_count = update_debt_statuses()
    print(f"  [10/17] Регистр задолженности: {debt_count}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 11: ПЛАНОВЫЕ ПЛАТЕЖИ (для платёжного календаря)
    # ══════════════════════════════════════════════════════════════════
    # Каждое неоплаченное поступление порождает плановый платёж.
    # Дополнительно создаём 30 будущих платежей (на следующие 30 дней)
    # чтобы календарь показывал данные вперёд.

    pp_count = 0
    for receipt in GoodsReceipt.objects.all():
        outstanding = receipt.outstanding_amount
        if outstanding <= 0 and not receipt.is_paid:
            continue
        overdue = receipt.overdue_days
        if receipt.is_paid:
            status = "completed"
            actual = receipt.date + timedelta(days=random.randint(5, 45))
        elif overdue > 0:
            status = "overdue"
            actual = None
        else:
            status = "pending"
            actual = None
        priority = "high" if outstanding > Decimal("30000") or overdue > 30 else ("medium" if outstanding > Decimal("10000") else "low")
        pp, created = PlannedPayment.objects.get_or_create(
            source_document=receipt,
            defaults={
                "counterparty": receipt.counterparty, "contract": receipt.contract,
                "planned_date": receipt.payment_due_date,
                "actual_date": actual,
                "amount": outstanding if not receipt.is_paid else receipt.amount,
                "status": status, "priority": priority,
                "deviation_days": (actual - receipt.payment_due_date).days if actual else 0,
            },
        )
        if created:
            pp_count += 1

    # Будущие платежи
    for i in range(30):
        cp = random.choice(counterparties)
        contract = contracts[counterparties.index(cp)]
        future_date = today + timedelta(days=random.randint(1, 35))
        amount = Decimal(random.randint(50000, 3000000)) / 100
        future_receipt, _ = GoodsReceipt.objects.get_or_create(
            number=f"PTU-F{i+1:03d}",
            defaults={
                "date": today - timedelta(days=random.randint(1, 15)),
                "counterparty": cp, "contract": contract,
                "amount": amount, "payment_due_date": future_date,
                "is_paid": False, "paid_amount": Decimal("0"),
                "created_by": users["buhgalter"],
            },
        )
        PlannedPayment.objects.get_or_create(
            source_document=future_receipt,
            defaults={
                "counterparty": cp, "contract": contract,
                "planned_date": future_date, "amount": amount,
                "status": "pending", "priority": random.choice(["high", "medium", "low"]),
            },
        )
        pp_count += 1
    print(f"  [11/17] Плановые платежи: {PlannedPayment.objects.count()}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 12: ПРОГНОЗ ОСТАТКОВ И КАССОВЫЕ РАЗРЫВЫ
    # ══════════════════════════════════════════════════════════════════
    # Моделируем прогноз на 45 дней.
    # Начальный баланс 1.5 млн (меньше чем раньше — чтобы были разрывы).
    # Каждый день: баланс + входящие (случайные) - исходящие (плановые платежи).
    # Если баланс < 0 — это кассовый разрыв, создаём CashGapAlert.

    balance = Decimal("1500000")
    gap_count = 0
    for day_offset in range(45):
        d = today + timedelta(days=day_offset)
        outflow = PlannedPayment.objects.filter(
            planned_date=d, status__in=["pending", "overdue"]
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        inflow = Decimal(random.randint(0, 150000))
        closing = balance + inflow - outflow
        is_gap = closing < 0

        CashBalance.objects.update_or_create(
            date=d, defaults={
                "opening_balance": balance, "total_inflow": inflow,
                "total_outflow": outflow, "closing_balance": closing,
                "is_cash_gap": is_gap,
            },
        )
        if is_gap:
            CashGapAlert.objects.get_or_create(date=d, defaults={"deficit_amount": abs(closing)})
            gap_count += 1
        balance = max(closing, Decimal("50000"))
    print(f"  [12/17] Прогноз остатков: 45 дней, кассовых разрывов: {gap_count}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 13: ОБЪЁМЫ ЗАКУПОК (помесячно за 6 месяцев)
    # ══════════════════════════════════════════════════════════════════
    # Для каждого контрагента и каждого месяца считаем:
    # - volume_rub: сколько закупили в рублях
    # - share_percent: доля этого контрагента в общем объёме за месяц
    # - procurement_kind: вид закупок (raw/material/service — из номенклатуры)

    pv_count = 0
    for month_offset in range(6):
        period_start = (today.replace(day=1) - timedelta(days=30 * month_offset)).replace(day=1)
        period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        month_receipts = GoodsReceipt.objects.filter(date__gte=period_start, date__lte=period_end)
        total_volume = sum(r.amount for r in month_receipts) or Decimal("1")

        for cp in counterparties:
            contract = contracts[counterparties.index(cp)]
            cp_volume = sum(r.amount for r in month_receipts.filter(counterparty=cp))
            if cp_volume > 0:
                share = (cp_volume / total_volume * 100).quantize(Decimal("0.01"))
                kind_map = {"supply": "raw", "service": "service", "work": "material", "lease": "service"}
                ProcurementVolume.objects.update_or_create(
                    counterparty=cp, period_start=period_start, period_end=period_end, period_type="month",
                    defaults={
                        "contract": contract, "volume_rub": cp_volume,
                        "share_percent": share,
                        "procurement_kind": kind_map.get(contract.kind, "raw"),
                    },
                )
                pv_count += 1
    print(f"  [13/17] Объёмы закупок: {pv_count}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 14: СВЕРКИ И РАСХОЖДЕНИЯ
    # ══════════════════════════════════════════════════════════════════
    # Для каждого ключевого контрагента формируем акт сверки.
    # Если есть неоплаченные документы — создаём расхождения.
    # Статусы: open (новое), in_progress (в работе), resolved (закрыто).

    rec_count = disc_count = 0
    for cp in counterparties[:8]:
        receipts_sum = GoodsReceipt.objects.filter(counterparty=cp).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        payments_sum = PaymentOrder.objects.filter(counterparty=cp).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        our_balance = receipts_sum - payments_sum
        their_offset = Decimal(random.randint(-10000, 10000))

        act, _ = ReconciliationAct.objects.get_or_create(
            counterparty=cp, period_start=today - timedelta(days=90), period_end=today,
            defaults={
                "our_balance": our_balance,
                "their_balance": our_balance + their_offset,
                "is_matched": abs(their_offset) < 100,
                "created_by": users["buhgalter"],
            },
        )
        rec_count += 1

        if not act.is_matched:
            unmatched = GoodsReceipt.objects.filter(counterparty=cp, is_paid=False)[:3]
            for receipt in unmatched:
                Discrepancy.objects.get_or_create(
                    reconciliation_act=act, counterparty=cp,
                    document_ref=f"Поступление №{receipt.number} от {receipt.date.strftime('%d.%m.%Y')}",
                    defaults={
                        "our_amount": receipt.amount,
                        "their_amount": receipt.amount + Decimal(random.randint(-5000, 5000)),
                        "discrepancy_amount": abs(Decimal(random.randint(100, 15000))),
                        "reason": random.choice(["amount_mismatch", "missing_doc", "date_mismatch"]),
                        "status": random.choice(["open", "open", "in_progress", "resolved"]),
                        "responsible": users["buhgalter"],
                    },
                )
                disc_count += 1
    print(f"  [14/17] Акты сверки: {rec_count}, расхождения: {disc_count}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 15: СНИМКИ КОНТРАГЕНТОВ
    # ══════════════════════════════════════════════════════════════════
    # Автоматический снимок текущего состояния каждого контрагента.
    # Позволяет видеть исторические данные.

    for cp in counterparties:
        CounterpartyHistorySnapshot.objects.update_or_create(
            counterparty=cp, snapshot_date=today,
            defaults={
                "data": {"name": cp.name, "inn": cp.inn, "kpp": cp.kpp, "is_key_supplier": cp.is_key_supplier, "phone": cp.phone, "email": cp.email},
                "changed_by": users["buhgalter"],
            },
        )
    print(f"  [15/17] Снимки контрагентов: {CounterpartyHistorySnapshot.objects.count()}")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 16: KPI-СНИМКИ (за 90 дней — для графиков динамики)
    # ══════════════════════════════════════════════════════════════════
    # Для графика «Динамика задолженности» нужны исторические данные.
    # Создаём по снимку на каждый день за последние 90 дней
    # с реалистичной динамикой (плавное изменение с трендом).

    from apps.analytics.services import recalculate_all_kpi

    base_debt = 2200000
    base_overdue = 600000
    for day_offset in range(90, 0, -1):
        snap_date = today - timedelta(days=day_offset)
        # Плавное изменение с трендом роста задолженности
        noise = random.randint(-80000, 80000)
        total_debt = Decimal(base_debt + noise + day_offset * 1500)
        overdue = Decimal(base_overdue + random.randint(-50000, 50000) + day_offset * 800)
        overdue = min(overdue, total_debt)
        ratio = (overdue / total_debt * 100).quantize(Decimal("0.01")) if total_debt > 0 else Decimal("0")
        turnover = Decimal(str(35 + random.uniform(-8, 8) + day_offset * 0.1)).quantize(Decimal("0.1"))

        AnalyticsSnapshot.objects.update_or_create(
            date=snap_date,
            defaults={
                "total_debt": total_debt, "overdue_debt": overdue,
                "overdue_ratio": ratio, "turnover_days": turnover,
                "payment_ratio": Decimal(str(random.uniform(0.6, 0.95))).quantize(Decimal("0.001")),
                "avg_payment_days": Decimal(str(random.uniform(18, 42))).quantize(Decimal("0.1")),
                "avg_deviation_days": Decimal(str(random.uniform(-3, 12))).quantize(Decimal("0.1")),
                "key_supplier_share": Decimal(str(random.uniform(65, 82))).quantize(Decimal("0.01")),
                "forecast_cash_need_week": Decimal(random.randint(200000, 900000)),
                "forecast_cash_need_month": Decimal(random.randint(900000, 3500000)),
                "cash_gap_probability": Decimal(str(random.uniform(0, 25))).quantize(Decimal("0.1")),
            },
        )

    # Текущий снимок — настоящий расчёт из реальных данных
    snapshot = recalculate_all_kpi()
    print(f"  [16/17] KPI-снимки: {AnalyticsSnapshot.objects.count()} (текущий: долг={snapshot.total_debt}, просрочка={snapshot.overdue_ratio}%)")

    # ══════════════════════════════════════════════════════════════════
    # БЛОК 17: УВЕДОМЛЕНИЯ + АУДИТ-ЛОГ + ИМПОРТ
    # ══════════════════════════════════════════════════════════════════
    # Создаём уведомления для всех пользователей (кроме procurement).
    # Импортируем сессию для демонстрации модуля импорта.
    # Заполняем аудит-лог для журнала действий.

    notif_types = [
        ("overdue", "warning", "Просрочка: ООО АгроКорм (3 док.)", "Контрагент: ООО АгроКорм (ИНН: 7701234567)\nПросроченных документов: 3\nОбщая сумма просрочки: 890 000 руб.\nМаксимальная просрочка: 45 дней", "/registers/debt/?search=АгроКорм"),
        ("overdue", "critical", "Просрочка: КФХ Нива (5 док.)", "Контрагент: КФХ Нива (ИНН: 7706789012)\nПросроченных документов: 5\nОбщая сумма просрочки: 1 240 000 руб.\nМаксимальная просрочка: 92 дня", "/registers/debt/?search=Нива"),
        ("overdue", "warning", "Просрочка: ЗАО ЗерноТрейд (2 док.)", "Контрагент: ЗАО ЗерноТрейд (ИНН: 7702345678)\nПросроченных документов: 2\nОбщая сумма: 340 000 руб.\nМаксимальная просрочка: 28 дней", "/registers/debt/?search=ЗерноТрейд"),
        ("cash_gap", "critical", f"Кассовый разрыв {(today + timedelta(days=5)).strftime('%d.%m.%Y')}", f"Дата: {(today + timedelta(days=5)).strftime('%d.%m.%Y')}\nПрогнозируемый дефицит: 350 000 руб.\nОсновные платежи:\n- ООО АгроКорм: 200 000 руб.\n- КФХ Нива: 150 000 руб.", "/payments/alerts/"),
        ("cash_gap", "warning", f"Риск разрыва {(today + timedelta(days=12)).strftime('%d.%m.%Y')}", f"Дата: {(today + timedelta(days=12)).strftime('%d.%m.%Y')}\nВероятность: 15%\nРекомендуется перенести низкоприоритетные платежи.", f"/payments/calendar/?year={today.year}&month={today.month}"),
        ("import_complete", "info", "Импорт из 1С завершён", "Режим: первоначальная загрузка\nФормат: Excel\nЗагружено контрагентов: 15\nЗагружено договоров: 15\nНайдено дублей: 2\nОшибок: 0", "/import/1/results/"),
        ("discrepancy", "warning", "Расхождение: ЗАО ЗерноТрейд", "Документ: Поступление №PTU-0012 от 15.02.2026\nНаша сумма: 450 000 руб.\nСумма контрагента: 442 500 руб.\nРасхождение: 7 500 руб.\nПричина: Расхождение в сумме", "/reconciliation/"),
        ("discrepancy", "warning", "Расхождение: ООО ПремиксПро", "Документ: Поступление №PTU-0024 от 28.02.2026\nОтсутствует документ у контрагента\nСумма: 125 000 руб.", "/reconciliation/"),
        ("system", "info", "Пересчёт KPI завершён", "Все аналитические показатели обновлены.\nОбщая КЗ: 2 434 985 руб.\nПросрочка: 68,8%\nОборачиваемость: 89 дней", "/analytics/"),
        ("overdue", "info", "Предстоящие платежи: 9 в ближайшие 3 дня", f"В ближайшие 3 дня необходимо оплатить 9 платежей:\n- ООО АгроКорм: 120 000 руб.\n- ЗАО ЗерноТрейд: 85 000 руб.\n- ООО ПремиксПро: 45 000 руб.\n- и ещё 6 платежей", f"/payments/calendar/?year={today.year}&month={today.month}"),
    ]
    notif_count = 0
    for user in users.values():
        if user.role in ("admin", "accountant", "manager"):
            for n_type, sev, title, msg, link in notif_types:
                Notification.objects.get_or_create(
                    user=user, type=n_type, title=title,
                    defaults={"message": msg, "severity": sev, "link": link, "is_read": random.random() < 0.2},
                )
                notif_count += 1
    print(f"  [17/17] Уведомления: {notif_count}")

    # Демо-сессия импорта
    session, _ = ImportSession.objects.get_or_create(
        mode="initial", file_format="excel", status="completed",
        defaults={
            "total_records": 30, "processed_records": 30,
            "created_records": 25, "updated_records": 5,
            "error_records": 0, "duplicates_found": 2,
            "initiated_by": users["buhgalter"],
            "uploaded_file": "imports/demo/demo_import.xlsx",
            "checksum": "a1b2c3d4e5f6",
        },
    )
    ImportLog.objects.get_or_create(session=session, level="info", message="Импорт начат", defaults={"object_type": "ImportSession"})
    ImportLog.objects.get_or_create(session=session, level="info", message="Загружено 15 контрагентов", defaults={"object_type": "Counterparty", "object_data": {"code_1c": "1C-001"}})
    ImportLog.objects.get_or_create(session=session, level="info", message="Загружено 15 договоров", defaults={"object_type": "Contract"})
    ImportLog.objects.get_or_create(session=session, level="warning", message="Найден дубль: ИНН 7701234567 (ООО АгроКорм)", defaults={"object_type": "Counterparty"})

    # Аудит-лог
    for i, (action, obj_type, obj_repr) in enumerate([
        ("login", "User", "Вход: admin"),
        ("login", "User", "Вход: buhgalter"),
        ("POST", "Counterparty", "Создан контрагент ООО РусЗерно"),
        ("POST", "Contract", "Создан договор D-2024-011"),
        ("POST", "GoodsReceipt", "Поступление PTU-0001"),
        ("POST", "PaymentOrder", "Платёжное поручение PP-0001"),
        ("POST", "ReconciliationAct", "Сформирован акт сверки"),
        ("POST", "ImportSession", "Запущен импорт данных"),
        ("manual_correction", "Counterparty", "Ручная корректировка: ООО АгроКорм (импорт #1)"),
        ("login_failed", "User", "Неудачная попытка входа: unknown_user"),
    ]):
        ActivityLog.objects.create(
            user=users["admin"], action=action,
            object_type=obj_type, object_repr=obj_repr,
            ip_address="192.168.1." + str(random.randint(10, 250)),
        )

    # ══════════════════════════════════════════════════════════════════
    # ИТОГО
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  ВСЕ ДАННЫЕ ЗАГРУЖЕНЫ!")
    print("=" * 70)
    print(f"""
  Подразделения:          {Department.objects.count()}
  Пользователи:           {User.objects.count()}
  Номенклатура:           {Nomenclature.objects.count()}
  Контрагенты:            {Counterparty.objects.count()}
  Договоры:               {Contract.objects.count()}
  Поступления:            {GoodsReceipt.objects.count()}
  Строки поступлений:     {GoodsReceiptItem.objects.count()}
  Платёжные поручения:    {PaymentOrder.objects.count()}
  Счета на оплату:        {Invoice.objects.count()}
  Остатки по счетам:      {AccountBalance.objects.count()}
  Регистр задолженности:  {DebtByTerms.objects.count()}
  Плановые платежи:       {PlannedPayment.objects.count()}
  Объёмы закупок:         {ProcurementVolume.objects.count()}
  Прогноз остатков:       {CashBalance.objects.count()}
  Кассовые разрывы:       {CashGapAlert.objects.count()}
  Акты сверки:            {ReconciliationAct.objects.count()}
  Расхождения:            {Discrepancy.objects.count()}
  История условий:        {ContractConditionHistory.objects.count()}
  Снимки контрагентов:    {CounterpartyHistorySnapshot.objects.count()}
  KPI-снимки (90 дней):   {AnalyticsSnapshot.objects.count()}
  Уведомления:            {Notification.objects.count()}
  Сессии импорта:         {ImportSession.objects.count()}
  Записи аудит-лога:      {ActivityLog.objects.count()}

  Логин: admin / demo12345!  (суперпользователь, Django Admin)
  Логин: buhgalter / demo12345!
  Логин: rukovod / demo12345!
  Логин: zakupki1 / demo12345!  (видит только своих контрагентов)
    """)
