from django import forms
from .models import Printer, Organization

class PrinterForm(forms.ModelForm):
    # Покажем только активные организации + плейсхолдер
    organization = forms.ModelChoiceField(
        label="Организация",
        queryset=Organization.objects.filter(active=True).order_by("name"),
        required=True,  # сделай False, если организация не обязательна
        empty_label="— выберите организацию —",
    )

    class Meta:
        model = Printer
        fields = ['ip_address', 'serial_number', 'model', 'snmp_community', 'mac_address', 'organization']
        labels = {
            'ip_address': 'IP-адрес',
            'serial_number': 'Серийный номер',
            'model': 'Модель',
            'snmp_community': 'SNMP сообщество',
            'mac_address': 'MAC-адрес',
            'organization': 'Организация',
        }
        widgets = {
            'mac_address': forms.TextInput(attrs={'placeholder': 'XX:XX:XX:XX:XX:XX'}),
        }

    def clean_organization(self):
        org = self.cleaned_data['organization']
        # Доп. защита на случай подмены POST: не даём выбрать неактивную
        if org is None or not org.active:
            raise forms.ValidationError("Выберите активную организацию.")
        return org
