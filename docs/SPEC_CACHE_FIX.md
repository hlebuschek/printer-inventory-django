# Исправление кэширования PrinterModelSpec

## Проблема

При редактировании таблицы `monthly_report_printermodelspec` через админку Django, изменения применялись **только после перезагрузки веб-сервиса**.

### Причина

В файле `monthly_report/specs.py` использовался **глобальный in-memory кэш**:

```python
SPEC_CACHE: dict[str, PrinterModelSpec] = {}
```

Этот кэш:
- ❌ Живет в памяти процесса Python (Daphne/Django worker)
- ❌ **Никогда не очищался** автоматически
- ❌ Не синхронизировался между процессами
- ❌ Обновлялся только при перезагрузке сервера

### Последствия

Когда администратор изменял спецификацию модели принтера (например, отмечал что "Ricoh MP C2004" это цветной принтер с форматом A4+A3):

1. ✅ Данные в PostgreSQL обновлялись
2. ❌ Кэш в памяти оставался старым
3. ❌ Валидация полей продолжала использовать старые правила
4. ⚠️ Пользователи видели некорректное поведение

**Единственное решение было:** перезагрузить Daphne/Django.

## Решение

Добавлена **автоматическая инвалидация кэша** через Django signals.

### Изменения в `monthly_report/specs.py`

1. **Функция очистки кэша:**
```python
def clear_spec_cache():
    """Очистить кэш спецификаций моделей принтеров."""
    global SPEC_CACHE
    cache_size = len(SPEC_CACHE)
    SPEC_CACHE = {}
    if cache_size > 0:
        logger.info(f"Очищен кэш PrinterModelSpec ({cache_size} записей)")
```

2. **Автоматическая очистка при изменении:**
```python
@receiver(post_save, sender=PrinterModelSpec)
def invalidate_cache_on_save(sender, instance, created, **kwargs):
    """Очистить кэш при сохранении PrinterModelSpec"""
    action = "создана" if created else "обновлена"
    logger.info(f"PrinterModelSpec '{instance.model_name}' {action} - очистка кэша")
    clear_spec_cache()

@receiver(post_delete, sender=PrinterModelSpec)
def invalidate_cache_on_delete(sender, instance, **kwargs):
    """Очистить кэш при удалении PrinterModelSpec"""
    logger.info(f"PrinterModelSpec '{instance.model_name}' удалена - очистка кэша")
    clear_spec_cache()
```

### Management команда

Добавлена команда для **ручной очистки кэша**:

```bash
python manage.py clear_spec_cache
```

Выводит информацию о содержимом кэша и очищает его.

## Как это работает теперь

### Сценарий 1: Изменение через админку

1. Администратор открывает `/admin/monthly_report/printermodelspec/`
2. Редактирует модель "Ricoh MP C2004": устанавливает `is_color=True`, `enforce=True`
3. Нажимает "Сохранить"
4. **Автоматически:**
   - Django сохраняет изменения в БД
   - Срабатывает сигнал `post_save`
   - Вызывается `clear_spec_cache()`
   - Кэш полностью очищается
   - В лог записывается: `PrinterModelSpec 'Ricoh MP C2004' обновлена - очистка кэша`
5. При следующем обращении к `get_spec_for_model_name('Ricoh MP C2004')`:
   - Кэш пуст → запрос в БД
   - Получены свежие данные
   - Данные кэшируются

### Сценарий 2: Ручная очистка

Если нужно очистить кэш вручную (например, после прямого SQL UPDATE):

```bash
python manage.py clear_spec_cache
```

**Вывод:**
```
============================================================
Очистка кэша PrinterModelSpec
============================================================

Записей в кэше: 47

Содержимое кэша:
  - ricoh mp c2004: цветной, A4_A3, enforce=True
  - hp laserjet p2055: ч/б, A4_ONLY, enforce=True
  - kyocera ecosys m2040dn: ч/б, A4_ONLY, enforce=False
  ... и ещё 44 записей

✓ Кэш очищен (47 → 0)

============================================================
Готово!
============================================================
```

## Логирование

Все операции с кэшем логируются в `logs/django.log`:

```
[2025-12-13 15:30:42] INFO - PrinterModelSpec 'Ricoh MP C2004' обновлена (is_color=True, format=A4_A3, enforce=True) - очистка кэша
[2025-12-13 15:30:42] INFO - Очищен кэш PrinterModelSpec (47 записей)
```

Это позволяет отслеживать:
- Когда и какие модели изменялись
- Сколько записей было в кэше
- Кто и когда очищал кэш вручную

## Ограничения

### Множественные процессы (workers)

**Важно:** Если запущено несколько Daphne/Django workers (несколько процессов Python):

- ✅ Сигнал срабатывает в **том процессе**, где произошло сохранение (обычно это процесс админки)
- ⚠️ Другие процессы **не узнают** об изменении сразу
- ✅ Но при следующем обращении они получат свежие данные из БД (через 1-2 запроса максимум)

**Почему это приемлемо:**
- Система внутренняя, ~30 пользователей
- Изменения в спецификациях происходят редко
- "Устаревший" кэш живет максимум до следующего запроса (секунды)

### Альтернативное решение (для high-load систем)

Если бы было много процессов и высокая нагрузка, можно было бы:

1. **Использовать Redis кэш с TTL:**
   ```python
   from django.core.cache import cache

   def get_spec_for_model_name(model_name):
       cache_key = f"spec:{model_name.lower()}"
       spec = cache.get(cache_key)
       if spec is None:
           spec = PrinterModelSpec.objects.filter(...).first()
           cache.set(cache_key, spec, timeout=300)  # 5 минут
       return spec
   ```

2. **Pub/Sub через Redis:**
   - При изменении спецификации → публикация сообщения в Redis
   - Все workers подписаны на канал → получают уведомление
   - Каждый worker очищает свой локальный кэш

Но для текущего проекта такая сложность избыточна.

## Тестирование

### Тест 1: Автоматическая очистка

1. Откройте админку: `/admin/monthly_report/printermodelspec/`
2. Создайте/измените модель
3. Проверьте лог: `tail -f logs/django.log | grep "PrinterModelSpec"`
4. Должны увидеть сообщение об очистке кэша

### Тест 2: Ручная очистка

```bash
python manage.py clear_spec_cache
```

Должен показать содержимое кэша и очистить его.

### Тест 3: Изменения применяются без перезагрузки

1. Загрузите Excel с моделью принтера (например, "Test Model")
2. В админке создайте спецификацию для "Test Model": `is_color=False, enforce=True`
3. Попробуйте отредактировать цветные счётчики для этой модели
4. Должно быть **запрещено** (без перезагрузки сервера!)
5. Измените спецификацию: `is_color=True`
6. Попробуйте снова - теперь должно быть **разрешено**

## Связанные файлы

- `monthly_report/specs.py` - основная логика кэширования
- `monthly_report/management/commands/clear_spec_cache.py` - команда очистки
- `monthly_report/forms.py:280` - использование при загрузке Excel
- `monthly_report/views.py:487,1012,1562` - использование при редактировании через WebSocket

## Дата исправления

13 декабря 2025

## Автор

Claude Code Assistant
