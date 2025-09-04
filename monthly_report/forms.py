# monthly_report/forms.py
from __future__ import annotations

from django import forms
from .models import MonthlyReport
import pandas as pd
import re
import unicodedata


class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(label='Загрузить Excel-файл')
    month = forms.DateField(
        label='Месяц (первый день)',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    replace_month = forms.BooleanField(
        label='Очистить записи за месяц перед загрузкой',
        required=False
    )

    # ---------- helpers ----------
    @staticmethod
    def _norm(s: str) -> str:
        if s is None:
            return ""
        s = unicodedata.normalize("NFKC", str(s)).strip().lower()
        s = s.replace("\xa0", " ").replace("ё", "е").replace("ч/б", "чб").replace("№", "no")
        s = s.replace("а4", "a4").replace("а3", "a3")
        s = re.sub(r"[^a-z0-9а-я]+", "", s)
        return s

    @staticmethod
    def _to_int(x) -> int:
        if x is None:
            return 0
        if isinstance(x, (int, float)) and not pd.isna(x):
            try:
                return int(float(x))
            except Exception:
                return 0
        s = str(x).strip().replace(",", ".")
        if s == "" or s.lower() == "nan":
            return 0
        m = re.search(r"-?\d+(\.\d+)?", s)
        try:
            return int(float(m.group(0))) if m else 0
        except Exception:
            return 0

    @staticmethod
    def _to_float(x) -> float:
        if x is None:
            return 0.0
        if isinstance(x, (int, float)) and not pd.isna(x):
            return float(x)
        s = str(x).strip().replace(",", ".")
        if s == "" or s.lower() == "nan":
            return 0.0
        m = re.search(r"-?\d+(\.\d+)?", s)
        try:
            return float(m.group(0)) if m else 0.0
        except Exception:
            return 0.0

    # нормализованные заголовки -> поля модели
    ALIASES = {
        # идентификация
        "nopp": "order_number", "noпп": "order_number",
        "организация": "organization",
        "филиал": "branch",
        "город": "city",
        "адрес": "address",
        "модель": "equipment_model", "модельинаименованиеоборудования": "equipment_model",
        "серийныйномероборудования": "serial_number", "серийныйномер": "serial_number",
        "серийныйno": "serial_number", "серийный": "serial_number",
        "инвномер": "inventory_number", "инвno": "inventory_number", "инв": "inventory_number",

        # A4 короткие
        "a4чбначало": "a4_bw_start", "a4чбконец": "a4_bw_end",
        "a4цветначало": "a4_color_start", "a4цветконец": "a4_color_end",
        # A4 длинные
        "показаниесчетчикаa4чбнаначалопериода": "a4_bw_start",
        "показаниесчетчикаa4чбнаконецпериода": "a4_bw_end",
        "показаниесчетчикаa4цветныенаначалопериода": "a4_color_start",
        "показаниесчетчикаa4цветныенаконецпериода": "a4_color_end",

        # A3 короткие
        "a3чбначало": "a3_bw_start", "a3чбконец": "a3_bw_end",
        "a3цветначало": "a3_color_start", "a3цветконец": "a3_color_end",
        # A3 длинные
        "показаниесчетчикаa3чбнаначалопериода": "a3_bw_start",
        "показаниесчетчикаa3чбнаконецпериода": "a3_bw_end",
        "показаниесчетчикаa3цветныенаначалопериода": "a3_color_start",
        "показаниесчетчикаa3цветныенаконецпериода": "a3_color_end",

        # SLA
        "анорматив": "normative_availability",
        "dнедоступность": "actual_downtime",
        "lнепросроченные": "non_overdue_requests",
        "wобщее": "total_requests",
        "нормативноевременидоступностиa": "normative_availability",
        "фактическиевремененедоступностиd": "actual_downtime",
        "количествонепросроченныхзапросовl": "non_overdue_requests",
        "общеколичествозапросовw": "total_requests",

        "итогоотпечатков": None,  # игнорировать колонку из файла
    }

    # эвристика по токенам для нестрогих заголовков
    TOKENS = {
        "a4_bw_start": [["a4"], ["чб", "bw", "моно"], ["начало", "start"]],
        "a4_bw_end":   [["a4"], ["чб", "bw", "моно"], ["конец", "end", "оконч"]],
        "a4_color_start": [["a4"], ["цвет", "color"], ["начало", "start"]],
        "a4_color_end":   [["a4"], ["цвет", "color"], ["конец", "end", "оконч"]],
        "a3_bw_start": [["a3"], ["чб", "bw", "моно"], ["начало", "start"]],
        "a3_bw_end":   [["a3"], ["чб", "bw", "моно"], ["конец", "end", "оконч"]],
        "a3_color_start": [["a3"], ["цвет", "color"], ["начало", "start"]],
        "a3_color_end":   [["a3"], ["цвет", "color"], ["конец", "end", "оконч"]],
    }

    def _find_column(self, norm_to_real: dict[str, str], field: str) -> str | None:
        # точные алиасы
        for norm_name, model_field in self.ALIASES.items():
            if model_field == field and norm_name in norm_to_real:
                return norm_to_real[norm_name]
        # эвристика токенов
        tokens = self.TOKENS.get(field)
        if not tokens:
            return None
        for norm_name, real in norm_to_real.items():
            ok = True
            for group in tokens:
                if not any(tok in norm_name for tok in group):
                    ok = False
                    break
            if ok:
                return real
        return None

    # ---------- основной импорт ----------
    def process_data(self) -> int:
        excel_file = self.cleaned_data['excel_file']
        month = self.cleaned_data['month'].replace(day=1)

        # по желанию — очистка месяца перед загрузкой
        if self.cleaned_data.get('replace_month'):
            MonthlyReport.objects.filter(month=month).delete()

        df = pd.read_excel(excel_file, sheet_name=0, dtype=str, keep_default_na=False)

        # возможная первая "служебная" строка типа "1 2 3 ... 0 0"
        if len(df) > 0:
            first = df.iloc[0].astype(str).str.strip()
            only_numbers = (first.apply(lambda v: re.fullmatch(r"\d{1,3}", v) is not None).sum()
                            >= max(4, min(8, len(df.columns)//2)))
            has_zeros_like = any(v in {"0", "0,0", "0.0"} for v in first)
            if only_numbers or has_zeros_like:
                df = df.iloc[1:].reset_index(drop=True)

        norm_to_real = {self._norm(col): col for col in df.columns}

        def col(field: str) -> str | None:
            return self._find_column(norm_to_real, field)

        rows: list[MonthlyReport] = []

        for idx, row in df.iterrows():
            def get_s(field, default=""):
                c = col(field)
                v = row.get(c, "") if c else ""
                return (str(v).strip() if v is not None else default)

            def get_i(field):
                c = col(field)
                return self._to_int(row.get(c)) if c else 0

            def get_f(field):
                c = col(field)
                return self._to_float(row.get(c)) if c else 0.0

            # № п/п
            c_num = col("order_number")
            order_number = self._to_int(row.get(c_num)) if c_num else 0
            if not order_number:
                order_number = idx + 1

            # счётчики (ints)
            a4_bw_s = get_i("a4_bw_start");    a4_bw_e = get_i("a4_bw_end")
            a4_cl_s = get_i("a4_color_start"); a4_cl_e = get_i("a4_color_end")
            a3_bw_s = get_i("a3_bw_start");    a3_bw_e = get_i("a3_bw_end")
            a3_cl_s = get_i("a3_color_start"); a3_cl_e = get_i("a3_color_end")

            # базовый total = A4 + A3 (для одиночек/пустых ключей)
            a4 = max(0, a4_bw_e - a4_bw_s) + max(0, a4_cl_e - a4_cl_s)
            a3 = max(0, a3_bw_e - a3_bw_s) + max(0, a3_cl_e - a3_cl_s)
            total = a4 + a3

            data = {
                "month": month,
                "order_number": order_number,
                "organization": get_s("organization"),
                "branch": get_s("branch"),
                "city": get_s("city"),
                "address": get_s("address"),
                "equipment_model": get_s("equipment_model"),
                "serial_number": get_s("serial_number"),
                "inventory_number": get_s("inventory_number"),

                "a4_bw_start": a4_bw_s,
                "a4_bw_end": a4_bw_e,
                "a4_color_start": a4_cl_s,
                "a4_color_end": a4_cl_e,
                "a3_bw_start": a3_bw_s,
                "a3_bw_end": a3_bw_e,
                "a3_color_start": a3_cl_s,
                "a3_color_end": a3_cl_e,

                "normative_availability": get_f("normative_availability"),
                "actual_downtime": get_f("actual_downtime"),
                "non_overdue_requests": get_i("non_overdue_requests"),
                "total_requests": get_i("total_requests"),

                "total_prints": total,
            }

            # пропустить полностью пустые строки
            if not any([
                data["organization"], data["equipment_model"], data["serial_number"], data["inventory_number"],
                data["a4_bw_start"], data["a4_bw_end"], data["a4_color_start"], data["a4_color_end"],
                data["a3_bw_start"], data["a3_bw_end"], data["a3_color_start"], data["a3_color_end"],
                data["normative_availability"], data["actual_downtime"],
                data["non_overdue_requests"], data["total_requests"]
            ]):
                continue

            rows.append(MonthlyReport(**data))

        if rows:
            # быстрее и без сигналов
            MonthlyReport.objects.bulk_create(rows, batch_size=1000)
            # разложить total_prints по группам (верхний id = A4, нижние = A3)
            from .services import recompute_month
            recompute_month(month)

        return len(rows)
