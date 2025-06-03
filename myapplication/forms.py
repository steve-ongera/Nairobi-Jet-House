from django import forms
from .models import GroupInquiry

class GroupInquiryForm(forms.ModelForm):
    class Meta:
        model = GroupInquiry
        fields = ['group_name', 'contact_email', 'passenger_count', 'travel_date']
        widgets = {
            'group_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Group Name'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contact Email'
            }),
            'passenger_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Passenger Count',
                'min': 10
            }),
            'travel_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Travel Date(s)'
            }),
        }


from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Booking, FlightLeg, Passenger

User = get_user_model()

# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta

from .models import User, Booking, FlightLeg, Passenger, Aircraft, Airport

class BookingForm(forms.ModelForm):
    """Form for creating/editing bookings"""
    
    class Meta:
        model = Booking
        fields = ['aircraft', 'trip_type', 'special_requests']
        widgets = {
            'aircraft': forms.Select(attrs={
                'class': 'form-control',
                'id': 'aircraft_select'
            }),
            'trip_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'trip_type_select'
            }),
            'special_requests': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any special requests or notes...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active aircraft
        self.fields['aircraft'].queryset = Aircraft.objects.filter(is_active=True).select_related('aircraft_type')
        
        # Add empty label
        self.fields['aircraft'].empty_label = "Select an aircraft"
        
        # Make fields required
        self.fields['aircraft'].required = True
        self.fields['trip_type'].required = True

class FlightLegForm(forms.ModelForm):
    """Form for individual flight legs"""
    
    class Meta:
        model = FlightLeg
        fields = [
            'departure_airport', 'arrival_airport', 
            'departure_datetime', 'arrival_datetime', 
            'flight_hours'
        ]
        widgets = {
            'departure_airport': forms.Select(attrs={
                'class': 'form-control airport-select',
                'data-type': 'departure'
            }),
            'arrival_airport': forms.Select(attrs={
                'class': 'form-control airport-select',
                'data-type': 'arrival'
            }),
            'departure_datetime': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'arrival_datetime': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'flight_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0.1',
                'placeholder': 'Flight duration in hours'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set airport choices
        self.fields['departure_airport'].queryset = Airport.objects.all().order_by('city', 'name')
        self.fields['arrival_airport'].queryset = Airport.objects.all().order_by('city', 'name')
        
        # Add empty labels
        self.fields['departure_airport'].empty_label = "Select departure airport"
        self.fields['arrival_airport'].empty_label = "Select arrival airport"
        
        # Make all fields required
        for field_name, field in self.fields.items():
            field.required = True
    
    def clean(self):
        cleaned_data = super().clean()
        departure_datetime = cleaned_data.get('departure_datetime')
        arrival_datetime = cleaned_data.get('arrival_datetime')
        departure_airport = cleaned_data.get('departure_airport')
        arrival_airport = cleaned_data.get('arrival_airport')
        
        # Validate dates
        if departure_datetime and arrival_datetime:
            if departure_datetime >= arrival_datetime:
                raise ValidationError("Departure time must be before arrival time.")
            
            # Check if departure is in the future (at least 2 hours from now)
            min_departure_time = timezone.now() + timedelta(hours=2)
            if departure_datetime < min_departure_time:
                raise ValidationError("Departure time must be at least 2 hours from now.")
        
        # Validate airports are different
        if departure_airport and arrival_airport:
            if departure_airport == arrival_airport:
                raise ValidationError("Departure and arrival airports must be different.")
        
        return cleaned_data

class PassengerForm(forms.ModelForm):
    """Form for passenger information"""
    
    class Meta:
        model = Passenger
        fields = ['name', 'nationality', 'date_of_birth', 'passport_number']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name as on passport'
            }),
            'nationality': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nationality'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'passport_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Passport number'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Name is required, others are optional
        self.fields['name'].required = True
        self.fields['nationality'].required = False
        self.fields['date_of_birth'].required = False
        self.fields['passport_number'].required = False
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = timezone.now().date()
            if dob > today:
                raise ValidationError("Date of birth cannot be in the future.")
            
            # Check if person is too old (reasonable limit)
            if (today - dob).days > 365 * 120:  # 120 years
                raise ValidationError("Invalid date of birth.")
        
        return dob

class ClientAccountForm(UserCreationForm):
    """Form for creating new client accounts"""
    
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address'
        })
    )
    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone number'
        })
    )
    company_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Company name (optional)'
        })
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Address (optional)'
        })
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email', 
            'phone_number', 'company_name', 'address', 
            'password1', 'password2'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Username'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Update password field widgets
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
        
        # Make certain fields required
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        self.fields['phone_number'].required = True
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username=username).exists():
            raise ValidationError("A user with this username already exists.")
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'client'
        user.is_active = True
        user.verified = False  # Will need to be verified later
        
        if commit:
            user.save()
        return user

class ClientSelectionForm(forms.Form):
    """Simple form for selecting existing clients"""
    
    client = forms.ModelChoiceField(
        queryset=User.objects.filter(user_type='client', is_active=True),
        empty_label="Select a client",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'client_select'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order clients by name for better UX
        self.fields['client'].queryset = User.objects.filter(
            user_type='client', 
            is_active=True
        ).order_by('first_name', 'last_name')




# forms.py
from django import forms
from .models import PricingRule

class PricingRuleForm(forms.ModelForm):
    class Meta:
        model = PricingRule
        fields = '__all__'
        widgets = {
            'aircraft_type': forms.Select(attrs={'class': 'form-select'}),
            'base_hourly_rate': forms.NumberInput(attrs={'class': 'form-control'}),
            'minimum_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'empty_leg_discount': forms.NumberInput(attrs={'class': 'form-control'}),
            'peak_season_multiplier': forms.NumberInput(attrs={'class': 'form-control'}),
            'weekend_surcharge': forms.NumberInput(attrs={'class': 'form-control'}),
            'last_minute_surcharge': forms.NumberInput(attrs={'class': 'form-control'}),
        }