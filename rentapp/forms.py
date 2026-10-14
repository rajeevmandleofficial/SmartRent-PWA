from django import forms
from django.contrib.auth.models import User
from .models import Room, Tenant, MonthlyBill, LandlordProfile
from decimal import Decimal


TAILWIND_INPUT = "w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200 text-sm shadow-sm"
TAILWIND_SELECT = "w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200 text-sm shadow-sm"
TAILWIND_FILE = "w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 dark:file:bg-indigo-900/40 dark:file:text-indigo-300"


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = [
            'room_number', 'floor', 'property_type', 'base_rent',
            'default_maintenance', 'security_deposit', 'electricity_rate_per_unit',
            'current_meter_reading', 'billing_day'
        ]
        widgets = {
            'room_number': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. 101, F-2, B-402'}),
            'floor': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. Ground Floor, 1st Floor'}),
            'property_type': forms.Select(attrs={'class': TAILWIND_SELECT}),
            'base_rent': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. 8500', 'step': '0.01'}),
            'default_maintenance': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. 500', 'step': '0.01'}),
            'security_deposit': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. 10000', 'step': '0.01'}),
            'electricity_rate_per_unit': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. 8.00', 'step': '0.01'}),
            'current_meter_reading': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. 1420.5', 'step': '0.01'}),
            'billing_day': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'min': 1, 'max': 31, 'placeholder': '1 to 31'}),
        }


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = [
            'room', 'full_name', 'mobile_number',
            'emergency_contact', 'security_deposit', 'aadhaar_document',
            'agreement_document', 'move_in_date', 'is_active'
        ]
        widgets = {
            'room': forms.Select(attrs={'class': TAILWIND_SELECT}),
            'full_name': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. Rahul Sharma'}),
            'mobile_number': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': '10-digit mobile (e.g. 9876543210)'}),
            'emergency_contact': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'Emergency phone number'}),
            'security_deposit': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'Deposit amount in ₹', 'step': '0.01'}),
            'aadhaar_document': forms.ClearableFileInput(attrs={'class': TAILWIND_FILE, 'accept': '.pdf,.jpg,.jpeg,.png,.webp'}),
            'agreement_document': forms.ClearableFileInput(attrs={'class': TAILWIND_FILE, 'accept': '.pdf,.jpg,.jpeg,.png,.webp'}),
            'move_in_date': forms.DateInput(attrs={'class': TAILWIND_INPUT, 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-indigo-600 rounded focus:ring-indigo-500 border-gray-300 dark:border-gray-600 dark:bg-slate-700'}),
        }

    def __init__(self, *args, **kwargs):
        landlord = kwargs.pop('landlord', None)
        super().__init__(*args, **kwargs)
        self.landlord = landlord
        if landlord:
            self.fields['room'].queryset = Room.objects.filter(landlord=landlord)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.landlord and not instance.pk:
            instance.landlord = self.landlord
        if commit:
            instance.save()
        return instance


class MonthlyBillForm(forms.ModelForm):
    class Meta:
        model = MonthlyBill
        fields = [
            'room', 'tenant', 'billing_month', 'due_date',
            'previous_reading', 'current_reading', 'rate_per_unit',
            'rent_amount', 'maintenance_amount', 'paid_amount',
            'payment_method', 'payment_reference', 'meter_photo', 'notes'
        ]
        widgets = {
            'room': forms.Select(attrs={'class': TAILWIND_SELECT, 'id': 'id_room_select'}),
            'tenant': forms.Select(attrs={'class': TAILWIND_SELECT, 'id': 'id_tenant_select'}),
            'billing_month': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. October 2026'}),
            'due_date': forms.DateInput(attrs={'class': TAILWIND_INPUT, 'type': 'date'}),
            'previous_reading': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'id': 'id_prev_reading', 'step': '0.01'}),
            'current_reading': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'id': 'id_curr_reading', 'step': '0.01', 'placeholder': 'Input latest sub-meter reading'}),
            'rate_per_unit': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'id': 'id_rate_unit', 'step': '0.01'}),
            'rent_amount': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'id': 'id_rent_amt', 'step': '0.01'}),
            'maintenance_amount': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'id': 'id_maint_amt', 'step': '0.01'}),
            'paid_amount': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'id': 'id_paid_amt', 'step': '0.01', 'placeholder': '0.00'}),
            'payment_method': forms.Select(attrs={'class': TAILWIND_SELECT}),
            'payment_reference': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'UPI UTR / Cheque Ref'}),
            'meter_photo': forms.ClearableFileInput(attrs={'class': TAILWIND_FILE, 'accept': 'image/*'}),
            'notes': forms.Textarea(attrs={'class': TAILWIND_INPUT, 'rows': 2, 'placeholder': 'Internal notes (optional)'}),
        }

    def __init__(self, *args, **kwargs):
        landlord = kwargs.pop('landlord', None)
        super().__init__(*args, **kwargs)
        if landlord:
            self.fields['room'].queryset = Room.objects.filter(landlord=landlord)
            self.fields['tenant'].queryset = Tenant.objects.filter(landlord=landlord, is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        prev = cleaned_data.get('previous_reading')
        curr = cleaned_data.get('current_reading')

        if prev is not None and curr is not None:
            if Decimal(str(curr)) < Decimal(str(prev)):
                self.add_error('current_reading', f"Current sub-meter reading ({curr}) cannot be lower than previous reading ({prev}).")
        return cleaned_data


class RecordPaymentForm(forms.ModelForm):
    """Quick modal form to record partial or full rent payment."""
    class Meta:
        model = MonthlyBill
        fields = ['paid_amount', 'payment_method', 'payment_reference']
        widgets = {
            'paid_amount': forms.NumberInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'Amount in ₹', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': TAILWIND_SELECT}),
            'payment_reference': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'UPI Ref / UTR / Cheque No.'}),
        }


class LandlordProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': TAILWIND_INPUT}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': TAILWIND_INPUT}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': TAILWIND_INPUT}))

    class Meta:
        model = LandlordProfile
        fields = ['business_name', 'phone_number', 'upi_id', 'address']
        widgets = {
            'business_name': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. Sunrise Residency, Sharma Niwas'}),
            'phone_number': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. 9876543210'}),
            'upi_id': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'e.g. 9876543210@paytm or rajesh@oksbi'}),
            'address': forms.Textarea(attrs={'class': TAILWIND_INPUT, 'rows': 2, 'placeholder': 'Full property address printed on rent receipts'}),
        }


class LandlordRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'Enter strong password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'Confirm your password'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'Username (e.g. rajesh_landlord)'}),
            'email': forms.EmailInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'Email address'}),
            'first_name': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': TAILWIND_INPUT, 'placeholder': 'Last Name'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data
