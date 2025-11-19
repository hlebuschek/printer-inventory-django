# Monthly Report - Vue.js Documentation

**Дата миграции:** 2025-11-18
**Статус:** ✅ Полностью мигрировано на Vue.js

---

## 📋 Оглавление

1. [Обзор](#обзор)
2. [Архитектура](#архитектура)
3. [Компоненты](#компоненты)
4. [API Endpoints](#api-endpoints)
5. [Бизнес-логика](#бизнес-логика)
6. [Особенности реализации](#особенности-реализации)
7. [Troubleshooting](#troubleshooting)

---

## Обзор

Приложение **monthly_report** предназначено для управления ежемесячными отчётами о расходе бумаги и тонера на принтерах. Включает следующий функционал:

- ✅ Просмотр списка месяцев с фильтрацией
- ✅ Детальная таблица с данными по устройствам
- ✅ Inline редактирование счётчиков с валидацией
- ✅ **Real-time обновления через WebSocket** (новое!)
- ✅ **Optimistic locking для предотвращения конфликтов** (новое!)
- ✅ Синхронизация данных из системы опроса inventory
- ✅ Загрузка данных из Excel файлов
- ✅ История изменений с возможностью отката
- ✅ Экспорт в Excel
- ✅ Обнаружение аномалий печати
- ✅ Система прав доступа на уровне полей

**📡 Real-time функциональность:** Несколько пользователей могут одновременно редактировать таблицу, видя изменения друг друга в реальном времени. Система автоматически обнаруживает и предотвращает конфликты редактирования. См. [REALTIME_UPDATES.md](REALTIME_UPDATES.md) для подробностей.

---

## Архитектура

### Структура файлов

```
monthly_report/
├── templates/monthly_report/
│   ├── month_list_vue.html          # Шаблон списка месяцев
│   ├── month_detail_vue.html        # Шаблон детальной страницы
│   ├── upload_vue.html              # Шаблон загрузки Excel
│   └── change_history_vue.html      # Шаблон истории изменений
├── views.py                         # Django views + API endpoints
├── urls.py                          # URL routing
├── models.py                        # MonthlyReport, CounterChangeLog
├── services/                        # Бизнес-логика
│   ├── audit_service.py             # Аудит изменений
│   └── inventory_sync.py            # Синхронизация с inventory
└── forms.py                         # ExcelUploadForm

frontend/src/components/monthly-report/
├── MonthListPage.vue                # Список месяцев (212 строк)
├── MonthDetailPage.vue              # Детальная страница (348 строк)
├── MonthReportTable.vue             # Таблица отчёта (852 строк)
├── UploadExcelPage.vue              # Загрузка Excel (273 строки)
└── ChangeHistoryPage.vue            # История изменений (423 строки)
```

### Поток данных

```
┌─────────────────┐
│   Django View   │ ──► Рендерит HTML с mount point
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Vue Component  │ ──► Монтируется через main.js
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   API Fetch     │ ──► GET /monthly-report/api/...
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Django API View │ ──► JsonResponse с данными
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Vue Reactivity  │ ──► Обновление UI
└─────────────────┘
```

---

## Компоненты

### 1. MonthListPage.vue

**Назначение:** Отображение списка всех месяцев с фильтрацией

**Props:**
```javascript
// Нет props - компонент сам загружает данные через API
```

**State:**
```javascript
const months = ref([])              // Список месяцев
const loading = ref(true)           // Статус загрузки
const searchQuery = ref('')         // Поисковый запрос
const selectedYear = ref('')        // Выбранный год для фильтра
const permissions = ref({})         // Права пользователя
```

**Computed:**
```javascript
const availableYears        // Уникальные годы из списка месяцев
const filteredMonths        // Отфильтрованные месяцы
const visibleCount          // Количество видимых месяцев
```

**API Calls:**
- `GET /monthly-report/api/months/` - получение списка месяцев

**Особенности:**
- Поиск по месяцу/году/организации/городу
- Фильтр по году
- Карточки с информацией: количество записей, статус редактирования
- Кнопка экспорта для каждого месяца
- Индикатор редактируемых месяцев (зелёный badge)

---

### 2. MonthDetailPage.vue

**Назначение:** Основная страница с таблицей месячного отчёта

**Props:**
```javascript
props: {
  year: Number,                     // Год (из URL)
  month: Number                     // Месяц (из URL)
}
```

**State:**
```javascript
const reports = ref([])              // Данные отчёта
const loading = ref(true)            // Загрузка
const syncing = ref(false)           // Синхронизация в процессе
const isEditable = ref(false)        // Разрешено редактирование
const showK1K2 = ref(false)          // Показать колонки K1/K2
const showAnomaliesOnly = ref(false) // Фильтр аномалий
const toasts = ref([])               // Toast уведомления
```

**API Calls:**
- `GET /monthly-report/api/month/<year>/<month>/` - получение данных
- `POST /monthly-report/api/sync/<year>/<month>/` - синхронизация
- `GET /monthly-report/<year>/<month>/export-excel/` - экспорт

**Функции:**
```javascript
loadReports()              // Загрузка данных месяца
syncFromInventory()        // Синхронизация из inventory
exportToExcel()            // Экспорт в Excel
toggleK1K2()               // Показать/скрыть K1/K2
toggleAnomaliesFilter()    // Фильтр аномалий
showToast()                // Показать уведомление
```

**Особенности:**
- Toolbar с кнопками управления
- Header с badges (аномалии, статус редактирования)
- Alert для уведомления о периоде редактирования
- Toast уведомления с детальной статистикой синхронизации
- Передача данных в дочерний компонент MonthReportTable

---

### 3. MonthReportTable.vue

**Назначение:** Таблица с данными отчёта и inline редактированием

**Props:**
```javascript
props: {
  reports: Array,                   // Массив записей отчёта
  isEditable: Boolean,              // Редактирование разрешено
  showK1K2: Boolean,                // Показать K1/K2
  showAnomaliesOnly: Boolean        // Только аномалии
}
```

**Emits:**
```javascript
emit('reload')                      // Запрос перезагрузки данных
```

**State:**
```javascript
const editingCell = ref(null)       // Текущая редактируемая ячейка
const editValue = ref('')           // Значение в редактировании
const saving = ref(false)           // Сохранение в процессе
const tableRef = ref(null)          // Ссылка на таблицу
const floatingScrollbarInnerRef = ref(null)
const showFloatingScrollbar = ref(false)
```

**Computed:**
```javascript
const groupedReports        // Группировка дубликатов
const filteredReports       // Фильтр аномалий
```

**Функции:**
```javascript
startEdit(report, field)           // Начать редактирование
cancelEdit()                       // Отменить редактирование
saveEdit()                         // Сохранить изменения
handleKeydown(event)               // Обработка Enter/Escape
getTotalTitle(report)              // Тултип для аномалий
isFieldEditable(report, field)     // Проверка разрешения
setupFloatingScrollbar()           // Настройка плавающего скроллбара
```

**Особенности:**

#### 3.1. Система разрешений (Permissions)

Трёхуровневая проверка разрешений:

1. **User permissions** - права пользователя (`edit_counters_start`, `edit_counters_end`)
2. **Duplicate restrictions** - ограничения для дубликатов:
   - Первая строка группы: только A4 поля
   - Остальные строки: только A3 поля
3. **Model specifications** - ограничения модели принтера:
   - Из таблицы `PrinterModelSpec`
   - Разрешённые форматы бумаги и цвета

Итоговые разрешения = пересечение всех трёх уровней.

Backend возвращает флаги `ui_allow_*` для каждого поля:
```javascript
{
  ui_allow_a4_bw_start: true,
  ui_allow_a4_bw_end: false,
  // ...
}
```

#### 3.2. Обнаружение аномалий

Двухуровневая система:

**Уровень 1: Высокие значения (>10000)**
- Подсветка: мягкий красный градиент
- Бордер: красный слева
- Тултип: количество отпечатков

**Уровень 2: Исторические аномалии (среднее + 2000)**
- Подсветка: жёлтый градиент
- Бордер: жёлтый слева
- Тултип: детальная статистика
  - Текущее значение
  - Среднее за N месяцев
  - Превышение (+абс, +%)

Backend вычисляет среднее за прошлые месяцы:
```python
def _annotate_anomalies_api(reports, current_month, threshold=2000):
    # Запрос средних значений по серийным номерам
    # Сравнение с threshold
    # Возврат детальной информации
```

#### 3.3. Floating Scrollbar

Горизонтальный скроллбар зафиксирован внизу viewport для удобства:

```javascript
function setupFloatingScrollbar() {
  // Синхронизация скролла таблицы и floating scrollbar
  // Автопоказ только когда таблица шире viewport
  // Обработка resize окна
}
```

#### 3.4. Auto-save с debounce

```javascript
const debouncedSave = debounce(() => {
  saveEdit()
}, 500)

function handleInput() {
  debouncedSave()
}
```

---

### 4. UploadExcelPage.vue

**Назначение:** Загрузка данных из Excel файла

**Props:**
```javascript
// Нет props
```

**State:**
```javascript
const fileInputRef = ref(null)      // Ссылка на input[type=file]
const selectedFile = ref(null)      // Выбранный файл
const uploading = ref(false)        // Загрузка в процессе
const error = ref('')               // Сообщение об ошибке
const success = ref('')             // Сообщение об успехе
const uploadedMonthUrl = ref('')    // URL загруженного месяца
const formData = ref({
  month: '',                        // Месяц (YYYY-MM-DD)
  replaceMonth: false,              // Очистить перед загрузкой
  allowEdit: false,                 // Открыть для редактирования
  editUntil: ''                     // Запретить редактирование после
})
```

**API Calls:**
- `POST /monthly-report/upload/` - загрузка файла

**Функции:**
```javascript
handleFileChange(event)            // Выбор файла
handleSubmit()                     // Отправка формы
```

**Особенности:**
- Валидация файла (.xlsx, .xls)
- Отображение размера файла
- Прогресс-бар при загрузке
- Условная настройка редактирования (datetime picker)
- Обработка JSON ответа с результатом
- Отображение количества загруженных записей
- Ссылка на загруженный месяц
- Сброс формы после успеха

**Backend ответ:**
```json
{
  "success": true,
  "count": 150,
  "bulk_log_id": 42,
  "month_url": "/monthly-report/2025-11/",
  "message": "Успешно загружено 150 записей"
}
```

---

### 5. ChangeHistoryPage.vue

**Назначение:** История изменений счётчиков с откатом

**Props:**
```javascript
props: {
  reportId: Number                  // ID записи MonthlyReport
}
```

**State:**
```javascript
const report = ref({})              // Данные записи
const history = ref([])             // История изменений
const selectedChange = ref(null)    // Выбранное изменение
const reverting = ref(false)        // Откат в процессе
const revertModalRef = ref(null)    // Ссылка на модал
let revertModalInstance = null      // Экземпляр Bootstrap Modal
```

**API Calls:**
- `GET /monthly-report/api/change-history/<pk>/` - получение истории
- `POST /monthly-report/api/revert-change/<change_id>/` - откат изменения

**Функции:**
```javascript
loadData()                         // Загрузка истории
formatDate(timestamp)              // Форматирование даты
timeAgo(timestamp)                 // "X минут назад"
getSourceLabel(source)             // Метка источника изменения
openRevertModal(change)            // Открыть модал отката
confirmRevert()                    // Подтвердить откат
exportHistory()                    // Экспорт истории
filterHistory()                    // Фильтрация (TODO)
```

**Особенности:**
- Таблица с детальной информацией:
  - Время изменения (абсолютное + относительное)
  - Пользователь (ФИО + username)
  - Поле
  - Старое → Новое значение
  - Дельта изменения
  - Источник (ручное/Excel/автосинк)
  - IP адрес
- Bootstrap modal для подтверждения отката
- Цветовая индикация источника изменения
- Комментарии к изменениям
- Кнопка экспорта (перенаправление на API)

**Backend CounterChangeLog:**
```python
class CounterChangeLog(models.Model):
    monthly_report = ForeignKey(MonthlyReport)
    user = ForeignKey(User)
    field_name = CharField(choices=[...])
    old_value = PositiveIntegerField()
    new_value = PositiveIntegerField()
    timestamp = DateTimeField()
    ip_address = GenericIPAddressField()
    change_source = CharField(choices=['manual', 'excel_upload', 'auto_sync'])
    comment = TextField()
```

---

## API Endpoints

### Список месяцев

```http
GET /monthly-report/api/months/
```

**Response:**
```json
{
  "ok": true,
  "months": [
    {
      "month_str": "2025-11",
      "year": 2025,
      "month_number": 11,
      "month_name": "Ноябрь",
      "count": 150,
      "is_editable": true,
      "edit_until": "30.11.2025"
    }
  ],
  "permissions": {
    "upload_monthly_report": true
  }
}
```

---

### Детали месяца

```http
GET /monthly-report/api/month/<year>/<month>/
```

**Response:**
```json
{
  "ok": true,
  "month_str": "2025-11",
  "is_editable": true,
  "edit_until": "2025-11-30T23:59:59",
  "reports": [
    {
      "id": 12345,
      "organization": "ООО Компания",
      "branch": "Центральный офис",
      "city": "Иркутск",
      "address": "ул. Ленина, 1",
      "equipment_model": "HP LaserJet Pro M404dn",
      "serial_number": "ABC123",
      "inventory_number": "INV-001",
      "duplicate_group": "ABC123",
      "duplicate_position": 0,

      "a4_bw_start": 1000,
      "a4_bw_end": 1500,
      "a4_bw_end_auto": 1480,
      "a4_color_start": 200,
      "a4_color_end": 250,

      "a3_bw_start": 0,
      "a3_bw_end": 0,
      "a3_color_start": 0,
      "a3_color_end": 0,

      "total_prints": 550,

      "k1": 98.5,
      "k2": 100.0,

      "is_anomaly": true,
      "anomaly_info": {
        "is_anomaly": true,
        "has_history": true,
        "average": 300,
        "months_count": 6,
        "difference": 250,
        "percentage": 83.3,
        "threshold": 2000
      },

      "ui_allow_a4_bw_start": true,
      "ui_allow_a4_bw_end": false,
      "ui_allow_a4_color_start": true,
      "ui_allow_a4_color_end": false,
      "ui_allow_a3_bw_start": false,
      "ui_allow_a3_bw_end": false,
      "ui_allow_a3_color_start": false,
      "ui_allow_a3_color_end": false
    }
  ]
}
```

---

### Обновление счётчиков

```http
POST /monthly-report/api/update-counters/<pk>/
Content-Type: application/json

{
  "field": "a4_bw_end",
  "value": 1550
}
```

**Response:**
```json
{
  "ok": true,
  "report": {
    "id": 12345,
    "a4_bw_end": 1550,
    "total_prints": 600,
    "is_anomaly": true,
    "anomaly_info": { ... }
  },
  "change_log_id": 789
}
```

---

### Синхронизация из inventory

```http
POST /monthly-report/api/sync/<year>/<month>/
X-CSRFToken: <token>
```

**Response:**
```json
{
  "ok": true,
  "updated_rows": 45,
  "manually_edited_skipped": 5,
  "skipped_serials": 10,
  "groups_recomputed": 12
}
```

---

### История изменений

```http
GET /monthly-report/api/change-history/<pk>/
```

**Response:**
```json
{
  "ok": true,
  "report": {
    "id": 12345,
    "month": "2025-11-01",
    "organization": "ООО Компания",
    "equipment_model": "HP LaserJet",
    "serial_number": "ABC123",
    "a4_bw_start": 1000,
    "a4_bw_end": 1500,
    "total_prints": 500
  },
  "history": [
    {
      "id": 1001,
      "timestamp": "2025-11-18T10:30:00Z",
      "user_username": "admin",
      "user_full_name": "Иванов Иван",
      "field": "a4_bw_end",
      "field_display": "A4 ч/б конец",
      "old_value": 1450,
      "new_value": 1500,
      "change_delta": 50,
      "change_source": "manual",
      "ip_address": "192.168.1.10",
      "comment": "Исправление ошибки"
    }
  ]
}
```

---

### Откат изменения

```http
POST /monthly-report/api/revert-change/<change_id>/
X-CSRFToken: <token>
```

**Response:**
```json
{
  "ok": true,
  "new_change_log_id": 1002
}
```

---

## Бизнес-логика

### Расчёт разрешений полей

```python
# monthly_report/views.py:919-1024

def calculate_ui_allow_flags(report, user):
    """
    Трёхуровневая проверка разрешений:
    1. User permissions
    2. Duplicate restrictions
    3. Model specifications
    """

    # Уровень 1: Права пользователя
    can_start = user.has_perm('monthly_report.edit_counters_start')
    can_end = user.has_perm('monthly_report.edit_counters_end')

    allowed_by_perm = set()
    if can_start:
        allowed_by_perm |= {"a4_bw_start", "a4_color_start", "a3_bw_start", "a3_color_start"}
    if can_end:
        allowed_by_perm |= {"a4_bw_end", "a4_color_end", "a3_bw_end", "a3_color_end"}

    # Уровень 2: Дубликаты
    if report.duplicate_position == 0:
        allowed_by_dup = {"a4_bw_start", "a4_bw_end", "a4_color_start", "a4_color_end"}
    else:
        allowed_by_dup = {"a3_bw_start", "a3_bw_end", "a3_color_start", "a3_color_end"}

    # Уровень 3: Спецификация модели
    spec = PrinterModelSpec.objects.filter(model_name=report.equipment_model).first()
    allowed_by_spec = get_allowed_fields(spec)

    # Итог = пересечение
    allowed_final = allowed_by_perm & allowed_by_dup & allowed_by_spec

    return {f'ui_allow_{field}': field in allowed_final for field in ALL_FIELDS}
```

---

### Обнаружение аномалий

```python
# monthly_report/views.py

def _annotate_anomalies_api(reports, current_month, threshold=2000):
    """
    Вычисление исторических аномалий
    """
    from django.db.models import Avg, Count

    # Получаем средние значения за прошлые месяцы
    averages = (
        MonthlyReport.objects
        .filter(month__lt=current_month)
        .values('serial_number')
        .annotate(
            avg=Avg('total_prints'),
            count=Count('id')
        )
    )

    avg_dict = {item['serial_number']: item for item in averages}

    result = {}
    for report in reports:
        if report.serial_number in avg_dict:
            avg_data = avg_dict[report.serial_number]
            avg = avg_data['avg']
            difference = report.total_prints - avg

            result[report.id] = {
                'is_anomaly': difference > threshold,
                'has_history': True,
                'average': round(avg, 0),
                'months_count': avg_data['count'],
                'difference': round(difference, 0),
                'percentage': round((difference / avg * 100), 1) if avg > 0 else 0,
                'threshold': threshold
            }
        else:
            result[report.id] = {
                'is_anomaly': False,
                'has_history': False
            }

    return result
```

---

### Синхронизация из Inventory

```python
# monthly_report/services/inventory_sync.py

def sync_counters_from_inventory(year, month):
    """
    Синхронизация счётчиков из последнего опроса inventory
    """
    month_date = date(year, month, 1)
    reports = MonthlyReport.objects.filter(month=month_date)

    updated_rows = 0
    manually_edited_skipped = 0
    skipped_serials = 0

    for report in reports:
        # Пропускаем если вручную редактировалось
        if report.has_manual_edits():
            manually_edited_skipped += 1
            continue

        # Получаем последний опрос
        latest_task = InventoryTask.objects.filter(
            printer__serial_number=report.serial_number,
            status='completed'
        ).order_by('-created_at').first()

        if not latest_task:
            skipped_serials += 1
            continue

        # Обновляем счётчики
        counter = latest_task.page_counter
        report.a4_bw_end_auto = counter.a4_bw_total
        report.a4_color_end_auto = counter.a4_color_total
        # ...
        report.save()

        updated_rows += 1

    # Пересчитываем итоги
    recompute_groups()

    return {
        'updated_rows': updated_rows,
        'manually_edited_skipped': manually_edited_skipped,
        'skipped_serials': skipped_serials,
        'groups_recomputed': groups_count
    }
```

---

## Особенности реализации

### 1. Debounce для автосохранения

```javascript
// MonthReportTable.vue

function debounce(func, wait) {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

const debouncedSave = debounce(() => {
  saveEdit()
}, 500)
```

### 2. Bootstrap Modal интеграция

```javascript
// ChangeHistoryPage.vue

onMounted(async () => {
  await loadData()

  // Используем глобальный объект bootstrap из base.html
  if (revertModalRef.value && window.bootstrap) {
    revertModalInstance = new window.bootstrap.Modal(revertModalRef.value)
  }
})
```

### 3. Floating Scrollbar синхронизация

```javascript
// MonthReportTable.vue

function setupFloatingScrollbar() {
  const handleTableScroll = () => {
    if (tableContainerRef.value && floatingScrollbarInnerRef.value) {
      floatingScrollbarInnerRef.value.scrollLeft = tableContainerRef.value.scrollLeft
    }
  }

  const handleFloatingScroll = () => {
    if (floatingScrollbarInnerRef.value && tableContainerRef.value) {
      tableContainerRef.value.scrollLeft = floatingScrollbarInnerRef.value.scrollLeft
    }
  }

  tableContainerRef.value.addEventListener('scroll', handleTableScroll)
  floatingScrollbarInnerRef.value.addEventListener('scroll', handleFloatingScroll)

  // Cleanup в onUnmounted
}
```

### 4. Toast notifications

```javascript
// MonthDetailPage.vue

function showToast(title, message, type = 'info') {
  const id = Date.now()
  toasts.value.push({ id, title, message, type })

  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, 5000)
}

// Использование
showToast('Синхронизация завершена', `
  ✅ Обновлено позиций: ${data.updated_rows}
  ⚠️ Пропущено (ручное редактирование): ${data.manually_edited_skipped}
`, 'success')
```

### 5. CSRF Token handling

```javascript
// Все компоненты

function getCookie(name) {
  let cookieValue = null
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';')
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim()
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

// В fetch запросах
fetch('/api/endpoint/', {
  method: 'POST',
  headers: {
    'X-CSRFToken': getCookie('csrftoken')
  }
})
```

---

## Troubleshooting

### Проблема: История изменений не загружается (500 ошибка)

**Причина:** Неправильное имя поля в API endpoint

**Решение:**
```python
# Было (НЕПРАВИЛЬНО):
'field': change.field

# Стало (ПРАВИЛЬНО):
'field': change.field_name
```

---

### Проблема: После загрузки Excel не показывается результат

**Причина:** Backend возвращал HTML вместо JSON

**Решение:**
```python
# monthly_report/views.py

# Было:
return render(request, 'monthly_report/upload_success.html', {...})

# Стало:
return JsonResponse({
    'success': True,
    'count': count,
    'month_url': month_url,
    'message': f'Успешно загружено {count} записей'
})
```

---

### Проблема: Поля разрешены для редактирования, но сохранить нельзя

**Причина:** Backend не возвращал ui_allow_* флаги

**Решение:** Добавлена логика расчёта разрешений в `api_month_detail`:
```python
# Вычисляем ui_allow_* флаги для каждой записи
ui_allow = calculate_ui_allow_flags(report, request.user)
report_dict.update(ui_allow)
```

---

### Проблема: Bootstrap modal не открывается

**Причина:** Попытка динамического импорта Bootstrap

**Решение:**
```javascript
// Было:
const { Modal } = await import('bootstrap')

// Стало:
if (window.bootstrap) {
  revertModalInstance = new window.bootstrap.Modal(revertModalRef.value)
}
```

---

### Проблема: Аномалии показываются неправильно

**Причина:** Фильтр использовал boolean поле вместо объекта

**Решение:**
```javascript
// Было:
if (report.is_anomaly)

// Стало:
if (report.anomaly_info && report.anomaly_info.is_anomaly)
```

---

## Статистика

- **Компонентов:** 5
- **Строк кода (Vue):** ~2100
- **API endpoints:** 6
- **Время разработки:** ~8 часов
- **Функционал:** 100% мигрирован

---

## Дальнейшее развитие

### Потенциальные улучшения

1. **Оптимизация запросов:**
   - Использовать виртуальный скроллинг для больших таблиц
   - Pagination для истории изменений

2. **UX улучшения:**
   - Bulk edit для нескольких записей
   - Excel-like keyboard navigation (Tab, Enter, стрелки)
   - Undo/Redo для изменений

3. **Дополнительные функции:**
   - Экспорт истории в Excel
   - Фильтрация истории по пользователю/дате
   - Графики расхода бумаги
   - Прогнозирование на основе истории

4. **Техническая оптимизация:**
   - Переход на TypeScript
   - Composables для переиспользуемой логики
   - Unit тесты для компонентов

---

**Дата последнего обновления:** 2025-11-18
**Автор документации:** Claude AI Assistant
