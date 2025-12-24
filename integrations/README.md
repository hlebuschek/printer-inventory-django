# Integrations App

Приложение для интеграции с внешними системами.

## Поддерживаемые системы

### GLPI (IT Asset Management)

Интеграция с GLPI через REST API для проверки наличия принтеров в системе учёта.

#### Возможности:
- ✅ Проверка принтера по серийному номеру
- ✅ **Поиск по двум полям:** стандартное поле serial + кастомное поле "серийный номер на бирке"
- ✅ OR логика: находит принтер при совпадении в любом из полей
- ✅ Обнаружение дубликатов (несколько карточек с одним серийником)
- ✅ Массовая проверка устройств
- ✅ История синхронизаций
- ✅ Логирование всех операций

## Настройка

### 1. Добавьте приложение в INSTALLED_APPS

В `printer_inventory/settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'integrations',
    # ...
]
```

### 2. Настройте переменные окружения

Добавьте в `.env`:

```bash
# GLPI API настройки
GLPI_API_URL=https://glpi.yourcompany.com/apirest.php
GLPI_APP_TOKEN=your_app_token_here
GLPI_USER_TOKEN=your_user_token_here

# Альтернативно можно использовать username/password вместо user_token:
# GLPI_USERNAME=api_user
# GLPI_PASSWORD=api_password

# ID полей для поиска принтеров
GLPI_SERIAL_FIELD_ID=5  # Стандартное поле serial (по умолчанию 5)
GLPI_LABEL_SERIAL_FIELD_ID=  # ID кастомного поля "серийный номер на бирке" (оставьте пустым если не используете)
```

**Как узнать ID кастомного поля:**
1. Откройте карточку принтера в GLPI
2. Откройте DevTools браузера (F12) → Network
3. Обновите страницу и найдите запрос к API с данными принтера
4. В ответе найдите поле с серийным номером на бирке и его ID

**Логика поиска:**
- Если указан только `GLPI_SERIAL_FIELD_ID` → поиск только по стандартному полю
- Если указаны оба поля → поиск с OR логикой (находит при совпадении в любом из полей)
```

### 3. Добавьте URLs

В `printer_inventory/urls.py`:

```python
urlpatterns = [
    # ...
    path('integrations/', include('integrations.urls', namespace='integrations')),
    # ...
]
```

### 4. Создайте миграции

```bash
python manage.py makemigrations integrations
python manage.py migrate integrations
```

## Получение токенов GLPI

### Через веб-интерфейс GLPI:

1. **App Token:**
   - Войдите как администратор
   - Setup → General → API
   - Включите REST API
   - Создайте App Token

2. **User Token:**
   - Setup → Users → [Ваш пользователь] → Remote access keys
   - Создайте API token

## Использование

### Python API

```python
from integrations.glpi.services import check_device_in_glpi
from contracts.models import ContractDevice

# Проверить одно устройство
device = ContractDevice.objects.get(id=1)
sync = check_device_in_glpi(device, user=request.user)

print(sync.status)  # 'FOUND_SINGLE', 'FOUND_MULTIPLE', 'NOT_FOUND', 'ERROR'
print(sync.glpi_ids)  # [123] - ID карточек в GLPI
print(sync.has_conflict)  # True если найдено > 1 карточки
```

### REST API Endpoints

#### Проверить одно устройство

```http
POST /integrations/glpi/check-device/123/
Content-Type: application/json

{
  "force": true  # опционально, принудительная проверка
}
```

Ответ:
```json
{
  "ok": true,
  "sync": {
    "id": 456,
    "status": "FOUND_SINGLE",
    "status_display": "Найден (1 карточка)",
    "glpi_ids": [789],
    "glpi_count": 1,
    "is_synced": true,
    "has_conflict": false,
    "error_message": null,
    "checked_at": "2025-12-22T10:30:00Z",
    "checked_by": "admin"
  }
}
```

#### Проверить несколько устройств

```http
POST /integrations/glpi/check-multiple/
Content-Type: application/json

{
  "device_ids": [1, 2, 3, 4, 5]
}
```

Ответ:
```json
{
  "ok": true,
  "stats": {
    "total": 5,
    "found_single": 3,
    "found_multiple": 1,
    "not_found": 1,
    "errors": 0
  }
}
```

#### Получить статус синхронизации

```http
GET /integrations/glpi/sync-status/123/
```

#### Получить устройства с конфликтами

```http
GET /integrations/glpi/conflicts/
```

#### Получить устройства не найденные в GLPI

```http
GET /integrations/glpi/not-found/
```

## Интеграция с фронтендом (Vue.js)

Пример добавления кнопки проверки в GLPI в таблицу устройств:

```vue
<template>
  <button
    @click="checkInGLPI(device.id)"
    :disabled="checking"
    class="btn btn-outline-info btn-sm"
  >
    <i class="bi bi-cloud-check"></i>
    {{ checking ? 'Проверка...' : 'Проверить в GLPI' }}
  </button>

  <!-- Статус -->
  <span v-if="device.glpi_status" :class="getGLPIStatusClass(device.glpi_status)">
    {{ device.glpi_status_display }}
  </span>
</template>

<script setup>
import { ref } from 'vue'

const checking = ref(false)

async function checkInGLPI(deviceId) {
  checking.value = true

  try {
    const response = await fetch(`/integrations/glpi/check-device/${deviceId}/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCSRFToken(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ force: true })
    })

    const data = await response.json()

    if (data.ok) {
      // Обновить статус устройства
      device.glpi_status = data.sync.status
      device.glpi_status_display = data.sync.status_display
      device.glpi_count = data.sync.glpi_count

      // Показать уведомление
      showToast('Успешно', `Статус: ${data.sync.status_display}`,
        data.sync.has_conflict ? 'warning' : 'success')
    } else {
      showToast('Ошибка', data.error, 'error')
    }
  } catch (error) {
    showToast('Ошибка', 'Не удалось проверить устройство', 'error')
  } finally {
    checking.value = false
  }
}

function getGLPIStatusClass(status) {
  const classes = {
    'FOUND_SINGLE': 'badge bg-success',
    'FOUND_MULTIPLE': 'badge bg-warning',
    'NOT_FOUND': 'badge bg-secondary',
    'ERROR': 'badge bg-danger'
  }
  return classes[status] || 'badge bg-secondary'
}

function getCSRFToken() {
  const meta = document.querySelector('meta[name="csrf-token"]')
  return meta ? meta.getAttribute('content') : ''
}
</script>
```

## Модели

### GLPISync

Хранит результаты проверки устройств в GLPI.

**Поля:**
- `contract_device` - Связь с ContractDevice
- `status` - Статус проверки (NOT_FOUND, FOUND_SINGLE, FOUND_MULTIPLE, ERROR)
- `searched_serial` - Искомый серийный номер
- `glpi_ids` - Список ID найденных карточек в GLPI
- `glpi_data` - Полные данные из GLPI API (JSON)
- `error_message` - Сообщение об ошибке (если есть)
- `checked_at` - Время проверки
- `checked_by` - Пользователь, инициировавший проверку

### IntegrationLog

Общий лог для всех интеграций.

**Поля:**
- `system` - Система (GLPI, OTHER)
- `level` - Уровень (DEBUG, INFO, WARNING, ERROR)
- `message` - Сообщение
- `details` - Детали (JSON)
- `created_at` - Время
- `user` - Пользователь

## Кэширование

Результаты проверки кэшируются на 1 час. Для принудительной проверки используйте `force_check=True` или `force=true` в API.

## Расширение

Для добавления интеграции с другой системой:

1. Создайте директорию `integrations/newsystem/`
2. Добавьте `client.py` с клиентом API
3. Добавьте `services.py` с бизнес-логикой
4. Создайте модели для логирования (опционально)
5. Добавьте views и URLs

Пример структуры:
```
integrations/
├── glpi/          # GLPI интеграция
├── newsystem/     # Новая система
│   ├── client.py
│   ├── services.py
│   └── ...
├── models.py
├── views.py
└── urls.py
```

## Безопасность

⚠️ **Важно:**
- Храните GLPI токены в `.env`, не коммитьте их в git
- Используйте HTTPS для GLPI API URL
- Ограничьте права API пользователя в GLPI только чтением

## Мониторинг

Все операции логируются в:
- **Django Admin** → Integrations → Integration Logs
- **Django Admin** → Integrations → GLPI Syncs

Для мониторинга ошибок:
```bash
# Посмотреть последние ошибки
python manage.py shell
>>> from integrations.models import IntegrationLog
>>> IntegrationLog.objects.filter(level='ERROR').order_by('-created_at')[:10]
```

## Troubleshooting

### Ошибка: "GLPI API URL не настроен"
Проверьте наличие `GLPI_API_URL` в `.env`

### Ошибка: "Ошибка аутентификации GLPI"
Проверьте корректность токенов. Убедитесь что API включен в GLPI (Setup → General → API)

### Ничего не находится, хотя устройство точно есть в GLPI
Проверьте поле для поиска серийного номера. В GLPI это обычно поле с ID=5, но может отличаться. Измените в `glpi/client.py`:
```python
'field': '5',  # ID поля "serial" в вашем GLPI
```
