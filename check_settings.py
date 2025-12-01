#!/usr/bin/env python
"""Check Django CSRF settings"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'printer_inventory.settings')
django.setup()

from django.conf import settings

print("="*80)
print("Django CSRF Settings")
print("="*80)
print(f"DEBUG: {settings.DEBUG}")
print(f"USE_HTTPS (from env): {os.getenv('USE_HTTPS', 'Not set')}")
print(f"CSRF_COOKIE_SECURE: {settings.CSRF_COOKIE_SECURE}")
print(f"CSRF_COOKIE_HTTPONLY: {settings.CSRF_COOKIE_HTTPONLY}")
print(f"SESSION_COOKIE_SECURE: {settings.SESSION_COOKIE_SECURE}")
print(f"CSRF_COOKIE_SAMESITE: {settings.CSRF_COOKIE_SAMESITE}")
print("="*80)
