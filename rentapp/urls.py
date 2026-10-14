from django.urls import path
from . import views

urlpatterns = [
    # Dashboard & Auth
    path('', views.dashboard_view, name='dashboard'),
    path('register/', views.landlord_register_view, name='register'),
    path('login/', views.landlord_login_view, name='login'),
    path('logout/', views.landlord_logout_view, name='logout'),
    path('settings/profile/', views.profile_settings_view, name='profile_settings'),

    # Module 1: Flat & Room Registry
    path('rooms/', views.room_list_view, name='room_list'),
    path('rooms/add/', views.room_create_view, name='room_create'),
    path('rooms/<int:pk>/', views.room_detail_view, name='room_detail'),
    path('rooms/<int:pk>/edit/', views.room_update_view, name='room_update'),
    path('rooms/<int:pk>/delete/', views.room_delete_view, name='room_delete'),

    # Module 2: Tenant & Document Vault
    path('tenants/', views.tenant_list_view, name='tenant_list'),
    path('tenants/add/', views.tenant_create_view, name='tenant_create'),
    path('tenants/<int:pk>/', views.tenant_detail_view, name='tenant_detail'),
    path('tenants/<int:pk>/edit/', views.tenant_update_view, name='tenant_update'),
    path('tenants/<int:pk>/vacate/', views.tenant_vacate_view, name='tenant_vacate'),

    # Secure Document Vault Streaming (Protected from Unauthorized Access)
    path('documents/aadhaar/<int:tenant_id>/', views.secure_aadhaar_view, name='secure_aadhaar'),
    path('documents/agreement/<int:tenant_id>/', views.secure_agreement_view, name='secure_agreement'),

    # Module 3 & 4: Monthly Bills, Sub-meter & Ledger
    path('bills/', views.bill_list_view, name='bill_list'),
    path('bills/create/', views.bill_create_view, name='bill_create'),
    path('bills/<int:pk>/', views.bill_detail_view, name='bill_detail'),
    path('bills/<int:pk>/delete/', views.bill_delete_view, name='bill_delete'),
    path('bills/<int:pk>/toggle-status/', views.bill_toggle_status_view, name='bill_toggle_status'),
    path('bills/<int:pk>/record-payment/', views.bill_record_payment_view, name='bill_record_payment'),
    path('bills/<int:pk>/receipt-pdf/', views.bill_receipt_pdf_view, name='bill_receipt_pdf'),
    path('bills/export-csv/', views.bill_export_csv_view, name='bill_export_csv'),

    # HTMX / AJAX helper endpoints
    path('api/rooms/<int:room_id>/details/', views.get_room_bill_details, name='api_room_details'),
]
