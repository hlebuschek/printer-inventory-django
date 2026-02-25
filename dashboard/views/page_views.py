# dashboard/views/page_views.py
"""Страничные views для дашборда."""

import json
import logging

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from dashboard.services import get_organizations

logger = logging.getLogger(__name__)


@login_required
@permission_required('dashboard.access_dashboard_app', raise_exception=False)
def dashboard_index(request):
    organizations = get_organizations()
    return render(request, 'dashboard/index.html', {
        'organizations_json': json.dumps(organizations, ensure_ascii=False),
    })
