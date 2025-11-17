# CLAUDE.md - AI Assistant Guide for Printer Inventory Django

**Last Updated:** 2025-11-17
**Purpose:** Comprehensive guide for AI assistants working on this Django printer inventory management system

---

## Quick Project Overview

**What is this?** A Django web application for managing network printers with SNMP polling, web-based parsing, real-time updates, contract management, and compliance reporting.

**Tech Stack:** Django 5.2 + PostgreSQL + Redis + Celery + Django Channels + Keycloak/OIDC + Alpine.js + Bootstrap 5

**Size:** ~8,000 lines of Python code across 4 Django apps

---

## Critical Files & Locations

### Configuration
- `printer_inventory/settings.py` (23KB) - All Django configuration, middleware, installed apps
- `.env` - Environment variables (DATABASE, REDIS, KEYCLOAK credentials)
- `docker-compose.yml` - Keycloak setup for development

### Core Business Logic
- `inventory/services.py` (611 lines) - **PRIMARY POLLING ENGINE** - Read this first!
- `inventory/web_parser.py` (18KB) - Web scraping engine (XPath + Regex)
- `monthly_report/services_inventory_sync.py` (16KB) - Inventory sync logic
- `printer_inventory/auth_backends.py` (13KB) - Keycloak/OIDC integration

### Models (Data Schema)
- `inventory/models.py` (377 lines) - Printer, InventoryTask, PageCounter, WebParsingRule
- `contracts/models.py` (10KB) - DeviceModel, ContractDevice, Cartridge
- `monthly_report/models.py` (311 lines) - MonthlyReport
- `access/models.py` - AllowedUser (whitelist)

### Views (Modularized)
- `inventory/views/printer_views.py` - CRUD operations for printers
- `inventory/views/api_views.py` - REST API endpoints (17KB)
- `inventory/views/web_parser_views.py` - Web parsing UI (23KB)
- `inventory/views/export_views.py` - Excel export (14KB)
- `contracts/views.py` (33KB) - Contract management
- `monthly_report/views.py` (49KB) - Reporting interface

### Async Tasks
- `inventory/tasks.py` - Celery tasks for polling
- `inventory/consumers.py` - WebSocket consumer (Django Channels)
- `printer_inventory/celery.py` - Celery app configuration

### Templates & Frontend
- `templates/base.html` - Master layout with Alpine.js
- `static/js/vendor/alpine.min.js` - Reactive framework
- `static/css/vendor/bootstrap.min.css` - CSS framework

---

## Architecture Patterns

### 1. Django Apps (Modular Design)
Each app is self-contained with models, views, forms, templates, admin, URLs:
- **inventory** - Printer management & polling
- **contracts** - Device contract tracking
- **access** - Authentication & authorization
- **monthly_report** - Compliance reporting

### 2. Service Layer Pattern
**Heavy business logic lives in `services.py` files, NOT in views.**
- Views handle HTTP request/response
- Services handle business logic
- Example: `run_inventory_for_printer()` in `inventory/services.py`

### 3. Task Queue (Celery)
Long-running operations use Celery tasks:
- **3 priority queues:** high_priority, default, low_priority
- Scheduled tasks via Celery Beat
- Keeps UI responsive

### 4. Caching Strategy (Redis)
**3 Redis databases:**
- DB 0: General cache (15-min TTL)
- DB 1: Sessions (7-day TTL)
- DB 2: Inventory data (30-min TTL)

### 5. Real-time Updates (WebSockets)
- Django Channels + Redis pub/sub
- WebSocket endpoint: `/ws/inventory/`
- Pushes updates when polls complete

### 6. Error Handling
- Custom error pages (400, 403, 404, 405, 500)
- Production-ready logging to `logs/django.log` and `logs/errors.log`
- Security middleware and CSRF protection

### 7. Authentication (Enterprise OIDC)
- Keycloak as identity provider
- AllowedUser whitelist model
- Custom OIDC backend with automatic token refresh
- Group-based permissions

---

## Data Model Hierarchy

```
Organization
  ├── Printer (IP address, SNMP community, polling method)
  │   ├── InventoryTask (polling history with status)
  │   │   └── PageCounter (counters & consumables per poll)
  │   └── WebParsingRule (XPath/Regex extraction rules)
  │       └── WebParsingTemplate (reusable configurations)
  │
  └── ContractDevice (device in contract management)
      ├── DeviceModel (manufacturer, specs, type)
      │   ├── Manufacturer
      │   ├── Cartridge (consumables)
      │   └── ContractStatus
      └── OneToOne → Printer (links to inventory)

MonthlyReport (synced from InventoryTask data)
  └── Counters (start/end, manual edit flags, K1/K2 calculations)
```

---

## Core Workflows

### Polling Workflow (Most Important!)
```
1. Trigger
   - Manual: User clicks "Run Poll" button
   - Automatic: Celery Beat scheduler (every 60 mins by default)

2. Task Dispatch
   - Manual → run_inventory_task_priority() [high_priority queue]
   - Scheduled → run_inventory_task() [low_priority queue]

3. Service Execution (inventory/services.py)
   run_inventory_for_printer(printer_id)
   ├── If polling_method == SNMP:
   │   ├── Call GLPI Agent via subprocess
   │   ├── Parse XML response
   │   └── Extract counters, consumables, serial, MAC
   └── If polling_method == WEB:
       ├── Fetch printer's web interface
       ├── Apply XPath/Regex rules (WebParsingRule)
       └── Extract counters from HTML

4. Save Results
   - Create InventoryTask (status, timestamps, error messages)
   - Create PageCounter (counters, consumables, levels)
   - Link to Printer

5. Notify Clients
   - Send WebSocket message to 'inventory_updates' group
   - Real-time UI update without page refresh

6. Sync (Optional)
   - monthly_report app syncs counters if configured
```

### Authentication Workflow
```
1. User visits /accounts/login/
2. Choose Keycloak (OIDC) or Django login
3. If Keycloak:
   - Redirect to Keycloak login page
   - User authenticates
   - Callback to /oidc/callback/
   - CustomOIDCAuthenticationBackend.authenticate()
     └── Check AllowedUser.objects.filter(username=..., is_active=True)
     └── Create or update Django User
4. Set session in Redis (7-day expiry)
5. Middleware auto-refreshes token before expiry
6. Group membership determines permissions
```

### Monthly Reporting Workflow
```
1. Admin imports Excel with equipment data
2. MonthlyReport rows created (with start_* counters)
3. Sync command runs:
   - Fetch latest InventoryTask for each device
   - Update end_* counters (respecting manual_edit_* flags)
4. Calculate metrics:
   - K1 = availability percentage
   - K2 = SLA compliance
5. Export to Excel for billing/compliance
```

---

## Development Workflows

### Adding a New Feature
```bash
1. Create/modify model in apps/<app>/models.py
2. Generate migration: python manage.py makemigrations
3. Apply migration: python manage.py migrate
4. Add view in apps/<app>/views/ (or views.py)
5. Create template in templates/<app>/
6. Register URL in apps/<app>/urls.py
7. Add admin interface in apps/<app>/admin.py (optional)
8. Write tests in apps/<app>/tests.py
9. Update this CLAUDE.md if it's a significant change
```

### Adding an API Endpoint
```bash
1. Create function in inventory/views/api_views.py
2. Use @require_http_methods(['GET', 'POST']) decorator
3. Return JsonResponse() or use @json_response decorator
4. Register in inventory/urls.py
5. Document in API section below
```

### Adding a Celery Task
```bash
1. Create @shared_task in apps/<app>/tasks.py
2. Import in printer_inventory/celery.py if needed
3. For periodic: Add to CELERY_BEAT_SCHEDULE in settings.py
4. Test: python manage.py shell
   >>> from inventory.tasks import my_task
   >>> my_task.delay(args)
5. Monitor: Check logs/celery.log
```

### Fixing a Bug
```bash
1. Check logs:
   - logs/django.log (general errors)
   - logs/errors.log (production errors)
   - logs/celery.log (task failures)
   - logs/keycloak_auth.log (auth issues)

2. Reproduce in development:
   - python manage.py runserver
   - Add print() or logger.debug() statements

3. Identify root cause:
   - Check view/service involved
   - Review recent git commits: git log --oneline

4. Write test case to prevent regression

5. Fix and commit with clear message
```

### Running Tests
```bash
# All tests
python manage.py test

# Specific app
python manage.py test inventory

# Specific test class
python manage.py test inventory.tests.TestPrinterModel

# Keep database between runs (faster)
python manage.py test --keepdb

# Verbose output
python manage.py test --verbosity=2
```

---

## Common Commands

### Development
```bash
# Web server (WSGI - simple, no WebSockets)
python manage.py runserver 0.0.0.0:8000

# ASGI server (WebSockets enabled)
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application

# Celery worker (separate terminal)
celery -A printer_inventory worker --loglevel=info

# Celery beat scheduler (separate terminal)
celery -A printer_inventory beat --loglevel=info

# Or use helper script (production)
./start_workers.sh  # Starts 3 workers + beat
```

### Database
```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Database shell
python manage.py dbshell

# Django shell
python manage.py shell
```

### Utilities
```bash
# Toggle DEBUG mode
python manage.py toggle_debug --status
python manage.py toggle_debug --on
python manage.py toggle_debug --off

# Clean old polling tasks
python manage.py cleanup_old_tasks

# Import legacy Flask database
python manage.py import_flask_db path/to/db.sqlite

# Manage whitelist
python manage.py manage_whitelist --add username
python manage.py manage_whitelist --list

# Monitor Celery tasks
python manage.py celery_monitor

# Test error pages
python manage.py test_errors --test-all

# Collect static files (production)
python manage.py collectstatic --noinput
```

---

## Key Conventions & Best Practices

### Code Style
- **Python:** PEP 8 (4-space indentation)
- **Django:** Follow Django style guide
- **Line length:** 120 characters max (configured in settings)
- **Imports:** Group in order: stdlib, third-party, Django, local
- **Comments:** Explain WHY, not WHAT (code should be self-documenting)

### Django Conventions
- Use `select_related()` and `prefetch_related()` to avoid N+1 queries
- Always add `__str__()` methods to models
- Use `get_absolute_url()` for model URLs
- Prefer class-based views for CRUD, function views for APIs
- Use Django forms for validation
- Always set `verbose_name` and `verbose_name_plural` in model Meta

### Logging
```python
import logging
logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed diagnostic info")
logger.info("General informational messages")
logger.warning("Warning messages")
logger.error("Error messages")
logger.exception("Exception with traceback")  # Use in except blocks
```

### Error Handling
```python
# In services
try:
    result = risky_operation()
except SpecificException as e:
    logger.error(f"Failed to do X: {e}")
    return None, str(e)  # Return tuple (result, error)

# In views
try:
    data = service_function()
except Exception as e:
    messages.error(request, f"Operation failed: {e}")
    return redirect('some_view')
```

### Celery Tasks
```python
from celery import shared_task

@shared_task(bind=True, max_retries=3)
def my_task(self, arg):
    try:
        # Do work
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)  # Retry after 60s
```

### WebSocket Messages
```python
# Send update to group
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()
async_to_sync(channel_layer.group_send)(
    "inventory_updates",
    {
        "type": "inventory_update",
        "message": "Poll completed",
        "printer_id": printer.id,
    }
)
```

---

## API Endpoints (inventory app)

### GET /inventory/api/printers/
Returns JSON list of all printers

### GET /inventory/api/printer/<id>/
Returns JSON details for specific printer

### POST /inventory/api/run-poll/
Trigger poll for printer(s)
- Body: `{"printer_ids": [1, 2, 3]}`
- Returns: Task IDs

### GET /inventory/api/task-status/<task_id>/
Get status of Celery task

### GET /inventory/api/latest-task/<printer_id>/
Get latest InventoryTask for printer

### POST /inventory/api/web-parser/test/
Test web parsing rules
- Body: `{"url": "...", "rules": [...]}`

### GET /inventory/export/excel/
Export printers to Excel

### GET /inventory/export/amb/<org_id>/
Export AMB format for organization

---

## URL Patterns (62 total)

### Main Routes
- `/` - Home page (redirects to inventory)
- `/admin/` - Django admin (limited use, prefer OIDC)
- `/accounts/login/` - Login page
- `/accounts/logout/` - Logout
- `/oidc/` - OIDC endpoints

### Inventory Routes
- `/inventory/` - Printer list
- `/inventory/printer/<id>/` - Printer detail
- `/inventory/printer/add/` - Add printer
- `/inventory/printer/<id>/edit/` - Edit printer
- `/inventory/printer/<id>/delete/` - Delete printer
- `/inventory/run-poll/` - Bulk poll interface
- `/inventory/web-parser/` - Web parsing management
- `/inventory/api/...` - API endpoints (see above)

### Contract Routes
- `/contracts/` - Contract device list
- `/contracts/device/<id>/` - Device detail
- `/contracts/import/` - Import from Excel

### Monthly Report Routes
- `/monthly-report/` - Report list
- `/monthly-report/<id>/` - Report detail
- `/monthly-report/sync/` - Sync from inventory
- `/monthly-report/export/` - Export to Excel

### Debug Routes (DEBUG=True only)
- `/debug/errors/` - Error testing menu

---

## Environment Variables Reference

### Required
```bash
SECRET_KEY=<random-50-char-string>
DEBUG=False
DB_NAME=printer_inventory
DB_USER=postgres
DB_PASSWORD=<strong-password>
DB_HOST=localhost
DB_PORT=5432
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Authentication
```bash
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=printer-inventory
OIDC_CLIENT_ID=<from-keycloak>
OIDC_CLIENT_SECRET=<from-keycloak>
OIDC_VERIFY_SSL=True  # False for dev only
```

### Network
```bash
ALLOWED_HOSTS=localhost,127.0.0.1,example.com
CSRF_TRUSTED_ORIGINS=http://localhost:8000,https://example.com
BASE_URL=http://localhost:8000
USE_HTTPS=False  # True for production
```

### GLPI Agent
```bash
GLPI_PATH=/usr/bin  # Linux: /usr/bin, Mac: /Applications/GLPI-Agent/bin
HTTP_CHECK=True  # Enable web parsing
POLL_INTERVAL_MINUTES=60
```

### Optional
```bash
REDIS_PASSWORD=<if-set>
REDIS_DB=0
REDIS_SESSION_DB=1
REDIS_INVENTORY_DB=2
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

---

## Debugging & Troubleshooting

### Enable DEBUG Mode
```bash
python manage.py toggle_debug --on
```
**WARNING:** Never enable in production! Exposes sensitive data.

### Check Logs
```bash
# Django errors
tail -f logs/django.log

# Production errors
tail -f logs/errors.log

# Celery tasks
tail -f logs/celery.log

# Auth issues
tail -f logs/keycloak_auth.log
```

### Test WebSockets
```javascript
// Browser console
const ws = new WebSocket('ws://localhost:5000/ws/inventory/');
ws.onmessage = (e) => console.log('Received:', JSON.parse(e.data));
ws.send(JSON.stringify({type: 'test', message: 'hello'}));
```

### Check Redis
```bash
redis-cli

# Check connected channels
SMEMBERS inventory_updates

# Check cached keys
KEYS *

# Check session
KEYS "django.contrib.sessions*"
```

### Monitor Celery
```bash
# Active tasks
celery -A printer_inventory inspect active

# Registered tasks
celery -A printer_inventory inspect registered

# Stats
celery -A printer_inventory inspect stats

# Or use management command
python manage.py celery_monitor
```

### Database Queries
```python
# In Django shell
from inventory.models import Printer

# See generated SQL
print(Printer.objects.filter(is_active=True).query)

# Explain query plan
print(Printer.objects.filter(is_active=True).explain())

# Count queries
from django.db import connection
print(len(connection.queries))
```

### Common Issues

**Issue:** WebSockets not working
**Fix:** Ensure Daphne is running (not runserver), Redis is accessible, check `/ws/inventory/` path

**Issue:** Celery tasks not running
**Fix:** Ensure worker is running, check logs/celery.log, verify Redis connection

**Issue:** OIDC authentication fails
**Fix:** Check Keycloak is running, verify OIDC_CLIENT_ID/SECRET, check logs/keycloak_auth.log

**Issue:** Polling fails
**Fix:** Check GLPI_PATH is correct, verify printer IP is reachable, check firewall rules

**Issue:** Import errors after pulling
**Fix:** `pip install -r requirements.txt`, run migrations, collectstatic

---

## Security Checklist

### Development
- [ ] DEBUG=True (only in dev)
- [ ] OIDC_VERIFY_SSL=False (acceptable for local Keycloak)
- [ ] Weak SECRET_KEY (acceptable for dev)

### Production
- [ ] DEBUG=False **CRITICAL**
- [ ] Strong SECRET_KEY (50+ random chars)
- [ ] ALLOWED_HOSTS configured correctly
- [ ] CSRF_TRUSTED_ORIGINS configured
- [ ] USE_HTTPS=True
- [ ] OIDC_VERIFY_SSL=True
- [ ] Database password is strong
- [ ] Redis password set (recommended)
- [ ] Whitelist users in AllowedUser table
- [ ] Disable unnecessary Django admin access
- [ ] SSL certificates configured
- [ ] Logs directory permissions (chmod 700)
- [ ] Error pages don't expose sensitive data
- [ ] Regular backups configured

---

## Performance Optimization

### Database
```python
# Use select_related for ForeignKey
printers = Printer.objects.select_related('organization').all()

# Use prefetch_related for ManyToMany/Reverse FK
devices = ContractDevice.objects.prefetch_related('device_model__cartridges').all()

# Add database indexes
class Meta:
    indexes = [
        models.Index(fields=['created_at', 'status']),
    ]

# Use only() to limit fields
printers = Printer.objects.only('id', 'hostname', 'ip_address')

# Use defer() to exclude large fields
printers = Printer.objects.defer('notes')
```

### Caching
```python
from django.core.cache import cache

# Cache expensive queries
def get_active_printers():
    key = 'active_printers_list'
    data = cache.get(key)
    if data is None:
        data = list(Printer.objects.filter(is_active=True))
        cache.set(key, data, 60 * 15)  # 15 minutes
    return data

# Invalidate on save
from django.db.models.signals import post_save

@receiver(post_save, sender=Printer)
def invalidate_printer_cache(sender, instance, **kwargs):
    cache.delete('active_printers_list')
```

### Pagination
```python
from django.core.paginator import Paginator

def printer_list(request):
    printers = Printer.objects.all()
    paginator = Paginator(printers, 50)  # 50 per page
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'template.html', {'page': page})
```

### Celery Optimization
```python
# Use priority queues
@shared_task(queue='high_priority')
def urgent_task():
    pass

# Batch operations
@shared_task
def process_batch(item_ids):
    items = Item.objects.filter(id__in=item_ids)
    # Process in bulk
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] All tests pass: `python manage.py test`
- [ ] Migrations generated: `python manage.py makemigrations --check`
- [ ] No pending migrations: `python manage.py migrate --plan`
- [ ] Static files collected: `python manage.py collectstatic`
- [ ] Environment variables configured in .env
- [ ] SECRET_KEY rotated
- [ ] DEBUG=False verified

### Infrastructure
- [ ] PostgreSQL installed and configured
- [ ] Redis installed and configured
- [ ] Keycloak realm configured
- [ ] SSL certificates installed
- [ ] Nginx/Apache configured as reverse proxy
- [ ] Firewall rules configured
- [ ] Backup strategy in place

### Services
- [ ] Daphne running: `python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application`
- [ ] Celery workers running: `./start_workers.sh`
- [ ] Celery beat running (for scheduled tasks)
- [ ] Services configured to auto-restart (systemd)

### Post-Deployment
- [ ] Run migrations: `python manage.py migrate`
- [ ] Create superuser: `python manage.py createsuperuser`
- [ ] Whitelist initial users
- [ ] Test login flow
- [ ] Test polling (manual trigger)
- [ ] Verify WebSocket connections
- [ ] Check error pages (trigger 404, 500)
- [ ] Monitor logs for errors
- [ ] Setup log rotation
- [ ] Configure monitoring/alerting

---

## Testing Strategy

### Unit Tests
```python
from django.test import TestCase
from inventory.models import Printer

class PrinterModelTest(TestCase):
    def setUp(self):
        self.printer = Printer.objects.create(
            hostname='test-printer',
            ip_address='192.168.1.100'
        )

    def test_printer_creation(self):
        self.assertEqual(self.printer.hostname, 'test-printer')

    def test_str_method(self):
        self.assertIn('test-printer', str(self.printer))
```

### Integration Tests
```python
from django.test import Client, TestCase

class PrinterViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Create test user and login

    def test_printer_list_view(self):
        response = self.client.get('/inventory/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inventory/printer_list.html')
```

### Celery Task Tests
```python
from inventory.tasks import run_inventory_task_priority

class TaskTest(TestCase):
    def test_polling_task(self):
        printer = Printer.objects.create(...)
        result = run_inventory_task_priority.apply(args=[printer.id])
        self.assertTrue(result.successful())
```

---

## Migration Best Practices

### Creating Migrations
```bash
# Always check what will be created
python manage.py makemigrations --dry-run

# Create migration
python manage.py makemigrations

# Review migration file before applying!
cat inventory/migrations/0XXX_*.py

# Apply with plan preview
python manage.py migrate --plan

# Apply
python manage.py migrate
```

### Data Migrations
```python
# Create empty migration
python manage.py makemigrations --empty inventory

# Edit migration file
from django.db import migrations

def populate_data(apps, schema_editor):
    Printer = apps.get_model('inventory', 'Printer')
    # Populate data

def reverse_data(apps, schema_editor):
    # Reverse operation

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0XXX_previous'),
    ]

    operations = [
        migrations.RunPython(populate_data, reverse_data),
    ]
```

### Rollback
```bash
# Rollback last migration
python manage.py migrate inventory 0XXX_previous_migration

# Rollback all migrations for app
python manage.py migrate inventory zero
```

---

## Git Workflow

### Branch Strategy
- **main** - Production-ready code
- **claude/claude-md-mi2q74wa992fojfo-012g2tXZiXDou9JDBK88v3tX** - Current feature branch (develop here!)

### Commit Messages
```
# Good commit messages
Add web parsing support for HP printers
Fix: Resolve polling timeout issue (#123)
Refactor: Extract SNMP logic to service layer
Update: Increase cache TTL for inventory data

# Bad commit messages
fix bug
update
WIP
asdf
```

### Pull Request Workflow
```bash
# Ensure you're on the correct branch
git checkout claude/claude-md-mi2q74wa992fojfo-012g2tXZiXDou9JDBK88v3tX

# Make changes, commit
git add .
git commit -m "Add feature X"

# Push (CRITICAL: use -u flag for first push)
git push -u origin claude/claude-md-mi2q74wa992fojfo-012g2tXZiXDou9JDBK88v3tX

# Create PR via GitHub UI or gh CLI
gh pr create --title "Feature X" --body "Description..."
```

---

## Common AI Assistant Tasks

### Task: Add a new printer attribute
1. Add field to `Printer` model in `inventory/models.py`
2. Run `python manage.py makemigrations`
3. Review migration, then `python manage.py migrate`
4. Add field to `PrinterForm` in `inventory/forms.py`
5. Update template to display field
6. Update admin if needed
7. Write test

### Task: Add a new API endpoint
1. Add function to `inventory/views/api_views.py`
2. Add URL pattern to `inventory/urls.py`
3. Test with curl or Postman
4. Document in this file (API section)
5. Write test

### Task: Fix a polling bug
1. Check `logs/celery.log` for task failures
2. Add logging to `inventory/services.py`
3. Test with single printer: trigger manual poll
4. Fix issue
5. Verify with multiple printers
6. Update error handling if needed
7. Commit with "Fix:" prefix

### Task: Optimize slow query
1. Enable query logging in settings (DEBUG=True temporarily)
2. Identify slow queries
3. Add `select_related()` or `prefetch_related()`
4. Add database indexes if needed
5. Test performance improvement
6. Commit with "Optimize:" prefix

### Task: Add a scheduled task
1. Create task in `inventory/tasks.py`
2. Add to `CELERY_BEAT_SCHEDULE` in `settings.py`
3. Test: `celery -A printer_inventory beat --loglevel=debug`
4. Verify task runs at correct interval
5. Check logs
6. Commit

---

## Additional Resources

### Documentation
- Django: https://docs.djangoproject.com/
- Celery: https://docs.celeryproject.org/
- Django Channels: https://channels.readthedocs.io/
- Keycloak: https://www.keycloak.org/documentation
- Alpine.js: https://alpinejs.dev/
- Bootstrap 5: https://getbootstrap.com/docs/5.0/

### Project Documentation
- `/docs/CODEBASE_OVERVIEW.md` - Detailed codebase structure
- `/docs/QUICK_REFERENCE.md` - Quick reference guide
- `/docs/ERROR_HANDLING.md` - Error handling documentation
- `/README.md` - Installation and setup

### Useful Commands
```bash
# View git history
git log --oneline | head -20
git log --graph --oneline --all

# Find specific commit
git log --grep="polling"
git log --author="username"

# View file history
git log --follow -- inventory/services.py

# Blame (who changed what)
git blame inventory/services.py

# Search codebase
grep -r "function_name" .
grep -r "TODO" . --exclude-dir=venv
```

---

## Notes for AI Assistants

### When Starting a Task
1. **Read relevant files first** - Don't make assumptions
2. **Check recent commits** - Understand recent changes
3. **Review existing patterns** - Follow established conventions
4. **Plan before coding** - Break down complex tasks
5. **Ask for clarification** - If requirements are unclear

### Code Modification Guidelines
1. **ALWAYS read files before editing** - Use Read tool first
2. **Preserve existing patterns** - Don't introduce new patterns without reason
3. **Update related files** - Forms, admin, templates, tests
4. **Test changes** - Run tests before committing
5. **Document significant changes** - Update this CLAUDE.md if needed

### Common Pitfalls to Avoid
- Don't modify `migrations/` files directly (always use makemigrations)
- Don't hardcode sensitive data (use environment variables)
- Don't skip error handling (wrap risky operations in try/except)
- Don't forget to update tests when modifying code
- Don't commit with DEBUG=True
- Don't use synchronous code in Celery tasks for DB queries (use .objects.select_for_update())
- Don't forget to invalidate cache when data changes

### Best Practices
- Use descriptive variable names
- Keep functions focused (single responsibility)
- Add docstrings to complex functions
- Use type hints where helpful
- Log important operations
- Handle edge cases
- Write tests for new features
- Keep commits atomic (one logical change per commit)

---

**Last Updated:** 2025-11-17
**Maintainer:** AI Assistant
**Status:** Active Development

This document should be updated whenever significant changes are made to the codebase architecture, workflows, or conventions.
