# Quick Reference Guide - Printer Inventory Django

## What is This Project?
A Django web app for managing network printers with SNMP polling, web-based parsing, real-time updates, and compliance reporting.

## Key Statistics
- **Python Files**: ~8,000 lines of code (excluding migrations)
- **Django Apps**: 4 (inventory, contracts, access, monthly_report)
- **Database**: PostgreSQL with 9 main models
- **APIs**: 20+ REST endpoints
- **WebSockets**: Real-time inventory updates via Django Channels
- **Background Tasks**: Celery with 3 priority queues
- **Authentication**: Keycloak/OIDC with whitelist

---

## Project Structure at a Glance

| Directory | Purpose | Files |
|-----------|---------|-------|
| `printer_inventory/` | Django project config | settings.py, urls.py, asgi.py, wsgi.py |
| `inventory/` | Printer management | models (377 lines), services (611 lines), views (94 lines exported) |
| `contracts/` | Device tracking | models (10KB), views (33KB), 3 import commands |
| `access/` | Authentication | Keycloak whitelist, middleware, 4 setup commands |
| `monthly_report/` | Reporting | models (311 lines), views (49KB), sync logic |
| `templates/` | HTML UI | base.html (Alpine.js), error pages, form templates |
| `static/` | Assets | Bootstrap 5, Alpine.js, Chart.js, icons |
| `docs/` | Documentation | ERROR_HANDLING.md, CODEBASE_OVERVIEW.md (this!) |

---

## Technology Stack (TL;DR)

**Backend:**
- Django 5.2 + PostgreSQL + Redis
- Celery (async tasks) + Celery Beat (scheduler)
- Daphne (ASGI server for WebSockets)

**Authentication:**
- Keycloak 22.0 (OIDC provider)
- mozilla-django-oidc

**Frontend:**
- Alpine.js (reactive UI without build step)
- Bootstrap 5 + Bootstrap Icons
- Chart.js (graphs)

**Data Processing:**
- GLPI Agent (SNMP polling)
- Selenium (web automation)
- XPath + Regex (web parsing)
- openpyxl (Excel import/export)
- pandas (data manipulation)

---

## Key Architectural Patterns

### 1. Django Apps (Modular)
Each app is self-contained with models, views, forms, templates, admin, URLs.

### 2. Service Layer (Business Logic)
Heavy lifting in `services.py` - not in views. Example: `run_inventory_for_printer()`

### 3. Task Queue (Async Work)
Long operations via Celery tasks (polling, imports, syncs) - keeps UI responsive.

### 4. Caching (Performance)
3 Redis databases:
- DB 0: General cache (15-min TTL)
- DB 1: Sessions (7-day TTL)
- DB 2: Inventory (30-min TTL)

### 5. WebSockets (Real-time)
Django Channels + Redis → Push updates to connected clients as polls complete.

### 6. Error Handling (Production-ready)
Custom error pages + logging to files + security headers.

### 7. Authentication (Enterprise)
OIDC via Keycloak + whitelist (AllowedUser) + role-based permissions.

---

## Core Models Hierarchy

```
Organization
  ├── Printer (with IP, SNMP, organization)
  │   ├── InventoryTask (poll history)
  │   │   └── PageCounter (counters per poll)
  │   └── WebParsingRule (extraction rules)
  │       └── WebParsingTemplate (reusable configs)
  │
  └── ContractDevice (device in contracts)
      ├── DeviceModel (specs)
      │   ├── Manufacturer
      │   ├── Cartridge (consumables)
      │   └── ContractStatus (status)
      └── OneToOne → Printer (links to inventory)

MonthlyReport (synced from InventoryTask data)
```

---

## Core Workflows

### Polling Workflow
```
1. User clicks "Run Poll" OR Scheduler triggers
2. Celery task: run_inventory_task_priority() [user] or run_inventory_task() [periodic]
3. Service: run_inventory_for_printer()
   - Option A: GLPI Agent → SNMP polling → XML parsing
   - Option B: Web Parser → XPath + Regex extraction
4. Save to InventoryTask + PageCounter
5. Send WebSocket update: "Poll completed"
6. Optional: Sync to monthly_report counters
```

### Authentication Workflow
```
1. User visits /accounts/login/
2. Choose Keycloak or Django login
3. Keycloak redirects to login form
4. After auth, callback to /oidc/callback/
5. Backend checks AllowedUser whitelist
6. Create Django User if needed
7. Set session in Redis
8. Middleware auto-refreshes token before expiry
```

### Monthly Reporting Workflow
```
1. Admin imports Excel with equipment data
2. MonthlyReport rows created (with start counters)
3. Sync from inventory: fetch latest InventoryTask for each device
4. Update end counters (respecting manual edit flags)
5. Recalculate K1 (availability) and K2 (SLA)
6. Export back to Excel for billing/compliance
```

---

## Common Tasks for AI Assistants

### Add a New Feature
1. Create model in `apps/models.py`
2. Create migration: `python manage.py makemigrations`
3. Add view(s) in `apps/views.py` or `apps/views/`
4. Add template in `templates/appname/`
5. Add URL in `apps/urls.py`
6. Register in Django admin (`apps/admin.py`)
7. Add tests in `apps/tests.py`

### Add an API Endpoint
1. Create view function in `inventory/views/api_views.py`
2. Add @json_response decorator (or return JsonResponse)
3. Register URL in `inventory/urls.py`
4. Document in QUICK_REFERENCE.md

### Add a Periodic Task
1. Create `@shared_task` in `apps/tasks.py`
2. Register in `CELERY_BEAT_SCHEDULE` (settings.py)
3. Test: `python manage.py celery_monitor`
4. Logs: `logs/celery.log`

### Fix a Bug
1. Check error logs: `logs/errors.log` or `logs/django.log`
2. Identify view/service involved
3. Add print/logging for debugging
4. Run: `python manage.py runserver`
5. Write test case
6. Commit with clear message

### Optimize Performance
1. Check slow queries: `django-debug-toolbar` (add to settings)
2. Add database indexes (in model Meta.indexes)
3. Use `select_related()` / `prefetch_related()`
4. Increase cache TTL for stable data
5. Paginate large querysets

---

## Important Files to Know

**Configuration:**
- `printer_inventory/settings.py` (23KB) - All Django config
- `.env` - Secrets, hosts, credentials
- `docker-compose.yml` - Keycloak for dev

**Core Logic:**
- `inventory/services.py` (611 lines) - Polling engine
- `inventory/web_parser.py` (18KB) - Web scraping
- `monthly_report/services_inventory_sync.py` (16KB) - Sync logic

**Views (Modularized):**
- `inventory/views/printer_views.py` - CRUD operations
- `inventory/views/api_views.py` - JSON APIs
- `inventory/views/web_parser_views.py` - Web parsing UI
- `inventory/views/export_views.py` - Excel export

**Admin & Auth:**
- `printer_inventory/auth_backends.py` (13KB) - Keycloak integration
- `access/models.py` - Whitelist model
- `access/middleware.py` - App-level access control

**Async Work:**
- `inventory/tasks.py` - Celery tasks
- `monthly_report/signals.py` - Post-save hooks

**Frontend:**
- `templates/base.html` - Master layout with Alpine.js
- `static/js/vendor/alpine.min.js` - Reactive framework
- `static/css/vendor/bootstrap.min.css` - CSS framework

---

## Environment Variables (Must Haves)

```bash
# Django
SECRET_KEY=<random 50+ char string>
DEBUG=False (production)
USE_HTTPS=True (production)
ALLOWED_HOSTS=example.com,www.example.com

# Database
DB_NAME=printer_inventory
DB_USER=postgres
DB_PASSWORD=<strong password>
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=<optional>

# Keycloak
KEYCLOAK_SERVER_URL=https://keycloak.example.com
KEYCLOAK_REALM=printer-inventory
OIDC_CLIENT_ID=<from Keycloak>
OIDC_CLIENT_SECRET=<from Keycloak>
OIDC_VERIFY_SSL=True

# GLPI Agent
GLPI_PATH=/usr/bin (Linux), /Applications/GLPI-Agent/bin (Mac), etc.
HTTP_CHECK=True (enable web parsing)
POLL_INTERVAL_MINUTES=60
```

---

## Running Commands

**Development:**
```bash
python manage.py runserver 0.0.0.0:8000        # Web server
celery -A printer_inventory worker              # Async worker (sep terminal)
celery -A printer_inventory beat                # Scheduler (sep terminal)
```

**Production:**
```bash
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application
./start_workers.sh                              # Starts 3 workers + beat
```

**Database:**
```bash
python manage.py migrate                        # Apply migrations
python manage.py makemigrations                 # Create migrations
python manage.py createsuperuser                # Create admin user
```

**Utilities:**
```bash
python manage.py toggle_debug --status          # Check DEBUG
python manage.py cleanup_old_tasks              # Delete old polls
python manage.py import_flask_db                # Legacy import
python manage.py manage_whitelist --add username # Add user
```

---

## Testing

```bash
python manage.py test                           # Run all tests
python manage.py test inventory                 # App-specific
python manage.py test --verbosity=2             # Detailed output
python manage.py test inventory.tests.TestPrinterModel --keepdb
```

---

## Debugging Tips

**Enable detailed logging:**
- Set `DEBUG=True` in development
- Check `logs/django.log` for exceptions
- Check `logs/celery.log` for task failures
- Check `logs/keycloak_auth.log` for auth issues

**Test WebSockets:**
- Open browser console: `const ws = new WebSocket('ws://localhost:5000/ws/inventory/')`
- Check groups: `redis-cli SMEMBERS inventory_updates`

**Monitor Celery:**
```bash
python manage.py celery_monitor
# Or: celery -A printer_inventory inspect active
```

**Database queries:**
- Add `print(str(query.query))` before `.all()`
- Check slow queries in logs
- Use explain: `printer.objects.all().explain()`

---

## Deployment Checklist

- [ ] Set DEBUG=False
- [ ] Generate SECRET_KEY (50+ chars)
- [ ] Configure PostgreSQL (backup plan)
- [ ] Setup Redis (with password)
- [ ] Setup Keycloak realm & client
- [ ] Configure CSRF origins
- [ ] Setup SSL certificates
- [ ] Run migrations
- [ ] Collect static files
- [ ] Start Daphne + workers
- [ ] Setup reverse proxy (nginx)
- [ ] Monitor logs
- [ ] Whitelist initial users
- [ ] Test error pages (intentional 500)
- [ ] Setup backup strategy

---

## Code Style & Conventions

- **Python**: PEP 8 (4-space indent)
- **Django**: Django style guide (class-based views, ModelForms)
- **Templates**: Jinja2 with Bootstrap classes
- **Logging**: logger = logging.getLogger(__name__)
- **Comments**: Explain WHY, not what (code is self-explanatory)

---

## Performance Baselines

- Printer list page: <1s (with caching)
- Single poll: 2-5s (depends on SNMP/web response)
- Bulk import: 10s per 100 rows (Excel)
- WebSocket message: <100ms (real-time updates)
- API response: <500ms (JSON endpoints)

---

## Security Checklist

- [ ] Whitelist users in AllowedUser table
- [ ] Disable Django admin in production (not used with OIDC)
- [ ] Enable CSRF protection (enabled by default)
- [ ] Use HTTPS in production (USE_HTTPS=True)
- [ ] Rotate SECRET_KEY if leaked
- [ ] Use strong database password
- [ ] Use Redis password (optional but recommended)
- [ ] Monitor logs for suspicious activity
- [ ] Disable DEBUG in production
- [ ] Test error pages without exposing stack traces

---

## Useful Django Admin Commands

```bash
# Inspect models
python manage.py inspectdb

# Dump data
python manage.py dumpdata --indent 2 > data.json

# Load data
python manage.py loaddata data.json

# Reset migrations (DANGEROUS)
python manage.py migrate inventory zero

# Check database
python manage.py dbshell

# See installed apps
python manage.py debugsqlshell
```

---

## Where to Start (for new developers)

1. **Read** `docs/CODEBASE_OVERVIEW.md` (you are here)
2. **Setup** local environment: `.env`, migrate, create superuser
3. **Explore** inventory app: Models → Views → Templates
4. **Run** development server: `python manage.py runserver`
5. **Add** test printer via admin or UI
6. **Trigger** manual poll: See async in action
7. **Check** logs: `logs/django.log`, `logs/celery.log`
8. **Read** code: Start with `inventory/services.py` (core logic)
9. **Add** feature: Follow "Add a New Feature" section above
10. **Deploy**: Follow deployment checklist

---

## Contacts & Support

- Django Docs: https://docs.djangoproject.com/
- Celery Docs: https://docs.celeryproject.org/
- Channels: https://channels.readthedocs.io/
- Keycloak: https://www.keycloak.org/
- GLPI: https://github.com/glpi-project/glpi-agent
- PostgreSQL: https://www.postgresql.org/docs/

For codebase questions, check git commit history:
```bash
git log --oneline | head -20                    # Recent commits
git show <commit> --stat                        # What changed
git blame <file>                                # Who changed what
```

---

**Generated**: 2025-11-17
**Total Files**: 1 (QUICK_REFERENCE.md)
**Purpose**: Quick lookup for developers working on this codebase

