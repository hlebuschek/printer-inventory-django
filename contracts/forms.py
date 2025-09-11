from django import forms
from django.db.models import Q
from datetime import datetime, date
from .models import ContractDevice, ContractStatus


class ContractDeviceForm(forms.ModelForm):
    service_start_month = forms.DateField(
        label="Месяц принятия на обслуживание",
        required=False,
        widget=forms.DateInput(
            attrs={
                'type': 'month',
                'class': 'form-control'
            }
        ),
        help_text="Месяц и год начала обслуживания устройства"
    )

    class Meta:
        model = ContractDevice
        fields = "__all__"
        widgets = {
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'organization': forms.Select(attrs={'class': 'form-control'}),
            'city': forms.Select(attrs={'class': 'form-control'}),
            'model': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'printer': forms.Select(attrs={'class': 'form-control'}),
        }

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

    def clean_service_start_month(self):
        """Нормализация даты - установка первого дня месяца"""
        date_value = self.cleaned_data.get('service_start_month')
        if date_value:
            # Устанавливаем первое число месяца для консистентности
            return date_value.replace(day=1)
        return date_value


# ─── Формы для массовых операций в админке ────────────────────────────────────

class BulkChangeStatusForm(forms.Form):
    """Форма для массового изменения статуса устройств"""
    new_status = forms.ModelChoiceField(
        queryset=ContractStatus.objects.filter(is_active=True),
        empty_label="Выберите новый статус",
        label="Новый статус",
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Выберите статус, который будет установлен для всех выбранных устройств"
    )

    confirm = forms.BooleanField(
        label="Подтверждаю изменение",
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Поставьте галочку для подтверждения массового изменения статуса"
    )

    def __init__(self, *args, **kwargs):
        # Можем передать дополнительные параметры, например, исключить определенные статусы
        exclude_statuses = kwargs.pop('exclude_statuses', None)
        super().__init__(*args, **kwargs)

        if exclude_statuses:
            self.fields['new_status'].queryset = self.fields['new_status'].queryset.exclude(
                id__in=exclude_statuses
            )


class BulkChangeServiceMonthForm(forms.Form):
    """Форма для массового изменения месяца обслуживания"""
    new_service_month = forms.CharField(
        label="Новый месяц обслуживания",
        required=False,
        widget=forms.TextInput(
            attrs={
                'type': 'month',
                'class': 'form-control',
                'placeholder': 'YYYY-MM'
            }
        ),
        help_text="Выберите месяц и год начала обслуживания для всех выбранных устройств"
    )

    clear_service_month = forms.BooleanField(
        label="Очистить месяц обслуживания",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Поставьте галочку, чтобы очистить месяц обслуживания (вместо установки нового)"
    )

    confirm = forms.BooleanField(
        label="Подтверждаю изменение",
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Поставьте галочку для подтверждения массового изменения месяца обслуживания"
    )

    def clean_new_service_month(self):
        """Парсим месяц из формата YYYY-MM в date объект"""
        month_str = self.cleaned_data.get('new_service_month')

        if not month_str:
            return None

        try:
            # Ожидаем формат YYYY-MM от HTML5 month input
            if '-' in month_str and len(month_str) == 7:  # YYYY-MM
                year, month = month_str.split('-')
                year, month = int(year), int(month)

                # Проверяем корректность года и месяца
                if year < 1900 or year > 2100:
                    raise forms.ValidationError("Год должен быть между 1900 и 2100.")
                if month < 1 or month > 12:
                    raise forms.ValidationError("Месяц должен быть между 1 и 12.")

                return date(year, month, 1)
            else:
                raise forms.ValidationError("Неверный формат месяца. Ожидается YYYY-MM.")

        except (ValueError, TypeError):
            raise forms.ValidationError("Введите корректный месяц в формате YYYY-MM (например: 2024-01).")

    def clean(self):
        cleaned_data = super().clean()
        new_service_month = cleaned_data.get('new_service_month')
        clear_service_month = cleaned_data.get('clear_service_month')

        if clear_service_month and new_service_month:
            raise forms.ValidationError(
                "Нельзя одновременно установить новый месяц и очистить его. "
                "Выберите что-то одно."
            )

        if not clear_service_month and not new_service_month:
            raise forms.ValidationError(
                "Необходимо либо выбрать новый месяц обслуживания, "
                "либо поставить галочку для очистки."
            )

        return cleaned_data


class BulkChangeStatusAndServiceMonthForm(forms.Form):
    """Форма для одновременного изменения статуса и месяца обслуживания"""
    new_status = forms.ModelChoiceField(
        queryset=ContractStatus.objects.filter(is_active=True),
        empty_label="Оставить без изменений",
        label="Новый статус",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Выберите новый статус или оставьте пустым для сохранения текущего"
    )

    new_service_month = forms.CharField(
        label="Новый месяц обслуживания",
        required=False,
        widget=forms.TextInput(
            attrs={
                'type': 'month',
                'class': 'form-control',
                'placeholder': 'YYYY-MM'
            }
        ),
        help_text="Выберите новый месяц обслуживания или оставьте пустым"
    )

    clear_service_month = forms.BooleanField(
        label="Очистить месяц обслуживания",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Поставьте галочку, чтобы очистить месяц обслуживания"
    )

    confirm = forms.BooleanField(
        label="Подтверждаю изменения",
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Поставьте галочку для подтверждения массовых изменений"
    )

    def clean_new_service_month(self):
        """Парсим месяц из формата YYYY-MM в date объект"""
        month_str = self.cleaned_data.get('new_service_month')

        if not month_str:
            return None

        try:
            # Ожидаем формат YYYY-MM от HTML5 month input
            if '-' in month_str and len(month_str) == 7:  # YYYY-MM
                year, month = month_str.split('-')
                year, month = int(year), int(month)

                # Проверяем корректность года и месяца
                if year < 1900 or year > 2100:
                    raise forms.ValidationError("Год должен быть между 1900 и 2100.")
                if month < 1 or month > 12:
                    raise forms.ValidationError("Месяц должен быть между 1 и 12.")

                return date(year, month, 1)
            else:
                raise forms.ValidationError("Неверный формат месяца. Ожидается YYYY-MM.")

        except (ValueError, TypeError):
            raise forms.ValidationError("Введите корректный месяц в формате YYYY-MM (например: 2024-01).")

    def clean(self):
        cleaned_data = super().clean()
        new_status = cleaned_data.get('new_status')
        new_service_month = cleaned_data.get('new_service_month')
        clear_service_month = cleaned_data.get('clear_service_month')

        # Проверяем, что хотя бы одно изменение выбрано
        if not new_status and not new_service_month and not clear_service_month:
            raise forms.ValidationError(
                "Необходимо выбрать хотя бы одно изменение: "
                "новый статус, новый месяц обслуживания или очистку месяца."
            )

        # Проверяем конфликт между установкой и очисткой месяца
        if clear_service_month and new_service_month:
            raise forms.ValidationError(
                "Нельзя одновременно установить новый месяц и очистить его."
            )

        return cleaned_data