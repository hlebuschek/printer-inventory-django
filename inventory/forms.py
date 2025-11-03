from django import forms
from .models import Printer, Organization
from contracts.models import DeviceModel


class PrinterForm(forms.ModelForm):
    # Вспомогательное поле для производителя (не сохраняется в БД)
    manufacturer = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )

    # ID модели из справочника
    device_model = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )

    # Организация
    organization = forms.ModelChoiceField(
        label="Организация",
        queryset=Organization.objects.filter(active=True).order_by("name"),
        required=True,
        empty_label="— выберите организацию —",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Printer
        fields = [
            'ip_address',
            'serial_number',
            'device_model',
            'snmp_community',
            'mac_address',
            'organization'
        ]
        labels = {
            'ip_address': 'IP-адрес',
            'serial_number': 'Серийный номер',
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
        }
        help_texts = {
            'snmp_community': 'По умолчанию: public',
        }

    def clean_organization(self):
        org = self.cleaned_data.get('organization')
        if org is None or not org.active:
            raise forms.ValidationError("Выберите активную организацию.")
        return org

    def clean_device_model(self):
        """Валидация и преобразование ID модели в объект"""
        model_id = self.cleaned_data.get('device_model')

        if not model_id:
            raise forms.ValidationError("Необходимо выбрать модель устройства")

        try:
            device_model = DeviceModel.objects.get(pk=model_id, device_type='printer')
            return device_model
        except DeviceModel.DoesNotExist:
            raise forms.ValidationError("Выбранная модель не существует в базе данных")

    def save(self, commit=True):
        instance = super().save(commit=False)

        device_model = self.cleaned_data.get('device_model')
        if device_model:
            instance.device_model = device_model

        if commit:
            instance.save()

        return instance