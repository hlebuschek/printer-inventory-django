"""Расчёт рабочего времени по графику объекта и производственному календарю.

Используется для нормативных сроков SLA: и срок устранения инцидента, и время
недоступности оборудования (D в показателе K1) считаются в рабочих часах объекта,
а не в астрономических.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .models import ProductionCalendarDay, WorkSchedule

# Предохранитель от зацикливания на графике без рабочего времени
# (например, work_start == work_end или все дни недели выпали в праздники).
MAX_SEARCH_DAYS = 730


class NoWorkingTimeError(RuntimeError):
    """График не даёт рабочего времени — норматив посчитать невозможно."""


class WorkingTimeCalculator:
    """Считает рабочее время по одному графику и часовому поясу.

    Производственный календарь подгружается погодно по годам и кэшируется в экземпляре,
    поэтому калькулятор стоит переиспользовать для всех расчётов по одному объекту.
    """

    def __init__(self, schedule: WorkSchedule, timezone_name: str):
        self.schedule = schedule
        self.tz = ZoneInfo(timezone_name)
        self.weekdays = schedule.weekday_set
        self._hours_by_weekday = {day.weekday: (day.work_start, day.work_end) for day in schedule.day_exceptions.all()}
        self._calendar_years: dict[int, dict[date, str]] = {}

    def _calendar(self, year: int) -> dict[date, str]:
        if year not in self._calendar_years:
            self._calendar_years[year] = dict(
                ProductionCalendarDay.objects.filter(date__year=year).values_list("date", "kind")
            )
        return self._calendar_years[year]

    def day_window(self, day: date) -> tuple[datetime, datetime] | None:
        """Рабочий интервал дня в локальном времени объекта или None, если день нерабочий."""
        kind = self._calendar(day.year).get(day)
        weekday = day.isoweekday()

        if kind == ProductionCalendarDay.HOLIDAY:
            return None
        if kind != ProductionCalendarDay.WORKING_WEEKEND and weekday not in self.weekdays:
            return None

        work_start, work_end = self._hours_by_weekday.get(weekday, (self.schedule.work_start, self.schedule.work_end))
        start = datetime.combine(day, work_start, tzinfo=self.tz)
        end = datetime.combine(day, work_end, tzinfo=self.tz)
        # Предпраздничный день сокращается от времени именно этого дня недели,
        # а не от общего времени графика.
        if kind == ProductionCalendarDay.SHORT:
            end -= timedelta(minutes=self.schedule.short_day_minutes)

        return (start, end) if end > start else None

    def working_hours_between(self, start: datetime, end: datetime) -> float:
        """Сколько рабочих часов уместилось между двумя моментами времени."""
        if end <= start:
            return 0.0

        start = start.astimezone(self.tz)
        end = end.astimezone(self.tz)

        total = timedelta()
        day = start.date()
        while day <= end.date():
            window = self.day_window(day)
            if window:
                lo = max(window[0], start)
                hi = min(window[1], end)
                if hi > lo:
                    total += hi - lo
            day += timedelta(days=1)

        return total.total_seconds() / 3600

    def month_bounds(self, year: int, month: int) -> tuple[datetime, datetime]:
        """Границы календарного месяца в местном времени объекта.

        Отчётный период у объектов в разных часовых поясах начинается в разные моменты,
        поэтому для показателей K1/K2 месяц режется по времени объекта, а не по серверному.
        """
        start = datetime(year, month, 1, tzinfo=self.tz)
        end = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=self.tz)
        return start, end

    def working_hours_in_month(self, year: int, month: int) -> float:
        """Рабочих часов в календарном месяце — нормативное время доступности A в K1."""
        return self.working_hours_between(*self.month_bounds(year, month))

    def next_working_moment(self, moment: datetime) -> datetime:
        """Ближайший момент, начиная с которого идёт рабочее время.

        Заявка, поданная вечером или в выходной, по нормативу начинает отсчёт
        с открытия объекта, а не с момента регистрации.
        """
        moment = moment.astimezone(self.tz)
        day = moment.date()

        for _ in range(MAX_SEARCH_DAYS):
            window = self.day_window(day)
            if window and moment < window[1]:
                return max(window[0], moment)
            day += timedelta(days=1)
            moment = datetime.combine(day, time.min, tzinfo=self.tz)

        raise NoWorkingTimeError(f"График «{self.schedule.name}» не содержит рабочего времени")

    def add_working_hours(self, start: datetime, hours: float) -> datetime:
        """Момент, наступающий через указанное число рабочих часов после start."""
        cursor = self.next_working_moment(start)
        remaining = timedelta(hours=hours)
        day = cursor.date()

        for _ in range(MAX_SEARCH_DAYS):
            window = self.day_window(day)
            if window:
                lo = max(window[0], cursor)
                if window[1] > lo:
                    available = window[1] - lo
                    if available >= remaining:
                        return lo + remaining
                    remaining -= available
            day += timedelta(days=1)

        raise NoWorkingTimeError(f"График «{self.schedule.name}» не даёт {hours} рабочих часов за разумный срок")


def calculator_for_device(device) -> WorkingTimeCalculator:
    """Калькулятор для устройства по договору: график устройства → города → умолчания."""
    schedule = device.effective_work_schedule
    if schedule is None:
        raise NoWorkingTimeError(
            "Не задан график работы: у устройства и города график не выбран, "
            "график по умолчанию отсутствует (см. manage.py bootstrap_sla_reference)"
        )
    return WorkingTimeCalculator(schedule, device.city.timezone)


def calculator_for_request(service_request, cache) -> WorkingTimeCalculator | None:
    """Калькулятор по графику заявки; None — если графика нет.

    Кэш общий на весь проход по журналу: каждый экземпляр вычитывает производственный
    календарь, а графиков на договор единицы. Без кэша выгрузка и аналитика читают
    календарь на каждой заявке.
    """
    schedule = service_request.schedule_snapshot or service_request.device.effective_work_schedule
    if schedule is None:
        return None

    key = (schedule.pk, service_request.device.city.timezone)
    if key not in cache:
        cache[key] = WorkingTimeCalculator(schedule, service_request.device.city.timezone)
    return cache[key]
