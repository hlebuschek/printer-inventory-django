# План интеграции USB-агента PrinterCollector

## Обзор

PrinterCollector — Windows-агент на C#, который:
- Читает счетчики USB-принтеров из реестра Windows (`PageCount`)
- Извлекает серийные номера из USB DeviceInstanceId
- Генерирует XML-файлы с данными опроса
- Может работать в headless-режиме (планировщик задач Windows)

**Цель:** интегрировать USB-опросы в существующую систему inventory наравне со SNMP и Web-парсингом.

## Ключевые решения (финальная версия)

1. **Привязка к организациям**: через существующую таблицу `ContractDevice` по серийному номеру (как в `/inventory/add/`)
   - Принтер должен быть сначала добавлен в `/contracts/`
   - При получении данных от агента: поиск по S/N → автоматическое назначение Organization и DeviceModel

2. **Аутентификация**: токен на агента, создается при первом подключении (self-registration)
   - Модель `USBAgent` с полями: `agent_id`, `token`, `hostname`, `is_active`, `last_seen`
   - Агент отправляет токен в заголовке `Authorization: Bearer <token>`
   - При первом подключении агент регистрируется через специальный endpoint

3. **Опрос расходников**: НЕ планируется через USB
   - Агент отправляет только счетчики страниц (total, A4 ч/б, A4 цвет, A3 ч/б, A3 цвет)
   - Расходники опрашиваются через SNMP/Web для сетевых принтеров или вносятся вручную

4. **Множественные агенты**: каждый агент опрашивает только локальные принтеры
   - Выбор принтера в настройках агента (один принтер на агента)
   - Если несколько агентов опрашивают один принтер — все опросы сохраняются с `agent_id`
   - Дедупликация по timestamp (опросы с разницей < 5 минут считаются дубликатами)

5. **Опрос с сервера**: НЕ планируется
   - Агент работает по расписанию (раз в час) автоматически
   - Модель `AgentCommand` и polling endpoints не нужны
   - Кнопка "Опросить сейчас" в UI не нужна
   - **Webhook (push) отложен** — требует согласования с ИБ (агент должен открывать порт)

6. **UI интеграция**: расширение существующих страниц, без отдельных разделов
   - `/inventory/`: бейдж "USB" в колонке IP, hostname агента
   - `/monthly-report/`: вместо `ip-auto` показывать `usb-auto` для USB-принтеров (аналогично существующей логике)

---

## 1. Архитектурные решения

### 1.1 Новый метод опроса: USB_API

```python
# inventory/models.py
class PollingMethod(models.TextChoices):
    SNMP = "SNMP", "SNMP (GLPI Agent)"
    WEB = "WEB", "Web Parsing"
    USB_API = "USB_API", "USB Agent (API)"  # НОВОЕ
```

**Обоснование:**
- SNMP — сетевой опрос через GLPI Agent
- WEB — HTTP-скрейпинг веб-интерфейса принтера
- USB_API — данные от внешнего агента через REST API

### 1.2 Идентификация принтеров

**Проблема:** USB-принтеры не имеют IP-адреса.

**Решение:**
- `Printer.ip_address` остается обязательным (constraint в БД)
- Для USB-принтеров используем **псевдо-IP формата `usb-<serial>`**
  - Пример: `usb-CNBXK12345` для принтера с S/N CNBXK12345
  - Валидация: `^usb-[A-Z0-9]+$` (не проходит GenericIPAddressField)
  
**Альтернатива (рекомендуется):**
- Изменить `Printer.ip_address` на `CharField` с валидацией:
  ```python
  ip_address = models.CharField(
      max_length=50,
      db_index=True,
      validators=[validate_ip_or_usb_identifier],
      verbose_name="IP-адрес или USB ID"
  )
  ```
- Добавить `connection_type` (IP/USB) для фильтрации

### 1.3 Маркировка источника данных

**Добавить в InventoryTask:**
```python
class DataSource(models.TextChoices):
    SNMP_LOCAL = "SNMP_LOCAL", "SNMP (локальный GLPI)"
    WEB_SCRAPING = "WEB_SCRAPING", "Web Parsing"
    USB_AGENT = "USB_AGENT", "USB Agent API"

data_source = models.CharField(
    max_length=20,
    choices=DataSource.choices,
    default=DataSource.SNMP_LOCAL,
    db_index=True,
    verbose_name="Источник данных"
)
```

**Зачем:**
- Отличать данные от разных источников в отчетах
- Фильтровать по методу сбора
- Аудит: кто/что отправил данные

---

## 2. API Endpoint

### 2.1 Структура запроса

**POST /api/v1/inventory/usb-readings/**

```json
{
  "agent_id": "WIN-PC-001",
  "agent_version": "1.0.0",
  "readings": [
    {
      "timestamp": "2026-05-05T13:00:00Z",
      "printer_name": "HP LaserJet Pro M404dn",
      "model": "HP LaserJet Pro M404dn PCL 6",
      "serial_number": {
        "source": "device",
        "value": "CNBXK12345"
      },
      "counters": {
        "total_pages": 12450,
        "bw_a4": 10200,
        "color_a4": 1800,
        "bw_a3": 350,
        "color_a3": 100
      },
      "connection_verified": true,
      "device_instance_id": "USB\\VID_03F0&PID_042A\\CNBXK12345"
    }
  ]
}
```

**Поля:**
- `agent_id` — идентификатор клиента (hostname/UUID)
- `agent_version` — версия агента (для совместимости)
- `readings[]` — массив опросов (batch upload)
- `serial_number.source` — `device` (автоопределение) или `manual` (ручной ввод)
- `counters` — счетчики страниц по форматам (как в SNMP/Web):
  - `total_pages` — общий счетчик (обязательное)
  - `bw_a4` — A4 ч/б (опционально)
  - `color_a4` — A4 цвет (опционально)
  - `bw_a3` — A3 ч/б (опционально)
  - `color_a3` — A3 цвет (опционально)

### 2.2 Валидация

```python
# inventory/serializers.py
from rest_framework import serializers

class SerialNumberSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=['device', 'manual'])
    value = serializers.CharField(max_length=100)

class CountersSerializer(serializers.Serializer):
    """Счетчики страниц по форматам (как в PageCounter)"""
    total_pages = serializers.IntegerField(min_value=0, required=True)
    bw_a4 = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    color_a4 = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    bw_a3 = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    color_a3 = serializers.IntegerField(min_value=0, required=False, allow_null=True)

class USBReadingSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField()
    printer_name = serializers.CharField(max_length=200)
    model = serializers.CharField(max_length=200)
    serial_number = SerialNumberSerializer()
    counters = CountersSerializer()
    connection_verified = serializers.BooleanField()
    device_instance_id = serializers.CharField(max_length=200)

class USBBatchSerializer(serializers.Serializer):
    agent_id = serializers.CharField(max_length=100)
    agent_version = serializers.CharField(max_length=20)
    readings = USBReadingSerializer(many=True)
```

### 2.3 Обработка

```python
# inventory/views.py (новый view)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Требует токен
def usb_readings_upload(request):
    """
    Прием данных от USB-агента.
    """
    serializer = USBBatchSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    results = []
    
    for reading in data['readings']:
        try:
            result = process_usb_reading(
                reading=reading,
                agent_id=data['agent_id'],
                agent_version=data['agent_version']
            )
            results.append(result)
        except Exception as e:
            logger.exception(f"Failed to process reading: {reading}")
            results.append({
                'serial_number': reading['serial_number']['value'],
                'status': 'error',
                'message': str(e)
            })
    
    return Response({
        'processed': len(results),
        'results': results
    }, status=status.HTTP_200_OK)
```

### 2.4 Бизнес-логика

```python
# inventory/services.py (новая функция)
def process_usb_reading(reading: dict, agent_id: str, agent_version: str) -> dict:
    """
    Обработка одного USB-опроса.
    
    1. Найти ContractDevice по serial_number
    2. Найти/создать Printer с данными из договора
    3. Создать InventoryTask (data_source=USB_AGENT)
    4. Валидировать счетчики через validate_against_history()
    5. Создать PageCounter при успехе
    6. Отправить WebSocket-уведомление
    """
    from contracts.models import ContractDevice
    
    serial = reading['serial_number']['value']
    usb_id = f"usb-{serial}"
    
    # 1. Найти ContractDevice по серийнику (как в inventory/add/)
    contract_device = ContractDevice.objects.filter(
        serial_number=serial
    ).select_related('device_model__manufacturer', 'organization').first()
    
    if not contract_device:
        return {
            'serial_number': serial,
            'status': 'error',
            'message': f'Принтер с S/N {serial} не найден в договорах. Добавьте в /contracts/ сначала.'
        }
    
    # 2. Найти или создать Printer с данными из договора
    printer, created = Printer.objects.get_or_create(
        serial_number=serial,
        defaults={
            'ip_address': usb_id,
            'device_model': contract_device.device_model,
            'organization': contract_device.organization,
            'polling_method': PollingMethod.USB_API,
            'snmp_community': '',
        }
    )
    
    if not created:
        # Обновить данные если принтер уже существовал
        printer.device_model = contract_device.device_model
        printer.organization = contract_device.organization
        printer.polling_method = PollingMethod.USB_API
        printer.ip_address = usb_id
        printer.save()
    
    # 3. Создать задачу
    task = InventoryTask.objects.create(
        printer=printer,
        task_timestamp=reading['timestamp'],
        status='SUCCESS',
        data_source=DataSource.USB_AGENT,
        agent_id=agent_id  # Сохраняем ID агента для аудита
    )
    
    # 4. Валидация счетчиков (используем существующую функцию)
    counters = reading.get('counters', {})
    total_pages = counters.get('total_pages')
    bw_a4 = counters.get('bw_a4')
    color_a4 = counters.get('color_a4')
    
    if total_pages is not None:
        validation_result = validate_against_history(
            printer=printer,
            new_total=total_pages,
            new_bw_a4=bw_a4,
            new_color_a4=color_a4,
            task_timestamp=reading['timestamp']
        )
        
        if not validation_result['valid']:
            task.status = 'HISTORICAL_INCONSISTENCY'
            task.error_message = validation_result['reason']
            task.save()
            return {
                'serial_number': serial,
                'status': 'rejected',
                'reason': validation_result['reason']
            }
    
    # 5. Сохранить счетчики (как в SNMP/Web)
    PageCounter.objects.create(
        task=task,
        total_pages=total_pages,
        bw_a4=bw_a4,
        color_a4=color_a4,
        bw_a3=counters.get('bw_a3'),
        color_a3=counters.get('color_a3')
    )
    
    # 6. WebSocket-уведомление
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'inventory_updates',
        {
            'type': 'inventory_update',
            'message': {
                'printer_id': printer.id,
                'ip_address': printer.ip_address,
                'status': task.status,
                'timestamp': task.task_timestamp.isoformat(),
                'source': 'USB_AGENT',
                'agent_id': agent_id
            }
        }
    )
    
    return {
        'serial_number': serial,
        'status': 'success',
        'task_id': task.id,
        'printer_id': printer.id
    }
```

---

## 3. Безопасность и аутентификация агентов

### 3.1 Модель USBAgent

```python
# inventory/models.py
class USBAgent(models.Model):
    """USB-агент для опроса локальных принтеров"""
    agent_id = models.CharField(max_length=100, unique=True, db_index=True, verbose_name="ID агента")
    token = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="Токен доступа")
    hostname = models.CharField(max_length=200, blank=True, verbose_name="Имя компьютера")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")
    last_seen = models.DateTimeField(auto_now=True, verbose_name="Последняя активность")
    
    class Meta:
        verbose_name = "USB-агент"
        verbose_name_plural = "USB-агенты"
        ordering = ['-last_seen']
    
    def __str__(self):
        return f"{self.agent_id} ({self.hostname})"
```

### 3.2 Аутентификация через токен

```python
# inventory/authentication.py
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone

class USBAgentTokenAuthentication(BaseAuthentication):
    """Аутентификация USB-агентов по токену"""
    
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header[7:]  # Убрать "Bearer "
        
        try:
            agent = USBAgent.objects.get(token=token, is_active=True)
            agent.last_seen = timezone.now()
            agent.save(update_fields=['last_seen'])
            return (agent, None)  # agent становится request.user
        except USBAgent.DoesNotExist:
            raise AuthenticationFailed('Invalid agent token')
```

### 3.3 Self-registration endpoint

```python
# inventory/views.py
@api_view(['POST'])
def register_usb_agent(request):
    """
    Регистрация нового USB-агента (self-registration).
    Требует registration_key из settings.
    """
    registration_key = request.data.get('registration_key')
    
    # Проверка мастер-ключа
    if registration_key != settings.USB_AGENT_REGISTRATION_KEY:
        return Response({'error': 'Invalid registration key'}, status=403)
    
    agent_id = request.data.get('agent_id')
    hostname = request.data.get('hostname', '')
    
    if not agent_id:
        return Response({'error': 'agent_id is required'}, status=400)
    
    # Проверка существования
    if USBAgent.objects.filter(agent_id=agent_id).exists():
        return Response({'error': 'Agent already registered'}, status=400)
    
    # Создание агента
    import secrets
    agent = USBAgent.objects.create(
        agent_id=agent_id,
        hostname=hostname,
        token=secrets.token_hex(32)
    )
    
    return Response({
        'agent_id': agent.agent_id,
        'token': agent.token,
        'message': 'Agent registered successfully'
    }, status=201)

# В urls.py
urlpatterns = [
    path('api/v1/inventory/usb-agents/register/', register_usb_agent, name='usb_agent_register'),
    path('api/v1/inventory/usb-readings/', usb_readings_upload, name='usb_readings_upload'),
]
```

### 3.4 Конфигурация в settings.py

```python
# settings.py
USB_AGENT_REGISTRATION_KEY = env('USB_AGENT_REGISTRATION_KEY', default='change-me-in-production')
```

### 3.5 Workflow регистрации агента

1. **Первый запуск агента:**
   ```csharp
   // Агент проверяет наличие токена в settings.json
   if (string.IsNullOrEmpty(settings.ApiToken))
   {
       // Регистрация
       var response = await httpClient.PostAsJsonAsync(
           $"{settings.ApiEndpoint}/usb-agents/register/",
           new {
               agent_id = Environment.MachineName,
               hostname = Environment.MachineName,
               registration_key = settings.RegistrationKey
           }
       );
       
       var result = await response.Content.ReadFromJsonAsync<RegistrationResponse>();
       
       // Сохранить токен в settings.json
       settings.ApiToken = result.Token;
       SaveSettings(settings);
   }
   ```

2. **Последующие запуски:**
   - Агент использует сохраненный токен
   - Токен передается в заголовке `Authorization: Bearer <token>`

### 3.6 Rate Limiting

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '100/hour',  # Агент может отправлять до 100 запросов/час
    }
}
```

### 3.7 Валидация данных

**Защита от replay-атак:**
```python
# В process_usb_reading()
from django.utils import timezone
from datetime import timedelta

reading_time = reading['timestamp']
if timezone.now() - reading_time > timedelta(hours=1):
    return {
        'serial_number': serial,
        'status': 'error',
        'message': 'Reading timestamp is too old (>1 hour)'
    }

# Проверка дубликатов (serial + timestamp)
if InventoryTask.objects.filter(
    printer__serial_number=serial,
    task_timestamp=reading_time,
    data_source=DataSource.USB_AGENT
).exists():
    return {
        'serial_number': serial,
        'status': 'duplicate',
        'message': 'Reading already processed'
    }
```

---

## 4. Изменения в агенте (C#)

### 4.1 Конфигурация

```json
{
  "PrinterName": "HP LaserJet Pro M404dn",
  "OutputFolder": "C:\\PrinterCollector\\xml",
  "ApiEndpoint": "https://inventory.example.com/api/v1/inventory",
  "RegistrationKey": "SECRET_KEY_FROM_SERVER",
  "ApiToken": "",
  "AgentId": "",
  "ScheduleInterval": "01:00:00"
}
```

**Поля:**
- `ApiToken` — заполняется автоматически при регистрации
- `AgentId` — заполняется автоматически (hostname)
- `RegistrationKey` — мастер-ключ для регистрации новых агентов
- `ScheduleInterval` — интервал опроса (по умолчанию 1 час)

### 4.2 Структура XML с форматами страниц

```xml
<?xml version="1.0" encoding="utf-8"?>
<PrinterReading>
  <Timestamp>2026-05-05T13:00:00</Timestamp>
  <PrinterName>HP LaserJet Pro M404dn</PrinterName>
  <Model>HP LaserJet Pro M404dn PCL 6</Model>
  <SerialNumber source="device">CNBXK12345</SerialNumber>
  <Counters>
    <TotalPages>12450</TotalPages>
    <BwA4>10200</BwA4>
    <ColorA4>1800</ColorA4>
    <BwA3>350</BwA3>
    <ColorA3>100</ColorA3>
  </Counters>
  <ConnectionVerified>true</ConnectionVerified>
  <DeviceInstanceId>USB\VID_03F0&amp;PID_042A\CNBXK12345</DeviceInstanceId>
</PrinterReading>
```

**Примечание:** Агент должен читать счетчики по форматам из реестра Windows или драйвера принтера. Если драйвер не предоставляет детализацию — отправлять только `TotalPages`.

### 4.3 HTTP-клиент с регистрацией

```csharp
// Services/ApiClient.cs
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;

public class ApiClient
{
    private readonly HttpClient _http;
    private readonly AppSettings _settings;
    private readonly string _settingsPath;

    public ApiClient(AppSettings settings, string settingsPath)
    {
        _settings = settings;
        _settingsPath = settingsPath;
        _http = new HttpClient();
        _http.Timeout = TimeSpan.FromSeconds(30);
    }

    public async Task<bool> EnsureRegistered()
    {
        // Проверка наличия токена
        if (!string.IsNullOrEmpty(_settings.ApiToken))
        {
            _http.DefaultRequestHeaders.Clear();
            _http.DefaultRequestHeaders.Add("Authorization", $"Bearer {_settings.ApiToken}");
            return true;
        }

        // Регистрация
        try
        {
            var agentId = Environment.MachineName;
            var response = await _http.PostAsJsonAsync(
                $"{_settings.ApiEndpoint}/usb-agents/register/",
                new
                {
                    agent_id = agentId,
                    hostname = Environment.MachineName,
                    registration_key = _settings.RegistrationKey
                }
            );

            if (!response.IsSuccessStatusCode)
            {
                var error = await response.Content.ReadAsStringAsync();
                Logger.Log($"Registration failed: {error}");
                return false;
            }

            var result = await response.Content.ReadFromJsonAsync<RegistrationResponse>();
            
            // Сохранить токен
            _settings.ApiToken = result.Token;
            _settings.AgentId = agentId;
            SaveSettings();

            _http.DefaultRequestHeaders.Add("Authorization", $"Bearer {result.Token}");
            Logger.Log($"Agent registered: {agentId}");
            return true;
        }
        catch (Exception ex)
        {
            Logger.Log($"Registration error: {ex.Message}");
            return false;
        }
    }

    public async Task<bool> UploadReading(PrinterReading reading)
    {
        if (!await EnsureRegistered())
            return false;

        var payload = new
        {
            agent_id = _settings.AgentId,
            agent_version = "1.0.0",
            readings = new[] { reading }
        };

        try
        {
            var response = await _http.PostAsJsonAsync(
                $"{_settings.ApiEndpoint}/usb-readings/",
                payload
            );

            if (response.IsSuccessStatusCode)
            {
                Logger.Log($"Reading uploaded: {reading.SerialNumber.Value}");
                return true;
            }
            else
            {
                var error = await response.Content.ReadAsStringAsync();
                Logger.Log($"Upload failed: {error}");
                return false;
            }
        }
        catch (Exception ex)
        {
            Logger.Log($"Upload error: {ex.Message}");
            return false;
        }
    }

    private void SaveSettings()
    {
        var json = JsonSerializer.Serialize(_settings, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(_settingsPath, json);
    }
}

public class RegistrationResponse
{
    public string AgentId { get; set; }
    public string Token { get; set; }
    public string Message { get; set; }
}
```

### 4.4 Fallback на локальные XML

```csharp
// Services/OfflineQueue.cs
public class OfflineQueue
{
    private readonly string _queueDir;

    public OfflineQueue(string queueDir)
    {
        _queueDir = queueDir;
        Directory.CreateDirectory(_queueDir);
    }

    public void Enqueue(PrinterReading reading)
    {
        var filename = $"{reading.SerialNumber.Value}_{reading.Timestamp:yyyyMMdd_HHmmss}.json";
        var path = Path.Combine(_queueDir, filename);
        
        var json = JsonSerializer.Serialize(reading);
        File.WriteAllText(path, json);
        
        Logger.Log($"Reading queued offline: {filename}");
    }

    public async Task<int> FlushQueue(ApiClient apiClient)
    {
        var files = Directory.GetFiles(_queueDir, "*.json");
        int uploaded = 0;

        foreach (var file in files)
        {
            try
            {
                var json = File.ReadAllText(file);
                var reading = JsonSerializer.Deserialize<PrinterReading>(json);
                
                if (await apiClient.UploadReading(reading))
                {
                    File.Delete(file);
                    uploaded++;
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to flush {file}: {ex.Message}");
            }
        }

        return uploaded;
    }
}
```

### 4.5 Планировщик задач Windows

**Настройка автоматического опроса:**
```powershell
# Создать задачу в планировщике Windows
schtasks /create /tn "PrinterCollector" /tr "C:\PrinterCollector\PrinterCollector.exe --headless" /sc hourly /st 09:00
```

**Или через GUI:**
1. Открыть "Планировщик заданий"
2. Создать простую задачу
3. Триггер: Ежедневно, повторять каждый час
4. Действие: Запуск программы `C:\PrinterCollector\PrinterCollector.exe --headless`

---

## 5. UI/UX изменения

### 5.1 Список принтеров

**Добавить колонку "Метод опроса":**
```html
<td>
  {% if printer.polling_method == 'USB_API' %}
    <span class="badge bg-info">USB Agent</span>
  {% elif printer.polling_method == 'WEB' %}
    <span class="badge bg-warning">Web</span>
  {% else %}
    <span class="badge bg-primary">SNMP</span>
  {% endif %}
</td>
```

### 5.2 Карточка принтера

**Показать источник последнего опроса:**
```html
<div class="card">
  <div class="card-header">Последний опрос</div>
  <div class="card-body">
    <p>Дата: {{ last_task.task_timestamp }}</p>
    <p>Статус: {{ last_task.get_status_display }}</p>
    <p>Источник: 
      {% if last_task.data_source == 'USB_AGENT' %}
        USB Agent ({{ last_task.agent_id }})
      {% else %}
        {{ last_task.get_data_source_display }}
      {% endif %}
    </p>
  </div>
</div>
```

### 5.3 Фильтры

**Добавить фильтр по методу опроса:**
```python
# inventory/filters.py
class PrinterFilter(django_filters.FilterSet):
    polling_method = django_filters.ChoiceFilter(choices=PollingMethod.choices)
    
    class Meta:
        model = Printer
        fields = ['organization', 'polling_method', 'is_active']
```

---

## 6. UI/UX изменения

### 5.1 Список принтеров (`/inventory/`)

**Колонка IP-адрес — показывать бейдж USB + hostname агента:**
```html
<!-- inventory/templates/inventory/printer_list.html -->
<td>
  {% if printer.polling_method == 'USB_API' %}
    <span class="badge bg-info" title="USB-принтер">
      <i class="bi bi-usb"></i> USB
    </span>
    <br>
    <small class="text-muted">{{ printer.last_agent_hostname|default:"неизвестно" }}</small>
  {% else %}
    {{ printer.ip_address }}
  {% endif %}
</td>
```

**Колонка "Последний опрос" — показывать agent_id:**
```html
<td>
  {{ printer.last_inventory_time|timesince }} назад
  {% if printer.polling_method == 'USB_API' and printer.last_agent_id %}
    <br><small class="text-muted">Agent: {{ printer.last_agent_id }}</small>
  {% endif %}
</td>
```

**Добавить свойства в модель Printer:**
```python
# inventory/models.py
class Printer(models.Model):
    # ... существующие поля
    
    @property
    def last_agent_id(self):
        """ID последнего агента, который опрашивал принтер"""
        last_task = self.inventorytask_set.filter(
            data_source='USB_AGENT'
        ).order_by('-task_timestamp').first()
        return last_task.agent_id if last_task else None
    
    @property
    def last_agent_hostname(self):
        """Hostname агента"""
        if self.last_agent_id:
            try:
                agent = USBAgent.objects.get(agent_id=self.last_agent_id)
                return agent.hostname
            except USBAgent.DoesNotExist:
                return self.last_agent_id
        return None
```

### 5.2 Карточка принтера (`/inventory/<pk>/history/`)

**Показать источник последнего опроса:**
```html
<div class="card mb-3">
  <div class="card-header">Последний опрос</div>
  <div class="card-body">
    <p><strong>Дата:</strong> {{ last_task.task_timestamp }}</p>
    <p><strong>Статус:</strong> {{ last_task.get_status_display }}</p>
    <p><strong>Источник:</strong> 
      {% if last_task.data_source == 'USB_AGENT' %}
        <span class="badge bg-info">USB Agent</span>
        ({{ last_task.agent_id }})
      {% elif last_task.data_source == 'WEB_SCRAPING' %}
        <span class="badge bg-warning">Web Parsing</span>
      {% else %}
        <span class="badge bg-primary">SNMP</span>
      {% endif %}
    </p>
  </div>
</div>
```

### 5.3 Ежемесячные отчеты (`/monthly-report/`)

**Вместо `ip-auto` показывать `usb-auto` для USB-принтеров:**

```python
# monthly_report/models.py
class MonthlyReport(models.Model):
    # ... существующие поля
    data_source = models.CharField(
        max_length=20,
        choices=[
            ('SNMP_LOCAL', 'SNMP'),
            ('WEB_SCRAPING', 'Web'),
            ('USB_AGENT', 'USB Agent')
        ],
        default='SNMP_LOCAL',
        blank=True,
        verbose_name='Источник данных'
    )
```

**Шаблон — аналогично `ip-auto`:**
```html
<!-- monthly_report/templates/monthly_report/report_table.html -->
<td>
  {{ report.device_ip }}
  {% if report.data_source == 'USB_AGENT' %}
    <span class="badge bg-info" title="Данные от USB-агента">usb-auto</span>
  {% elif report.is_auto_polling %}
    <span class="badge bg-success" title="Автоматический опрос">ip-auto</span>
  {% endif %}
</td>
```

**Синхронизация из InventoryTask:**
```python
# monthly_report/services_inventory_sync.py
def sync_inventory_to_monthly_report(inventory_task, year, month):
    """Синхронизация данных из InventoryTask в MonthlyReport"""
    # ... существующая логика
    
    MonthlyReport.objects.update_or_create(
        organization=inventory_task.printer.organization.name,
        device_ip=inventory_task.printer.ip_address,
        year=year,
        month=month,
        defaults={
            # ... существующие поля
            'data_source': inventory_task.data_source,  # НОВОЕ
            'is_auto_polling': inventory_task.data_source in ['SNMP_LOCAL', 'USB_AGENT'],  # USB тоже авто
        }
    )
```

### 5.4 Фильтры

**Добавить фильтр по методу опроса:**
```python
# inventory/filters.py
import django_filters
from .models import Printer, PollingMethod

class PrinterFilter(django_filters.FilterSet):
    polling_method = django_filters.ChoiceFilter(
        choices=PollingMethod.choices,
        label='Метод опроса'
    )
    
    class Meta:
        model = Printer
        fields = ['organization', 'polling_method', 'is_active']
```

**В шаблоне:**
```html
<form method="get" class="mb-3">
  {{ filter.form.as_p }}
  <button type="submit" class="btn btn-primary">Применить</button>
</form>
```

---

## 6. Миграции БД

### 7.1 Добавление USB_API в PollingMethod

```python
# inventory/migrations/0XXX_add_usb_api_method.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0XXX_previous_migration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='printer',
            name='polling_method',
            field=models.CharField(
                choices=[
                    ('SNMP', 'SNMP (GLPI Agent)'),
                    ('WEB', 'Web Parsing'),
                    ('USB_API', 'USB Agent (API)')
                ],
                default='SNMP',
                max_length=10,
                verbose_name='Метод опроса'
            ),
        ),
    ]
```

### 7.2 Добавление data_source и agent_id

```python
# inventory/migrations/0XXX_add_data_source.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0XXX_add_usb_api_method'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventorytask',
            name='data_source',
            field=models.CharField(
                choices=[
                    ('SNMP_LOCAL', 'SNMP (локальный GLPI)'),
                    ('WEB_SCRAPING', 'Web Parsing'),
                    ('USB_AGENT', 'USB Agent API')
                ],
                default='SNMP_LOCAL',
                max_length=20,
                verbose_name='Источник данных'
            ),
        ),
        migrations.AddField(
            model_name='inventorytask',
            name='agent_id',
            field=models.CharField(
                max_length=100,
                blank=True,
                default='',
                verbose_name='ID агента'
            ),
        ),
        migrations.AddIndex(
            model_name='inventorytask',
            index=models.Index(fields=['data_source'], name='inv_task_data_source_idx'),
        ),
    ]
```

### 6.3 Создание таблицы USBAgent

```python
# inventory/migrations/0XXX_create_usb_agent.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0XXX_add_data_source'),
    ]

    operations = [
        migrations.CreateModel(
            name='USBAgent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('agent_id', models.CharField(db_index=True, max_length=100, unique=True, verbose_name='ID агента')),
                ('token', models.CharField(db_index=True, max_length=64, unique=True, verbose_name='Токен доступа')),
                ('hostname', models.CharField(blank=True, max_length=200, verbose_name='Имя компьютера')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')),
                ('last_seen', models.DateTimeField(auto_now=True, verbose_name='Последняя активность')),
            ],
            options={
                'verbose_name': 'USB-агент',
                'verbose_name_plural': 'USB-агенты',
                'ordering': ['-last_seen'],
            },
        ),
    ]
```

---

## 7. Roadmap реализации

### Фаза 1: Backend API (3-5 дней)
- [ ] Добавить `PollingMethod.USB_API`
- [ ] Добавить `DataSource` в `InventoryTask` + поле `agent_id`
- [ ] Создать модель `USBAgent`
- [ ] Создать serializers (`USBReadingSerializer`, `CountersSerializer`)
- [ ] Реализовать `process_usb_reading()` с привязкой через `ContractDevice`
- [ ] Создать API endpoints:
  - `POST /api/v1/inventory/usb-agents/register/`
  - `POST /api/v1/inventory/usb-readings/`
- [ ] Добавить `USBAgentTokenAuthentication`
- [ ] Unit-тесты

### Фаза 2: Агент (C#) (5-7 дней)
- [ ] Обновить XML-структуру (добавить `<Counters>`)
- [ ] Реализовать чтение счетчиков по форматам из реестра/драйвера
- [ ] HTTP-клиент с self-registration
- [ ] Offline queue (fallback на локальные JSON)
- [ ] Обработка ошибок и retry-логика
- [ ] Логирование
- [ ] Настройка планировщика задач Windows

### Фаза 3: UI (2-3 дня)
- [ ] Бейджи "USB" в списке принтеров (`/inventory/`)
- [ ] Отображение hostname агента в колонке IP
- [ ] Отображение `agent_id` в истории опросов
- [ ] Фильтр по методу опроса
- [ ] Добавить `data_source` в `MonthlyReport`
- [ ] Показывать `usb-auto` вместо `ip-auto` для USB-принтеров

### Фаза 4: Production (2-3 дня)
- [ ] Rate limiting (100 req/hour)
- [ ] Мониторинг (Prometheus metrics)
- [ ] Алерты (нет данных > 2 часов, процент ошибок > 10%)
- [ ] Документация API
- [ ] Инструкция по установке агента

**Общая оценка:** 12-18 дней

---

## 8. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Агент не может достучаться до API (firewall) | Высокая | Средняя | Fallback на локальные JSON, batch-загрузка при восстановлении связи |
| Дубликаты данных (агент отправил дважды) | Средняя | Низкая | Проверка (serial + timestamp), дедупликация в `process_usb_reading()` |
| Неверные счетчики (баг в реестре Windows) | Средняя | Высокая | Валидация через `validate_against_history()`, защита от Kyocera bug |
| Токен скомпрометирован | Низкая | Высокая | Rate limiting, возможность отключить агента (`is_active=False`), ротация токенов |
| Принтер не найден в ContractDevice | Средняя | Средняя | Возврат ошибки с инструкцией добавить в `/contracts/` |
| Драйвер не предоставляет счетчики по форматам | Высокая | Низкая | Отправлять только `total_pages`, остальные поля опциональны |
| Изменение схемы БД ломает SNMP/Web | Низкая | Критическая | Тщательное тестирование миграций, backward compatibility |

---

## 10. Приложение: Примеры данных

### 10.1 XML от агента (полный формат)

```xml
<?xml version="1.0" encoding="utf-8"?>
<PrinterReading>
  <Timestamp>2026-05-05T13:00:00</Timestamp>
  <PrinterName>HP LaserJet Pro M404dn</PrinterName>
  <Model>HP LaserJet Pro M404dn PCL 6</Model>
  <SerialNumber source="device">CNBXK12345</SerialNumber>
  <Counters>
    <TotalPages>12450</TotalPages>
    <BwA4>10200</BwA4>
    <ColorA4>1800</ColorA4>
    <BwA3>350</BwA3>
    <ColorA3>100</ColorA3>
  </Counters>
  <ConnectionVerified>true</ConnectionVerified>
  <DeviceInstanceId>USB\VID_03F0&amp;PID_042A\CNBXK12345</DeviceInstanceId>
</PrinterReading>
```

### 10.2 JSON payload к API

```json
{
  "agent_id": "WIN-OFFICE-01",
  "agent_version": "1.0.0",
  "readings": [
    {
      "timestamp": "2026-05-05T13:00:00Z",
      "printer_name": "HP LaserJet Pro M404dn",
      "model": "HP LaserJet Pro M404dn PCL 6",
      "serial_number": {
        "source": "device",
        "value": "CNBXK12345"
      },
      "counters": {
        "total_pages": 12450,
        "bw_a4": 10200,
        "color_a4": 1800,
        "bw_a3": 350,
        "color_a3": 100
      },
      "connection_verified": true,
      "device_instance_id": "USB\\VID_03F0&PID_042A\\CNBXK12345"
    }
  ]
}
```

### 10.3 Response от API (успех)

```json
{
  "processed": 1,
  "results": [
    {
      "serial_number": "CNBXK12345",
      "status": "success",
      "task_id": 12345,
      "printer_id": 67
    }
  ]
}
```

### 10.4 Response от API (ошибка)

```json
{
  "processed": 1,
  "results": [
    {
      "serial_number": "CNBXK12345",
      "status": "error",
      "message": "Принтер с S/N CNBXK12345 не найден в договорах. Добавьте в /contracts/ сначала."
    }
  ]
}
```

### 10.5 Response от API (валидация отклонена)

```json
{
  "processed": 1,
  "results": [
    {
      "serial_number": "CNBXK12345",
      "status": "rejected",
      "reason": "Counter decreased by 15% (12450 → 10583). Possible Kyocera bug or manual reset."
    }
  ]
}
```

---

## Итоговая архитектура

```
┌─────────────────┐
│  Windows PC     │
│  ┌───────────┐  │
│  │ USB Agent │  │──┐
│  │ (C#)      │  │  │
│  └───────────┘  │  │
│       │         │  │
│   USB cable     │  │
│       │         │  │
│  ┌───────────┐  │  │
│  │  Printer  │  │  │
│  └───────────┘  │  │
└─────────────────┘  │
                     │ HTTPS (Bearer token)
                     │ POST /api/v1/inventory/usb-readings/
                     ▼
            ┌─────────────────┐
            │  Django Server  │
            │  ┌───────────┐  │
            │  │ API View  │  │
            │  └─────┬─────┘  │
            │        │        │
            │  ┌─────▼──────────────────┐
            │  │ process_usb_reading()  │
            │  │ 1. Find ContractDevice │
            │  │ 2. Create/Update       │
            │  │    Printer             │
            │  │ 3. Validate counters   │
            │  │ 4. Create InventoryTask│
            │  │ 5. Create PageCounter  │
            │  │ 6. WebSocket notify    │
            │  └────────────────────────┘
            │        │
            │  ┌─────▼─────┐
            │  │ PostgreSQL│
            │  └───────────┘
            └─────────────────┘
```

**Ключевые моменты:**
1. Агент регистрируется при первом запуске (self-registration)
2. Принтер должен быть в `ContractDevice` (по серийнику)
3. Счетчики валидируются через `validate_against_history()`
4. Данные сохраняются как обычный `InventoryTask` + `PageCounter`
5. Агент проверяет команды с сервера каждые 5 минут
6. Fallback на локальные JSON при недоступности API

### 6.1 Добавление data_source

```python
# inventory/migrations/0XXX_add_data_source.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0XXX_previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventorytask',
            name='data_source',
            field=models.CharField(
                choices=[
                    ('SNMP_LOCAL', 'SNMP (локальный GLPI)'),
                    ('WEB_SCRAPING', 'Web Parsing'),
                    ('USB_AGENT', 'USB Agent API')
                ],
                default='SNMP_LOCAL',
                max_length=20,
                verbose_name='Источник данных'
            ),
        ),
        migrations.AddIndex(
            model_name='inventorytask',
            index=models.Index(fields=['data_source'], name='inv_task_data_source_idx'),
        ),
    ]
```

### 6.2 Изменение ip_address (опционально)

```python
# inventory/migrations/0XXX_allow_usb_identifiers.py
from django.db import migrations, models
from django.core.validators import RegexValidator

def validate_ip_or_usb(value):
    import re
    if re.match(r'^usb-[A-Z0-9]+$', value):
        return
    # Стандартная валидация IP
    from django.core.validators import validate_ipv4_address
    validate_ipv4_address(value)

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0XXX_add_data_source'),
    ]

    operations = [
        migrations.AlterField(
            model_name='printer',
            name='ip_address',
            field=models.CharField(
                max_length=50,
                db_index=True,
                validators=[validate_ip_or_usb],
                verbose_name='IP-адрес или USB ID'
            ),
        ),
    ]
```

---

## 7. Тестирование

### 7.1 Unit-тесты

```python
# inventory/tests/test_usb_api.py
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User

class USBAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('agent')
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
    
    def test_upload_valid_reading(self):
        payload = {
            'agent_id': 'TEST-001',
            'agent_version': '1.0.0',
            'readings': [{
                'timestamp': '2026-05-05T13:00:00Z',
                'printer_name': 'Test Printer',
                'model': 'HP Test',
                'serial_number': {'source': 'device', 'value': 'TEST123'},
                'page_count': 1000,
                'connection_verified': True,
                'device_instance_id': 'USB\\TEST'
            }]
        }
        
        response = self.client.post('/api/v1/inventory/usb-readings/', payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['processed'], 1)
    
    def test_reject_old_timestamp(self):
        # Timestamp старше 1 часа
        payload = {
            'agent_id': 'TEST-001',
            'agent_version': '1.0.0',
            'readings': [{
                'timestamp': '2026-05-05T10:00:00Z',  # 3 часа назад
                'serial_number': {'source': 'device', 'value': 'TEST123'},
                'page_count': 1000,
                # ...
            }]
        }
        
        response = self.client.post('/api/v1/inventory/usb-readings/', payload, format='json')
        self.assertEqual(response.data['results'][0]['status'], 'error')
```

### 7.2 Интеграционные тесты

```bash
# Тест с реальным агентом
curl -X POST https://inventory.example.com/api/v1/inventory/usb-readings/ \
  -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" \
  -H "Content-Type: application/json" \
  -d @test_reading.json
```

---

## 8. Мониторинг и логирование

### 8.1 Логи агента

```python
# inventory/models.py
class USBAgentLog(models.Model):
    agent_id = models.CharField(max_length=100, db_index=True)
    agent_version = models.CharField(max_length=20)
    request_timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    readings_count = models.IntegerField()
    success_count = models.IntegerField()
    error_count = models.IntegerField()
    ip_address = models.GenericIPAddressField()  # IP агента
    user_agent = models.CharField(max_length=200)
```

### 8.2 Метрики

**Prometheus-метрики:**
```python
from prometheus_client import Counter, Histogram

usb_readings_total = Counter('usb_readings_total', 'Total USB readings received', ['status'])
usb_processing_time = Histogram('usb_processing_seconds', 'Time to process USB reading')

# В view
with usb_processing_time.time():
    result = process_usb_reading(...)
    usb_readings_total.labels(status=result['status']).inc()
```

### 8.3 Алерты

**Grafana/Alertmanager:**
- Нет данных от агента > 2 часов
- Процент ошибок > 10%
- Рост rejected readings

---

## 9. Документация

### 9.1 API Reference

```markdown
# USB Agent API

## POST /api/v1/inventory/usb-readings/

Загрузка данных опроса USB-принтеров.

**Authentication:** Token

**Request:**
```json
{
  "agent_id": "string",
  "agent_version": "string",
  "readings": [...]
}
```

**Response 200:**
```json
{
  "processed": 1,
  "results": [
    {
      "serial_number": "CNBXK12345",
      "status": "success",
      "task_id": 12345,
      "printer_id": 67
    }
  ]
}
```

**Errors:**
- 400: Invalid data
- 401: Missing/invalid token
- 429: Rate limit exceeded
```

### 9.2 Инструкция для агента

```markdown
# Настройка PrinterCollector

1. Скачать агент: https://releases.example.com/PrinterCollector-1.0.0.zip
2. Распаковать в `C:\PrinterCollector`
3. Создать `settings.json`:
   ```json
   {
     "ApiEndpoint": "https://inventory.example.com/api/v1/inventory/usb-readings/",
     "ApiToken": "YOUR_TOKEN_HERE",
     "AgentId": "WIN-PC-001"
   }
   ```
4. Запустить GUI, выбрать принтер
5. Настроить планировщик задач:
   ```
   Программа: C:\PrinterCollector\PrinterCollector.exe
   Аргументы: --headless
   Расписание: Каждый час
   ```
```

---

## 10. Roadmap

### Фаза 1: MVP (1-2 недели)
- [ ] Добавить `data_source` в InventoryTask
- [ ] Создать API endpoint + serializers
- [ ] Реализовать `process_usb_reading()`
- [ ] Добавить Token authentication
- [ ] Unit-тесты

### Фаза 2: Агент (1 неделя)
- [ ] HTTP-клиент в C#
- [ ] Конфигурация API endpoint/token
- [ ] Fallback на локальные XML
- [ ] Offline queue

### Фаза 3: UI (3-5 дней)
- [ ] Бейджи "USB Agent" в списке принтеров
- [ ] Фильтр по методу опроса
- [ ] Отображение agent_id в карточке

### Фаза 4: Production (1 неделя)
- [ ] Rate limiting
- [ ] Мониторинг (Prometheus)
- [ ] Алерты
- [ ] Документация API
- [ ] Client certificates (опционально)

---

## 11. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Агент не может достучаться до API (firewall) | Высокая | Средняя | Fallback на локальные XML, batch-загрузка |
| Дубликаты данных (агент отправил дважды) | Средняя | Низкая | Проверка (serial + timestamp) |
| Неверные счетчики (баг в реестре Windows) | Средняя | Высокая | Валидация через `validate_against_history()` |
| Токен скомпрометирован | Низкая | Высокая | Rate limiting, ротация токенов, client certs |
| Изменение схемы БД ломает SNMP/Web | Низкая | Критическая | Тщательное тестирование миграций |

---

## 12. Вопросы для обсуждения

1. **IP-адрес для USB-принтеров:**
   - Использовать псевдо-IP `usb-<serial>` или изменить поле на CharField?
   
2. **Batch vs Immediate upload:**
   - Агент отправляет сразу после опроса или накапливает за день?
   
3. **Права доступа:**
   - Создать отдельную группу "USB Agents" или использовать существующую?
   
4. **Хранение токенов:**
   - В БД Django или в отдельном secrets manager?
   
5. **Обратная совместимость:**
   - Нужно ли поддерживать загрузку XML-файлов вручную?

---

## Приложение: Пример XML от агента

```xml
<?xml version="1.0" encoding="utf-8"?>
<PrinterReading>
  <Timestamp>2026-05-05T13:00:00</Timestamp>
  <PrinterName>HP LaserJet Pro M404dn</PrinterName>
  <Model>HP LaserJet Pro M404dn PCL 6</Model>
  <SerialNumber source="device">CNBXK12345</SerialNumber>
  <PageCount>12450</PageCount>
  <ConnectionVerified>true</ConnectionVerified>
  <DeviceInstanceId>USB\VID_03F0&amp;PID_042A\CNBXK12345</DeviceInstanceId>
</PrinterReading>
```

**Маппинг на Django-модели:**
- `SerialNumber.value` → `Printer.serial_number`
- `PageCount` → `PageCounter.total_pages`
- `Model` → `Printer.model` (или `device_model` через справочник)
- `Timestamp` → `InventoryTask.task_timestamp`
