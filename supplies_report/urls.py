from django.urls import path

from . import views

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
]
