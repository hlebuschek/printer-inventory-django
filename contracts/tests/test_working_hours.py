from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.test import TestCase

from contracts.models import (
    City,
    ContractDevice,
    ContractStatus,
    DeviceModel,
    Manufacturer,
    ProductionCalendarDay,
    WorkSchedule,
    WorkScheduleDay,
)
from contracts.services_working_hours import (
    NoWorkingTimeError,
    WorkingTimeCalculator,
    calculator_for_device,
)
from inventory.models import Organization

IRKUTSK = ZoneInfo("Asia/Irkutsk")


def dt(day, hour, minute=0):
    return datetime.fromisoformat(f"{day} {hour:02d}:{minute:02d}").replace(tzinfo=IRKUTSK)


class WorkingHoursTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.schedule = WorkSchedule.objects.create(
            name="Тестовый 5/2",
            work_start=time(8, 0),
            work_end=time(17, 0),
            weekdays="12345",
            short_day_minutes=60,
            is_default=True,
        )
        # 30.04 сокращённый, 01.05 праздник, 04.05 (понедельник) — праздник по переносу
        ProductionCalendarDay.objects.create(date="2026-04-30", kind=ProductionCalendarDay.SHORT)
        ProductionCalendarDay.objects.create(date="2026-05-01", kind=ProductionCalendarDay.HOLIDAY)
        ProductionCalendarDay.objects.create(date="2026-05-04", kind=ProductionCalendarDay.HOLIDAY)
        # 07.03 суббота отработана по переносу
        ProductionCalendarDay.objects.create(date="2026-03-07", kind=ProductionCalendarDay.WORKING_WEEKEND)

    def setUp(self):
        self.calc = WorkingTimeCalculator(self.schedule, "Asia/Irkutsk")

    # ─── working_hours_between ────────────────────────────────────────────────

    def test_within_single_day(self):
        self.assertEqual(self.calc.working_hours_between(dt("2026-03-02", 9), dt("2026-03-02", 12)), 3.0)

    def test_clamped_to_working_window(self):
        # Ночь и раннее утро в норматив не попадают: считается только 08:00-17:00
        self.assertEqual(self.calc.working_hours_between(dt("2026-03-02", 6), dt("2026-03-02", 23)), 9.0)

    def test_spans_night(self):
        self.assertEqual(self.calc.working_hours_between(dt("2026-03-02", 16), dt("2026-03-03", 9)), 2.0)

    def test_weekend_not_counted(self):
        # Пт 16:00 → Пн 09:00: час пятницы и час понедельника
        self.assertEqual(self.calc.working_hours_between(dt("2026-03-13", 16), dt("2026-03-16", 9)), 2.0)

    def test_holiday_not_counted(self):
        # 01.05 праздник, 02-03.05 выходные, 04.05 праздник по переносу
        self.assertEqual(self.calc.working_hours_between(dt("2026-05-01", 8), dt("2026-05-05", 8)), 0.0)

    def test_short_day_is_shorter(self):
        self.assertEqual(self.calc.working_hours_between(dt("2026-04-30", 8), dt("2026-04-30", 17)), 8.0)

    def test_working_weekend_counted(self):
        self.assertEqual(self.calc.working_hours_between(dt("2026-03-07", 8), dt("2026-03-07", 17)), 9.0)

    def test_reversed_interval_is_zero(self):
        self.assertEqual(self.calc.working_hours_between(dt("2026-03-02", 12), dt("2026-03-02", 9)), 0.0)

    def test_input_converted_from_other_timezone(self):
        moscow = dt("2026-03-02", 9).astimezone(ZoneInfo("Europe/Moscow"))
        self.assertEqual(self.calc.working_hours_between(moscow, dt("2026-03-02", 12)), 3.0)

    def test_working_hours_in_month(self):
        # Март 2026: 22 рабочих дня по 9 часов, плюс отработанная суббота 07.03
        self.assertEqual(self.calc.working_hours_in_month(2026, 3), 22 * 9 + 9)

    def test_working_hours_in_december_crosses_year(self):
        self.assertEqual(self.calc.working_hours_in_month(2026, 12), 23 * 9)

    # ─── next_working_moment ──────────────────────────────────────────────────

    def test_next_working_moment_keeps_moment_inside_window(self):
        self.assertEqual(self.calc.next_working_moment(dt("2026-03-02", 10)), dt("2026-03-02", 10))

    def test_next_working_moment_before_opening(self):
        self.assertEqual(self.calc.next_working_moment(dt("2026-03-02", 6)), dt("2026-03-02", 8))

    def test_next_working_moment_after_closing(self):
        self.assertEqual(self.calc.next_working_moment(dt("2026-03-02", 20)), dt("2026-03-03", 8))

    def test_next_working_moment_skips_holidays(self):
        self.assertEqual(self.calc.next_working_moment(dt("2026-05-01", 10)), dt("2026-05-05", 8))

    # ─── add_working_hours ────────────────────────────────────────────────────

    def test_deadline_within_same_day(self):
        self.assertEqual(self.calc.add_working_hours(dt("2026-03-02", 9), 4), dt("2026-03-02", 13))

    def test_deadline_rolls_to_next_day(self):
        # 09:00 + 10 рабочих часов: 8 часов до 17:00, остаток 2 часа — со следующего утра
        self.assertEqual(self.calc.add_working_hours(dt("2026-03-02", 9), 10), dt("2026-03-03", 10))

    def test_deadline_from_non_working_time(self):
        # Заявка в субботу: отсчёт с открытия в понедельник
        self.assertEqual(self.calc.add_working_hours(dt("2026-03-14", 12), 8), dt("2026-03-16", 16))

    def test_deadline_skips_holidays(self):
        # 30.04 сокращённый до 16:00, дальше праздники до 05.05
        self.assertEqual(self.calc.add_working_hours(dt("2026-04-30", 15), 4), dt("2026-05-05", 11))

    def test_sla_norm_of_eight_hours_is_next_working_day(self):
        self.assertEqual(self.calc.add_working_hours(dt("2026-03-02", 14), 8), dt("2026-03-03", 13))

    def test_schedule_without_working_time_raises(self):
        broken = WorkSchedule.objects.create(name="Пустой", work_start=time(9, 0), work_end=time(9, 0))
        calc = WorkingTimeCalculator(broken, "Asia/Irkutsk")
        with self.assertRaises(NoWorkingTimeError):
            calc.add_working_hours(dt("2026-03-02", 9), 1)


class PerWeekdayHoursTests(TestCase):
    """Реальный график объекта: пн-чт до 17:15, пятница до 16:00."""

    @classmethod
    def setUpTestData(cls):
        cls.schedule = WorkSchedule.objects.create(
            name="Пн-чт до 17:15, пт до 16:00",
            work_start=time(8, 0),
            work_end=time(17, 15),
            weekdays="12345",
            short_day_minutes=60,
        )
        WorkScheduleDay.objects.create(schedule=cls.schedule, weekday=5, work_start=time(8, 0), work_end=time(16, 0))
        ProductionCalendarDay.objects.create(date="2026-03-06", kind=ProductionCalendarDay.SHORT)

    def setUp(self):
        self.calc = WorkingTimeCalculator(self.schedule, "Asia/Irkutsk")

    def test_regular_day_uses_base_hours(self):
        self.assertEqual(self.calc.working_hours_between(dt("2026-03-02", 8), dt("2026-03-02", 23)), 9.25)

    def test_friday_uses_its_own_hours(self):
        self.assertEqual(self.calc.working_hours_between(dt("2026-03-13", 8), dt("2026-03-13", 23)), 8.0)

    def test_short_day_shortens_that_weekday_hours(self):
        # 06.03 — пятница и предпраздничный день: 16:00 минус час, а не 17:15 минус час
        self.assertEqual(self.calc.working_hours_between(dt("2026-03-06", 8), dt("2026-03-06", 23)), 7.0)

    def test_deadline_rolls_over_short_friday_to_monday(self):
        # Пятница сокращена до 15:00, значит остаток срока переходит на понедельник
        self.assertEqual(self.calc.add_working_hours(dt("2026-03-06", 14), 3), dt("2026-03-09", 10))

    def test_week_total(self):
        # Пн-чт по 9.25 плюс обычная пятница 8.0
        self.assertEqual(self.calc.working_hours_between(dt("2026-03-09", 0), dt("2026-03-14", 0)), 4 * 9.25 + 8.0)


class CalculatorResolutionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.default = WorkSchedule.objects.create(name="Умолчание", is_default=True)
        cls.city_schedule = WorkSchedule.objects.create(name="График города")
        cls.device_schedule = WorkSchedule.objects.create(name="График объекта")

        cls.city = City.objects.create(name="Иркутск", timezone="Asia/Irkutsk", sla_standard_hours=8)
        org = Organization.objects.create(name="Тест")
        manufacturer = Manufacturer.objects.create(name="HP")
        model = DeviceModel.objects.create(manufacturer=manufacturer, name="M404")
        status = ContractStatus.objects.create(name="В работе")
        cls.device = ContractDevice.objects.create(
            organization=org, city=cls.city, address="ул. Ленина, 1", model=model, status=status
        )

    def test_falls_back_to_default_schedule(self):
        self.assertEqual(calculator_for_device(self.device).schedule, self.default)

    def test_city_schedule_wins_over_default(self):
        self.city.work_schedule = self.city_schedule
        self.city.save(update_fields=["work_schedule"])
        self.assertEqual(calculator_for_device(self.device).schedule, self.city_schedule)

    def test_device_schedule_wins_over_city(self):
        self.city.work_schedule = self.city_schedule
        self.city.save(update_fields=["work_schedule"])
        self.device.work_schedule = self.device_schedule
        self.device.save(update_fields=["work_schedule"])
        self.assertEqual(calculator_for_device(self.device).schedule, self.device_schedule)

    def test_city_timezone_is_used(self):
        self.city.timezone = "Europe/Moscow"
        self.city.save(update_fields=["timezone"])
        self.assertEqual(calculator_for_device(self.device).tz, ZoneInfo("Europe/Moscow"))

    def test_no_schedule_at_all_raises(self):
        WorkSchedule.objects.all().delete()
        self.device.refresh_from_db()
        with self.assertRaises(NoWorkingTimeError):
            calculator_for_device(self.device)
