from decimal import Decimal
import uuid
import urllib.parse
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


# 10-digit Indian Mobile Number validator (for clean WhatsApp direct linking)
phone_regex = RegexValidator(
    regex=r'^[6-9]\d{9}$',
    message="Mobile number must be a valid 10-digit Indian number starting with 6-9."
)


class Room(models.Model):
    PROPERTY_TYPES = [
        ('SINGLE_ROOM', 'Single Room'),
        ('1BHK', '1BHK Apartment'),
        ('2BHK', '2BHK Apartment'),
        ('FLAT', 'Multi-story Flat'),
        ('SHOP', 'Commercial / Shop'),
    ]

    landlord = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=50, help_text="e.g. 101, F-2, B-402")
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES, default='1BHK')
    base_rent = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Monthly rent in ₹")
    default_maintenance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Monthly maintenance charge in ₹")
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
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenants',
        help_text="Assigned room/flat"
    )
    full_name = models.CharField(max_length=150)
    mobile_number = models.CharField(
        max_length=15,
        validators=[phone_regex],
        help_text="10-digit mobile number for WhatsApp reminders"
    )
    emergency_contact = models.CharField(max_length=15, blank=True, help_text="Optional emergency contact number")
    
    # Document Vault: Store uploaded Aadhaar and Rent Agreement documents securely
    aadhaar_document = models.FileField(
        upload_to='tenants/aadhaar/%Y/%m/',
        blank=True,
        null=True,
        help_text="Aadhaar Card scan/photo (PDF/JPG/PNG). Government ID number is not stored in plaintext."
    )
    agreement_document = models.FileField(
        upload_to='tenants/agreements/%Y/%m/',
        blank=True,
        null=True,
        help_text="Rent Agreement document (PDF/JPG/PNG)"
    )
    move_in_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True, help_text="Uncheck to mark tenant as moved out / vacated")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
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
        ('PAID', 'Paid / Jama'),
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
    
    # Core charges
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    maintenance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_bill = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Status & Ledger
    payment_status = models.CharField(max_length=15, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    paid_on = models.DateTimeField(null=True, blank=True)
    receipt_number = models.CharField(max_length=64, unique=True, blank=True)
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

    def save(self, *args, **kwargs):
        # 1. Validation check
        if self.current_reading < self.previous_reading:
            raise ValidationError("Current reading cannot be lower than previous meter reading.")

        # 2. Formula 1: Sub-Meter Unit Calculation
        # Units Consumed = Current Reading - Previous Reading
        self.units_consumed = Decimal(str(self.current_reading)) - Decimal(str(self.previous_reading))
        
        # Electricity Bill = Units Consumed * Rate Per Unit
        self.electricity_bill = (self.units_consumed * Decimal(str(self.rate_per_unit))).quantize(Decimal('0.01'))

        # 3. Formula 2: Total Monthly Bill Formula
        # Total Bill = Rent + Electricity Bill + Maintenance
        self.total_bill = (
            Decimal(str(self.rent_amount)) +
            self.electricity_bill +
            Decimal(str(self.maintenance_amount))
        ).quantize(Decimal('0.01'))

        # 4. Generate unique receipt number if not present
        if not self.receipt_number:
            clean_room = "".join(c for c in self.room.room_number if c.isalnum()).upper()
            unique_suffix = uuid.uuid4().hex[:6].upper()
            self.receipt_number = f"SR-{clean_room}-{unique_suffix}"

        # 5. Timestamp for payment status
        if self.payment_status == 'PAID' and not self.paid_on:
            self.paid_on = timezone.now()
        elif self.payment_status == 'PENDING':
            self.paid_on = None

        super().save(*args, **kwargs)

        # 6. Auto-Update Room Meter Reading
        # Once a bill is generated, update Room.current_meter_reading = MonthlyBill.current_reading
        # so next month's bill automatically fetches it as previous_reading!
        if self.room and self.room.current_meter_reading != self.current_reading:
            self.room.current_meter_reading = self.current_reading
            Room.objects.filter(pk=self.room.pk).update(current_meter_reading=self.current_reading)

    @property
    def whatsapp_url(self):
        """
        Generates a direct WhatsApp link with polite, structured bill details:
        https://wa.me/91<tenant_mobile>?text=...
        """
        mobile = "".join(filter(str.isdigit, str(self.tenant.mobile_number)))
        if len(mobile) == 10:
            formatted_mobile = f"91{mobile}"
        else:
            formatted_mobile = mobile

        status_text = "PAID (Jama ho gaya hai)" if self.payment_status == 'PAID' else "DUE (Kripya samay par jama karein)"
        
        message = (
            f"Namaste {self.tenant.full_name} ji! 🙏\n\n"
            f"Aapka SmartRent monthly bill generate ho gaya hai:\n"
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
            f"📌 Status: {status_text}\n"
            f"📄 Bill No: {self.receipt_number}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Kripya bill due date se pehle UPI / NetBanking dwara jama karein. Dhanyawad!"
        )

        encoded_text = urllib.parse.quote(message)
        return f"https://wa.me/{formatted_mobile}?text={encoded_text}"
