import re
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from openpyxl import load_workbook
from django.db import transaction
from django.db import IntegrityError
from inventory.models import Organization, Printer
from contracts.models import City, Manufacturer, DeviceModel, ContractDevice, ContractStatus

HEADERS = {
    "№": "rownum",
    "номер": "rownum",
    "организация": "organization",
    "город": "city",
    "адрес": "address",
    "№ кабинета": "room",
    "кабинет": "room",
    "производитель": "manufacturer",
    "модель оборудования": "model",
    "модель": "model",
    "серийный номер": "serial",
    "sn": "serial",
    "статус": "status",
    "комментарий": "comment",
}

def norm(s):
    if s is None:
        return ""
    s = str(s).strip()
    return re.sub(r"\s+", " ", s)

def key_of(header: str) -> str | None:
    if not header:
        return None
    h = norm(header).lower()
    return HEADERS.get(h)

def ci_get_or_create(model, name_value: str, name_field: str = "name", **extra_filters):
    """
    Case-insensitive get_or_create по текстовому полю `name_field`.
    """
    q = {f"{name_field}__iexact": name_value, **extra_filters}
    obj = model.objects.filter(**q).first()
    if obj:
        return obj, False
    try:
        obj = model.objects.create(**{name_field: name_value, **extra_filters})
        return obj, True
    except IntegrityError:
        # На случай гонки или Uniq(Lower(name)) — повторно читаем
        obj = model.objects.filter(**q).first()
        if obj:
            return obj, False
        raise

class Command(BaseCommand):
    help = "Импорт устройств по договору из Excel (№, Организация, Город, Адрес, № кабинета, Производитель, Модель оборудования, Серийный номер, Статус, Комментарий)."

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str, help="Путь к .xlsx файлу")
        parser.add_argument("--sheet", type=str, default=None, help="Имя листа (по умолчанию первый)")
        parser.add_argument("--dry-run", action="store_true", help="Не сохранять, только показать, что будет сделано")
        parser.add_argument("--truncate", action="store_true",
                            help="Если значения длиннее лимита поля модели, обрезать вместо ошибки")

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["xlsx_path"])
        if not path.exists():
            raise CommandError(f"Файл не найден: {path}")

        wb = load_workbook(filename=str(path), read_only=True, data_only=True)
        ws = wb[opts["sheet"]] if opts["sheet"] else wb.worksheets[0]

        # лимиты моделей (на случай будущих изменений берём из метаданных)
        ROOM_MAX  = ContractDevice._meta.get_field("room_number").max_length
        SN_MAX    = ContractDevice._meta.get_field("serial_number").max_length
        ADDR_MAX  = ContractDevice._meta.get_field("address").max_length
        STAT_MAX  = ContractStatus._meta.get_field("name").max_length
        CITY_MAX  = City._meta.get_field("name").max_length
        MFR_MAX   = Manufacturer._meta.get_field("name").max_length
        DMOD_MAX  = DeviceModel._meta.get_field("name").max_length

        def clip(val: str, maxlen: int, label: str) -> str:
            if val and len(val) > maxlen:
                if opts["truncate"]:
                    self.stdout.write(self.style.WARNING(
                        f"[TRUNCATE] {label}: '{val[:50]}...' ({len(val)} симв.) → {maxlen}"
                    ))
                    return val[:maxlen]
                raise CommandError(
                    f"[ДЛИНА] {label}: '{val[:120]}' ({len(val)} симв.) превышает лимит {maxlen}. "
                    f"Запусти с --truncate или поправь данные."
                )
            return val

        # читаем заголовки
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        columns = [key_of(h) for h in header_row]

        required = {"organization", "city", "address", "manufacturer", "model", "status"}
        have = {c for c in columns if c}
        if not required.issubset(have):
            missing = required - have
            raise CommandError(f"В файле отсутствуют обязательные колонки: {', '.join(sorted(missing))}")

        created, updated, skipped = 0, 0, 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            data = {}
            for col_key, cell in zip(columns, row):
                if not col_key:
                    continue
                data[col_key] = norm(cell)

            if not data.get("organization") or not data.get("address"):
                skipped += 1
                continue

            # значения с учётом лимитов
            org_name = data["organization"]
            city_name = clip(data.get("city") or "—", CITY_MAX, "Город")
            mfr_name  = clip(data["manufacturer"], MFR_MAX, "Производитель")
            model_nm  = clip(data["model"], DMOD_MAX, "Модель оборудования")
            status_nm = clip(data.get("status") or "—", STAT_MAX, "Статус")
            serial    = clip(data.get("serial") or "", SN_MAX, "Серийный номер")
            room      = clip(data.get("room") or "", ROOM_MAX, "№ кабинета")
            address   = clip(data["address"], ADDR_MAX, "Адрес")
            comment   = data.get("comment") or ""

            # справочники (регистронезависимо)
            org, _ = ci_get_or_create(Organization, org_name)
            city, _ = ci_get_or_create(City, city_name)
            mfr, _ = ci_get_or_create(Manufacturer, mfr_name)
            dev_model, _ = DeviceModel.objects.get_or_create(manufacturer=mfr, name=model_nm)
            status, _ = ci_get_or_create(ContractStatus, status_nm)

            # поиск существующей записи
            obj = None
            if serial:
                obj = ContractDevice.objects.filter(organization=org, serial_number__iexact=serial).first()
            if not obj:
                obj = ContractDevice.objects.filter(
                    organization=org, address__iexact=address, room_number__iexact=room,
                    model=dev_model
                ).first()

            # автопривязка к Printer по SN
            printer = Printer.objects.filter(serial_number__iexact=serial).first() if serial else None

            fields = dict(
                organization=org, city=city, address=address, room_number=room,
                model=dev_model, serial_number=serial, status=status, comment=comment,
                printer=printer or None,
            )

            if obj:
                for k, v in fields.items():
                    setattr(obj, k, v)
                if not opts["dry_run"]:
                    obj.save()
                updated += 1
            else:
                if not opts["dry_run"]:
                    ContractDevice.objects.create(**fields)
                created += 1

        msg = f"Импорт завершён: создано {created}, обновлено {updated}, пропущено {skipped}."
        if opts["dry_run"]:
            msg += " (dry-run)"
            transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS(msg))
