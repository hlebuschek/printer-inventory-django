# Vue.js Frontend для Printer Inventory

## 📦 Что установлено

- **Vue 3** (v3.4.15) - Composition API
- **Pinia** (v2.1.7) - State management
- **Vite** (v5.0.11) - Build tool
- **Chart.js** (v4.4.1) + vue-chartjs (v5.3.0) - Графики

## 🏗 Структура проекта

```
frontend/
├── src/
│   ├── components/
│   │   ├── PrinterInventoryApp.vue     # Главный компонент
│   │   ├── common/
│   │   │   └── ToastContainer.vue      # Уведомления
│   │   └── printer/                    # (будущие компоненты)
│   ├── composables/
│   │   ├── useWebSocket.js             # WebSocket логика
│   │   ├── usePrinters.js              # API для принтеров
│   │   └── useToast.js                 # Уведомления
│   ├── stores/
│   │   └── printerStore.js             # Pinia store
│   ├── utils/
│   │   └── api.js                      # HTTP client
│   └── main.js                         # Entry point
├── package.json
└── README.md
```

## 🚀 Команды

### Разработка

```bash
# Установка зависимостей
npm install

# Dev режим (hot reload)
npm run dev

# Сборка для production
npm run build

# Предпросмотр production сборки
npm run preview
```

### Workflow

1. **Разработка**: Запускаете `npm run dev`, Vite dev server на порту 5173
2. **Production**: Запускаете `npm run build`, файлы появляются в `static/dist/`
3. Django автоматически подхватывает скомпилированные файлы из `static/dist/`

## 🔌 Интеграция с Django

### Тестовая страница

Чтобы проверить что Vue.js работает, перейдите на:

```
http://localhost:8000/inventory/vue-test/
```

Эта страница демонстрирует:
- ✅ Подключение Vue.js
- ✅ Реактивность (счетчик)
- ✅ WebSocket соединение
- ✅ Toast уведомления
- ✅ API запросы к Django

### Подключение в шаблоне

```django
{% extends "base.html" %}
{% load static %}

{% block content %}
<div
  id="printer-inventory-app"
  data-user-id="{{ user.id }}"
  data-permissions='{{ permissions_json|safe }}'
  data-initial-data='{}'
></div>
{% endblock %}

{% block scripts %}
{{ block.super }}
<link rel="stylesheet" href="{% static 'dist/css/main.[hash].css' %}">
<script type="module" src="{% static 'dist/js/main.[hash].js' %}"></script>
{% endblock %}
```

## 📚 Основные концепции

### 1. Pinia Store (printerStore.js)

Центральное хранилище состояния для принтеров:

```javascript
import { usePrinterStore } from '@/stores/printerStore'

const store = usePrinterStore()

// Доступ к данным
store.printers
store.loading
store.filters

// Actions
await store.fetchPrinters()
await store.runInventory(printerId)
store.updatePrinterFromWebSocket(data)
```

### 2. Composables

Переиспользуемая логика:

```javascript
// WebSocket
import { useWebSocket } from '@/composables/useWebSocket'
const { connected, send } = useWebSocket()

// Toast уведомления
import { useToast } from '@/composables/useToast'
const { showToast } = useToast()

showToast({
  title: 'Успешно',
  message: 'Операция выполнена',
  type: 'success',
  duration: 5000
})

// API для принтеров
import { usePrinters } from '@/composables/usePrinters'
const { fetchPrinters, runInventory } = usePrinters()
```

### 3. API Client (utils/api.js)

Все запросы к Django:

```javascript
import { printersApi } from '@/utils/api'

// Получить принтеры
const printers = await printersApi.getAll()

// Запустить опрос
await printersApi.runInventory(printerId)

// Обновить принтер
await printersApi.update(id, formData)
```

## 🎯 Что реализовано

- ✅ Базовая структура Vue приложения
- ✅ Pinia store для управления состоянием
- ✅ WebSocket интеграция (реактивные обновления)
- ✅ API client для Django
- ✅ Toast уведомления
- ✅ Тестовая страница

## 🔄 Следующие шаги

1. **Миграция списка принтеров** - PrinterTable.vue
2. **Миграция фильтров** - PrinterFilters.vue
3. **Миграция модальных окон** - PrinterModal.vue, HistoryModal.vue
4. **Интеграция Chart.js** - HistoryChart.vue
5. **Миграция других страниц** - contracts, monthly_report

## 🐛 Отладка

### Vue DevTools

Установите расширение [Vue DevTools](https://devtools.vuejs.org/) для Chrome/Firefox для удобной отладки:
- Просмотр состояния Pinia stores
- Инспекция компонентов
- Timeline событий
- Анализ производительности

### Console logs

- `✅ Vue.js Printer Inventory mounted successfully` - Vue инициализирован
- `✅ WebSocket connected` - WebSocket подключен
- `✅ PrinterInventoryApp mounted` - Главный компонент смонтирован

### Частые проблемы

**Проблема:** Vue не загружается
**Решение:** Проверьте что файлы скомпилированы (`npm run build`) и находятся в `static/dist/`

**Проблема:** WebSocket не подключается
**Решение:** Убедитесь что Daphne запущен (не runserver), проверьте путь `/ws/inventory/`

**Проблема:** API запросы не работают
**Решение:** Проверьте CSRF токен в `<meta name="csrf-token">`

## 📝 Соглашения по коду

- **Composition API** - используем `<script setup>`, не Options API
- **Именование**: PascalCase для компонентов, camelCase для функций
- **Импорты**: Используем alias `@/` вместо относительных путей
- **Reactivity**: Используем `ref()` и `computed()`, не `reactive()`
- **Props/Emits**: Всегда определяем типы

## 🔗 Полезные ссылки

- [Vue 3 Documentation](https://vuejs.org/)
- [Pinia Documentation](https://pinia.vuejs.org/)
- [Vite Documentation](https://vitejs.dev/)
- [Chart.js Documentation](https://www.chartjs.org/)
- [vue-chartjs Documentation](https://vue-chartjs.org/)
