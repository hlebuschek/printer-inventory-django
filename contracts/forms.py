from django import forms
from django.db.models import Q
from .models import ContractDevice, ContractStatus

class ContractDeviceForm(forms.ModelForm):
    class Meta:
        model = ContractDevice
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # В списке — активные, но если у экземпляра выбран неактивный, оставляем его доступным.
        qs = ContractStatus.objects.all()
        if self.instance and getattr(self.instance, "status_id", None):
            self.fields["status"].queryset = qs.filter(
                Q(is_active=True) | Q(pk=self.instance.status_id)
            ).distinct()
        else:
            self.fields["status"].queryset = qs.filter(is_active=True)
