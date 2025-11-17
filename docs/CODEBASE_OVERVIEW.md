# Printer Inventory Django - Comprehensive Codebase Overview

## Project Purpose
This is a Django-based web application for managing and polling network printers (originally migrated from Flask). It provides CRUD operations for printers, inventory polling via SNMP & HTTP, multithreaded bulk polling, real-time UI updates via WebSockets, and legacy data import capabilities.

**Key Features:**
- Network printer inventory management
- SNMP-based polling and device inventory via GLPI Agent
- HTTP web-parsing for printer status pages
- Real-time WebSocket updates (Django Channels)
- Excel export functionality
- Monthly reporting with counter tracking
- Keycloak/OIDC authentication with whitelist access control
- Contract management (device tracking across organizations)
- Async task processing (Celery + Redis)

---

## Directory Structure

```
printer-inventory-django/
├── printer_inventory/          # Django project settings & configuration
│   ├── settings.py             # Main Django settings (23KB)
│   ├── urls.py                 # Root URL routing
│   ├── asgi.py                 # ASGI config (WebSockets)
│   ├── wsgi.py                 # WSGI config
│   ├── celery.py               # Celery app configuration
│   ├── auth_backends.py        # Keycloak/OIDC authentication (13KB)
│   ├── auth_views.py           # Login/logout views
│   ├── middleware.py           # Security & custom middleware
│   ├── errors.py               # Error handlers (400, 403, 404, 500)
│   └── debug_views.py          # Error testing in debug mode
│
├── inventory/                  # Main inventory management app
│   ├── models.py               # 377 lines - Printer, InventoryTask, PageCounter
│   ├── views/                  # Modularized views (94 lines)
│   │   ├── __init__.py         # Exports all view functions
│   │   ├── printer_views.py    # CRUD operations (21KB)
│   │   ├── api_views.py        # REST API endpoints (17KB)
│   │   ├── export_views.py     # Excel/AMB export (14KB)
│   │   ├── web_parser_views.py # Web parsing UI (23KB)
│   │   └── report_views.py     # Reporting views
│   ├── services.py             # 611 lines - Core polling logic
│   ├── tasks.py                # Celery tasks for async polling
│   ├── web_parser.py           # XPath/Regex web parsing engine
│   ├── utils.py                # GLPI, SNMP, validation utilities
│   ├── consumers.py            # WebSocket consumer (Channels)
│   ├── routing.py              # WebSocket routing
│   ├── forms.py                # Django forms
│   ├── admin.py                # Django admin customization
│   ├── urls.py                 # App URL patterns
│   ├── management/commands/    # 8+ management commands
│   │   ├── import_flask_db.py
│   │   ├── import_inventory_xml.py
│   │   ├── cleanup_old_tasks.py
│   │   ├── toggle_debug.py
│   │   └── ... (migration & diagnostic commands)
│   ├── migrations/
│   └── templates/inventory/    # App templates
│
├── contracts/                  # Contract/Device management app
│   ├── models.py               # 10KB - DeviceModel, Cartridge, ContractDevice
│   ├── views.py                # 33KB - CBVs for contracts
│   ├── forms.py                # 11KB - Contract forms
│   ├── admin.py                # 23KB - Admin customization
│   ├── utils.py                # Excel linking utilities
│   ├── management/commands/    # 3 management commands
│   │   ├── contracts_import_xlsx.py
│   │   ├── import_cartridges_xlsx.py
│   │   └── link_devices_by_serial.py
│   ├── templatetags/           # Custom template filters
│   └── templates/contracts/
│
├── access/                     # Access control & authentication
│   ├── models.py               # AllowedUser model (whitelist)
│   ├── views.py                # Keycloak access denied, role checks
│   ├── middleware.py           # App access control middleware
│   ├── admin.py                # User whitelist admin
│   ├── management/commands/    # 4 setup commands
│   │   ├── setup_keycloak_groups.py
│   │   ├── setup_roles.py
│   │   ├── bootstrap_roles.py
│   │   └── manage_whitelist.py
│   └── templates/access/       # Access denied pages
│
├── monthly_report/             # Monthly reporting module
│   ├── models.py               # 311 lines - MonthlyReport, sync models
│   ├── models_modelspec.py     # Device model specs
│   ├── views.py                # 49KB - Report CRUD & reporting
│   ├── forms.py                # 14KB - Report forms
│   ├── services.py             # 8KB - Calculation services
│   ├── services_inventory.py   # 11KB - Inventory sync
│   ├── services_inventory_sync.py  # 16KB - Advanced sync logic
│   ├── integrations/           # Integration adapters
│   │   ├── inventory_adapter.py
│   │   ├── inventory_hooks.py
│   │   └── inventory_batch.py
│   ├── services/               # Service modules
│   │   ├── audit_service.py
│   │   └── excel_export.py
│   ├── specs.py                # Device model specifications
│   ├── signals.py              # Django signals
│   ├── admin.py                # 7KB - Report admin
│   ├── management/commands/    # 4 sync commands
│   │   ├── sync_inventory_debug.py
│   │   ├── init_monthly_report_roles.py
│   │   └── check_user_permissions.py
│   └── templates/monthly_report/
│
├── templates/                  # Global templates
│   ├── base.html               # Main layout with Alpine.js
│   ├── error.html              # Error page template
│   ├── registration/           # Login/auth templates
│   │   ├── login_choice.html
│   │   ├── django_login.html
│   │   └── keycloak_access_denied.html
│   ├── 400.html, 403.html, 404.html, 405.html, 500.html  # Error pages
│   ├── debug/                  # Debug error testing pages
│   └── partials/               # Reusable template components
│       ├── pagination.html
│       └── column_filter.html
│
├── static/                     # Frontend assets
│   ├── css/vendor/
│   │   ├── bootstrap.min.css
│   │   └── bootstrap-icons.css
│   ├── js/vendor/
│   │   ├── alpine.min.js       # Lightweight reactive UI framework
│   │   ├── alpine-*.min.js     # Alpine extensions
│   │   ├── bootstrap.bundle.min.js
│   │   └── chart.min.js        # Charting library
│   └── fonts/bootstrap-icons/
│
├── docs/
│   └── ERROR_HANDLING.md       # Error handling documentation
│
├── manage.py                   # Django management script
├── requirements.txt            # Python dependencies (23 packages)
├── daphne-requirements.txt    # ASGI server requirements
├── docker-compose.yml         # Keycloak for development
├── start_workers.sh           # Celery worker startup script
├── update_static_deps.sh      # Frontend dependencies update
├── README.md                  # Project documentation
└── .gitignore                # Git ignore patterns
```

---

## Django Apps Architecture

### 1. **inventory** - Core printer management
- **Purpose:** Manage printer assets, poll inventory, track page counters
- **Key Models:**
  - `Organization`: Groups of printers by organization
  - `Printer`: Individual printer devices with IP, SNMP community, polling method
  - `InventoryTask`: Historical polling records with status
  - `PageCounter`: Page counts and consumable levels per task
  - `WebParsingRule`: XPath/Regex rules for web-based polling
  - `WebParsingTemplate`: Reusable templates for web parsing configurations
  - `MatchRule`: Enum for matching rules (SN_MAC, MAC_ONLY, SN_ONLY)
  - `PollingMethod`: Enum (SNMP vs WEB)
  - `InventoryAccess`: Permission model for access control

- **Data Flow:**
  1. User triggers manual poll OR scheduler triggers periodic poll
  2. `run_inventory_task_priority` (high priority) or `run_inventory_task` (low priority) Celery task
  3. `run_inventory_for_printer()` service executes SNMP (GLPI) or web parsing
  4. Results saved to `InventoryTask` + `PageCounter`
  5. WebSocket updates sent to connected clients via Django Channels
  6. `monthly_report` app syncs data if configured

### 2. **contracts** - Device contract tracking
- **Purpose:** Track devices across organizations, manage cartridge compatibility
- **Key Models:**
  - `DeviceModel`: Model specifications (name, manufacturer, device_type)
  - `Manufacturer`: OEM information
  - `City`: Location reference data
  - `Cartridge`: Consumables with part numbers
  - `DeviceModelCartridge`: M2M with primary flag
  - `ContractStatus`: Status tracking (colors for UI badges)
  - `ContractDevice`: Master device record with org, location, status
  - OneToOne link to `Printer` for polling integration

- **Features:**
  - Excel import/export for bulk operations
  - Link devices to inventory printers
  - Track service start months
  - Cartridge compatibility tracking

### 3. **access** - Authentication & authorization
- **Purpose:** Control who can access the system
- **Key Models:**
  - `AllowedUser`: Keycloak whitelist (username, email, is_active)

- **Flow:**
  1. Keycloak OIDC returns user claims
  2. `CustomOIDCAuthenticationBackend` checks whitelist
  3. Middleware enforces app-level access rules
  4. Group-based permissions for reporting, inventory, contracts

### 4. **monthly_report** - Compliance & operational reporting
- **Purpose:** Track print counters, calculate SLA metrics
- **Key Models:**
  - `MonthlyReport`: Row-based monthly data (organization, equipment, counters)
  - `BulkChangeLog`: Change tracking for bulk edits
  - `CounterChangeLog`: Individual counter change history
  - Auto-sync fields from inventory with manual override flags

- **Workflow:**
  1. Import Excel with equipment data
  2. Sync counters from inventory (with manual flag protection)
  3. Calculate K1 (availability), K2 (SLA compliance)
  4. Export reports for compliance/billing

---

## Technology Stack

### Backend
- **Django 5.2.1**: Web framework
- **Python 3.12+**: Language
- **PostgreSQL**: Primary database
- **Redis**: Caching, sessions, Celery broker
- **Celery 5.3**: Async task queue
- **django-celery-beat 2.5**: Periodic task scheduler
- **django-channels 4.0**: WebSocket support
- **channels-redis 4.1**: Redis layer for channels
- **Daphne 4.0**: ASGI server

### Authentication
- **mozilla-django-oidc 4.0**: OIDC client
- **Keycloak 22.0**: Identity provider (Docker Compose provided)

### Data & Export
- **openpyxl**: Excel read/write
- **pandas**: Data manipulation
- **lxml 5.1**: XML parsing
- **psycopg[binary] 3.1**: PostgreSQL adapter

### Web Scraping & Automation
- **Selenium 4.15**: Browser automation (for complex web parsing)
- **webdriver-manager 4.0**: Chrome driver management

### Frontend
- **Alpine.js**: Lightweight reactive framework (in base.html)
- **Bootstrap 5**: CSS framework
- **Chart.js**: Data visualization
- **Bootstrap Icons**: Icon library

### DevOps & Utilities
- **whitenoise 5.3**: Static file serving in production
- **python-dotenv**: Environment configuration
- **python-dateutil 2.8**: Date utilities
- **requests 2.28**: HTTP client
- **kombu 5.3**: Message passing (Celery dependency)
- **autobahn 23.6**: WebSocket protocol support
- **pytz**: Timezone handling

---

## Configuration Structure

### Settings (printer_inventory/settings.py)

#### Environment Variables
```env
# Core
SECRET_KEY = Django secret key
DEBUG = True/False
USE_HTTPS = Enable HTTPS mode

# Database
DB_ENGINE = postgresql
DB_NAME = printer_inventory
DB_USER = postgres
DB_PASSWORD = 
DB_HOST = localhost
DB_PORT = 5432

# Redis
REDIS_HOST = localhost
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = (optional)

# Authentication
KEYCLOAK_SERVER_URL = http://localhost:8080
KEYCLOAK_REALM = printer-inventory
OIDC_CLIENT_ID = (from Keycloak)
OIDC_CLIENT_SECRET = (from Keycloak)
OIDC_VERIFY_SSL = True/False (for dev)

# Network
ALLOWED_HOSTS = localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS = http://localhost:8000
BASE_URL = http://localhost:8000

# GLPI Agent
GLPI_PATH = /usr/bin (Linux), etc.
GLPI_USER = (Linux/Mac sudo)
GLPI_USE_SUDO = False/True
HTTP_CHECK = True (enable web parsing)
POLL_INTERVAL_MINUTES = 60

# Timezone
TIME_ZONE = Asia/Irkutsk
CELERY_TIMEZONE = Asia/Irkutsk
```

#### Installed Apps
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    'channels',
    'mozilla_django_oidc',
    
    'inventory',
    'contracts',
    'access',
    'monthly_report',
]
```

#### Middleware Stack
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',        # Static files in prod
    'printer_inventory.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'mozilla_django_oidc.middleware.SessionRefresh',     # OIDC token refresh
    'access.middleware.AppAccessMiddleware',             # App-level access control
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

#### Caching (Redis)
Three separate Redis databases for isolation:
```python
CACHES = {
    'default': 60*15 timeout,           # DB 0 - General cache
    'sessions': 60*60*24*7 timeout,     # DB 1 - Session storage
    'inventory': 60*30 timeout,         # DB 2 - Inventory cache
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'
```

#### Celery Configuration
```python
CELERY_BROKER_URL = redis://localhost:6379/3
CELERY_RESULT_BACKEND = redis://localhost:6379/3
CELERY_TIMEZONE = 'Asia/Irkutsk'

# Queues (priority-based)
CELERY_TASK_QUEUES = (
    Queue('high_priority', routing_key='high'),  # User requests
    Queue('low_priority', routing_key='low'),    # Periodic tasks
    Queue('daemon', routing_key='daemon'),       # Daemon tasks
)

# Beat Schedule (periodic tasks)
CELERY_BEAT_SCHEDULE = {
    'inventory-daemon-every-hour': {...},           # Every hour
    'cleanup-old-data-daily': {...},                # Daily 03:00
}
```

#### Channels (WebSockets)
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [REDIS_CHANNEL_URL]},
    }
}
# Falls back to InMemoryChannelLayer if Redis unavailable
```

#### Logging
Rotating file handlers for:
- `logs/django.log`: General application logs
- `logs/errors.log`: Error-level logs
- `logs/celery.log`: Celery task logs
- `logs/redis.log`: Redis warnings
- `logs/keycloak_auth.log`: Authentication details

---

## Database Models & Schema

### Core Relations (Simplified ER Diagram)

```
Organization (1)
  ├── (1:N) Printer
  └── (1:N) ContractDevice

Printer (1)
  ├── (1:N) InventoryTask
  ├── (1:N) WebParsingRule
  ├── (1:N) PageCounter (via InventoryTask)
  ├── (0:1) ContractDevice
  └── (FK) DeviceModel (from contracts)

InventoryTask (1)
  └── (1:1) PageCounter

DeviceModel (1)
  ├── (N:M) Cartridge (via DeviceModelCartridge)
  └── (1:N) WebParsingTemplate

ContractDevice (1)
  ├── (FK) DeviceModel
  ├── (FK) ContractStatus
  ├── (FK) City
  └── (0:1) Printer (OneToOne)

MonthlyReport
  └── Synced from InventoryTask data monthly
```

### Key Indexes
- `Printer.ip_address` (unique)
- `Printer.serial_number` (db_index)
- `Printer.organization + ip_address` (composite)
- `InventoryTask.printer + status + timestamp` (composite)
- `MonthlyReport.month + serial_number + inventory_number` (composite)

---

## URL Routing & API Endpoints

### Inventory App (`/printers/`)
```
GET    /printers/                          → printer_list
GET    /printers/api/printers/            → api_printers (JSON)
GET    /printers/api/printer/<id>/        → api_printer detail (JSON)
GET    /printers/<id>/run/                → trigger manual poll
GET    /printers/run_all/                 → poll all printers
GET    /printers/export/                  → export Excel
GET    /printers/export-amb/              → export AMB report
POST   /printers/api/probe-serial/        → validate serial/MAC
GET    /printers/<id>/web-parser/         → web parsing setup UI
POST   /printers/api/web-parser/save-rule/ → save parsing rule
POST   /printers/api/web-parser/test-xpath/ → test XPath
GET    /printers/api/web-parser/fetch-page/ → fetch remote page
```

### Contracts App (`/contracts/`)
```
GET    /contracts/                        → list contracts
POST   /contracts/new/                    → create contract
GET    /contracts/<id>/edit/              → edit contract
POST   /contracts/api/<id>/update/        → API update
POST   /contracts/api/<id>/delete/        → API delete
GET    /contracts/export/                 → export Excel
POST   /contracts/api/lookup-by-serial/   → lookup by SN
```

### Monthly Report App (`/monthly-report/`)
```
GET    /monthly-report/                   → list reports
POST   /monthly-report/import/            → import Excel
GET    /monthly-report/<id>/edit/         → edit report
POST   /monthly-report/api/sync/          → sync from inventory
```

### Authentication (`/accounts/`)
```
GET    /accounts/login/                   → login choice (Django/Keycloak)
GET    /accounts/django-login/            → Django login form
GET    /accounts/logout/                  → logout
GET    /oidc/callback/                    → Keycloak OIDC callback
GET    /accounts/access-denied/           → access denied page
```

---

## Views & Templates Structure

### View Organization (inventory/views/)
```python
# printer_views.py (21KB)
├── printer_list(request)              # List + filter
├── add_printer(request)               # Create form
├── edit_printer(request)              # Update form
├── delete_printer(request)            # Delete with confirmation
├── run_inventory(request)             # Trigger single poll
├── run_inventory_all(request)         # Trigger all polls
└── history_view(request)              # Show poll history

# api_views.py (17KB)
├── api_printers(request)              # JSON list
├── api_printer(request)               # JSON detail
├── api_probe_serial(request)          # Validate serial/MAC
├── api_models_by_manufacturer(request) # Dropdown data
├── api_system_status(request)         # System health
└── api_status_statistics(request)     # Poll statistics

# export_views.py (14KB)
├── export_excel(request)              # Full inventory export
├── export_amb(request)                # AMB report format
└── generate_email_from_inventory(request) # Email generation

# web_parser_views.py (23KB)
├── web_parser_setup(request)          # Web parsing UI
├── save_web_parsing_rule(request)     # Save rule
├── test_xpath(request)                # Test XPath
├── fetch_page(request)                # Proxy fetch
├── execute_action(request)            # Pre-parsing actions
├── export_printer_xml(request)        # Export as XML
├── get_templates(request)             # Get templates
├── save_template(request)             # Save template
├── apply_template(request)            # Apply template to printer
└── delete_template(request)           # Delete template

# report_views.py
└── Reporting/statistics views
```

### Template Hierarchy
```
base.html (Master layout with Alpine.js)
├── inventory/printer_list.html
├── inventory/printer_form.html
├── inventory/web_parser.html
├── contracts/list.html
├── monthly_report/report_list.html
├── registration/login_choice.html
└── error.html (Error handling)
```

---

## Services & Business Logic

### inventory/services.py (611 lines)
Core polling orchestration:
```python
# GLPI-based polling
run_inventory_for_printer(printer_id, xml_path=None)
  → _get_glpi_paths() → Run glpi-netinventory/glpi-netdiscovery
  → Parse XML output → Extract device info, page counters, MAC
  → Validate against history → Save to InventoryTask/PageCounter
  → Send WebSocket update → Return success/error

# Web-based polling (fallback)
execute_web_parsing(printer) → [via web_parser.py]
  → Fetch page (with Selenium if needed)
  → Apply XPath rules
  → Extract values
  → Apply regex transformations
  → Return structured data
```

### inventory/tasks.py (Celery Tasks)
```python
@shared_task
run_inventory_task_priority(printer_id, user_id, xml_path)
  → High-priority user-triggered polls
  → Max retries: 2, Rate limit: 30/m
  → Time limit: 5 minutes

@shared_task
run_inventory_task(printer_id)
  → Low-priority periodic polls
  → Rate limit: 100/m
  → Time limit: 10 minutes

@shared_task
inventory_daemon_task()
  → Runs every hour (Beat schedule)
  → Health checks, cleanup

@shared_task
cleanup_old_inventory_data()
  → Runs daily at 03:00
  → Remove stale records
```

### monthly_report/services.py & services_inventory_sync.py
```python
# Sync counters from inventory
sync_from_inventory(month, organization)
  → Query latest InventoryTask for each device
  → Update MonthlyReport counters (respecting manual flags)
  → Recalculate totals

# Calculate metrics
calculate_k1(normative, actual_downtime)
  → K1 = ((A - D) / A) * 100%
  
calculate_k2(non_overdue, total)
  → K2 = (L / W) * 100%
```

### inventory/web_parser.py (18KB)
Advanced web scraping:
```python
execute_web_parsing(printer, rules)
  → Open browser/fetch page (Selenium/requests)
  → For each rule:
    - Extract via XPath
    - Apply regex patterns
    - Handle calculated fields (formulas)
  → Return extracted data dict

# Supports:
- Complex XPath expressions
- Regex capture groups
- Pre-parsing actions (click, wait, script injection)
- Calculated fields (formula-based)
```

---

## Authentication & Authorization

### Keycloak/OIDC Flow
```
1. User visits /accounts/login/
2. Choose "Login with Keycloak" or "Django Login"
3. Keycloak redirects to login form
4. After login, callback to /oidc/callback/
5. CustomOIDCAuthenticationBackend.verify_claims():
   - Check whitelist (AllowedUser table)
   - Verify is_active flag
   - Create Django User if needed
6. User logged in, session stored in Redis
7. SessionRefresh middleware refreshes token if expiring
```

### Permissions Model
```
# Table: access.AllowedUser (Whitelist)
- username (unique, from Keycloak)
- email
- is_active (soft disable)
- added_at, added_by

# Django Groups (created via management commands)
- Inventory Admins (run polls, export)
- Contracts Managers (edit devices, contracts)
- Report Viewers (view monthly reports)

# Object-level permissions
APP_ACCESS_RULES = {
    'inventory': 'inventory.access_inventory_app',
    'contracts': 'contracts.access_contracts_app',
}

# Feature permissions (via custom permissions)
- access_inventory_app
- run_inventory
- export_printers
- edit_counters_start / edit_counters_end
- sync_from_inventory
```

---

## WebSockets & Real-time Features

### Setup (Django Channels)
```python
# ASGI (printer_inventory/asgi.py)
application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(inventory.routing.websocket_urlpatterns)
    )
})

# Consumer (inventory/consumers.py)
class InventoryConsumer(AsyncJsonWebsocketConsumer):
    async def connect():
        → Add to 'inventory_updates' group
        → Accept connection
    
    async def disconnect():
        → Remove from group
    
    async def inventory_start(event):
        → Send to client: poll started
    
    async def inventory_update(event):
        → Send to client: poll result
```

### Client Connection
```javascript
// In template (Alpine.js)
const ws = new WebSocket('ws://localhost:5000/ws/inventory/');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Update UI with data.message, data.status
};
```

### Broadcasting Updates
```python
# From services.py after polling
channel_layer = get_channel_layer()

async_to_sync(channel_layer.group_send)('inventory_updates', {
    'type': 'inventory_update',
    'printer_id': printer.id,
    'status': 'SUCCESS',
    'message': 'Poll completed',
    'timestamp': now.isoformat(),
})
```

---

## Testing Setup

### Test Files
- `inventory/tests.py`: Inventory app tests
- `contracts/tests.py`: Contract model tests
- `access/tests.py`: Access control tests
- `monthly_report/tests.py`: Report calculation tests

### Test Patterns
- Unit tests for models and services
- View tests with authenticated requests
- Celery task tests (mocking Redis)
- Form validation tests

### Running Tests
```bash
python manage.py test                        # All tests
python manage.py test inventory              # App-specific
python manage.py test --verbosity=2          # Verbose output
python manage.py test --keepdb               # Faster (skip migrations)
```

---

## Management Commands

### Database & Setup
```bash
# Initial setup
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput

# Roles & access
python manage.py bootstrap_roles              # Create initial roles
python manage.py setup_roles                  # Setup in Keycloak
python manage.py manage_whitelist --add <username> --email <email>

# Initial data
python manage.py import_flask_db              # Legacy Flask SQLite import
python manage.py contracts_import_xlsx <file.xlsx>
python manage.py import_cartridges_xlsx <file.xlsx>
```

### Debug & Maintenance
```bash
python manage.py toggle_debug --status        # Check DEBUG mode
python manage.py toggle_debug --on
python manage.py toggle_debug --off
python manage.py test_errors --test-all       # Test error handlers

python manage.py cleanup_old_tasks            # Remove old polling records
python manage.py check_inventory_tasks        # Audit task status
python manage.py sync_printer_models          # Sync device models
python manage.py redis_management --list      # Redis stats

python manage.py celery_monitor               # Monitor Celery tasks
python manage.py diagnose_daemon              # Diagnose daemon
```

---

## Development Workflow

### Local Setup
```bash
# 1. Virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env
cp .env.example .env
# Edit with local settings

# 4. Database
python manage.py migrate
python manage.py createsuperuser

# 5. Keycloak (Docker Compose)
docker-compose up -d
# Visit http://localhost:8080/admin
# Create realm, client, configure groups

# 6. Run development server
python manage.py runserver 0.0.0.0:8000

# 7. Celery worker (separate terminal)
celery -A printer_inventory worker --loglevel=INFO

# 8. Celery Beat (separate terminal)
celery -A printer_inventory beat --loglevel=INFO
```

### Production Deployment
```bash
# Build
python manage.py collectstatic --noinput
python manage.py migrate

# Run with Daphne (ASGI)
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application

# Celery workers (use start_workers.sh)
./start_workers.sh

# Reverse proxy (nginx)
upstream asgi {
    server 127.0.0.1:5000;
}

server {
    listen 443 ssl http2;
    server_name example.com;
    
    location / {
        proxy_pass http://asgi;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /ws/ {
        proxy_pass http://asgi;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Key Configuration Files
- `.env`: Environment variables (secrets, hosts, credentials)
- `requirements.txt`: Python package versions
- `start_workers.sh`: Celery workers startup
- `docker-compose.yml`: Keycloak for development
- `settings.py`: All Django configuration

---

## API Endpoints Summary

### Core REST APIs
| Method | Endpoint | Purpose | Response |
|--------|----------|---------|----------|
| GET | `/printers/api/printers/` | List all printers | `{"printers": [...], "total": N}` |
| GET | `/printers/api/printer/1/` | Get printer details | `{...printer data...}` |
| POST | `/printers/api/probe-serial/` | Validate serial/MAC | `{"is_valid": bool, "error": str}` |
| GET | `/printers/api/system-status/` | System health | `{"redis": ok, "db": ok}` |
| POST | `/printers/api/web-parser/save-rule/` | Save parsing rule | `{"id": N, "success": bool}` |
| POST | `/contracts/api/<id>/update/` | Update contract | `{...updated data...}` |
| GET | `/monthly-report/api/sync/` | Sync from inventory | `{"synced": N, "errors": [...]}` |

### Non-REST Endpoints (Form-based)
- GET `/printers/` - HTML list with filters
- POST `/printers/add/` - Create new printer
- POST `/printers/<id>/edit/` - Update printer
- POST `/printers/<id>/delete/` - Delete printer
- GET `/printers/export/` - Download Excel file
- GET `/printers/<id>/run/` - Trigger poll (redirects)

---

## Error Handling

### Custom Error Pages
- `400.html`: Bad Request
- `403.html`: Forbidden / CSRF failures (`403_csrf.html`)
- `404.html`: Not Found
- `405.html`: Method Not Allowed
- `500.html`: Server Error
- `error.html`: Generic error template

### Error Logging
- Debug mode: Pretty HTML error pages
- Production: Custom error templates + logging to `logs/errors.log`
- CSRF failures: `logs/django.log`
- Auth failures: `logs/keycloak_auth.log`

### Testing Errors (Debug Mode)
```
GET /debug/errors/          → Error test menu
GET /debug/errors/400/      → Test 400 handler
GET /debug/errors/403/      → Test 403 handler
GET /debug/errors/404/      → Test 404 handler
GET /debug/errors/500/      → Test 500 handler
GET /debug/errors/csrf/     → CSRF form test
POST /debug/errors/csrf/submit/ → CSRF submission test
```

---

## Performance Considerations

### Caching Strategy
- **Inventory cache** (DB 2): 30-min TTL
  - Models list, organization list
  - Template suggestions
- **General cache** (DB 0): 15-min TTL
  - Statistics, status counts
- **Session cache** (DB 1): 7-day TTL
  - User sessions via Redis

### Database Optimization
- Composite indexes on frequent query patterns
- `select_related()` for ForeignKey queries
- `prefetch_related()` for reverse lookups
- Paginated list views (not all-at-once)

### Celery Optimization
- **High-priority queue**: 4 workers, immediate execution
- **Low-priority queue**: 2 workers, can be delayed
- **Daemon queue**: 1 worker, minimal concurrency
- **Max tasks per child**: 50-200 (prevents memory leaks)
- **Prefetch multiplier**: 1 (no pre-fetching, immediate ack)
- **Task acks late**: Retry on worker crash

### WebSocket Optimization
- Redis channel layer (vs in-memory)
- Group broadcasting (not individual channels)
- JSON serialization (compact)
- Automatic fallback to in-memory if Redis down

---

## File Size Summary
- `printer_inventory/settings.py`: 23KB
- `inventory/services.py`: 611 lines
- `inventory/views/web_parser_views.py`: 23KB
- `inventory/views/printer_views.py`: 21KB
- `monthly_report/views.py`: 49KB (largest)
- `contracts/views.py`: 33KB
- `contracts/admin.py`: 23KB

Total Python lines: ~8,000 (excluding migrations, vendor libs)

---

## Key Dependencies Graph
```
Django 5.2
├── Channels 4.0 (WebSockets)
├── Celery 5.3 (Async tasks)
│   └── Redis (Broker + Results)
├── OIDC (Mozilla) (Authentication)
│   └── Keycloak (Identity Provider)
├── PostgreSQL (Database)
├── WhiteNoise (Static files)
├── django-redis (Cache)
├── pandas (Data processing)
├── openpyxl (Excel)
├── Selenium (Web automation)
└── lxml (XML parsing)
```

---

## Security Features

### CSRF Protection
- `CsrfViewMiddleware` on all POST/PUT/DELETE
- Token in forms, AJAX headers
- Custom failure view: `custom_csrf_failure`
- SameSite cookie policy

### Authentication
- OIDC via Keycloak (not password-based)
- Whitelist enforcement (AllowedUser)
- Token refresh middleware
- Session timeout (7 days)

### Authorization
- View-level decorators (`@login_required`)
- Middleware app access control
- Custom permissions for features
- Group-based role checking

### SQL Injection
- ORM protects via parameterized queries
- All user input validated/sanitized

### XSS Prevention
- Template auto-escaping enabled
- CSP headers in SecurityHeadersMiddleware
- Alpine.js (no user HTML rendering)

### Sensitive Data
- No secrets in code (use `.env`)
- Passwords hashed (Django default)
- SSL/TLS in production (USE_HTTPS=True)
- Secure cookies in production

---

## Troubleshooting Guide

### Common Issues

**1. WebSocket Connection Failed**
- Check Redis is running: `redis-cli ping`
- Check Daphne is running on correct port
- Check CSRF origin in settings
- Browser dev console for connection errors

**2. Polling Tasks Not Running**
- Check Celery worker: `celery -A printer_inventory inspect active`
- Check Celery Beat: `ps aux | grep celery`
- Check Redis broker: `redis-cli keys *`
- Check task logs: `logs/celery.log`

**3. Authentication Fails**
- Check Keycloak running: `curl http://localhost:8080/`
- Verify client_id/secret in settings
- Check whitelist: `AllowedUser.objects.all()`
- Review `logs/keycloak_auth.log` for details

**4. Static Files Not Loading**
- Run `python manage.py collectstatic --noinput`
- Check WhiteNoise middleware configured
- Check STATIC_ROOT and STATIC_URL in settings
- Check permissions on `staticfiles/` directory

**5. Database Connection Error**
- Check PostgreSQL running: `psql -U postgres`
- Check credentials in `.env`
- Check DB_HOST/PORT accessible
- Run migrations: `python manage.py migrate`

---

## Deployment Checklist

- [ ] Set DEBUG=False in production
- [ ] Generate strong SECRET_KEY (>50 chars)
- [ ] Configure ALLOWED_HOSTS
- [ ] Set USE_HTTPS=True, SECURE_SSL_REDIRECT
- [ ] Configure CSRF_TRUSTED_ORIGINS for domain
- [ ] Setup Keycloak realm, client, groups
- [ ] Configure OIDC_RP_CLIENT_ID, OIDC_RP_CLIENT_SECRET
- [ ] Setup PostgreSQL with strong credentials
- [ ] Setup Redis with password (optional but recommended)
- [ ] Run `collectstatic` for all static files
- [ ] Run migrations: `manage.py migrate`
- [ ] Create superuser (backup, may not be used if OIDC only)
- [ ] Setup Daphne ASGI server
- [ ] Setup Celery workers (via start_workers.sh or systemd)
- [ ] Setup Celery Beat (hourly/daily tasks)
- [ ] Setup logging to files (logs/ directory)
- [ ] Configure reverse proxy (nginx/Apache)
- [ ] Setup SSL certificates
- [ ] Test error pages in production (DEBUG=False)
- [ ] Whitelist initial users in AllowedUser table
- [ ] Schedule regular backups (PostgreSQL, logs)

---

## Useful Resources

- Django Documentation: https://docs.djangoproject.com/
- Channels: https://channels.readthedocs.io/
- Celery: https://docs.celeryproject.org/
- Keycloak: https://www.keycloak.org/documentation
- GLPI Agent: https://github.com/glpi-project/glpi-agent
- PostgreSQL: https://www.postgresql.org/docs/
- Redis: https://redis.io/documentation

---

## Next Steps for AI Assistants

1. **Code Review**: Start with `inventory/services.py` - core polling logic
2. **Bug Fixes**: Check `logs/*.log` for errors
3. **Features**: Add to views in `inventory/views/` directory
4. **Database Changes**: Create migrations, update models
5. **Celery Tasks**: Add to `inventory/tasks.py` for async work
6. **Templates**: Modify `templates/` for UI changes
7. **Tests**: Add to `*/tests.py` files
8. **Deployment**: Follow checklist above

This codebase follows Django best practices with clean separation of concerns, comprehensive logging, and production-ready architecture.

