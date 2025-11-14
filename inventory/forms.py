from django import forms
from .models import Printer, Organization, PollingMethod
from contracts.models import DeviceModel
import logging

logger = logging.getLogger(__name__)


class PrinterForm(forms.ModelForm):
    """
    Форма для добавления/редактирования принтера.
    Поддерживает два метода опроса: SNMP и Web Parsing.
    """

    # Вспомогательное поле для производителя (не сохраняется в БД)
    manufacturer = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )

    # ID модели из справочника
    device_model = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
        help_text='Автоматически заполняется при выборе модели'
    )

    # Организация
    organization = forms.ModelChoiceField(
        label="Организация",
        queryset=Organization.objects.filter(active=True).order_by("name"),
        required=True,
        empty_label="— выберите организацию —",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Метод опроса
    polling_method = forms.ChoiceField(
        label="Метод опроса",
        choices=PollingMethod.choices,
        initial=PollingMethod.SNMP,
        required=False,
        help_text="SNMP - опрос через GLPI Agent, Web Parsing - парсинг веб-интерфейса",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_polling_method'
        })
    )

    # Поля для SNMP опроса
    snmp_community = forms.CharField(
        label="SNMP Community",
        required=False,
        initial='public',
        widget=forms.TextInput(attrs={
            'placeholder': 'public',
            'class': 'form-control'
        }),
        help_text='Используется для SNMP опроса'
    )

    # Поля для Web Parsing
    web_username = forms.CharField(
        label="Web логин",
        required=False,
        help_text="Логин для доступа к веб-интерфейсу принтера (если требуется)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'admin'
        })
    )

    web_password = forms.CharField(
        label="Web пароль",
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••',
            'render_value': True  # Показывать значение при редактировании
        }),
        help_text="Пароль для доступа к веб-интерфейсу принтера (если требуется)"
    )

    class Meta:
        model = Printer
        fields = [
            'ip_address',
            'serial_number',
            'manufacturer',
            'device_model',
            'polling_method',
            'snmp_community',
            'web_username',
            'web_password',
            'mac_address',
            'organization'
        ]

        labels = {
            'ip_address': 'IP-адрес',
            'serial_number': 'Серийный номер',
            'mac_address': 'MAC-адрес',
        }

        widgets = {
            'ip_address': forms.TextInput(attrs={
                'placeholder': '192.168.1.100',
                'class': 'form-control',
                'required': True
            }),
            'serial_number': forms.TextInput(attrs={
                'placeholder': 'Будет получен автоматически при первом опросе',
                'class': 'form-control'
            }),
            'mac_address': forms.TextInput(attrs={
                'placeholder': 'AA:BB:CC:DD:EE:FF',
                'class': 'form-control'
            }),
        }

        help_texts = {
            'serial_number': 'Можно оставить пустым - будет получен при первом опросе',
            'mac_address': 'Опционально',
        }

    def clean_organization(self):
        """Валидация организации"""
        org = self.cleaned_data.get('organization')

        if org is None or not org.active:
            raise forms.ValidationError("Выберите активную организацию.")

        return org

    def clean_device_model(self):
        """Валидация и преобразование ID модели в объект"""
        model_id = self.cleaned_data.get('device_model')

        if not model_id:
            return None

        try:
            device_model = DeviceModel.objects.get(pk=model_id, device_type='printer')
            logger.info(f"Found device_model: {device_model}")
            return device_model
        except DeviceModel.DoesNotExist:
            logger.error(f"DeviceModel with id={model_id} not found")
            raise forms.ValidationError("Выбранная модель не существует в базе данных")

    def clean_polling_method(self):
        """Валидация метода опроса"""
        method = self.cleaned_data.get('polling_method')

        # Если не указан - устанавливаем SNMP по умолчанию
        if not method:
            return PollingMethod.SNMP

        return method

    def clean(self):
        """Общая валидация формы с проверкой метода опроса"""
        cleaned_data = super().clean()
        polling_method = cleaned_data.get('polling_method', PollingMethod.SNMP)

        # Валидация в зависимости от метода опроса
        if polling_method == PollingMethod.SNMP:
            # Для SNMP требуется community string
            if not cleaned_data.get('snmp_community'):
                cleaned_data['snmp_community'] = 'public'

        elif polling_method == PollingMethod.WEB:
            # Для Web Parsing логин/пароль опциональны
            web_username = cleaned_data.get('web_username')
            web_password = cleaned_data.get('web_password')

            if web_password and not web_username:
                self.add_error('web_username', 'Укажите логин для веб-доступа')

        return cleaned_data

    def save(self, commit=True):
        """Сохранение принтера с учётом метода опроса"""
        instance = super().save(commit=False)

        # Устанавливаем связь с моделью из справочника
        device_model = self.cleaned_data.get('device_model')
        if device_model:
            instance.device_model = device_model

        # Убеждаемся что polling_method установлен
        if not instance.polling_method:
            instance.polling_method = PollingMethod.SNMP

        if commit:
            instance.save()

        return instance