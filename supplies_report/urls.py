from django.urls import path

from . import views, api_views_drf

app_name = "supplies_report"

urlpatterns = [
    # Pages
    path("", views.list_page, name="list"),
    path("<int:group_id>/", views.detail_page, name="detail"),
    path("<int:group_id>/download.eml", views.download_eml, name="download_eml"),
    # API
    path("api/groups/", views.api_groups_list, name="api_groups_list"),
    path("api/groups/<int:group_id>/", views.api_group_detail, name="api_group_detail"),
    path("api/groups/<int:group_id>/update/", views.api_group_update, name="api_group_update"),
    path("api/groups/<int:group_id>/send-now/", views.api_send_now, name="api_send_now"),
    path("api/groups/<int:group_id>/items/", views.api_item_create, name="api_item_create"),
    path("api/groups/<int:group_id>/reorder/", views.api_items_reorder, name="api_items_reorder"),
    path("api/items/<int:item_id>/", views.api_item_update, name="api_item_update"),
    path("api/items/<int:item_id>/delete/", views.api_item_delete, name="api_item_delete"),
    path("api/printers/search/", views.api_printer_search, name="api_printer_search"),
    # ═══════════════════════════════════════════════════════════════
    # DRF API ENDPOINTS (для OpenAPI документации)
    # ═══════════════════════════════════════════════════════════════
    path("api/v2/groups/", api_views_drf.api_groups_list_drf, name="api_v2_groups_list"),
    path("api/v2/groups/<int:group_id>/", api_views_drf.api_group_detail_drf, name="api_v2_group_detail"),
    path(
        "api/v2/groups/<int:group_id>/update/", api_views_drf.GroupUpdateAPIView.as_view(), name="api_v2_group_update"
    ),
    path("api/v2/items/<int:item_id>/", api_views_drf.ItemUpdateAPIView.as_view(), name="api_v2_item_update"),
]
