from django.shortcuts import render
from django.shortcuts import render , redirect
from django.utils import timezone
from datetime import datetime, timedelta
from .models import *
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.db import models
from django.views.decorators.http import require_http_methods

from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from datetime import datetime, timedelta, time
from django.utils import timezone
from .models import Aircraft, Airport, Availability
from django.shortcuts import render, redirect
from .forms import GroupInquiryForm

def find_aircraft(request):
    if request.method == 'POST':
        # Get form data
        departure_icao = request.POST.get('departure_airport', '').upper().strip()
        arrival_icao = request.POST.get('arrival_airport', '').upper().strip()
        passenger_count = int(request.POST.get('passenger_count', 1))
        departure_date = request.POST.get('departure_date')
        departure_time = request.POST.get('departure_time', '09:00')  # Default time if not provided
        trip_type = request.POST.get('trip_type', 'one_way')
        
        # Handle return trip data
        return_date = request.POST.get('return_date') if trip_type == 'round_trip' else None
        return_time = request.POST.get('return_time', '17:00') if trip_type == 'round_trip' else None
        
        # Validate required fields
        if not all([departure_icao, arrival_icao, departure_date, passenger_count]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('index')
        
        # Get airport details
        try:
            departure_airport = Airport.objects.get(icao_code=departure_icao)
            arrival_airport = Airport.objects.get(icao_code=arrival_icao)
        except Airport.DoesNotExist as e:
            messages.error(request, 'One or both airports not found. Please select valid airports.')
            return redirect('index')
        
        # Convert dates to datetime objects
        try:
            departure_datetime = datetime.strptime(f"{departure_date} {departure_time}", "%Y-%m-%d %H:%M")
            # Make timezone aware if using timezone support
            if timezone.is_aware(timezone.now()):
                departure_datetime = timezone.make_aware(departure_datetime)
                
            return_datetime = None
            if return_date:
                return_datetime = datetime.strptime(f"{return_date} {return_time}", "%Y-%m-%d %H:%M")
                if timezone.is_aware(timezone.now()):
                    return_datetime = timezone.make_aware(return_datetime)
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
            return redirect('index')
        
        # Create date range for searching (entire day flexibility)
        departure_date_start = departure_datetime.replace(hour=0, minute=0, second=0)
        departure_date_end = departure_datetime.replace(hour=23, minute=59, second=59)
        
        # Search strategy: Find aircraft that can accommodate the trip
        available_aircraft = find_suitable_aircraft(
            departure_airport=departure_airport,
            arrival_airport=arrival_airport,
            departure_date_start=departure_date_start,
            departure_date_end=departure_date_end,
            passenger_count=passenger_count,
            return_datetime=return_datetime
        )
        
        # Calculate estimated flight duration and pricing
        aircraft_with_details = []
        for aircraft in available_aircraft:
            # Estimate flight time (simplified calculation)
            estimated_flight_hours = estimate_flight_time(departure_airport, arrival_airport)
            
            # Calculate base price
            base_price = calculate_base_price(aircraft, estimated_flight_hours, trip_type)
            
            aircraft_info = {
                'aircraft': aircraft,
                'estimated_flight_hours': estimated_flight_hours,
                'base_price': base_price,
                'total_price': base_price * (2 if trip_type == 'round_trip' else 1),
                'can_accommodate': aircraft.aircraft_type.passenger_capacity >= passenger_count,
                'availability_status': get_availability_status(aircraft, departure_date_start, departure_date_end)
            }
            aircraft_with_details.append(aircraft_info)
        
        # Sort by price and suitability
        aircraft_with_details.sort(key=lambda x: (not x['can_accommodate'], x['total_price']))
        
        context = {
            'aircraft_list': aircraft_with_details,
            'departure_airport': departure_airport,
            'arrival_airport': arrival_airport,
            'departure_datetime': departure_datetime,
            'return_datetime': return_datetime,
            'passenger_count': passenger_count,
            'trip_type': trip_type,
            'client_email': request.POST.get('client_email'),
            'client_name': request.POST.get('client_name'),
            'special_requests': request.POST.get('special_requests'),
            'search_performed': True,
            'total_results': len(aircraft_with_details)
        }
        
        if not aircraft_with_details:
            messages.info(request, f'No aircraft found for your route {departure_airport.name} to {arrival_airport.name} on {departure_date}. Try adjusting your search criteria.')
        
        return render(request, 'booking/available_aircraft.html', context)
    
    # If not POST, redirect back
    return redirect('index')


def find_suitable_aircraft(departure_airport, arrival_airport, departure_date_start, departure_date_end, passenger_count, return_datetime=None):
    """
    Find aircraft suitable for the trip with lenient criteria
    """
    # Primary search: Aircraft currently at departure location or nearby
    aircraft_at_departure = Aircraft.objects.filter(
        current_location=departure_airport.icao_code,
        is_active=True,
        aircraft_type__passenger_capacity__gte=passenger_count
    ).select_related('aircraft_type', 'owner')
    
    # Secondary search: Aircraft that could potentially be positioned
    # (within reasonable range - you might want to implement distance calculation)
    aircraft_nearby = Aircraft.objects.filter(
        is_active=True,
        aircraft_type__passenger_capacity__gte=passenger_count
    ).exclude(
        current_location=departure_airport.icao_code
    ).select_related('aircraft_type', 'owner')
    
    # Filter by availability (more lenient approach)
    suitable_aircraft = []
    
    # Check aircraft at departure location first
    for aircraft in aircraft_at_departure:
        if is_aircraft_available(aircraft, departure_date_start, departure_date_end, return_datetime):
            suitable_aircraft.append(aircraft)
    
    # If not enough options, check nearby aircraft (with positioning cost consideration)
    if len(suitable_aircraft) < 5:  # Show more options
        for aircraft in aircraft_nearby[:10]:  # Limit to avoid too many queries
            if is_aircraft_available(aircraft, departure_date_start, departure_date_end, return_datetime):
                suitable_aircraft.append(aircraft)
    
    return suitable_aircraft


def is_aircraft_available(aircraft, start_date, end_date, return_datetime=None):
    """
    Check if aircraft is available during the requested period
    More lenient than strict time matching
    """
    # Check for conflicting bookings or maintenance periods
    conflicting_availabilities = aircraft.availabilities.filter(
        start_datetime__lt=end_date,
        end_datetime__gt=start_date,
        is_available=False
    )
    
    if conflicting_availabilities.exists():
        return False
    
    # If it's a round trip, check return date availability too
    if return_datetime:
        return_date_start = return_datetime.replace(hour=0, minute=0, second=0)
        return_date_end = return_datetime.replace(hour=23, minute=59, second=59)
        
        conflicting_return = aircraft.availabilities.filter(
            start_datetime__lt=return_date_end,
            end_datetime__gt=return_date_start,
            is_available=False
        )
        
        if conflicting_return.exists():
            return False
    
    return True


def estimate_flight_time(departure_airport, arrival_airport):
    """
    Estimate flight time between two airports
    This is a simplified calculation - in reality you'd use great circle distance
    """
    # Simple calculation based on coordinates (very rough estimate)
    try:
        import math
        
        lat1, lon1 = float(departure_airport.latitude), float(departure_airport.longitude)
        lat2, lon2 = float(arrival_airport.latitude), float(arrival_airport.longitude)
        
        # Haversine formula for distance
        R = 3440  # Earth radius in nautical miles
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        # Assume average speed of 400 knots for jets, add 30 minutes for taxi/approach
        flight_time = (distance / 400) + 0.5
        
        return round(flight_time, 1)
    except:
        # Fallback: assume 2 hours for any flight
        return 2.0


def calculate_base_price(aircraft, flight_hours, trip_type):
    """
    Calculate base price for the flight
    """
    # Convert Decimal to float to avoid type mixing
    base_rate = float(aircraft.hourly_rate)
    minimum_hours = float(aircraft.minimum_hours)
    flight_hours_float = float(flight_hours)
    
    # Use minimum hours or actual flight time, whichever is higher
    billable_hours = max(flight_hours_float, minimum_hours)
    
    base_price = base_rate * billable_hours
    
    return round(base_price, 2)



def get_availability_status(aircraft, start_date, end_date):
    """
    Get a human-readable availability status
    """
    # Check if there are any specific availability windows
    availabilities = aircraft.availabilities.filter(
        start_datetime__lte=end_date,
        end_datetime__gte=start_date
    )
    
    if not availabilities.exists():
        return "Available (no restrictions)"
    
    available_windows = availabilities.filter(is_available=True)
    if available_windows.exists():
        return "Available"
    else:
        return "Limited availability"


# Additional helper view for AJAX requests (optional)
def quick_aircraft_search(request):
    """
    Quick AJAX search for aircraft availability
    """
    if request.method == 'GET':
        departure = request.GET.get('departure', '').upper()
        arrival = request.GET.get('arrival', '').upper()
        date = request.GET.get('date')
        passengers = int(request.GET.get('passengers', 1))
        
        if not all([departure, arrival, date, passengers]):
            return JsonResponse({'error': 'Missing required parameters'})
        
        try:
            departure_airport = Airport.objects.get(icao_code=departure)
            arrival_airport = Airport.objects.get(icao_code=arrival)
            
            # Quick count of available aircraft
            aircraft_count = Aircraft.objects.filter(
                current_location=departure,
                is_active=True,
                aircraft_type__passenger_capacity__gte=passengers
            ).count()
            
            return JsonResponse({
                'aircraft_count': aircraft_count,
                'route': f"{departure_airport.name} to {arrival_airport.name}",
                'estimated_flight_time': estimate_flight_time(departure_airport, arrival_airport)
            })
            
        except Airport.DoesNotExist:
            return JsonResponse({'error': 'Airport not found'})
    
    return JsonResponse({'error': 'Invalid request'})


def index(request):
    # Get all airports for the dropdown, ordered by name for better UX
    airports = Airport.objects.all().order_by('name')
    
    # Optional: Get aircraft types if you want to show them in the form later
    aircraft_types = AircraftType.objects.all().order_by('name')
    
    context = {
        'airports': airports,
        'aircraft_types': aircraft_types,
    }
    return render(request, 'index.html', context)


# Optional: Add this view for AJAX search functionality
def search_airports(request):
    """
    AJAX endpoint to search airports by name or city
    Useful if you have many airports and want to implement search-as-you-type
    """
    query = request.GET.get('q', '')
    if len(query) >= 2:  # Only search if at least 2 characters
        airports = Airport.objects.filter(
            models.Q(name__icontains=query) | 
            models.Q(city__icontains=query) |
            models.Q(icao_code__icontains=query) |
            models.Q(iata_code__icontains=query)
        ).order_by('name')[:20]  # Limit to 20 results
        
        airport_data = [
            {
                'id': airport.icao_code,
                'name': airport.name,
                'city': airport.city,
                'country': airport.country,
                'icao': airport.icao_code,
                'iata': airport.iata_code or '',
                'display': f"{airport.name} ({airport.city}, {airport.country}) - {airport.icao_code}"
            }
            for airport in airports
        ]
        
        return JsonResponse({'airports': airport_data})
    
    return JsonResponse({'airports': []})

def about_us(request):
    return render(request, 'about.html')

from django.shortcuts import render, redirect
from .models import ContactSubmission
from django.contrib import messages

def contact_us(request):
    if request.method == 'POST':
        try:
            ContactSubmission.objects.create(
                name=request.POST.get('name'),
                email=request.POST.get('email'),
                phone=request.POST.get('phone'),
                subject=request.POST.get('subject'),
                message=request.POST.get('message')
            )
            messages.success(request, 'Your message has been sent successfully!')
            return redirect('contact_us')  # Redirect to clear the form
        except Exception as e:
            messages.error(request, f'Error submitting form: {str(e)}')
    
    return render(request, 'contact-us.html')

def services(request):
    return render(request, 'service.html') 

def aircraft_leasing(request):
    return render(request, 'aircraft_leasing.html') 

def air_cargo(request):
    return render(request, 'air_cargo.html') 

def private_jet_charter(request):
    return render(request, 'private_jet_charter.html') 

from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render, redirect

@csrf_protect
def group_charter(request):
    if request.method == 'POST':
        group_name = request.POST.get('group_name')
        contact_email = request.POST.get('contact_email')
        passenger_count = request.POST.get('passenger_count')
        travel_date = request.POST.get('travel_date')

        GroupInquiry.objects.create(
            group_name=group_name,
            contact_email=contact_email,
            passenger_count=passenger_count,
            travel_date=travel_date
        )
        return redirect('index')  # or your success page

    return render(request, 'group_charter.html')

from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('index') 



import json
import logging
from django.http import JsonResponse
from django.contrib.auth import get_user_model, login
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError

User = get_user_model()
logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def api_signup(request):
    """Handle user registration via API"""
    try:
        # Parse form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone_number = request.POST.get('phone_number', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        user_type = request.POST.get('user_type', '')
        address = request.POST.get('address', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        tax_id = request.POST.get('tax_id', '').strip()
        agree_terms = request.POST.get('agree_terms') == 'on'
        marketing_emails = request.POST.get('marketing_emails') == 'on'
        
        errors = {}
        
        # Validate required fields
        if not first_name:
            errors['first_name'] = ['First name is required']
        if not last_name:
            errors['last_name'] = ['Last name is required']
        if not username:
            errors['username'] = ['Username is required']
        elif len(username) < 3:
            errors['username'] = ['Username must be at least 3 characters long']
        if not email:
            errors['email'] = ['Email is required']
        if not phone_number:
            errors['phone_number'] = ['Phone number is required']
        if not password1:
            errors['password1'] = ['Password is required']
        if not password2:
            errors['password2'] = ['Password confirmation is required']
        if not user_type:
            errors['user_type'] = ['Please select an account type']
        if not agree_terms:
            errors['agree_terms'] = ['You must agree to the terms and conditions']
        
        # Validate email format
        if email:
            try:
                validate_email(email)
            except ValidationError:
                errors['email'] = ['Please enter a valid email address']
        
        # Validate password match
        if password1 and password2 and password1 != password2:
            errors['password2'] = ['Passwords do not match']
        
        # Validate password strength
        if password1:
            try:
                validate_password(password1)
            except ValidationError as e:
                errors['password1'] = list(e.messages)
        
        # Check if username already exists
        if username and User.objects.filter(username=username).exists():
            errors['username'] = ['This username is already taken']
        
        # Check if email already exists
        if email and User.objects.filter(email=email).exists():
            errors['email'] = ['This email is already registered']
        
        # Validate user type specific requirements
        if user_type in ['owner', 'agent'] and not company_name:
            errors['company_name'] = ['Company name is required for this account type']
        
        # Return errors if any
        if errors:
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
        
        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                user_type=user_type,
                phone_number=phone_number,
                address=address if address else None,
                company_name=company_name if company_name else None,
                tax_id=tax_id if tax_id else None,
                verified=True  # Set to False, require email verification
            )
            
            logger.info(f"New user registered: {user.username} ({user.email})")
            
            # Optionally auto-login the user
            # login(request, user)
            
            return JsonResponse({
                'success': True,
                'message': 'Account created successfully! Please check your email for verification.',
                'user_id': user.id
            })
            
        except IntegrityError as e:
            logger.error(f"User creation failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'An account with this information already exists.'
            }, status=400)
            
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred during registration. Please try again.'
        }, status=500)

@require_http_methods(["GET"])
def check_username_availability(request):
    """Check if username is available"""
    username = request.GET.get('username', '').strip()
    
    if not username or len(username) < 3:
        return JsonResponse({'available': False, 'message': 'Username too short'})
    
    available = not User.objects.filter(username=username).exists()
    
    return JsonResponse({
        'available': available,
        'message': 'Username available' if available else 'Username already taken'
    })

@require_http_methods(["GET"])
def check_email_availability(request):
    """Check if email is available"""
    email = request.GET.get('email', '').strip().lower()
    
    if not email:
        return JsonResponse({'available': False, 'message': 'Email required'})
    
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'available': False, 'message': 'Invalid email format'})
    
    available = not User.objects.filter(email=email).exists()
    
    return JsonResponse({
        'available': available,
        'message': 'Email available' if available else 'Email already registered'
    })


# views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.db import transaction
import json
import logging
import uuid
from datetime import datetime

# Assuming you have these models - adjust imports based on your actual model structure
from .models import Aircraft, Booking, Passenger, Airport

logger = logging.getLogger(__name__)

@require_http_methods(["GET"])
def check_auth(request):
    """Check if user is authenticated"""
    return JsonResponse({
        'authenticated': request.user.is_authenticated,
        'user_id': request.user.id if request.user.is_authenticated else None,
        'username': request.user.username if request.user.is_authenticated else None
    })

import json
import logging
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)

@csrf_exempt  # Add this if you're not handling CSRF tokens properly
@require_http_methods(["POST"])
def api_login(request):
    """Handle user login via API"""
    try:
        # Parse JSON data if content-type is application/json
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            remember_me = data.get('remember_me', False)
        else:
            # Handle form data
            email = request.POST.get('email', '').strip().lower()
            password = request.POST.get('password', '')
            remember_me = request.POST.get('remember_me') == 'on'

        # Validate input
        if not email or not password:
            return JsonResponse({
                'success': False,
                'message': 'Email and password are required'
            }, status=400)

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({
                'success': False,
                'message': 'Please enter a valid email address'
            }, status=400)

        # Get user by email first, then authenticate
        try:
            user_obj = User.objects.get(email=email)
            # Use the username field for authentication
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            logger.warning(f"Failed login attempt for email: {email} - User not found")
            return JsonResponse({
                'success': False,
                'message': 'Invalid email or password'
            }, status=401)
        
        if user is not None:
            if user.is_active:
                # Check if user is verified (if you're using email verification)
                if not user.verified:
                    return JsonResponse({
                        'success': False,
                        'message': 'Please verify your email address before logging in.'
                    }, status=403)
                
                login(request, user)
                
                # Set session expiry based on remember_me
                if not remember_me:
                    request.session.set_expiry(0)  # Session expires when browser closes
                else:
                    request.session.set_expiry(1209600)  # 2 weeks
                
                logger.info(f"User {user.username} logged in successfully")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'user_type': user.user_type,
                        'verified': user.verified
                    }
                })
            else:
                logger.warning(f"Inactive user login attempt: {email}")
                return JsonResponse({
                    'success': False,
                    'message': 'Your account has been deactivated. Please contact support.'
                }, status=403)
        else:
            logger.warning(f"Failed login attempt for email: {email} - Invalid password")
            return JsonResponse({
                'success': False,
                'message': 'Invalid email or password'
            }, status=401)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred during login. Please try again.'
        }, status=500)

from decimal import Decimal
from datetime import timedelta

@require_http_methods(["POST"])
@login_required
def create_booking(request):
    """Handle booking creation"""
    try:
        # Parse form data
        data = request.POST
        
        # Extract booking details
        aircraft_id = data.get('aircraft_id')
        departure_airport_code = data.get('departure_airport')
        arrival_airport_code = data.get('arrival_airport')
        departure_datetime_str = data.get('departure_datetime')
        return_datetime_str = data.get('return_datetime')
        trip_type = data.get('trip_type', 'one_way')
        passenger_count = int(data.get('passenger_count', 1))
        
        # Client information
        client_name = data.get('client_name', '').strip()
        client_email = data.get('client_email', '').strip().lower()
        client_phone = data.get('client_phone', '').strip()
        company_name = data.get('company_name', '').strip()
        
        # Flight preferences
        departure_time = data.get('departure_time')
        return_time = data.get('return_time')
        special_requests = data.get('special_requests', '').strip()
        catering_required = data.get('catering_required') == 'on'
        ground_transport = data.get('ground_transport') == 'on'
        
        # Commission rate (you may want to set this based on user/business logic)
        commission_rate = Decimal(data.get('commission_rate', '10.00'))  # Default 10%
        
        # Validation
        errors = []
        
        if not aircraft_id:
            errors.append("Aircraft selection is required")
        
        if not client_name:
            errors.append("Client name is required")
        
        if not client_email:
            errors.append("Client email is required")
        else:
            try:
                validate_email(client_email)
            except ValidationError:
                errors.append("Please enter a valid email address")
        
        if not client_phone:
            errors.append("Phone number is required")
        
        if not departure_datetime_str:
            errors.append("Departure date and time is required")
        
        if trip_type == 'round_trip' and not return_datetime_str:
            errors.append("Return date and time is required for round trip")
        
        if passenger_count < 1:
            errors.append("At least one passenger is required")
        
        # Validate passenger information
        passengers_data = []
        for i in range(1, passenger_count + 1):
            passenger_name = data.get(f'passenger_{i}_name', '').strip()
            passenger_dob = data.get(f'passenger_{i}_dob', '').strip()
            passenger_passport = data.get(f'passenger_{i}_passport', '').strip()
            passenger_nationality = data.get(f'passenger_{i}_nationality', '').strip()
            
            if not passenger_name:
                errors.append(f"Passenger {i} name is required")
            
            passengers_data.append({
                'name': passenger_name,
                'date_of_birth': passenger_dob if passenger_dob else None,
                'passport_number': passenger_passport,
                'nationality': passenger_nationality
            })
        
        if errors:
            return JsonResponse({
                'success': False,
                'message': 'Please correct the following errors: ' + '; '.join(errors)
            }, status=400)
        
        # Get related objects
        try:
            aircraft = get_object_or_404(Aircraft, id=aircraft_id)
            departure_airport = get_object_or_404(Airport, icao_code=departure_airport_code)
            arrival_airport = get_object_or_404(Airport, icao_code=arrival_airport_code)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Invalid aircraft or airport selection: {str(e)}'
            }, status=400)
        
        # Parse datetime strings
        try:
            departure_datetime = datetime.strptime(departure_datetime_str, '%Y-%m-%d %H:%M')
            departure_datetime = timezone.make_aware(departure_datetime)
            
            return_datetime = None
            if return_datetime_str:
                return_datetime = datetime.strptime(return_datetime_str, '%Y-%m-%d %H:%M')
                return_datetime = timezone.make_aware(return_datetime)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'message': f'Invalid date format: {str(e)}'
            }, status=400)
        
        # Calculate flight hours (you may need to implement this based on your business logic)
        def calculate_flight_hours(departure_airport, arrival_airport):
            # This is a placeholder - implement your actual flight time calculation
            # You might want to use distance calculation or a lookup table
            return Decimal('2.5')  # Default 2.5 hours
        
        # Calculate pricing
        base_hourly_rate = aircraft.hourly_rate if hasattr(aircraft, 'hourly_rate') else Decimal('1000.00')
        flight_hours = calculate_flight_hours(departure_airport, arrival_airport)
        leg_price = base_hourly_rate * flight_hours
        
        # Calculate total price based on trip type
        if trip_type == 'round_trip':
            total_price = leg_price * 2
        else:
            total_price = leg_price
        
        # Calculate commission and owner earnings
        agent_commission = total_price * (commission_rate / 100)
        owner_earnings = total_price - agent_commission
        
        # Create booking with transaction
        with transaction.atomic():
            # Create booking
            booking = Booking.objects.create(
                client=request.user,  # Changed from 'user' to 'client'
                aircraft=aircraft,
                trip_type=trip_type,
                commission_rate=commission_rate,
                total_price=total_price,
                agent_commission=agent_commission,
                owner_earnings=owner_earnings,
                special_requests=special_requests,
                status='pending'
            )
            
            # Create flight legs
            flight_legs = []
            
            # First leg (departure)
            arrival_datetime = departure_datetime + timedelta(hours=float(flight_hours))
            first_leg = FlightLeg.objects.create(
                booking=booking,
                departure_airport=departure_airport,
                arrival_airport=arrival_airport,
                departure_datetime=departure_datetime,
                arrival_datetime=arrival_datetime,
                flight_hours=flight_hours,
                passenger_count=passenger_count,
                leg_price=leg_price,
                sequence=1
            )
            flight_legs.append(first_leg)
            
            # Second leg for round trip
            if trip_type == 'round_trip' and return_datetime:
                return_arrival_datetime = return_datetime + timedelta(hours=float(flight_hours))
                second_leg = FlightLeg.objects.create(
                    booking=booking,
                    departure_airport=arrival_airport,  # Swap airports for return
                    arrival_airport=departure_airport,
                    departure_datetime=return_datetime,
                    arrival_datetime=return_arrival_datetime,
                    flight_hours=flight_hours,
                    passenger_count=passenger_count,
                    leg_price=leg_price,
                    sequence=2
                )
                flight_legs.append(second_leg)
            
            # Create passenger records (assuming you have a Passenger model)
            for i, passenger_data in enumerate(passengers_data):
                Passenger.objects.create(
                    booking=booking,
                    name=passenger_data['name'],
                    date_of_birth=passenger_data['date_of_birth'],
                    passport_number=passenger_data['passport_number'],
                    nationality=passenger_data['nationality']
                )

            
            # Log the booking creation
            logger.info(f"Booking created: #{booking.id} by user {request.user.username}")
            
            # You might want to send confirmation email here
            # send_booking_confirmation_email(booking)
            
            return JsonResponse({
                'success': True,
                'message': 'Booking request submitted successfully',
                'booking_id': booking.id,
                'total_price': float(total_price),
                'agent_commission': float(agent_commission),
                'owner_earnings': float(owner_earnings),
                'flight_legs': [
                    {
                        'sequence': leg.sequence,
                        'departure': f"{leg.departure_airport.icao_code}",
                        'arrival': f"{leg.arrival_airport.icao_code}",
                        'departure_time': leg.departure_datetime.isoformat(),
                        'flight_hours': float(leg.flight_hours),
                        'leg_price': float(leg.leg_price)
                    } for leg in flight_legs
                ]
            })
    
    except Exception as e:
        logger.error(f"Booking creation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while processing your booking. Please try again.'
        }, status=500)

# Alternative login view if you're using email as the username field
@require_http_methods(["POST"])
def api_login_with_email(request):
    """Handle user login via API using email lookup"""
    try:
        from django.contrib.auth.models import User
        
        # Parse data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            remember_me = data.get('remember_me', False)
        else:
            email = request.POST.get('email', '').strip().lower()
            password = request.POST.get('password', '')
            remember_me = request.POST.get('remember_me') == 'on'

        # Validate input
        if not email or not password:
            return JsonResponse({
                'success': False,
                'message': 'Email and password are required'
            }, status=400)

        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({
                'success': False,
                'message': 'Please enter a valid email address'
            }, status=400)

        # Find user by email
        try:
            user = User.objects.get(email=email)
            # Authenticate using username
            user = authenticate(request, username=user.username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None and user.is_active:
            login(request, user)
            
            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)
            
            logger.info(f"User {user.username} logged in successfully via email")
            
            return JsonResponse({
                'success': True,
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
            })
        else:
            logger.warning(f"Failed login attempt for email: {email}")
            return JsonResponse({
                'success': False,
                'message': 'Invalid email or password'
            }, status=401)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred during login. Please try again.'
        }, status=500)

# Utility function for sending booking confirmation email (optional)
def send_booking_confirmation_email(booking):
    """Send booking confirmation email to client"""
    try:
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.conf import settings
        
        subject = f'Booking Confirmation - {booking.booking_reference}'
        
        # Render email template
        html_message = render_to_string('emails/booking_confirmation.html', {
            'booking': booking,
            'passengers': booking.passengers.all()
        })
        
        plain_message = render_to_string('emails/booking_confirmation.txt', {
            'booking': booking,
            'passengers': booking.passengers.all()
        })
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [booking.client_email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Confirmation email sent for booking {booking.booking_reference}")
        
    except Exception as e:
        logger.error(f"Failed to send confirmation email for booking {booking.booking_reference}: {str(e)}")
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import AirCargoRequest, AircraftLeasingInquiry
import json

@csrf_exempt
@require_POST
def submit_cargo_request(request):
    try:
        data = json.loads(request.body)
        
        cargo_request = AirCargoRequest(
            request_type=data['request_type'],
            departure=data['departure'],
            destination=data['destination'],
            date=data['date'],
            departure_time=data.get('departure_time'),
            name=data['name'],
            company=data.get('company', ''),
            email=data['email'],
            telephone=data['telephone'],
            cargo_details=data['cargo_details'],
            special_requirements=data.get('special_requirements', '')
        )
        cargo_request.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Your cargo request has been submitted successfully!'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@csrf_exempt
@require_POST
def submit_leasing_inquiry(request):
    try:
        data = json.loads(request.body)
        
        leasing_inquiry = AircraftLeasingInquiry(
            leasing_type=data['leasing_type'],
            name=data['name'],
            company=data.get('company', ''),
            email=data['email'],
            telephone=data['telephone'],
            requirements=data['requirements'],
            duration=data.get('duration', '')
        )
        leasing_inquiry.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Your leasing inquiry has been submitted successfully!'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
    


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login


@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(username=email, password=password)
        
        if user is not None:
            login(request, user)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'message': 'Invalid credentials'}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def signup_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if User.objects.filter(username=email).exists():
            return JsonResponse({'success': False, 'message': 'Email already exists'}, status=400)
            
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name.split()[0],
            last_name=' '.join(name.split()[1:]) if ' ' in name else ''
        )
        
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid request'}, status=400)

