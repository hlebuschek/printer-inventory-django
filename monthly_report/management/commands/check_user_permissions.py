from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from monthly_report.models import MonthControl
from datetime import date

User = get_user_model()


class Command(BaseCommand):
    help = 'Проверяет права пользователя для редактирования monthly_report'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Имя пользователя для проверки')
        parser.add_argument('--month', type=str, help='Месяц в формате YYYY-MM (по умолчанию текущий)')

    def handle(self, *args, **options):
        username = options['username']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Пользователь {username} не найден'))
            return

        # Определяем месяц
        if options['month']:
            year, month = map(int, options['month'].split('-'))
            month_date = date(year, month, 1)
        else:
            today = date.today()
            month_date = today.replace(day=1)

        self.stdout.write(f"Проверка прав пользователя: {user.username}")
        self.stdout.write(f"Email: {user.email}")
        self.stdout.write(f"Месяц: {month_date}")
        self.stdout.write("-" * 50)

        # Проверяем группы
        groups = user.groups.all()
        self.stdout.write(f"Группы пользователя ({len(groups)}):")
        for group in groups:
            self.stdout.write(f"  - {group.name}")

        # Проверяем основные права
        permissions = [
            'monthly_report.access_monthly_report',
            'monthly_report.view_monthlyreport',
            'monthly_report.change_monthlyreport',
            'monthly_report.edit_counters_start',
            'monthly_report.edit_counters_end',
            'monthly_report.sync_from_inventory',
            'monthly_report.upload_monthly_report',
        ]

        self.stdout.write(f"\nПрава пользователя:")
        for perm in permissions:
            has_perm = user.has_perm(perm)
            status = "✓" if has_perm else "✗"
            self.stdout.write(f"  {status} {perm}")

        # Проверяем состояние месяца
        mc = MonthControl.objects.filter(month=month_date).first()
        self.stdout.write(f"\nСостояние месяца {month_date}:")
        if mc:
            now = timezone.now()
            is_editable = mc.edit_until and now < mc.edit_until
            self.stdout.write(f"  MonthControl существует: ✓")
            self.stdout.write(f"  edit_until: {mc.edit_until}")
            self.stdout.write(f"  Текущее время: {now}")
            self.stdout.write(f"  Месяц редактируемый: {'✓' if is_editable else '✗'}")
        else:
            self.stdout.write(f"  MonthControl НЕ СУЩЕСТВУЕТ: ✗")
            self.stdout.write(f"  Нужно создать запись или установить edit_until")

        # Итоговое заключение
        can_access = user.has_perm('monthly_report.access_monthly_report')
        can_edit_start = user.has_perm('monthly_report.edit_counters_start')
        can_edit_end = user.has_perm('monthly_report.edit_counters_end')
        month_open = mc and mc.is_editable if mc else False

        self.stdout.write(f"\n" + "=" * 50)
        self.stdout.write(f"ИТОГОВОЕ ЗАКЛЮЧЕНИЕ:")

        if not can_access:
            self.stdout.write(self.style.ERROR("❌ Нет доступа к модулю monthly_report"))
        elif not (can_edit_start or can_edit_end):
            self.stdout.write(self.style.ERROR("❌ Нет прав на редактирование счетчиков"))
        elif not month_open:
            self.stdout.write(self.style.ERROR("❌ Месяц закрыт для редактирования"))
        else:
            fields = []
            if can_edit_start:
                fields.append("поля *_start")
            if can_edit_end:
                fields.append("поля *_end")
            self.stdout.write(self.style.SUCCESS(f"✅ Пользователь может редактировать: {', '.join(fields)}"))

        # Рекомендации
        self.stdout.write(f"\nРЕКОМЕНДАЦИИ:")
        if not can_access:
            self.stdout.write("  1. Добавьте пользователя в группу 'MonthlyReport Viewers' или выше")
        if not (can_edit_start or can_edit_end):
            self.stdout.write("  2. Добавьте пользователя в группу 'MonthlyReport Editors (Start/End/Full)'")
        if not month_open:
            self.stdout.write("  3. Откройте месяц для редактирования через админку или команду:")
            self.stdout.write(f"     python manage.py shell -c \"")
            self.stdout.write(f"from monthly_report.models import MonthControl")
            self.stdout.write(f"from datetime import datetime, timedelta")
            self.stdout.write(f"from django.utils import timezone")
            self.stdout.write(
                f"mc, _ = MonthControl.objects.get_or_create(month=date({month_date.year}, {month_date.month}, 1))")
            self.stdout.write(f"mc.edit_until = timezone.now() + timedelta(days=30)")
            self.stdout.write(f"mc.save()\"")

        self.stdout.write(f"\nДля применения изменений в группах выполните:")
        self.stdout.write(f"  python manage.py init_monthly_report_roles")