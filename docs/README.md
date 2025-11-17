# Printer Inventory Django - Documentation Index

This directory contains comprehensive documentation for the Printer Inventory Django codebase, designed for AI assistants and developers working on this project.

## Documentation Files

### 1. **QUICK_REFERENCE.md** (Start Here!)
**Length:** 439 lines | **Read Time:** 10-15 minutes  
**Best For:** Quick lookups, getting started, common tasks

Quick reference guide with:
- Project overview & key statistics
- Architecture patterns at a glance
- Model hierarchy diagram
- 5 common tasks (add feature, API, periodic task, fix bug, optimize)
- Command cheat sheet
- Deployment checklist
- Debugging tips

**Start Here:** If you need to get up to speed quickly

---

### 2. **CODEBASE_OVERVIEW.md** (Deep Dive)
**Length:** 1,111 lines | **Read Time:** 45-60 minutes  
**Best For:** Understanding architecture, detailed technical reference

Comprehensive technical documentation with:
- Full directory structure (400 files explained)
- Django apps architecture (inventory, contracts, access, monthly_report)
- Complete technology stack (23 dependencies)
- Configuration structure (settings, env vars, middleware, caching, Celery)
- Database models & ER diagrams
- URL routing & API endpoints
- View organization & templates
- Services & business logic
- Authentication & authorization
- WebSocket & real-time features
- Testing setup & management commands
- Development & production workflows
- Performance considerations
- Troubleshooting guide
- Deployment checklist

**Start Here:** When you need to understand how everything works together

---

### 3. **ERROR_HANDLING.md** (Reference)
**Length:** 235 lines | **Read Time:** 5-10 minutes  
**Best For:** Error handling patterns, debugging

Documentation on:
- Custom error pages (400, 403, 404, 500)
- Logging system
- Testing error handlers
- Error types & handlers

---

## Quick Navigation

### By Use Case

**I'm an AI assistant, where do I start?**
1. Read: QUICK_REFERENCE.md (15 min)
2. Skim: CODEBASE_OVERVIEW.md (15 min)
3. Explore: inventory/models.py and inventory/services.py
4. Ask questions or start implementing!

**I need to add a new feature**
1. Read: QUICK_REFERENCE.md → "Common Tasks for AI Assistants"
2. Look at: inventory/models.py (model patterns)
3. Look at: inventory/views/printer_views.py (view patterns)
4. Look at: templates/base.html (frontend patterns)
5. Follow: Step-by-step guide in QUICK_REFERENCE.md

**I need to fix a bug**
1. Check: logs/django.log or logs/celery.log
2. Read: "Debugging Tips" in QUICK_REFERENCE.md
3. Locate: The view/service involved
4. Debug: python manage.py runserver + add logging
5. Test: python manage.py test
6. Commit: With clear message

**I need to understand the authentication**
1. Read: CODEBASE_OVERVIEW.md → "Authentication & Authorization"
2. Look at: printer_inventory/auth_backends.py
3. Check: access/models.py (AllowedUser whitelist)
4. Review: access/middleware.py (app-level access)

**I need to deploy this**
1. Read: QUICK_REFERENCE.md → "Deployment Checklist"
2. Follow: 15-item checklist
3. Use: CODEBASE_OVERVIEW.md → "Production Deployment"
4. Check: ERROR_HANDLING.md for error pages in prod

**I need to understand async tasks**
1. Read: CODEBASE_OVERVIEW.md → "Services & Business Logic" → "inventory/tasks.py"
2. Look at: inventory/tasks.py (task definitions)
3. Check: printer_inventory/settings.py → "CELERY Configuration"
4. Run: python manage.py celery_monitor

**I need to understand WebSockets**
1. Read: CODEBASE_OVERVIEW.md → "WebSockets & Real-time Features"
2. Look at: inventory/consumers.py (consumer definition)
3. Look at: inventory/routing.py (WebSocket routing)
4. Check: printer_inventory/asgi.py (ASGI config)

---

## Key Concepts Quick Ref

### The Four Django Apps

1. **inventory** - Core printer management
   - Models: Printer, InventoryTask, PageCounter, WebParsingRule
   - Services: SNMP polling via GLPI, web-based parsing
   - Async: Celery tasks for polling
   - Real-time: WebSockets for poll updates

2. **contracts** - Device contract tracking
   - Models: ContractDevice, DeviceModel, Cartridge
   - Features: Excel import/export, device linking
   - Integration: Links to Printer model

3. **access** - Authentication & access control
   - Model: AllowedUser (Keycloak whitelist)
   - Auth: OIDC via Keycloak
   - Middleware: App-level access control

4. **monthly_report** - Compliance reporting
   - Model: MonthlyReport
   - Features: Counter tracking, SLA metrics (K1, K2)
   - Sync: Pulls data from inventory periodically

### Core Workflows

**Polling Workflow:**
User/Scheduler → Celery Task → Service (GLPI or Web Parser) → InventoryTask/PageCounter → WebSocket Update → Optional Sync to Monthly Report

**Authentication Workflow:**
Keycloak OIDC → Whitelist Check → Django User → Redis Session → App Access Control

**Reporting Workflow:**
Import Excel → MonthlyReport Rows → Sync from Inventory → Calculate Metrics → Export Report

### Technology Stack at a Glance

- **Framework:** Django 5.2 + Python 3.12
- **Database:** PostgreSQL
- **Cache:** Redis (sessions, caching, Celery broker)
- **Async:** Celery (task queue) + Celery Beat (scheduler)
- **Server:** Daphne (ASGI for WebSockets)
- **Auth:** Keycloak (OIDC provider)
- **Frontend:** Alpine.js + Bootstrap 5 + Chart.js
- **Polling:** GLPI Agent (SNMP) + Selenium (web automation)
- **Export:** Excel (openpyxl) + Pandas

---

## File Structure

```
docs/
├── README.md (this file)
├── QUICK_REFERENCE.md (quick lookup guide)
├── CODEBASE_OVERVIEW.md (comprehensive reference)
└── ERROR_HANDLING.md (error handling patterns)

printer_inventory/
├── settings.py (23KB - all configuration)
├── auth_backends.py (13KB - Keycloak integration)
├── middleware.py (security & access control)
├── urls.py (root URL routing)
├── asgi.py (WebSocket config)
└── celery.py (Celery configuration)

inventory/ (Core printer management - 8,000 lines)
├── models.py (377 lines)
├── services.py (611 lines - CORE LOGIC)
├── views/ (5 modularized view files)
├── tasks.py (Celery tasks)
├── web_parser.py (18KB - web scraping)
├── admin.py (20KB - admin customization)
└── management/commands/ (8 import/export commands)

contracts/ (Device contracts)
├── models.py (10KB - 8 models)
├── views.py (33KB - 15+ CBVs)
├── forms.py (11KB - 5 forms)
├── admin.py (23KB - admin UI)
└── management/commands/ (3 import commands)

access/ (Authentication)
├── models.py (AllowedUser whitelist)
├── middleware.py (app-level access)
├── views.py (access denied handlers)
└── management/commands/ (4 setup commands)

monthly_report/ (Reporting)
├── models.py (311 lines)
├── views.py (49KB - reporting UI)
├── services_inventory_sync.py (16KB - sync logic)
├── integrations/ (adapter classes)
└── management/commands/ (4 sync commands)

templates/
├── base.html (master layout with Alpine.js)
├── error.html (error handling)
├── registration/ (login templates)
└── [app specific templates]

static/
├── css/vendor/ (Bootstrap)
├── js/vendor/ (Alpine.js, Chart.js)
└── fonts/ (Bootstrap Icons)
```

---

## Most Important Files to Know

### Must Read (in order)
1. `printer_inventory/settings.py` - All configuration explained
2. `inventory/services.py` - Core polling logic
3. `inventory/models.py` - Data models
4. `printer_inventory/auth_backends.py` - Keycloak integration

### Frequently Modified
- `inventory/views/printer_views.py` - UI changes
- `inventory/services.py` - Polling logic
- `templates/` - Frontend changes
- `printer_inventory/settings.py` - Config changes

### Reference
- `inventory/utils.py` - Validation & GLPI utilities
- `monthly_report/services_inventory_sync.py` - Sync logic
- `contracts/models.py` - Device model patterns

---

## Development Workflow

### Local Setup (5 min)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
```

### Run in Development (3 terminals)
```bash
# Terminal 1: Web server
python manage.py runserver 0.0.0.0:8000

# Terminal 2: Celery worker
celery -A printer_inventory worker --loglevel=INFO

# Terminal 3: Celery Beat (scheduler)
celery -A printer_inventory beat --loglevel=INFO
```

### Common Commands
```bash
# Testing
python manage.py test
python manage.py test inventory --verbosity=2

# Database
python manage.py migrate
python manage.py makemigrations

# Debugging
python manage.py toggle_debug --on
python manage.py test_errors --test-all

# Utilities
python manage.py cleanup_old_tasks
python manage.py manage_whitelist --add username
```

### Production (1 command per service)
```bash
# Web server
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application

# Workers
./start_workers.sh

# With reverse proxy (nginx/Apache)
# → proxy to 0.0.0.0:5000
```

---

## Getting Help

### Logs to Check
- `logs/django.log` - Django errors & info
- `logs/errors.log` - Error-level only
- `logs/celery.log` - Celery task logs
- `logs/keycloak_auth.log` - Auth debugging
- `logs/redis.log` - Redis warnings

### Debug Commands
```bash
# Check system health
python manage.py api/system-status/

# Monitor Celery
python manage.py celery_monitor

# Diagnose daemon
python manage.py diagnose_daemon

# Redis stats
redis-cli info
redis-cli SMEMBERS inventory_updates (WebSocket groups)
```

### Git History
```bash
git log --oneline | head -20
git show <commit> --stat
git blame <file>
```

---

## Checklists

### Pre-Commit Checklist
- [ ] Tests pass: `python manage.py test`
- [ ] No errors in logs
- [ ] Code follows PEP 8
- [ ] Added docstrings
- [ ] Updated models/migrations
- [ ] Updated docs if feature changed

### Deployment Checklist
- [ ] DEBUG = False
- [ ] SECRET_KEY generated (50+ chars)
- [ ] PostgreSQL configured
- [ ] Redis with password
- [ ] Keycloak realm/client setup
- [ ] CSRF origins configured
- [ ] SSL certificates installed
- [ ] Migrations run
- [ ] Static files collected
- [ ] Daphne + workers running
- [ ] Reverse proxy configured
- [ ] Logs directory exists with correct permissions
- [ ] Initial users whitelisted
- [ ] Error pages tested
- [ ] Backups configured

---

## Resources

### Official Documentation
- Django: https://docs.djangoproject.com/
- Celery: https://docs.celeryproject.org/
- Channels: https://channels.readthedocs.io/
- Keycloak: https://www.keycloak.org/documentation
- PostgreSQL: https://www.postgresql.org/docs/
- Redis: https://redis.io/documentation
- GLPI: https://github.com/glpi-project/glpi-agent

### Project Documentation
- See ERROR_HANDLING.md for error handling
- See CODEBASE_OVERVIEW.md for deep technical details
- See QUICK_REFERENCE.md for quick answers
- Check git history: `git log --oneline`

---

## About This Documentation

**Created:** 2025-11-17  
**Total Lines:** 1,785 (across 3 files)  
**Coverage:** Complete codebase structure, architecture, technology stack  
**Target Audience:** AI assistants, new developers, maintainers  
**Purpose:** Comprehensive onboarding & reference for codebase work

### File Sizes
- QUICK_REFERENCE.md: 439 lines (13 KB)
- CODEBASE_OVERVIEW.md: 1,111 lines (37 KB)
- ERROR_HANDLING.md: 235 lines (8.5 KB)
- README.md: This file

---

## Version Control

```
Current Branch: claude/...
Main Branch: (use for PRs)
Commits: 25+ recent (Merge PR, fix, web_parser, sync, etc)
```

---

## Questions?

If you have questions while working on this codebase:

1. **Code question?** Check the relevant file and read comments
2. **Architecture question?** See CODEBASE_OVERVIEW.md
3. **How do I...?** Check QUICK_REFERENCE.md
4. **Error?** Check logs/ directory and ERROR_HANDLING.md
5. **Still stuck?** Review the file structure and trace the flow

---

**Happy coding! The documentation is your friend.**

