# monthly_report/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/monthly-report/(?P<year>\d{4})/(?P<month>\d{2})/$', consumers.MonthlyReportConsumer.as_asgi()),
]
