from django.db import models

class Printer(models.Model):
    ip_address = models.GenericIPAddressField(unique=True, verbose_name='IP-адрес')
    serial_number = models.CharField(max_length=100, verbose_name='Серийный номер')
    model = models.CharField(max_length=200, blank=True, verbose_name='Модель')
    snmp_community = models.CharField(max_length=100, verbose_name='SNMP сообщество')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Последнее обновление')

    def __str__(self):
        return f"{self.ip_address} ({self.serial_number})"

class InventoryTask(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Успешно'),
        ('FAILED', 'Ошибка'),
        ('VALIDATION_ERROR', 'Ошибка валидации'),
    ]
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE, verbose_name='Принтер')
    task_timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Дата опроса')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='Статус')
    error_message = models.TextField(blank=True, null=True, verbose_name='Сообщение об ошибке')

class PageCounter(models.Model):
    task = models.ForeignKey(InventoryTask, on_delete=models.CASCADE, verbose_name='Задача')
    bw_a3 = models.IntegerField(null=True, blank=True, verbose_name='ЧБ A3')
    bw_a4 = models.IntegerField(null=True, blank=True, verbose_name='ЧБ A4')
    color_a3 = models.IntegerField(null=True, blank=True, verbose_name='Цвет A3')
    color_a4 = models.IntegerField(null=True, blank=True, verbose_name='Цвет A4')
    total_pages = models.IntegerField(null=True, blank=True, verbose_name='Всего страниц')
    recorded_at = models.DateTimeField(auto_now_add=True, verbose_name='Время записи')
