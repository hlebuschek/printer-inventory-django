from django import forms
from .models import Printer

class PrinterForm(forms.ModelForm):
    class Meta:
        model = Printer
        fields = ['ip_address', 'serial_number', 'model', 'snmp_community', 'mac_address']
        labels = {
            'ip_address': 'IP-адрес',
            'serial_number': 'Серийный номер',
            'model': 'Модель',
            'snmp_community': 'SNMP сообщество',
            'mac_address': 'MAC-адрес',
        }
        widgets = {
            'mac_address': forms.TextInput(attrs={'placeholder': 'XX:XX:XX:XX:XX:XX'}),
        }