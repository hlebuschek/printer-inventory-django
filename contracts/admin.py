from django.contrib import admin
from .models import City, Manufacturer, DeviceModel, ContractDevice, ContractStatus

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    search_fields = ["name"]

@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    search_fields = ["name"]

@admin.register(DeviceModel)
class DeviceModelAdmin(admin.ModelAdmin):
    list_display = ("manufacturer", "name", "device_type")
    list_filter = ("device_type", "manufacturer")
    search_fields = ("name", "manufacturer__name")

@admin.register(ContractStatus)
class ContractStatusAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)

@admin.register(ContractDevice)
class ContractDeviceAdmin(admin.ModelAdmin):
    list_display = ("id","organization","city","address","room_number","model","serial_number","status","printer")
    list_filter = ("organization","city","model__manufacturer","model","status")
    search_fields = ("serial_number","address","room_number","comment")
    autocomplete_fields = ("organization","city","model","printer","status")
