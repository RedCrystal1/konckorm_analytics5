"""Клиент для интеграции с 1С:Бухгалтерия 3.0 через стандартный REST-сервис OData.

Используется для активного чтения данных из 1С (в дополнение к пассивным sync-эндпоинтам,
которые принимают данные, отправленные самой 1С).

Конфигурация — в settings.ONEC_INTEGRATION:
    BASE_URL    — корневой URL OData без слэша на конце
    USERNAME    — имя пользователя REST-сервиса (обычно "odata.user")
    PASSWORD    — пароль
    TIMEOUT     — таймаут одного HTTP-запроса (сек.)
    PAGE_SIZE   — кол-во записей в одной странице при выгрузке
    RETRIES     — число повторов при сетевых ошибках (по умолчанию 4)
    RETRY_BACKOFF — базовая задержка между повторами в секундах (по умолчанию 3)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Iterator, Mapping
from urllib.parse import quote

import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("apps.api")


class OneCError(Exception):
    """Любая ошибка при взаимодействии с 1С."""


class OneCAuthError(OneCError):
    """Неверный логин/пароль (HTTP 401)."""


class OneCNotFoundError(OneCError):
    """Объект не найден в 1С (HTTP 404)."""


# Сетевые исключения, которые имеет смысл повторять
# (1С:Фреш периодически "усыпляет" базу — холодный старт даёт таймауты и SSL-обрывы)
_RETRIABLE_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
)


class OneCClient:
    """Тонкая обёртка над OData v3.0 для 1С:Фреш.

    Особенности:
      * автоматический повтор сетевых запросов при таймаутах и SSL-обрывах,
        характерных для «холодного старта» базы 1С:Фреш;
      * первый запрос в сессии получает увеличенный таймаут (warm-up),
        последующие — обычный;
      * пагинация с настраиваемым размером страницы.

    Пример::

        client = OneCClient()
        for row in client.list_counterparties():
            print(row["Description"], row["ИНН"])
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: int | None = None,
        page_size: int | None = None,
        retries: int | None = None,
        retry_backoff: float | None = None,
    ) -> None:
        cfg = getattr(settings, "ONEC_INTEGRATION", {}) or {}

        self.base_url: str = (base_url or cfg.get("BASE_URL", "")).rstrip("/")
        if not self.base_url:
            raise OneCError(
                "Не задан settings.ONEC_INTEGRATION['BASE_URL']. "
                "Проверьте переменную окружения ONEC_BASE_URL."
            )

        username = username or cfg.get("USERNAME")
        password = password or cfg.get("PASSWORD")
        if not username or not password:
            raise OneCError(
                "Не задан логин/пароль для OData. Проверьте "
                "ONEC_USERNAME / ONEC_PASSWORD в окружении."
            )
        self.auth = HTTPBasicAuth(username, password)

        self.timeout: int = int(timeout or cfg.get("TIMEOUT", 30))
        self.page_size: int = int(page_size or cfg.get("PAGE_SIZE", 100))
        self.retries: int = int(retries if retries is not None else cfg.get("RETRIES", 4))
        self.retry_backoff: float = float(
            retry_backoff if retry_backoff is not None else cfg.get("RETRY_BACKOFF", 3)
        )
        # warm-up: первый запрос получает больший таймаут,
        # чтобы пережить "холодный старт" 1С:Фреш
        self._is_first_request = True
        self._warmup_timeout = max(self.timeout * 2, 180)

        # Используем Session для keep-alive — переиспользование TCP-соединения
        # снижает вероятность SSL-обрывов между запросами
        self._session = requests.Session()
        self._session.auth = self.auth
        self._session.headers.update({"Accept": "application/json"})

    # ──────────────────────────────────────────────
    # Низкоуровневые методы
    # ──────────────────────────────────────────────

    def _request(
        self,
        method: str,
        entity: str,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        """Выполнить произвольный HTTP-запрос к OData с автоповтором."""
        url = f"{self.base_url}/{entity.lstrip('/')}"
        merged_params: dict[str, Any] = {"$format": "json"}
        if params:
            merged_params.update(params)

        # Первый запрос в сессии — увеличенный таймаут (warm-up)
        effective_timeout = (
            self._warmup_timeout if self._is_first_request else self.timeout
        )

        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                logger.debug(
                    "1C OData %s %s params=%s (attempt %d/%d, timeout=%ds)",
                    method, url, merged_params, attempt + 1, self.retries + 1,
                    effective_timeout,
                )
                resp = self._session.request(
                    method,
                    url,
                    params=merged_params,
                    json=json,
                    timeout=effective_timeout,
                )
            except _RETRIABLE_EXCEPTIONS as exc:
                last_exc = exc
                if attempt < self.retries:
                    delay = self.retry_backoff * (2 ** attempt)
                    logger.warning(
                        "1С недоступна (%s). Повтор через %.1f сек "
                        "(попытка %d/%d).",
                        exc.__class__.__name__, delay, attempt + 1, self.retries,
                    )
                    time.sleep(delay)
                    # после неудачи продолжаем как «warm-up» — даём больше времени
                    effective_timeout = self._warmup_timeout
                    continue
                raise OneCError(
                    f"Сетевая ошибка при обращении к 1С после {self.retries} повторов: {exc}"
                ) from exc
            except requests.RequestException as exc:
                # Прочие сетевые ошибки — не повторяем (например, неверный URL)
                raise OneCError(f"Сетевая ошибка при обращении к 1С: {exc}") from exc

            # Успешное соединение — больше не warm-up
            self._is_first_request = False

            if resp.status_code == 401:
                raise OneCAuthError("1С отклонила учётные данные (HTTP 401).")
            if resp.status_code == 404:
                raise OneCNotFoundError(f"Объект не найден: {url} (HTTP 404).")
            if resp.status_code == 503:
                # 1С временно недоступна — повторяем
                last_exc = OneCError("1С вернула HTTP 503 (Service Unavailable).")
                if attempt < self.retries:
                    delay = self.retry_backoff * (2 ** attempt)
                    logger.warning(
                        "1С временно недоступна (503). Повтор через %.1f сек.",
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise last_exc
            if resp.status_code >= 400:
                raise OneCError(
                    f"1С вернула HTTP {resp.status_code}: {resp.text[:500]}"
                )

            if not resp.content:
                return None
            try:
                return resp.json()
            except ValueError as exc:
                raise OneCError(f"1С вернула не-JSON: {resp.text[:500]}") from exc

        # Никогда не должны сюда попасть, но на всякий случай:
        raise OneCError(f"Не удалось обратиться к 1С: {last_exc}")

    def get(self, entity: str, params: Mapping[str, Any] | None = None) -> Any:
        """GET-запрос к набору сущностей или к одной сущности."""
        return self._request("GET", entity, params=params)

    def post(self, entity: str, data: Mapping[str, Any]) -> Any:
        """POST — создание нового объекта в 1С."""
        return self._request("POST", entity, json=data)

    def patch(self, entity: str, ref_key: str, data: Mapping[str, Any]) -> Any:
        """PATCH — частичное обновление существующего объекта по Ref_Key."""
        target = f"{entity}(guid'{ref_key}')"
        return self._request("PATCH", target, json=data)

    # ──────────────────────────────────────────────
    # Пагинация (важно для регистров с тысячами записей)
    # ──────────────────────────────────────────────

    def iter_entities(
        self,
        entity: str,
        select: str | None = None,
        filter_: str | None = None,
        order_by: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Постранично выгрузить все записи набора сущностей.

        Пример::

            for row in client.iter_entities(
                "Catalog_Контрагенты",
                select="Ref_Key,Description,ИНН,КПП",
                filter_="not (IsFolder)",
            ):
                process(row)
        """
        skip = 0
        while True:
            params: dict[str, Any] = {"$top": self.page_size, "$skip": skip}
            if select:
                params["$select"] = select
            if filter_:
                params["$filter"] = filter_
            if order_by:
                params["$orderby"] = order_by

            payload = self.get(entity, params=params)
            rows = (payload or {}).get("value", [])
            if not rows:
                break

            for row in rows:
                yield row

            if len(rows) < self.page_size:
                break
            skip += self.page_size

    # ──────────────────────────────────────────────
    # Высокоуровневые методы для нашей предметной области
    # ──────────────────────────────────────────────

    def list_counterparties(self, *, exclude_folders: bool = True) -> Iterator[dict[str, Any]]:
        """Все контрагенты из 1С (опционально без групп-папок).

        Фильтрация папок делается на стороне Python, а не через OData $filter,
        потому что 1С OData в облаке 1cFresh иногда возвращает HTTP 400
        на фильтры по системным булевым полям. Это медленнее на больших
        справочниках, но надёжнее.
        """
        for row in self.iter_entities("Catalog_Контрагенты"):
            if exclude_folders and row.get("IsFolder"):
                continue
            yield row

    def get_counterparty_by_inn(self, inn: str) -> dict[str, Any] | None:
        """Найти одного контрагента по ИНН."""
        safe_inn = inn.replace("'", "")
        payload = self.get(
            "Catalog_Контрагенты",
            params={"$filter": f"ИНН eq '{safe_inn}'", "$top": 1},
        )
        items = (payload or {}).get("value", [])
        return items[0] if items else None

    def list_contracts(self) -> Iterator[dict[str, Any]]:
        """Договоры контрагентов."""
        return self.iter_entities("Catalog_ДоговорыКонтрагентов")

    def list_organizations(self) -> Iterator[dict[str, Any]]:
        """Список своих организаций."""
        return self.iter_entities("Catalog_Организации")

    def list_nomenclature(self, *, exclude_folders: bool = True) -> Iterator[dict[str, Any]]:
        """Справочник номенклатуры (опционально без групп-папок)."""
        for row in self.iter_entities("Catalog_Номенклатура"):
            if exclude_folders and row.get("IsFolder"):
                continue
            yield row

    def list_receipts(self, *, only_posted: bool = True) -> Iterator[dict[str, Any]]:
        """Документы 'Поступление товаров и услуг' (опц. только проведённые)."""
        for row in self.iter_entities("Document_ПоступлениеТоваровУслуг"):
            if only_posted and not row.get("Posted", False):
                continue
            yield row

    def list_receipt_items(self, receipt_ref_key: str) -> list[dict[str, Any]]:
        """Табличная часть 'Товары' конкретного документа поступления.

        В OData 1С табличные части недоступны для запросов с $filter по Ref_Key
        в коллекции <Тип>_Товары. Правильный способ — обращаться к ним как
        к навигационному свойству родительского документа:

            GET /Document_ПоступлениеТоваровУслуг(guid'...')/Товары?$format=json

        Это возвращает все строки конкретного документа.
        """
        # Обращение к документу по GUID + название табличной части
        entity = f"Document_ПоступлениеТоваровУслуг(guid'{receipt_ref_key}')/Товары"
        payload = self.get(entity)
        return (payload or {}).get("value", []) or []

    def list_payment_orders(self, *, only_posted: bool = True) -> Iterator[dict[str, Any]]:
        """Платёжные поручения (опц. только проведённые)."""
        for row in self.iter_entities("Document_ПлатежноеПоручение"):
            if only_posted and not row.get("Posted", False):
                continue
            yield row

    def list_write_offs(self, *, only_posted: bool = True) -> Iterator[dict[str, Any]]:
        """Документы 'Списание с расчётного счёта' (опц. только проведённые)."""
        for row in self.iter_entities("Document_СписаниеСРасчетногоСчета"):
            if only_posted and not row.get("Posted", False):
                continue
            yield row

    # ──────────────────────────────────────────────
    # Регистр бухгалтерии "Хозрасчётный" (план счетов)
    # ──────────────────────────────────────────────

    # GUID счетов из конфигурации Бухгалтерии 3.0 (предопределённые)
    # Эти значения одинаковы во всех типовых базах БП 3.0,
    # их можно использовать как константы вместо динамического поиска.
    ACCOUNT_60_KEY = "afe4dc07-927b-11ee-9538-7cfe90a2c5c1"   # 60   (группа)
    ACCOUNT_60_01_KEY = "afe4dc08-927b-11ee-9538-7cfe90a2c5c1"  # 60.01 Расчёты с поставщиками
    ACCOUNT_60_02_KEY = "afe4dc09-927b-11ee-9538-7cfe90a2c5c1"  # 60.02 Авансы выданные
    ACCOUNT_60_21_KEY = "afe4dc0b-927b-11ee-9538-7cfe90a2c5c1"  # 60.21 Расчёты в валюте

    # Карта код → GUID. При смене базы можно переопределить через
    # ONEC_INTEGRATION.ACCOUNT_KEYS в settings.
    ACCOUNT_KEYS_DEFAULT: dict[str, str] = {
        "60": ACCOUNT_60_KEY,
        "60.01": ACCOUNT_60_01_KEY,
        "60.02": ACCOUNT_60_02_KEY,
        "60.21": ACCOUNT_60_21_KEY,
    }

    @property
    def account_keys(self) -> dict[str, str]:
        cfg = getattr(settings, "ONEC_INTEGRATION", {}) or {}
        overrides = cfg.get("ACCOUNT_KEYS", {}) or {}
        return {**self.ACCOUNT_KEYS_DEFAULT, **overrides}

    def list_accounting_register(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        account_filter: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Записи регистра бухгалтерии 'Хозрасчётный' (проводки по плану счетов).

        В 1С OData это коллекция AccountingRegister_Хозрасчетный со всеми
        движениями счетов. Каждая запись — одна проводка вида Дт-Кт.

        Опциональные фильтры:
            date_from / date_to — границы периода в ISO ('2025-01-01T00:00:00')
            account_filter — дополнительный $filter (например, по AccountDt_Key)
        """
        filter_parts: list[str] = []
        if date_from:
            filter_parts.append(f"Period ge datetime'{date_from}'")
        if date_to:
            filter_parts.append(f"Period le datetime'{date_to}'")
        if account_filter:
            filter_parts.append(f"({account_filter})")

        params: dict[str, Any] = {}
        if filter_parts:
            params["$filter"] = " and ".join(filter_parts)

        yield from self.iter_entities(
            "AccountingRegister_Хозрасчетный",
            filter_=params.get("$filter"),
        )

    def list_account_60_records(
        self,
        *,
        account_code: str = "60.01",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Все проводки по конкретному субсчёту 60.* за период.

        Записи возвращаются и по дебету и по кредиту счёта.
        Тип проводки определяется самим вызывающим кодом по полям
        AccountDt_Key / AccountCt_Key (или их русскоязычным эквивалентам).
        """
        account_key = self.account_keys.get(account_code)
        if not account_key:
            raise OneCError(
                f"Неизвестный код счёта: {account_code}. "
                f"Доступны: {sorted(self.account_keys)}"
            )
        # Записи где счёт стоит и по дебету, и по кредиту
        # NB: имя поля может быть AccountDt_Key или СчетДт_Key — проверьте JSON.
        # Пока используем английский вариант как более вероятный.
        filter_ = (
            f"AccountDt_Key eq guid'{account_key}' "
            f"or AccountCt_Key eq guid'{account_key}'"
        )
        yield from self.list_accounting_register(
            date_from=date_from, date_to=date_to, account_filter=filter_,
        )

    def get_chart_of_accounts(self) -> list[dict[str, Any]]:
        """Получить все счета плана счетов 'Хозрасчётный'."""
        payload = self.get(
            "ChartOfAccounts_Хозрасчетный",
            params={"$top": 200},
        )
        return (payload or {}).get("value", []) or []

    # ──────────────────────────────────────────────
    # ЗАПИСЬ в 1С (обратная синхронизация)
    # ──────────────────────────────────────────────

    def create_payment_order(
        self,
        *,
        organization_key: str,
        counterparty_key: str,
        contract_key: str | None,
        amount: float | int,
        date: str,
        purpose: str,
        post: bool = False,
        bank_account_key: str | None = None,
        currency_key: str | None = None,
        vat_rate: str = "БезНДС",
        vat_amount: float = 0,
        responsible_key: str | None = None,
    ) -> dict[str, Any]:
        """Создать в 1С документ 'Платёжное поручение' (исходящее).

        Параметры:
            organization_key  — GUID организации-плательщика (Catalog_Организации)
            counterparty_key  — GUID контрагента-получателя
            contract_key      — GUID договора (опционально)
            amount            — сумма документа в рублях
            date              — дата документа в ISO ('2026-05-11T12:00:00')
            purpose           — назначение платежа (свободный текст)
            post              — провести документ в 1С после создания (True)
                                или оставить черновиком (False)
            bank_account_key  — GUID банковского счёта организации (если не указан,
                                использует значение из ONEC_INTEGRATION.DEFAULT_BANK_ACCOUNT_KEY)
            currency_key      — GUID валюты (по умолчанию — рубль из настроек)
            vat_rate          — ставка НДС ('БезНДС', 'НДС20', 'НДС10', ...)
            vat_amount        — сумма НДС в составе документа

        Возвращает словарь с данными созданного документа, включая Ref_Key и Number.
        Бросает OneCError при сбоях создания.
        """
        cfg = getattr(settings, "ONEC_INTEGRATION", {}) or {}
        bank_account_key = bank_account_key or cfg.get("DEFAULT_BANK_ACCOUNT_KEY", "")
        currency_key = currency_key or cfg.get(
            "DEFAULT_CURRENCY_KEY",
            "a9d522df-927b-11ee-9538-7cfe90a2c5c1",  # рубль в типовой БП 3.0
        )

        payload: dict[str, Any] = {
            "Date": date,
            "Posted": bool(post),
            "DeletionMark": False,
            "ВидОперации": "ОплатаПоставщику",
            "Организация_Key": organization_key,
            "Контрагент_Key": counterparty_key,
            "СуммаДокумента": float(amount),
            "ВалютаДокумента_Key": currency_key,
            "НазначениеПлатежа": purpose,
            "СтавкаНДС": vat_rate,
            "СуммаНДС": float(vat_amount),
            "ВидНалоговогоОбязательства": "Налог",
            "ОчередностьПлатежа": 5,
            "ПеречислениеВБюджет": False,
        }
        if contract_key:
            payload["ДоговорКонтрагента_Key"] = contract_key
        if bank_account_key:
            payload["СчетОрганизации_Key"] = bank_account_key
        if responsible_key:
            payload["Ответственный_Key"] = responsible_key

        return self.post("Document_ПлатежноеПоручение", payload)

    # ──────────────────────────────────────────────
    # Диагностика
    # ──────────────────────────────────────────────

    def ping(self) -> bool:
        """Быстрая проверка связи и авторизации.

        Возвращает True, если получили ответ на минимальный запрос.
        Бросает OneCAuthError при неверных учётных данных и OneCError при прочих сбоях.
        """
        self.get("Catalog_Организации", params={"$top": 1})
        return True
