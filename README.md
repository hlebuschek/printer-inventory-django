# Printer Inventory Django

This project provides a Django-based web interface for managing and polling network printers, originally migrated from a Flask service. It supports:

* **CRUD** for printers (add, edit, delete)
* **Inventory polling** via SNMP & HTTP checks
* **Multithreaded bulk polling** with APScheduler & ThreadPoolExecutor
* **Real-time UI updates** via WebSockets (Django Channels + Daphne)
* **Import** of legacy Flask SQLite data

---

## Prerequisites

* **Python 3.12+**
* **Git**
* **Virtual environment** (recommended)

Optional:

* **Daphne** for ASGI server
* **Uvicorn** (alternative ASGI server)

---

## Installation

1. **Create & activate virtualenv**

   ```bash
   python -m venv .venv
   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1
   # macOS/Linux
   source .venv/bin/activate
   ```

2. **Install dependencies**

   * **Online** (requires Internet):

     ```bash
     pip install --upgrade pip
     pip install -r requirements.txt
     ```

   * **Offline** (no Internet):

     ```bash
     # pip_packages/ must contain wheels for all requirements
     pip install --no-index --find-links=pip_packages -r requirements.txt
     ```

## Database setup

1. **Migrate**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

2. **Create superuser**

   ```bash
   python manage.py createsuperuser
   ```

---

## Running the application

### Development server (WSGI)

```bash
python manage.py runserver 0.0.0.0:8000
```

Visit `http://<host>:8000/` in your browser.

### Production-like (ASGI) with Daphne

```bash
# Use module invocation to avoid launcher issues
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application
```

Open `http://<host>:5000/`. WebSockets will be served at `/ws/inventory/`.

---

## Vue.js Frontend

The project uses **Vue.js 3** with **Vite** for modern, reactive user interfaces.

### Quick Start

```bash
# Install Node.js dependencies
npm install

# Build for production
npm run build

# Development mode with hot reload
npm run dev
```

### Development Workflow

**Option 1: Production Build (Recommended)**
```bash
# 1. Build Vue.js assets
npm run build

# 2. Run Django
python manage.py runserver

# 3. Access at http://127.0.0.1:8000/
```

**Option 2: Hot Reload Development**
```bash
# Terminal 1: Vite dev server (hot reload)
npm run dev

# Terminal 2: Django backend
python manage.py runserver

# Vite: http://localhost:5173/
# Django: http://127.0.0.1:8000/
```

### Migrated Applications

#### ✅ Monthly Report (100% complete)

All pages migrated to Vue.js:

- **MonthListPage** - month grid with filtering
- **MonthDetailPage** - detailed report table
- **UploadExcelPage** - Excel file upload
- **ChangeHistoryPage** - change history with revert

**Features:**
- Inline editing with auto-save
- Three-level permissions system
- Anomaly detection (historical + threshold)
- Floating scrollbar for better UX
- Toast notifications
- Export to Excel

**Documentation:** See [`docs/MONTHLY_REPORT_VUE.md`](docs/MONTHLY_REPORT_VUE.md)

#### ✅ Inventory (Partial)

- **PrinterListPage** - printer management
- **PrinterForm** - add/edit printers
- **WebParserPage** - web parsing rules
- **AmbExportPage** - AMB format export

#### ✅ Contracts

- **ContractDeviceListPage** - contract device management

### Tech Stack

- **Vue 3.4.15** - Composition API
- **Vite 5.0.11** - Build tool
- **Pinia 2.1.7** - State management
- **Chart.js** - Charts and graphs
- **Bootstrap 5** - UI components (global)

### File Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── monthly-report/      # Monthly report components
│   │   ├── inventory/            # Inventory components
│   │   └── contracts/            # Contract components
│   ├── composables/              # Reusable logic
│   ├── stores/                   # Pinia stores
│   ├── utils/                    # Utilities
│   └── main.js                   # Entry point
├── package.json
└── vite.config.js

static/dist/                      # Built assets (gitignored)
```

### Documentation

- **Migration Status:** [`docs/VUE_MIGRATION_COMPLETE.md`](docs/VUE_MIGRATION_COMPLETE.md)
- **Monthly Report:** [`docs/MONTHLY_REPORT_VUE.md`](docs/MONTHLY_REPORT_VUE.md)
- **Frontend Guide:** [`frontend/README.md`](frontend/README.md)

---

## Error Handling & Debugging

The project includes a comprehensive error handling system with beautiful error pages, logging, and security middleware.

### Debug Mode Management

```bash
# Check current DEBUG status
python manage.py toggle_debug --status

# Enable DEBUG mode (development)
python manage.py toggle_debug --on

# Disable DEBUG mode (production)  
python manage.py toggle_debug --off

# Test error handlers
python manage.py test_errors --test-all
```

### Testing Error Pages

**In DEBUG mode**, visit `/debug/errors/` for an interactive error testing menu.

**In PRODUCTION mode**, error handlers activate automatically:
- Custom error pages (400, 403, 404, 405, 500)
- Error logging to `logs/django.log` and `logs/errors.log`
- Security headers and CSRF protection
- User-friendly error messages

### Error Types Handled

- **400** - Bad Request
- **403** - Access Denied / CSRF Failures  
- **404** - Page Not Found
- **405** - Method Not Allowed
- **500** - Internal Server Error

See `docs/ERROR_HANDLING.md` for complete documentation.

---
---

## 📚 Документация

### Основная документация
- **[CLAUDE.md](CLAUDE.md)** - Полное руководство для AI-ассистентов по проекту
- **[CHANGELOG.md](CHANGELOG.md)** - История изменений проекта

### Технические руководства (docs/)

#### Celery и очереди задач
- **[docs/TROUBLESHOOTING_QUEUE.md](docs/TROUBLESHOOTING_QUEUE.md)** - Решение проблем с очередью Celery (НАЧНИТЕ ОТСЮДА!)
- **[docs/QUEUE_OVERFLOW_FIX.md](docs/QUEUE_OVERFLOW_FIX.md)** - Развёртывание защиты от переполнения очереди
- **[docs/QUEUE_FIX_QUICK.md](docs/QUEUE_FIX_QUICK.md)** - Быстрое решение если очередь не очищается  
- **[docs/CELERY_BEAT_FIX_DEPLOYMENT.md](docs/CELERY_BEAT_FIX_DEPLOYMENT.md)** - Исправление зависания Celery Beat
- **[docs/QUEUE_MANAGEMENT.md](docs/QUEUE_MANAGEMENT.md)** - Управление очередями Celery

#### Развёртывание и миграция
- **[docs/MONITORING_GLPI_SYNC.md](docs/MONITORING_GLPI_SYNC.md)** - Мониторинг синхронизации с GLPI
- **[docs/NPM_OFFLINE_README.md](docs/NPM_OFFLINE_README.md)** - Offline установка NPM зависимостей
- **[docs/MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md)** - Руководство по миграции
- **[docs/LOAD_TESTING.md](docs/LOAD_TESTING.md)** - Нагрузочное тестирование

#### Разработка
- **[docs/WEBPARSER_WORKFLOW.md](docs/WEBPARSER_WORKFLOW.md)** - Работа с Web Parser
- **[docs/ERROR_HANDLING.md](docs/ERROR_HANDLING.md)** - Обработка ошибок
- **[docs/VUE_MIGRATION_COMPLETE.md](docs/VUE_MIGRATION_COMPLETE.md)** - Миграция на Vue.js
- **[docs/MONTHLY_REPORT_VUE.md](docs/MONTHLY_REPORT_VUE.md)** - Vue.js компоненты отчётов

### Часто используемые команды

```bash
# Запуск Celery Workers (в корне проекта)
./start_workers.sh

# Управление Django
python manage.py runserver              # Веб-сервер
python manage.py migrate                # Миграции БД
python manage.py toggle_debug --status  # Проверка DEBUG
```

---
