from django import forms
from django.db.models import Q
from .models import Printer, Organization
from contracts.models import DeviceModel, Manufacturer


class PrinterForm(forms.ModelForm):
    # Новое поле для выбора производителя (не из модели, вспомогательное)
    manufacturer = forms.ModelChoiceField(
        label="Производитель",
        queryset=Manufacturer.objects.all().order_by('name'),
        required=False,
        empty_label="— выберите производителя —",
        help_text="Сначала выберите производителя, затем модель",
    )

    # Поле для выбора модели из справочника
    device_model = forms.ModelChoiceField(
        label="Модель устройства",
        queryset=DeviceModel.objects.none(),  # изначально пусто, заполним через JS
        required=False,
        empty_label="— сначала выберите производителя —",
        help_text="Выберите модель из справочника (рекомендуется)",
    )

    # Организация
    organization = forms.ModelChoiceField(
        label="Организация",
        queryset=Organization.objects.filter(active=True).order_by("name"),
        required=True,
        empty_label="— выберите организацию —",
    )

    class Meta:
        model = Printer
        fields = [
            'ip_address',
            'serial_number',
            'manufacturer',  # вспомогательное поле (не сохраняется в БД)
            'device_model',
            'model',  # старое текстовое поле (резерв)
            'snmp_community',
            'mac_address',
            'organization'
        ]
        labels = {
            'ip_address': 'IP-адрес',
            'serial_number': 'Серийный номер',
            'model': 'Модель (текст)',
            'snmp_community': 'SNMP community',
            'mac_address': 'MAC-адрес',
        }
        widgets = {
            'ip_address': forms.TextInput(attrs={
                'placeholder': '192.168.1.100',
                'class': 'form-control'
            }),
            'serial_number': forms.TextInput(attrs={
                'placeholder': 'Будет получен автоматически при опросе',
                'class': 'form-control'
            }),
            'mac_address': forms.TextInput(attrs={
                'placeholder': 'AA:BB:CC:DD:EE:FF',
                'class': 'form-control'
            }),
            'snmp_community': forms.TextInput(attrs={
                'placeholder': 'public',
                'class': 'form-control'
            }),
            'model': forms.TextInput(attrs={
                'placeholder': 'Только если модели нет в справочнике',
                'class': 'form-control'
            }),
        }
        help_texts = {
            'model': 'Используйте только если модели нет в справочнике выше',
            'snmp_community': 'По умолчанию: public',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Применяем Bootstrap классы
        for field_name in ['manufacturer', 'device_model', 'organization']:
            self.fields[field_name].widget.attrs['class'] = 'form-select'

        # Если редактируем существующий принтер
        if self.instance and self.instance.pk and self.instance.device_model:
            # Устанавливаем производителя
            self.fields['manufacturer'].initial = self.instance.device_model.manufacturer
            # Загружаем модели этого производителя
            self.fields['device_model'].queryset = DeviceModel.objects.filter(
                manufacturer=self.instance.device_model.manufacturer,
                device_type='printer'
            ).select_related('manufacturer').order_by('name')

    def clean_organization(self):
        org = self.cleaned_data['organization']
        if org is None or not org.active:
            raise forms.ValidationError("Выберите активную организацию.")
        return org

    def clean(self):
        cleaned_data = super().clean()
        device_model = cleaned_data.get('device_model')
        model_text = cleaned_data.get('model')

        # Проверяем, что хотя бы одно из полей модели заполнено
        if not device_model and not model_text:
            raise forms.ValidationError(
                "Необходимо указать модель: либо выбрать из справочника, "
                "либо ввести текстом."
            )

        # Если выбрана модель из справочника, автоматически заполняем текстовое поле
        if device_model and not model_text:
            cleaned_data['model'] = device_model.name

        return cleaned_data