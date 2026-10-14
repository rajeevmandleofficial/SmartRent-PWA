from decimal import Decimal
import os
import csv
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, FileResponse, Http404
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Room, Tenant, MonthlyBill, LandlordProfile
from .forms import (
    RoomForm, TenantForm, MonthlyBillForm, RecordPaymentForm,
    LandlordRegistrationForm, LandlordProfileForm
)
from .pdf_utils import render_to_pdf


# ==========================================
# 1. LANDLORD AUTHENTICATION & PROFILE
# ==========================================

def landlord_register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LandlordRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, f"Welcome to SmartRent, {user.first_name or user.username}! Aapka account successfully create ho gaya.")
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Registration me kuch error hai, please details check karein.")
    else:
        form = LandlordRegistrationForm()
    return render(request, 'auth/register.html', {'form': form})


def landlord_login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}! 🚀")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username ya password. Kripya dobara try karein.")
    else:
        form = AuthenticationForm()
    return render(request, 'auth/login.html', {'form': form})


@login_required
def landlord_logout_view(request):
    logout(request)
    messages.info(request, "Aap successfully logout ho chuke hain.")
    return redirect('login')


@login_required
def profile_settings_view(request):
    profile, _ = LandlordProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = LandlordProfileForm(request.POST, instance=profile)
        if form.is_valid():
            p = form.save()
            user = request.user
            user.first_name = form.cleaned_data.get('first_name', user.first_name)
            user.last_name = form.cleaned_data.get('last_name', user.last_name)
            user.email = form.cleaned_data.get('email', user.email)
            user.save()
            messages.success(request, "Profile settings aur UPI details successfully update ho gayi! ✨")
            return redirect('profile_settings')
    else:
        initial = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        }
        form = LandlordProfileForm(instance=profile, initial=initial)
    return render(request, 'settings/profile.html', {'form': form, 'profile': profile})


# ==========================================
# 2. DASHBOARD VIEW (TOP SUMMARY & METRICS)
# ==========================================

@login_required
def dashboard_view(request):
    user = request.user
    rooms = Room.objects.filter(landlord=user).prefetch_related('tenants')
    
    total_rooms = rooms.count()
    occupied_rooms = rooms.filter(is_occupied=True).count()
    vacant_rooms = total_rooms - occupied_rooms

    # Financial metrics
    bills = MonthlyBill.objects.filter(room__landlord=user)
    
    # Total collected this month
    collected_month = bills.filter(
        billing_month__icontains=timezone.now().strftime("%B")
    ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')

    # Total pending / balance dues across all unpaid/partial bills
    total_pending = bills.aggregate(total=Sum('balance_amount'))['total'] or Decimal('0.00')

    # Lifetime collected rent
    total_collected_lifetime = bills.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')

    # Security deposits held in trust
    total_deposits = Tenant.objects.filter(landlord=user, is_active=True).aggregate(
        total=Sum('security_deposit')
    )['total'] or Decimal('0.00')

    # Recent bills
    recent_bills = bills.select_related('room', 'tenant').order_by('-created_at')[:8]

    # Active tenants count
    active_tenants_count = Tenant.objects.filter(landlord=user, is_active=True).count()

    context = {
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'vacant_rooms': vacant_rooms,
        'collected_month': collected_month,
        'total_pending': total_pending,
        'total_collected_lifetime': total_collected_lifetime,
        'total_deposits': total_deposits,
        'current_month_str': timezone.now().strftime("%B %Y"),
        'recent_bills': recent_bills,
        'rooms': rooms,
        'active_tenants_count': active_tenants_count,
        'profile': getattr(user, 'profile', None),
    }
    return render(request, 'dashboard.html', context)


# ==========================================
# 3. MODULE 1: FLAT & ROOM REGISTRY
# ==========================================

@login_required
def room_list_view(request):
    filter_status = request.GET.get('status', 'all')
    rooms = Room.objects.filter(landlord=request.user)

    if filter_status == 'occupied':
        rooms = rooms.filter(is_occupied=True)
    elif filter_status == 'vacant':
        rooms = rooms.filter(is_occupied=False)

    return render(request, 'room_list.html', {
        'rooms': rooms,
        'filter_status': filter_status,
        'total_count': Room.objects.filter(landlord=request.user).count(),
        'occupied_count': Room.objects.filter(landlord=request.user, is_occupied=True).count(),
        'vacant_count': Room.objects.filter(landlord=request.user, is_occupied=False).count(),
    })


@login_required
def room_create_view(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.landlord = request.user
            room.save()
            messages.success(request, f"Room {room.room_number} successfully add ho gaya! 🎉")
            return redirect('room_list')
    else:
        form = RoomForm()
    return render(request, 'room_form.html', {'form': form, 'title': 'Add New Room / Flat'})


@login_required
def room_detail_view(request, pk):
    room = get_object_or_404(Room, pk=pk, landlord=request.user)
    bills = room.bills.select_related('tenant').order_by('-created_at')
    active_tenant = room.active_tenant
    return render(request, 'room_detail.html', {
        'room': room,
        'bills': bills,
        'active_tenant': active_tenant,
    })


@login_required
def room_update_view(request, pk):
    room = get_object_or_404(Room, pk=pk, landlord=request.user)
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, f"Room {room.room_number} details successfully update ho gayi! ✨")
            return redirect('room_detail', pk=room.pk)
    else:
        form = RoomForm(instance=room)
    return render(request, 'room_form.html', {'form': form, 'title': f'Edit Room {room.room_number}', 'room': room})


@login_required
def room_delete_view(request, pk):
    room = get_object_or_404(Room, pk=pk, landlord=request.user)
    if request.method == 'POST':
        room_number = room.room_number
        room.delete()
        messages.success(request, f"Room {room_number} delete kar diya gaya.")
        return redirect('room_list')
    return render(request, 'confirm_delete.html', {'object': room, 'type': 'Room'})


# ==========================================
# 4. MODULE 2: TENANT & DOCUMENT VAULT
# ==========================================

@login_required
def tenant_list_view(request):
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'active')
    
    tenants = Tenant.objects.filter(landlord=request.user).select_related('room')
    
    if status_filter == 'active':
        tenants = tenants.filter(is_active=True)
    elif status_filter == 'vacated':
        tenants = tenants.filter(is_active=False)

    if search_query:
        tenants = tenants.filter(
            Q(full_name__icontains=search_query) |
            Q(mobile_number__icontains=search_query) |
            Q(room__room_number__icontains=search_query)
        )

    return render(request, 'tenant_list.html', {
        'tenants': tenants,
        'search_query': search_query,
        'status_filter': status_filter,
    })


@login_required
def tenant_create_view(request):
    initial_room_id = request.GET.get('room')
    initial_data = {}
    if initial_room_id:
        initial_data['room'] = initial_room_id

    if request.method == 'POST':
        form = TenantForm(request.POST, request.FILES, landlord=request.user)
        if form.is_valid():
            tenant = form.save(commit=False)
            tenant.landlord = request.user
            tenant.save()
            messages.success(request, f"Tenant {tenant.full_name} onboard ho gaye! Documents Vault me secure hain. 📂")
            if tenant.room:
                return redirect('room_detail', pk=tenant.room.pk)
            return redirect('tenant_detail', pk=tenant.pk)
    else:
        form = TenantForm(initial=initial_data, landlord=request.user)
    return render(request, 'tenant_form.html', {'form': form, 'title': 'Onboard New Tenant'})


@login_required
def tenant_detail_view(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk, landlord=request.user)
    bills = tenant.bills.order_by('-created_at')
    return render(request, 'tenant_detail.html', {
        'tenant': tenant,
        'bills': bills,
    })


@login_required
def tenant_update_view(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk, landlord=request.user)
    if request.method == 'POST':
        form = TenantForm(request.POST, request.FILES, instance=tenant, landlord=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"{tenant.full_name} ki details update ho gayi.")
            return redirect('tenant_detail', pk=tenant.pk)
    else:
        form = TenantForm(instance=tenant, landlord=request.user)
    return render(request, 'tenant_form.html', {'form': form, 'title': f'Edit Tenant {tenant.full_name}', 'tenant': tenant})


@login_required
def tenant_vacate_view(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk, landlord=request.user)
    if request.method == 'POST':
        tenant.is_active = False
        tenant.move_out_date = timezone.now().date()
        old_room = tenant.room
        tenant.room = None  # Free the room
        tenant.save()
        if old_room:
            old_room.sync_occupancy_status()
        messages.success(request, f"{tenant.full_name} ko vacate mark kar diya gaya hai. Room ab Vacant (Khali) hai. 🟢")
        return redirect('tenant_detail', pk=tenant.pk)
    return render(request, 'confirm_vacate.html', {'tenant': tenant})


# ==========================================
# 5. SECURITY: SECURE DOCUMENT VAULT STREAMING
# ==========================================

@login_required
def secure_aadhaar_view(request, tenant_id):
    """
    CRITICAL SECURITY VIEW:
    Restricts access to Aadhaar documents strictly to the authorized Landlord.
    Unauthorized users receive a 403 Forbidden.
    """
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    if tenant.landlord != request.user:
        return HttpResponseForbidden("Security Violation: You do not have permission to access this tenant's KYC document.")

    if not tenant.aadhaar_document or not os.path.exists(tenant.aadhaar_document.path):
        raise Http404("Aadhaar document file not found.")

    mime_type, _ = mimetypes.guess_type(tenant.aadhaar_document.path)
    return FileResponse(open(tenant.aadhaar_document.path, 'rb'), content_type=mime_type or 'application/octet-stream')


@login_required
def secure_agreement_view(request, tenant_id):
    """
    CRITICAL SECURITY VIEW:
    Restricts access to Rent Agreements strictly to the authorized Landlord.
    """
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    if tenant.landlord != request.user:
        return HttpResponseForbidden("Security Violation: You do not have permission to access this rent agreement.")

    if not tenant.agreement_document or not os.path.exists(tenant.agreement_document.path):
        raise Http404("Rent agreement file not found.")

    mime_type, _ = mimetypes.guess_type(tenant.agreement_document.path)
    return FileResponse(open(tenant.agreement_document.path, 'rb'), content_type=mime_type or 'application/octet-stream')


# ==========================================
# 6. MODULE 3 & 4: MONTHLY BILL GENERATOR & LEDGER
# ==========================================

@login_required
def bill_list_view(request):
    status_filter = request.GET.get('status', 'all')
    month_filter = request.GET.get('month', '')
    bills = MonthlyBill.objects.filter(room__landlord=request.user).select_related('room', 'tenant')

    if status_filter in ['PENDING', 'PARTIAL', 'PAID']:
        bills = bills.filter(payment_status=status_filter)
    if month_filter:
        bills = bills.filter(billing_month__icontains=month_filter)

    total_pending = MonthlyBill.objects.filter(room__landlord=request.user).aggregate(total=Sum('balance_amount'))['total'] or Decimal('0.00')
    total_paid = MonthlyBill.objects.filter(room__landlord=request.user).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')

    return render(request, 'bill_list.html', {
        'bills': bills,
        'status_filter': status_filter,
        'month_filter': month_filter,
        'total_pending': total_pending,
        'total_paid': total_paid,
    })


@login_required
def get_room_bill_details(request, room_id):
    """
    HTMX/AJAX Endpoint:
    Returns prefill data when landlord selects a room in bill generator.
    """
    try:
        room = Room.objects.get(pk=room_id, landlord=request.user)
        active_tenant = room.active_tenant
        data = {
            'success': True,
            'room_id': room.id,
            'room_number': room.room_number,
            'base_rent': float(room.base_rent),
            'default_maintenance': float(room.default_maintenance),
            'electricity_rate': float(room.electricity_rate_per_unit),
            'previous_reading': float(room.current_meter_reading),
            'billing_day': room.billing_day,
            'tenant_id': active_tenant.id if active_tenant else None,
            'tenant_name': active_tenant.full_name if active_tenant else 'No active tenant',
            'is_occupied': room.is_occupied,
        }
        return JsonResponse(data)
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Room not found'}, status=404)


@login_required
def bill_create_view(request):
    room_id = request.GET.get('room')
    initial_data = {
        'billing_month': timezone.now().strftime("%B %Y"),
        'due_date': timezone.now().date() + timezone.timedelta(days=7),
    }

    if room_id:
        try:
            r = Room.objects.get(pk=room_id, landlord=request.user)
            initial_data['room'] = r.id
            initial_data['previous_reading'] = r.current_meter_reading
            initial_data['rent_amount'] = r.base_rent
            initial_data['maintenance_amount'] = r.default_maintenance
            initial_data['rate_per_unit'] = r.electricity_rate_per_unit
            if r.active_tenant:
                initial_data['tenant'] = r.active_tenant.id
        except Room.DoesNotExist:
            pass

    if request.method == 'POST':
        form = MonthlyBillForm(request.POST, request.FILES, landlord=request.user)
        if form.is_valid():
            bill = form.save()
            messages.success(request, f"Bill #{bill.receipt_number} generate ho gaya! Total: ₹{bill.total_bill}. WhatsApp link ready hai. ⚡")
            return redirect('bill_detail', pk=bill.pk)
        else:
            messages.error(request, "Bill creation me error hai. Meter reading check karein.")
    else:
        form = MonthlyBillForm(initial=initial_data, landlord=request.user)

    rooms = Room.objects.filter(landlord=request.user)
    return render(request, 'bill_create.html', {
        'form': form,
        'rooms': rooms,
    })


@login_required
def bill_detail_view(request, pk):
    bill = get_object_or_404(MonthlyBill, pk=pk, room__landlord=request.user)
    payment_form = RecordPaymentForm(instance=bill)
    return render(request, 'bill_detail.html', {
        'bill': bill,
        'payment_form': payment_form,
    })


@login_required
def bill_record_payment_view(request, pk):
    """
    Records a payment (Partial or Full) on an existing bill.
    Supports HTMX updates or standard redirect.
    """
    bill = get_object_or_404(MonthlyBill, pk=pk, room__landlord=request.user)
    if request.method == 'POST':
        amount = request.POST.get('paid_amount')
        method = request.POST.get('payment_method', 'UPI')
        reference = request.POST.get('payment_reference', '')
        
        try:
            bill.paid_amount = Decimal(str(amount))
            bill.payment_method = method
            bill.payment_reference = reference
            bill.save()
            messages.success(request, f"Payment recorded! Paid: ₹{bill.paid_amount}, Balance: ₹{bill.balance_amount}. Status: {bill.get_payment_status_display()}")
        except Exception as e:
            messages.error(request, f"Payment recording failed: {e}")

    return redirect('bill_detail', pk=bill.pk)


@login_required
def bill_toggle_status_view(request, pk):
    """
    HTMX 1-Click Quick Toggle:
    Flips between PENDING (₹0 paid) and PAID (100% cleared).
    """
    bill = get_object_or_404(MonthlyBill, pk=pk, room__landlord=request.user)
    if bill.payment_status in ['PENDING', 'PARTIAL']:
        bill.paid_amount = bill.total_bill
        bill.payment_status = 'PAID'
        bill.paid_on = timezone.now()
    else:
        bill.paid_amount = Decimal('0.00')
        bill.payment_status = 'PENDING'
        bill.paid_on = None
    bill.save()

    if request.headers.get('HX-Request'):
        return render(request, 'partials/bill_status_badge.html', {'bill': bill})
    
    messages.success(request, f"Bill #{bill.receipt_number} status updated to {bill.payment_status}.")
    return redirect('bill_detail', pk=bill.pk)


@login_required
def bill_receipt_pdf_view(request, pk):
    """
    Generates downloadable digital PDF rent receipt with Landlord Profile & UPI details.
    """
    bill = get_object_or_404(MonthlyBill, pk=pk, room__landlord=request.user)
    context = {
        'bill': bill,
        'landlord': request.user,
        'profile': getattr(request.user, 'profile', None),
        'generated_at': timezone.now(),
    }
    pdf = render_to_pdf('receipt_pdf.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"Rent_Receipt_{bill.receipt_number}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    return HttpResponse("Error generating PDF receipt", status=500)


@login_required
def bill_delete_view(request, pk):
    bill = get_object_or_404(MonthlyBill, pk=pk, room__landlord=request.user)
    if request.method == 'POST':
        receipt_num = bill.receipt_number
        bill.delete()
        messages.success(request, f"Bill #{receipt_num} delete kar diya gaya.")
        return redirect('bill_list')
    return render(request, 'confirm_delete.html', {'object': bill, 'type': 'Bill'})


@login_required
def bill_export_csv_view(request):
    """
    Exports the entire landlord billing ledger to a formatted CSV file.
    Ready for accounting / Excel tax filing.
    """
    bills = MonthlyBill.objects.filter(room__landlord=request.user).select_related('room', 'tenant').order_by('-created_at')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="SmartRent_Ledger_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Receipt No', 'Month', 'Room', 'Property Type', 'Tenant Name', 'Mobile',
        'Prev Meter (kWh)', 'Curr Meter (kWh)', 'Units Consumed', 'Rate/Unit (INR)',
        'Electricity Bill (INR)', 'Base Rent (INR)', 'Maintenance (INR)', 'Total Bill (INR)',
        'Paid Amount (INR)', 'Balance Due (INR)', 'Payment Status', 'Payment Method', 'Payment Ref', 'Due Date', 'Paid Date'
    ])
    
    for b in bills:
        writer.writerow([
            b.receipt_number,
            b.billing_month,
            b.room.room_number,
            b.room.get_property_type_display(),
            b.tenant.full_name,
            b.tenant.mobile_number,
            b.previous_reading,
            b.current_reading,
            b.units_consumed,
            b.rate_per_unit,
            b.electricity_bill,
            b.rent_amount,
            b.maintenance_amount,
            b.total_bill,
            b.paid_amount,
            b.balance_amount,
            b.get_payment_status_display(),
            b.get_payment_method_display(),
            b.payment_reference,
            b.due_date.strftime("%Y-%m-%d"),
            b.paid_on.strftime("%Y-%m-%d %H:%M") if b.paid_on else ''
        ])
        
    return response
