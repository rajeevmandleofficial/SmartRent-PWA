from decimal import Decimal
import uuid
import os
import urllib.parse
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models.signals import post_save
from django.dispatch import receiver


# 10-digit Indian Mobile Number validator (for clean WhatsApp direct linking)
phone_regex = RegexValidator(
    regex=r'^[6-9]\d{9}$',
    message="Mobile number must be a valid 10-digit Indian number starting with 6-9."
)


def validate_document_file(file):
    """
    Validates file extension and size (Max 5MB) for KYC Documents.
    Allows only PDF and secure image formats (JPG, JPEG, PNG, WEBP).
    """
    max_size_mb = 5
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"File size cannot exceed {max_size_mb}MB.")

    valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.webp']
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(f"Unsupported file type ({ext}). Allowed: PDF, JPG, PNG, WEBP.")


class LandlordProfile(models.Model):
    """
    Extended profile for the Landlord / Property Owner:
    Stores property name, UPI ID for receiving payments, and contact details.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    business_name = models.CharField(max_length=150, blank=True, help_text="e.g. Sunrise Residency, Sharma Niwas")
    phone_number = models.CharField(max_length=15, blank=True, help_text="Landlord's contact number")
    upi_id = models.CharField(max_length=100, blank=True, help_text="e.g. 9876543210@paytm, rajesh@oksbi for direct tenant UPI payments")
    address = models.TextField(blank=True, help_text="Property address printed on receipts")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.business_name or self.user.username} Profile"

    @property
    def display_name(self):
        return self.business_name or self.user.get_full_name() or self.user.username


@receiver(post_save, sender=User)
def create_or_update_landlord_profile(sender, instance, created, **kwargs):
    """Auto-creates LandlordProfile on User creation."""
    if created:
        LandlordProfile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()


class Room(models.Model):
    PROPERTY_TYPES = [
        ('SINGLE_ROOM', 'Single Room'),
        ('1BHK', '1BHK Apartment'),
        ('2BHK', '2BHK Apartment'),
        ('3BHK', '3BHK Apartment'),
        ('FLAT', 'Multi-story Flat'),
        ('SHOP', 'Commercial / Shop'),
    ]

    landlord = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=50, help_text="e.g. 101, F-2, B-402")
    floor = models.CharField(max_length=50, default='Ground Floor', blank=True, help_text="e.g. Ground Floor, 1st Floor")
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES, default='1BHK')
    base_rent = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Monthly rent in ₹")
    default_maintenance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Monthly maintenance charge in ₹")
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Security deposit in ₹")
    electricity_rate_per_unit = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('8.00'), help_text="Rate per unit in ₹ (e.g. ₹8.00)")
    current_meter_reading = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Latest sub-meter reading in kWh units")
    billing_day = models.IntegerField(default=1, help_text="Day of month when bill is due (1-31)")
    is_occupied = models.BooleanField(default=False, help_text="Live Status: Vacant vs Occupied")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['room_number']
        unique_together = ('landlord', 'room_number')
        indexes = [
            models.Index(fields=['landlord', 'room_number']),
            models.Index(fields=['is_occupied']),
        ]

    def __str__(self):
        status = "Bhara hua" if self.is_occupied else "Khali"
        return f"Room {self.room_number} ({self.get_property_type_display()}) - [{status}]"

    @property
    def active_tenant(self):
        """Returns the currently active tenant in this room, if any."""
        return self.tenants.filter(is_active=True).first()

    def sync_occupancy_status(self):
        """Syncs is_occupied boolean based on active tenants."""
        has_active = self.tenants.filter(is_active=True).exists()
        if self.is_occupied != has_active:
            self.is_occupied = has_active
            Room.objects.filter(pk=self.pk).update(is_occupied=has_active)


class Tenant(models.Model):
    landlord = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenants', default=1)
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenants',
        help_text="Assigned room/flat (optional if vacated)"
    )
    full_name = models.CharField(max_length=150)
    mobile_number = models.CharField(
        max_length=15,
        validators=[phone_regex],
        help_text="10-digit mobile number for WhatsApp reminders"
    )
    emergency_contact = models.CharField(max_length=15, blank=True, help_text="Optional emergency contact number")
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Deposit paid by tenant (₹)")
    deposit_refunded = models.BooleanField(default=False, help_text="Checked if deposit was returned on move-out")
    
    # Document Vault: Store uploaded Aadhaar and Rent Agreement documents securely
    aadhaar_document = models.FileField(
        upload_to='tenants/aadhaar/%Y/%m/',
        blank=True,
        null=True,
        validators=[validate_document_file],
        help_text="Aadhaar Card scan/photo (PDF/JPG/PNG). Government ID number is not stored in plaintext."
    )
    agreement_document = models.FileField(
        upload_to='tenants/agreements/%Y/%m/',
        blank=True,
        null=True,
        validators=[validate_document_file],
        help_text="Rent Agreement document (PDF/JPG/PNG)"
    )
    move_in_date = models.DateField(default=timezone.now)
    move_out_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, help_text="Uncheck to mark tenant as moved out / vacated")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['landlord', 'is_active']),
            models.Index(fields=['room', 'is_active']),
            models.Index(fields=['mobile_number']),
        ]

    def __str__(self):
        room_label = f"Room {self.room.room_number}" if self.room else "Unassigned"
        return f"{self.full_name} ({room_label})"

    def clean(self):
        # If tenant is marked active and assigned a room, check if room already has another active tenant
        if self.is_active and self.room:
            existing = Tenant.objects.filter(room=self.room, is_active=True).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({
                    'room': f"Room {self.room.room_number} is already occupied by {existing.first().full_name}. Please vacate existing tenant first."
                })

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-update room.is_occupied status
        if self.room:
            self.room.sync_occupancy_status()

    def delete(self, *args, **kwargs):
        room = self.room
        super().delete(*args, **kwargs)
        if room:
            room.sync_occupancy_status()


class MonthlyBill(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending / Baaki'),
        ('PARTIAL', 'Partially Paid / Kuch Jama'),
        ('PAID', 'Full Paid / Jama'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('UPI', 'UPI (GPay / PhonePe / Paytm)'),
        ('CASH', 'Cash / Nakad'),
        ('BANK_TRANSFER', 'Bank Transfer / NEFT'),
        ('CHEQUE', 'Cheque'),
        ('OTHER', 'Other'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bills')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='bills')
    billing_month = models.CharField(max_length=30, help_text="e.g. October 2026")
    due_date = models.DateField()
    
    # Sub-meter Electricity calculation
    previous_reading = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Previous sub-meter reading (kWh)"
    )
    current_reading = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Current sub-meter reading (kWh)"
    )
    units_consumed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Current - Previous Reading"
    )
    rate_per_unit = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('8.00'),
        help_text="Cost per unit in ₹"
    )
    electricity_bill = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Units * Rate per unit"
    )
    meter_photo = models.ImageField(
        upload_to='meter_readings/%Y/%m/',
        blank=True,
        null=True,
        help_text="Sub-meter photograph proof taken on billing day"
    )
    
    # Core charges
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    maintenance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_bill = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Flexible Payment Ledger (Full & Partial support)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Amount paid so far in ₹")
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Remaining balance in ₹")
    payment_status = models.CharField(max_length=15, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='UPI', blank=True)
    payment_reference = models.CharField(max_length=100, blank=True, help_text="UPI Ref / UTR / Cheque number")
    paid_on = models.DateTimeField(null=True, blank=True)
    
    receipt_number = models.CharField(max_length=64, unique=True, blank=True)
    notes = models.TextField(blank=True, null=True, help_text="Internal landlord notes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room', 'billing_month']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['receipt_number']),
        ]

    def __str__(self):
        return f"Bill {self.receipt_number} - {self.room.room_number} ({self.billing_month}): ₹{self.total_bill}"

    def clean(self):
        if self.current_reading is not None and self.previous_reading is not None:
            if self.current_reading < self.previous_reading:
                raise ValidationError({
                    'current_reading': f"Current reading ({self.current_reading}) cannot be less than previous reading ({self.previous_reading}). Sub-meter readings only move forward!"
                })
        if self.paid_amount is not None and self.paid_amount < Decimal('0.00'):
            raise ValidationError({'paid_amount': "Paid amount cannot be negative."})

    def save(self, *args, **kwargs):
        # 1. Validation check
        if self.current_reading < self.previous_reading:
            raise ValidationError("Current reading cannot be lower than previous meter reading.")

        # 2. Formula 1: Sub-Meter Unit Calculation
        self.units_consumed = Decimal(str(self.current_reading)) - Decimal(str(self.previous_reading))
        self.electricity_bill = (self.units_consumed * Decimal(str(self.rate_per_unit))).quantize(Decimal('0.01'))

        # 3. Formula 2: Total Monthly Bill Formula
        self.total_bill = (
            Decimal(str(self.rent_amount)) +
            self.electricity_bill +
            Decimal(str(self.maintenance_amount))
        ).quantize(Decimal('0.01'))

        # 4. Compute balance amount and auto-status
        if self.paid_amount is None:
            self.paid_amount = Decimal('0.00')

        self.balance_amount = max(Decimal('0.00'), self.total_bill - self.paid_amount).quantize(Decimal('0.01'))

        if self.paid_amount >= self.total_bill and self.total_bill > 0:
            self.payment_status = 'PAID'
            if not self.paid_on:
                self.paid_on = timezone.now()
        elif self.paid_amount > 0:
            self.payment_status = 'PARTIAL'
            if not self.paid_on:
                self.paid_on = timezone.now()
        else:
            self.payment_status = 'PENDING'
            self.paid_on = None

        # 5. Generate unique receipt number
        if not self.receipt_number:
            clean_room = "".join(c for c in self.room.room_number if c.isalnum()).upper()
            unique_suffix = uuid.uuid4().hex[:6].upper()
            self.receipt_number = f"SR-{clean_room}-{unique_suffix}"

        super().save(*args, **kwargs)

        # 6. Auto-Update Room Meter Reading
        if self.room and self.room.current_meter_reading != self.current_reading:
            self.room.current_meter_reading = self.current_reading
            Room.objects.filter(pk=self.room.pk).update(current_meter_reading=self.current_reading)

    @property
    def whatsapp_url(self):
        """
        Generates a direct WhatsApp link with polite, structured bill details & Landlord UPI ID:
        https://wa.me/91<tenant_mobile>?text=...
        """
        mobile = "".join(filter(str.isdigit, str(self.tenant.mobile_number)))
        if len(mobile) == 10:
            formatted_mobile = f"91{mobile}"
        else:
            formatted_mobile = mobile

        landlord_profile = getattr(self.room.landlord, 'profile', None)
        upi_id = landlord_profile.upi_id if landlord_profile and landlord_profile.upi_id else None
        prop_name = landlord_profile.business_name if landlord_profile and landlord_profile.business_name else "SmartRent"

        status_text = "PAID (Jama ho gaya hai)" if self.payment_status == 'PAID' else (
            f"PARTIALLY PAID (₹{self.paid_amount} received, Balance: ₹{self.balance_amount})"
            if self.payment_status == 'PARTIAL'
            else "DUE (Kripya samay par jama karein)"
        )
        
        upi_message = f"\n📲 Pay via UPI: {upi_id}\n" if upi_id else ""

        message = (
            f"Namaste {self.tenant.full_name} ji! 🙏\n\n"
            f"Aapka monthly bill ({prop_name}) generate ho gaya hai:\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏠 Room / Flat: {self.room.room_number} ({self.room.get_property_type_display()})\n"
            f"📅 Billing Month: {self.billing_month}\n"
            f"⏰ Due Date: {self.due_date.strftime('%d %b, %Y')}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Monthly Rent: ₹{self.rent_amount}\n"
            f"⚡ Bijli Sub-Meter: {self.previous_reading} to {self.current_reading}\n"
            f"⚡ Units Consumed: {self.units_consumed} units @ ₹{self.rate_per_unit}/unit\n"
            f"⚡ Electricity Amount: ₹{self.electricity_bill}\n"
            f"🛠 Maintenance: ₹{self.maintenance_amount}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💵 TOTAL AMOUNT DUE: ₹{self.total_bill}\n"
            f"💳 Amount Paid: ₹{self.paid_amount}\n"
            f"⚠️ Balance Due: ₹{self.balance_amount}\n"
            f"📌 Status: {status_text}\n"
            f"📄 Bill No: {self.receipt_number}\n"
            f"{upi_message}"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Kripya due date se pehle payment karein. Dhanyawad!"
        )

        encoded_text = urllib.parse.quote(message)
        return f"https://wa.me/{formatted_mobile}?text={encoded_text}"
