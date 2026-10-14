from django.contrib import admin
from .models import Room, Tenant, MonthlyBill


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'landlord', 'property_type', 'base_rent', 'current_meter_reading', 'billing_day', 'is_occupied')
    list_filter = ('property_type', 'is_occupied', 'landlord')
    search_fields = ('room_number', 'landlord__username')
    ordering = ('room_number',)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'mobile_number', 'room', 'is_active', 'move_in_date')
    list_filter = ('is_active', 'room__property_type')
    search_fields = ('full_name', 'mobile_number')


@admin.register(MonthlyBill)
class MonthlyBillAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'room', 'tenant', 'billing_month', 'total_bill', 'payment_status', 'due_date')
    list_filter = ('payment_status', 'billing_month')
    search_fields = ('receipt_number', 'room__room_number', 'tenant__full_name')
    ordering = ('-created_at',)
