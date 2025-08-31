from django import forms
from .models import ContractDevice

class ContractDeviceForm(forms.ModelForm):
    class Meta:
        model = ContractDevice
        fields = [
            "organization","city","address","room_number",
            "model","serial_number","status","comment","printer"
        ]
