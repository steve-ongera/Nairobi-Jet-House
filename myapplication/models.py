from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.utils import timezone

class User(AbstractUser):
    """Custom user model that extends Django's built-in user model"""
    USER_TYPE_CHOICES = (
        ('client', 'Client'),
        ('owner', 'Aircraft Owner'),
        ('agent', 'Booking Agent'),
        ('admin', 'System Admin'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    phone_number = models.CharField(max_length=20)
    address = models.TextField(blank=True, null=True)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    tax_id = models.CharField(max_length=50, blank=True, null=True)
    verified = models.BooleanField(default=False)

    def __str__(self):
        if self.get_full_name():
            return f"{self.get_full_name()} ({self.email})"
        return self.email

class AircraftType(models.Model):
    """Different types of aircraft (jets, helicopters, etc.)"""
    
    CATEGORY_CHOICES = [
        ('helicopter', 'Helicopter'),
        ('chopper', 'Chopper'),
        ('jet', 'Jet'),
        ('propeller', 'Propeller Plane'),
        ('glider', 'Glider'),
        # Add more as needed
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='aircraft_types/', blank=True, null=True)
    passenger_capacity = models.PositiveIntegerField()
    range_nautical_miles = models.PositiveIntegerField(help_text="Maximum range in nautical miles")
    speed_knots = models.PositiveIntegerField(help_text="Cruising speed in knots")

    # New Fields
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='helicopter')
    price_per_hour_usd = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

class Aircraft(models.Model):
    """Individual aircraft owned by owners"""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='aircrafts')
    aircraft_type = models.ForeignKey(AircraftType, on_delete=models.PROTECT)
    registration_number = models.CharField(max_length=20, unique=True)
    model_name = models.CharField(max_length=100)
    year_manufactured = models.PositiveIntegerField()
    base_airport = models.CharField(max_length=10, help_text="ICAO code of home airport")
    current_location = models.CharField(max_length=10, help_text="ICAO code of current location")
    is_active = models.BooleanField(default=True)
    features = models.TextField(blank=True)
    interior_images = models.ManyToManyField('AircraftImage', blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, help_text="Base hourly rate in USD")
    minimum_hours = models.DecimalField(max_digits=5, decimal_places=1, default=1.0)
    
    def __str__(self):
        return f"{self.model_name} ({self.registration_number})"

class AircraftImage(models.Model):
    """Images for aircraft"""
    image = models.ImageField(upload_to='aircraft_images/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return self.caption or f"Aircraft Image {self.id}"

class Airport(models.Model):
    """Airport information"""
    icao_code = models.CharField(max_length=4, unique=True)
    iata_code = models.CharField(max_length=3, blank=True, null=True)
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_private_aviation_friendly = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.icao_code} - {self.name}"

class Availability(models.Model):
    """When aircraft are available for booking"""
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='availabilities')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    is_available = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Availabilities"
        ordering = ['start_datetime']

    def __str__(self):
        return f"{self.aircraft} available from {self.start_datetime} to {self.end_datetime}"

import random
import string

from django.core.validators import MinValueValidator

class Booking(models.Model):
    """Client bookings"""
    TRIP_TYPE_CHOICES = (
        ('one_way', 'One Way'),
        ('round_trip', 'Round Trip'),
        ('multi_leg', 'Multi-leg'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    client = models.ForeignKey(User, on_delete=models.PROTECT, related_name='bookings')
    aircraft = models.ForeignKey(Aircraft, on_delete=models.PROTECT, related_name='bookings')
    trip_type = models.CharField(max_length=20, choices=TRIP_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    agent_commission = models.DecimalField(max_digits=12, decimal_places=2)
    owner_earnings = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.BooleanField(default=False)
    special_requests = models.TextField(blank=True)
    booking_order_id =  models.CharField(max_length=10, blank=True, null=True)

    # New fields for empty leg functionality
    is_empty_leg = models.BooleanField(default=False)
    return_date = models.DateTimeField(null=True, blank=True)
    return_time = models.TimeField(null=True, blank=True)
    stay_duration_days = models.PositiveIntegerField(null=True, blank=True)
    
    def generate_booking_order_id(self):
        """Generate a unique 10-character alphanumeric booking order ID"""
        while True:
            # Generate 8 random alphanumeric characters + 2 digits
            letters_digits = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            # Add 2 more digits at the end
            digits = ''.join(random.choices(string.digits, k=2))
            code = letters_digits + digits
            
            # Check if code already exists
            if not Booking.objects.filter(booking_order_id=code).exists():
                return code
    
    def save(self, *args, **kwargs):
        # Generate booking order ID only if it doesn't exist
        if not self.booking_order_id:
            self.booking_order_id = self.generate_booking_order_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Booking #{self.id} - {self.client} for {self.aircraft}"

class FlightLeg(models.Model):
    """Individual legs of a booking (supports one-way, round-trip, multi-leg)"""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='flight_legs')
    departure_airport = models.ForeignKey(Airport, on_delete=models.PROTECT, related_name='departing_flights')
    arrival_airport = models.ForeignKey(Airport, on_delete=models.PROTECT, related_name='arriving_flights')
    departure_datetime = models.DateTimeField()
    arrival_datetime = models.DateTimeField()
    flight_hours = models.DecimalField(max_digits=5, decimal_places=1)
    passenger_count = models.PositiveIntegerField()
    leg_price = models.DecimalField(max_digits=12, decimal_places=2)
    sequence = models.PositiveIntegerField()

    class Meta:
        ordering = ['booking', 'sequence']

    def __str__(self):
        return f"Leg {self.sequence} of Booking {self.booking.id}: {self.departure_airport} to {self.arrival_airport}"

class PricingRule(models.Model):
    """Rules for calculating prices based on various factors"""
    aircraft_type = models.ForeignKey(AircraftType, on_delete=models.CASCADE)
    base_hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_hours = models.DecimalField(max_digits=5, decimal_places=1, default=1.0)
    empty_leg_discount = models.DecimalField(max_digits=5, decimal_places=2, default=0, 
                                           help_text="Discount percentage for empty leg flights")
    peak_season_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.0,
                                               help_text="Multiplier for peak season pricing")
    weekend_surcharge = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                          help_text="Additional percentage for weekend flights")
    last_minute_surcharge = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                              help_text="Additional percentage for bookings made within 24 hours")

    def __str__(self):
        return f"Pricing for {self.aircraft_type}"

class ClientPreferences(models.Model):
    """Client preferences and frequent flyer information"""
    client = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    preferred_aircraft_types = models.ManyToManyField(AircraftType, blank=True)
    dietary_restrictions = models.TextField(blank=True)
    preferred_payment_method = models.CharField(max_length=50, blank=True)
    passport_number = models.CharField(max_length=50, blank=True)
    passport_expiry = models.DateField(blank=True, null=True)
    frequent_flyer_programs = models.TextField(blank=True)

    def __str__(self):
        return f"Preferences for {self.client}"

class OwnerPayout(models.Model):
    """Records of payments to aircraft owners"""
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='payouts')
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name='payouts')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payout_date = models.DateField()
    transaction_reference = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=(
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ), default='pending')

    def __str__(self):
        return f"Payout of ${self.amount} to {self.owner} for booking #{self.booking.id}"

class AircraftTracking(models.Model):
    """Real-time tracking of aircraft locations"""
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='tracking')
    timestamp = models.DateTimeField(default=timezone.now)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    altitude = models.PositiveIntegerField(help_text="Altitude in feet")
    heading = models.PositiveIntegerField(help_text="Heading in degrees")
    speed = models.PositiveIntegerField(help_text="Speed in knots")
    source = models.CharField(max_length=50, help_text="Source of tracking data")

    class Meta:
        ordering = ['-timestamp']
        get_latest_by = 'timestamp'

    def __str__(self):
        return f"{self.aircraft} at {self.timestamp}"
    
import random
import string
from django.db import models

class Passenger(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='passengers')
    name = models.CharField(max_length=100)
    nationality = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    passport_number = models.CharField(max_length=100, blank=True)
    order = models.CharField(max_length=10, blank=True, unique=True)
    
    def generate_order_code(self):
        """Generate a unique 10-character alphanumeric code"""
        while True:
            # Generate 8 random alphanumeric characters + 2 digits
            letters_digits = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            # Add 2 more digits at the end
            digits = ''.join(random.choices(string.digits, k=2))
            code = letters_digits + digits
            
            # Check if code already exists
            if not Passenger.objects.filter(order=code).exists():
                return code
    
    def save(self, *args, **kwargs):
        # Generate code only if it doesn't exist
        if not self.order:
            self.order = self.generate_order_code()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} - {self.passport_number or 'No Passport'}"
    

from django.db import models

class AirCargoRequest(models.Model):
    REQUEST_TYPE_CHOICES = [
        ('one_way', 'One Way'),
        ('return', 'Return'),
        ('multileg', 'Multileg'),
    ]
    
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    departure = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    date = models.DateField()
    departure_time = models.TimeField(null=True, blank=True)
    name = models.CharField(max_length=100)
    company = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    telephone = models.CharField(max_length=20)
    cargo_details = models.TextField()
    special_requirements = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Cargo Request #{self.id} - {self.departure} to {self.destination}"

import string
import random
from django.db import models

def generate_inquiry_code():
    """Generate a random 10-character alphanumeric code"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(10))

class AircraftLeasingInquiry(models.Model):
    LEASING_TYPE_CHOICES = [
        ('private_jet', 'Private Jet Charter'),
        ('group_charter', 'Group Air Charter'),
        ('aircraft_leasing', 'Aircraft Leasing'),
    ]
    
    # Auto-generated inquiry code
    inquiry_code = models.CharField(
        max_length=10, 
        blank=True,
        null=  True, 
        unique= True  ,
        default=generate_inquiry_code,
        editable=True
    )
    
    leasing_type = models.CharField(max_length=20, choices=LEASING_TYPE_CHOICES)
    name = models.CharField(max_length=100)
    company = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    telephone = models.CharField(max_length=20)
    requirements = models.TextField()
    duration = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Supporting Documents (up to 2 documents)
    supporting_document_1 = models.FileField(upload_to='aircraft_leasing/documents/', blank=True, null=True)
    supporting_document_2 = models.FileField(upload_to='aircraft_leasing/documents/', blank=True, null=True)
    
    def save(self, *args, **kwargs):
        # Ensure unique code generation in case of collision
        if not self.inquiry_code:
            while True:
                code = generate_inquiry_code()
                if not AircraftLeasingInquiry.objects.filter(inquiry_code=code).exists():
                    self.inquiry_code = code
                    break
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Inquiry {self.inquiry_code} - {self.get_leasing_type_display()}"


class GroupInquiry(models.Model):
    TRAVEL_TYPE_CHOICES = [
        ('corporate', 'Corporate Travel'),
        ('group', 'Group Travel'),
    ]
    
    # Basic Information
    group_name = models.CharField(max_length=100)
    contact_email = models.EmailField()
    passenger_count = models.PositiveIntegerField()
    travel_date = models.DateField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    # Travel Type
    travel_type = models.CharField(max_length=20,choices=TRAVEL_TYPE_CHOICES,null=True,blank=True,) 
    departure = models.CharField(max_length=200,null=True,blank=True)
    destination = models.CharField(max_length=200,null=True,blank=True,)
    departure_time = models.TimeField(null=True,blank=True,)
    
    # Contact Information
    telephone = models.CharField(max_length=20,  null=True, blank=True)    
    special_requirements = models.TextField(null=True,blank=True,)
    

    def __str__(self):
        travel_type_display = self.get_travel_type_display() if self.travel_type else "Unspecified"
        return f"{self.group_name} - {travel_type_display} - {self.contact_email}"
    
    def get_passenger_count_display(self):
        """Return a formatted passenger count string"""
        return f"{self.passenger_count} passenger{'s' if self.passenger_count != 1 else ''}"
    
    def is_corporate_travel(self):
        """Check if this is corporate travel"""
        return self.travel_type == 'corporate'
    
    def is_group_travel(self):
        """Check if this is group travel"""
        return self.travel_type == 'group'
    

from django.db import models

class ContactSubmission(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    subject = models.CharField(max_length=50, choices=[
        ('Charter Inquiry', 'Charter Inquiry'),
        ('Membership', 'Membership'),
        ('Group Booking', 'Group Booking'),
        ('Other', 'Other'),
    ])
    message = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject} ({self.submitted_at.strftime('%Y-%m-%d')})"

    class Meta:
        verbose_name = "Contact Submission"
        verbose_name_plural = "Contact Submissions"
        ordering = ['-submitted_at']



from django.db import models
from django.utils import timezone

class Inquiry(models.Model):
    # Contact Information
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    # Flight Details
    aircraft_type = models.ForeignKey(
        'AircraftType', 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='inquiries'
    )
    departure = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    passengers = models.PositiveIntegerField()
    travel_date = models.DateField()
    
    # Metadata
    submitted_at = models.DateTimeField(default=timezone.now)
    is_processed = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = "Inquiries"
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Inquiry from {self.full_name} ({self.submitted_at.strftime('%Y-%m-%d')})"
    
# membership and aircraft tracking system
class OwnerDashboard(models.Model):
    """Central hub for all owner operations"""
    owner = models.OneToOneField(
        'User', 
        on_delete=models.CASCADE,
        limit_choices_to={'user_type': 'owner'},
        related_name='owner_dashboard'
    )
    joined_date = models.DateField(auto_now_add=True)
    last_accessed = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Owner Dashboards"
    
    def __str__(self):
        return f"{self.owner}'s Aircraft Dashboard"

    @property
    def total_aircraft(self):
        return self.owner.aircrafts.count()

    @property
    def active_aircraft(self):
        return self.owner.aircrafts.filter(is_active=True).count()
    

class AircraftPerformance(models.Model):
    """Tracks all operational metrics for a single aircraft"""
    aircraft = models.OneToOneField(
        'Aircraft',
        on_delete=models.CASCADE,
        related_name='performance'
    )
    total_flight_hours = models.DecimalField(max_digits=9, decimal_places=1, default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance_due = models.DateField(null=True, blank=True)
    nautical_miles = models.PositiveIntegerField(default=0)
    
    def update_metrics(self):
        """Auto-calculates metrics from existing bookings"""
        from django.db.models import Sum
        legs = self.aircraft.bookings.all().aggregate(
            total_hours=Sum('flight_hours'),
            total_rev=Sum('owner_earnings')
        )
        self.total_flight_hours = legs['total_hours'] or 0
        self.total_revenue = legs['total_rev'] or 0
        self.save()
    
    def __str__(self):
        return f"{self.aircraft} Performance"
    

class FlightRoute(models.Model):
    """Tracks where each aircraft has flown"""
    aircraft = models.ForeignKey(
        'Aircraft',
        on_delete=models.CASCADE,
        related_name='flight_history'
    )
    departure = models.CharField(max_length=100)  # Airport code
    destination = models.CharField(max_length=100)
    date = models.DateField()
    flight_hours = models.DecimalField(max_digits=5, decimal_places=1)
    nautical_miles = models.PositiveIntegerField()
    passengers = models.PositiveSmallIntegerField()
    booking_reference = models.CharField(max_length=20, blank=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.aircraft}: {self.departure}→{self.destination} ({self.date})"
    

class MaintenanceTicket(models.Model):
    """Owner-initiated maintenance requests"""
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ]
    
    aircraft = models.ForeignKey(
        'Aircraft',
        on_delete=models.CASCADE,
        related_name='maintenance_tickets'
    )
    title = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'user_type': 'owner'}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.aircraft} - {self.title}"
    

class OwnerNotification(models.Model):
    """Real-time alerts for owners"""
    owner = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        limit_choices_to={'user_type': 'owner'},
        related_name='notifications'
    )
    message = models.CharField(max_length=200)
    related_aircraft = models.ForeignKey(
        'Aircraft',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Alert for {self.owner}"