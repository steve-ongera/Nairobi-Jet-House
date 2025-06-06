from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from .models import (
    User, AircraftType, Aircraft, AircraftImage, Airport, 
    Availability, Booking, FlightLeg, PricingRule, 
    ClientPreferences, OwnerPayout, AircraftTracking ,Passenger
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Custom User Admin with additional fields"""
    list_display = ('username', 'email', 'user_type', 'phone_number', 'company_name', 'verified', 'is_active', 'date_joined')
    list_filter = ('user_type', 'verified', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'phone_number', 'company_name', 'first_name', 'last_name')
    readonly_fields = ('date_joined', 'last_login')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('user_type', 'phone_number', 'address', 'company_name', 'tax_id', 'verified')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('user_type', 'phone_number', 'email', 'company_name')
        }),
    )
    
    actions = ['mark_as_verified', 'mark_as_unverified']
    
    def mark_as_verified(self, request, queryset):
        queryset.update(verified=True)
        self.message_user(request, f"{queryset.count()} users marked as verified.")
    mark_as_verified.short_description = "Mark selected users as verified"
    
    def mark_as_unverified(self, request, queryset):
        queryset.update(verified=False)
        self.message_user(request, f"{queryset.count()} users marked as unverified.")
    mark_as_unverified.short_description = "Mark selected users as unverified"


@admin.register(AircraftType)
class AircraftTypeAdmin(admin.ModelAdmin):
    """Aircraft Type Admin"""
    list_display = ('name', 'passenger_capacity', 'range_nautical_miles', 'speed_knots', 'aircraft_count' , 'price_per_hour_usd')
    list_filter = ('passenger_capacity',)
    search_fields = ('name', 'description')
    readonly_fields = ('aircraft_count',)
    
    def aircraft_count(self, obj):
        return obj.aircraft_set.count()
    aircraft_count.short_description = 'Aircraft Count'
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            aircraft_count=Count('aircraft')
        )


class AircraftImageInline(admin.TabularInline):
    """Inline for Aircraft Images"""
    model = Aircraft.interior_images.through
    extra = 1
    verbose_name = "Interior Image"
    verbose_name_plural = "Interior Images"


class AvailabilityInline(admin.TabularInline):
    """Inline for Aircraft Availability"""
    model = Availability
    extra = 1
    fields = ('start_datetime', 'end_datetime', 'is_available', 'notes')


@admin.register(Aircraft)
class AircraftAdmin(admin.ModelAdmin):
    """Aircraft Admin"""
    list_display = ('registration_number', 'model_name', 'owner', 'aircraft_type', 'base_airport', 'current_location', 'is_active', 'hourly_rate', 'booking_count')
    list_filter = ('aircraft_type', 'is_active', 'year_manufactured', 'owner__user_type')
    search_fields = ('registration_number', 'model_name', 'owner__username', 'base_airport', 'current_location')
    readonly_fields = ('booking_count', 'total_flight_hours', 'last_tracked')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('owner', 'aircraft_type', 'registration_number', 'model_name', 'year_manufactured')
        }),
        ('Location & Status', {
            'fields': ('base_airport', 'current_location', 'is_active')
        }),
        ('Pricing & Features', {
            'fields': ('hourly_rate', 'minimum_hours', 'features')
        }),
        ('Statistics', {
            'fields': ('booking_count', 'total_flight_hours', 'last_tracked'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [AircraftImageInline, AvailabilityInline]
    
    def booking_count(self, obj):
        return obj.bookings.count()
    booking_count.short_description = 'Total Bookings'
    
    def total_flight_hours(self, obj):
        total = obj.bookings.aggregate(total_hours=Sum('flight_legs__flight_hours'))['total_hours']
        return f"{total or 0} hours"
    total_flight_hours.short_description = 'Total Flight Hours'
    
    def last_tracked(self, obj):
        last_track = obj.tracking.first()
        if last_track:
            return last_track.timestamp
        return "Never tracked"
    last_tracked.short_description = 'Last Tracked'


@admin.register(AircraftImage)
class AircraftImageAdmin(admin.ModelAdmin):
    """Aircraft Image Admin"""
    list_display = ('id', 'caption', 'is_primary', 'image_preview')
    list_filter = ('is_primary',)
    search_fields = ('caption',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "No Image"
    image_preview.short_description = 'Preview'


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    """Airport Admin"""
    list_display = ('icao_code', 'iata_code', 'name', 'city', 'country', 'is_private_aviation_friendly', 'departure_count', 'arrival_count')
    list_filter = ('country', 'is_private_aviation_friendly')
    search_fields = ('icao_code', 'iata_code', 'name', 'city', 'country')
    readonly_fields = ('departure_count', 'arrival_count')
    
    def departure_count(self, obj):
        return obj.departing_flights.count()
    departure_count.short_description = 'Departures'
    
    def arrival_count(self, obj):
        return obj.arriving_flights.count()
    arrival_count.short_description = 'Arrivals'


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    """Availability Admin"""
    list_display = ('aircraft', 'start_datetime', 'end_datetime', 'is_available', 'duration')
    list_filter = ('is_available', 'aircraft__aircraft_type', 'start_datetime')
    search_fields = ('aircraft__registration_number', 'aircraft__model_name')
    date_hierarchy = 'start_datetime'
    
    def duration(self, obj):
        duration = obj.end_datetime - obj.start_datetime
        return f"{duration.days} days, {duration.seconds // 3600} hours"
    duration.short_description = 'Duration'


class FlightLegInline(admin.TabularInline):
    """Inline for Flight Legs"""
    model = FlightLeg
    extra = 1
    fields = ('sequence', 'departure_airport', 'arrival_airport', 'departure_datetime', 'arrival_datetime', 'flight_hours', 'passenger_count', 'leg_price')
    ordering = ('sequence',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Booking Admin"""
    list_display = ('id', 'client', 'aircraft', 'trip_type', 'status', 'total_price', 'payment_status', 'created_at', 'flight_legs_count')
    list_filter = ('status', 'trip_type', 'payment_status', 'created_at', 'aircraft__aircraft_type')
    search_fields = ('client__username', 'client__email', 'aircraft__registration_number', 'id')
    readonly_fields = ('created_at', 'updated_at', 'flight_legs_count', 'total_flight_hours')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Booking Information', {
            'fields': ('client', 'aircraft', 'trip_type', 'status')
        }),
        ('Financial Details', {
            'fields': ('total_price', 'commission_rate', 'agent_commission', 'owner_earnings', 'payment_status')
        }),
        ('Additional Information', {
            'fields': ('special_requests',)
        }),
        ('Timestamps & Statistics', {
            'fields': ('created_at', 'updated_at', 'flight_legs_count', 'total_flight_hours'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [FlightLegInline]
    actions = ['mark_as_confirmed', 'mark_as_completed', 'mark_as_paid']
    
    def flight_legs_count(self, obj):
        return obj.flight_legs.count()
    flight_legs_count.short_description = 'Flight Legs'
    
    def total_flight_hours(self, obj):
        total = obj.flight_legs.aggregate(total_hours=Sum('flight_hours'))['total_hours']
        return f"{total or 0} hours"
    total_flight_hours.short_description = 'Total Hours'
    
    def mark_as_confirmed(self, request, queryset):
        queryset.update(status='confirmed')
        self.message_user(request, f"{queryset.count()} bookings marked as confirmed.")
    mark_as_confirmed.short_description = "Mark selected bookings as confirmed"
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f"{queryset.count()} bookings marked as completed.")
    mark_as_completed.short_description = "Mark selected bookings as completed"
    
    def mark_as_paid(self, request, queryset):
        queryset.update(payment_status=True)
        self.message_user(request, f"{queryset.count()} bookings marked as paid.")
    mark_as_paid.short_description = "Mark selected bookings as paid"


@admin.register(FlightLeg)
class FlightLegAdmin(admin.ModelAdmin):
    """Flight Leg Admin"""
    list_display = ('booking', 'sequence', 'departure_airport', 'arrival_airport', 'departure_datetime', 'flight_hours', 'passenger_count', 'leg_price')
    list_filter = ('departure_datetime', 'departure_airport__country', 'arrival_airport__country')
    search_fields = ('booking__id', 'departure_airport__icao_code', 'arrival_airport__icao_code')
    date_hierarchy = 'departure_datetime'


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    """Pricing Rule Admin"""
    list_display = ('aircraft_type', 'base_hourly_rate', 'minimum_hours', 'empty_leg_discount', 'peak_season_multiplier', 'weekend_surcharge', 'last_minute_surcharge')
    list_filter = ('aircraft_type',)
    search_fields = ('aircraft_type__name',)


@admin.register(ClientPreferences)
class ClientPreferencesAdmin(admin.ModelAdmin):
    """Client Preferences Admin"""
    list_display = ('client', 'preferred_payment_method', 'passport_expiry', 'has_dietary_restrictions')
    list_filter = ('preferred_payment_method', 'passport_expiry')
    search_fields = ('client__username', 'client__email')
    filter_horizontal = ('preferred_aircraft_types',)
    
    def has_dietary_restrictions(self, obj):
        return bool(obj.dietary_restrictions)
    has_dietary_restrictions.boolean = True
    has_dietary_restrictions.short_description = 'Has Dietary Restrictions'


@admin.register(OwnerPayout)
class OwnerPayoutAdmin(admin.ModelAdmin):
    """Owner Payout Admin"""
    list_display = ('owner', 'booking', 'amount', 'payout_date', 'status', 'transaction_reference')
    list_filter = ('status', 'payout_date')
    search_fields = ('owner__username', 'booking__id', 'transaction_reference')
    readonly_fields = ('booking_link',)
    date_hierarchy = 'payout_date'
    
    def booking_link(self, obj):
        if obj.booking:
            # Replace 'your_app' with your actual app name
            # Since your URL shows 'myapplication', use that:
            url = reverse('admin:myapplication_booking_change', args=[obj.booking.id])
            return format_html('<a href="{}">Booking #{}</a>', url, obj.booking.id)
        return "No booking"
    booking_link.short_description = 'Related Booking'
    
    actions = ['mark_as_processed', 'mark_as_failed']
    
    def mark_as_processed(self, request, queryset):
        queryset.update(status='processed')
        self.message_user(request, f"{queryset.count()} payouts marked as processed.")
    mark_as_processed.short_description = "Mark selected payouts as processed"
    
    def mark_as_failed(self, request, queryset):
        queryset.update(status='failed')
        self.message_user(request, f"{queryset.count()} payouts marked as failed.")
    mark_as_failed.short_description = "Mark selected payouts as failed"


@admin.register(AircraftTracking)
class AircraftTrackingAdmin(admin.ModelAdmin):
    """Aircraft Tracking Admin"""
    list_display = ('aircraft', 'timestamp', 'latitude', 'longitude', 'altitude', 'speed', 'heading', 'source')
    list_filter = ('source', 'timestamp', 'aircraft__aircraft_type')
    search_fields = ('aircraft__registration_number', 'aircraft__model_name', 'source')
    readonly_fields = ('timestamp', 'location_link')
    date_hierarchy = 'timestamp'
    
    def location_link(self, obj):
        if obj.latitude and obj.longitude:
            google_maps_url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
            return format_html('<a href="{}" target="_blank">View on Google Maps</a>', google_maps_url)
        return "No coordinates"
    location_link.short_description = 'Location'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('aircraft')

@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_display = ('name', 'passport_number', 'nationality', 'date_of_birth', 'booking')
    search_fields = ('name', 'passport_number', 'nationality')
    list_filter = ('nationality', 'booking')


from django.contrib import admin
from .models import AirCargoRequest, AircraftLeasingInquiry


@admin.register(AirCargoRequest)
class AirCargoRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'request_type', 'departure', 'destination', 'date',
        'name', 'email', 'telephone', 'created_at'
    )
    list_filter = ('request_type', 'date', 'created_at')
    search_fields = ('name', 'email', 'departure', 'destination', 'company')
    readonly_fields = ('created_at',)


@admin.register(AircraftLeasingInquiry)
class AircraftLeasingInquiryAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'leasing_type', 'name', 'email', 'telephone', 'created_at'
    )
    list_filter = ('leasing_type', 'created_at')
    search_fields = ('name', 'email', 'company')
    readonly_fields = ('created_at',)

from django.contrib import admin
from .models import GroupInquiry

@admin.register(GroupInquiry)
class GroupInquiryAdmin(admin.ModelAdmin):
    list_display = ('group_name', 'contact_email', 'passenger_count', 'travel_date', 'submitted_at')
    search_fields = ('group_name', 'contact_email')
    list_filter = ('travel_date', 'submitted_at')
    ordering = ('-submitted_at',)

from django.contrib import admin
from .models import ContactSubmission

@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'submitted_at')
    list_filter = ('subject', 'submitted_at')
    search_fields = ('name', 'email', 'message')
    readonly_fields = ('submitted_at',)

from django.contrib import admin
from .models import Inquiry

@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = (
        'full_name', 'email', 'phone', 
        'aircraft_type', 'departure', 
        'destination', 'travel_date', 
        'is_processed', 'submitted_at'
    )
    list_filter = ('is_processed', 'aircraft_type', 'travel_date', 'submitted_at')
    search_fields = ('full_name', 'email', 'phone', 'departure', 'destination')
    list_editable = ('is_processed',)
    date_hierarchy = 'travel_date'
    ordering = ('-submitted_at',)


# Custom admin site configuration
admin.site.site_header = "Private Jet Booking Administration"
admin.site.site_title = "Private Jet Admin"
admin.site.index_title = "Welcome to Private Jet Booking System Administration"