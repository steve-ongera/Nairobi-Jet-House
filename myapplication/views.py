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


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Inquiry  # Assuming you have an Inquiry model

@csrf_exempt  # Only if you're having CSRF issues, otherwise remove this
def save_inquiry(request):
    if request.method == 'POST':
        try:
            # Create and save the inquiry
            inquiry = Inquiry(
                full_name=request.POST.get('fullName'),
                email=request.POST.get('email'),
                phone=request.POST.get('phone'),
                aircraft_type_id=request.POST.get('aircraftType'),
                departure=request.POST.get('departure'),
                destination=request.POST.get('destination'),
                passengers=request.POST.get('passengers'),
                travel_date=request.POST.get('date')
            )
            inquiry.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


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
    # Get all airports for the dropdown, ordered by name for better UX
    airports = Airport.objects.all().order_by('name')
    
    # Optional: Get aircraft types if you want to show them in the form later
    aircraft_types = AircraftType.objects.all().order_by('name')
    
    context = {
        'airports': airports,
        'aircraft_types': aircraft_types,
    }
    return render(request, 'private_jet_charter.html', context) 

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
    


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login
from django.contrib import messages

@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        try:
            # Parse JSON data from request body
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')
            
            # Validate required fields
            if not email or not password:
                messages.error(request, 'Email and password are required')
                return JsonResponse({
                    'success': False, 
                    'message': 'Email and password are required'
                }, status=400)
            
            # Authenticate user
            user = authenticate(username=email, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name or user.username}! You have successfully logged in.')
                return JsonResponse({'success': True})
            else:
                messages.error(request, 'Invalid email or password. Please try again.')
                return JsonResponse({
                    'success': False, 
                    'message': 'Invalid credentials'
                }, status=400)
                
        except json.JSONDecodeError:
            messages.error(request, 'Invalid data format received')
            return JsonResponse({
                'success': False, 
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            messages.error(request, 'An unexpected error occurred. Please try again.')
            return JsonResponse({
                'success': False, 
                'message': 'Server error occurred'
            }, status=500)
    
    messages.error(request, 'Invalid request method')
    return JsonResponse({'error': 'Invalid request method'}, status=405)


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.contrib import messages

# Get your custom User model
User = get_user_model()

@csrf_exempt
def signup_view(request):
    if request.method == 'POST':
        try:
            # Parse JSON data from request body
            data = json.loads(request.body)
            name = data.get('name')
            email = data.get('email')
            password = data.get('password')
            
            # Validate required fields
            if not name or not email or not password:
                messages.error(request, 'Name, email, and password are required')
                return JsonResponse({
                    'success': False, 
                    'message': 'Name, email, and password are required'
                }, status=400)
            
            # Check if user already exists (check both username and email)
            if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
                messages.error(request, 'An account with this email already exists. Please use a different email or try logging in.')
                return JsonResponse({
                    'success': False, 
                    'message': 'Email already exists'
                }, status=400)
            
            # Split name safely
            name_parts = name.strip().split()
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            
            # Create user with your custom User model
            user = User.objects.create_user(
                username=email,  # Use email as username
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            messages.success(request, f'Welcome {first_name}! Your account has been created successfully. You can now log in.')
            return JsonResponse({'success': True})
            
        except json.JSONDecodeError:
            messages.error(request, 'Invalid data format received')
            return JsonResponse({
                'success': False, 
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            messages.error(request, 'An unexpected error occurred during registration. Please try again.')
            return JsonResponse({
                'success': False, 
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    messages.error(request, 'Invalid request method')
    return JsonResponse({'error': 'Invalid request method'}, status=405)




from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count, Sum, Q
from datetime import timedelta
from .models import (
    User, Aircraft, Booking, FlightLeg, 
    Availability, AircraftTracking, OwnerPayout,
    Inquiry, AirCargoRequest, AircraftLeasingInquiry
)
import json

def admin_dashboard(request):
    if not request.user.is_authenticated or request.user.user_type != 'admin':
        return redirect('login')
    
    # Date calculations
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    # User statistics
    total_clients = User.objects.filter(user_type='client').count()
    total_owners = User.objects.filter(user_type='owner').count()
    total_agents = User.objects.filter(user_type='agent').count()
    
    # Aircraft statistics
    total_aircraft = Aircraft.objects.count()
    active_aircraft = Aircraft.objects.filter(is_active=True).count()
    
    # Booking statistics
    total_bookings = Booking.objects.count()
    today_bookings = Booking.objects.filter(
        flight_legs__departure_datetime__date=today
    ).distinct().count()
    monthly_revenue = Booking.objects.filter(
        created_at__gte=thirty_days_ago
    ).aggregate(total=Sum('total_price'))['total'] or 0
    
    # Booking status breakdown
    booking_status = Booking.objects.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Recent bookings
    recent_bookings = Booking.objects.select_related(
        'client', 'aircraft', 'aircraft__aircraft_type'
    ).prefetch_related('flight_legs').order_by('-created_at')[:10]
    
    # Aircraft type distribution
    aircraft_types = AircraftType.objects.annotate(
        count=Count('aircraft')
    ).order_by('-count')[:5]
    
    # Revenue trends (last 7 days)
    revenue_data = []
    date_labels = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        date_labels.append(date.strftime('%b %d'))
        daily_revenue = Booking.objects.filter(
            flight_legs__departure_datetime__date=date
        ).aggregate(total=Sum('total_price'))['total'] or 0
        revenue_data.append(float(daily_revenue))
    
    # Inquiry statistics
    recent_inquiries = Inquiry.objects.select_related(
        'aircraft_type'
    ).order_by('-submitted_at')[:5]
    
    # Aircraft locations
    active_flights = AircraftTracking.objects.select_related(
        'aircraft', 'aircraft__aircraft_type'
    ).order_by('-timestamp')[:5]
    
    # Payment method breakdown
    payment_methods = {
        'Credit Card': 65,
        'Bank Transfer': 20,
        'Mobile Money': 10,
        'Cash': 5
    }
    
    context = {
        'total_clients': total_clients,
        'total_owners': total_owners,
        'total_agents': total_agents,
        'total_aircraft': total_aircraft,
        'active_aircraft': active_aircraft,
        'total_bookings': total_bookings,
        'today_bookings': today_bookings,
        'monthly_revenue': monthly_revenue,
        'booking_status': booking_status,
        'recent_bookings': recent_bookings,
        'aircraft_types': aircraft_types,
        'revenue_labels': json.dumps(date_labels),
        'revenue_data': json.dumps(revenue_data),
        'payment_methods': payment_methods,
        'recent_inquiries': recent_inquiries,
        'active_flights': active_flights,
    }
    
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def admin_logout_view(request):
    logout(request)
    messages.success(request , 'logged out sucessfullyy !')
    return redirect('admin-login')  # Make sure this name matches your admin login URL name

def admin_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # Redirect based on user_type
            if user.user_type == 'client':
                return redirect('client_dashboard')
            elif user.user_type == 'owner':
                return redirect('owner_dashboard')
            elif user.user_type == 'agent':
                return redirect('agent_dashboard')
            elif user.user_type == 'admin':
                messages.success(request , 'welcome back admin !')
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Unknown user type.')
                return redirect('login')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'auth/login.html')



from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import User

def client_list(request):
    # Get all clients (filter by user_type='client')
    clients = User.objects.filter(user_type='client').order_by('-date_joined')
    
    # Pagination
    paginator = Paginator(clients, 10)  # Show 10 clients per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'clients/clients.html', context)

def client_detail(request, client_id):
    try:
        client = User.objects.get(id=client_id, user_type='client')
        data = {
            'success': True,
            'client': {
                'id': client.id,
                'full_name': client.get_full_name(),
                'email': client.email,
                'phone_number': client.phone_number,
                'company_name': client.company_name,
                'address': client.address,
                'tax_id': client.tax_id,
                'verified': 'Yes' if client.verified else 'No',
                'date_joined': client.date_joined.strftime("%b %d, %Y %I:%M %p"),
                'last_login': client.last_login.strftime("%b %d, %Y %I:%M %p") if client.last_login else 'Never',
            }
        }
    except User.DoesNotExist:
        data = {
            'success': False,
            'error': 'Client not found'
        }
    return JsonResponse(data)



def aircraft_owner_list(request):
    # Get all aircraft owners
    owners = User.objects.filter(user_type='owner').order_by('-date_joined')
    
    # Pagination
    paginator = Paginator(owners, 10)  # Show 10 owners per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'owners/aircraftowners.html', context)

def aircraft_owner_detail(request, owner_id):
    try:
        owner = User.objects.get(id=owner_id, user_type='owner')
        data = {
            'success': True,
            'owner': {
                'id': owner.id,
                'full_name': owner.get_full_name(),
                'email': owner.email,
                'phone_number': owner.phone_number,
                'company_name': owner.company_name,
                'address': owner.address,
                'tax_id': owner.tax_id,
                'verified': owner.verified,
                'date_joined': owner.date_joined.strftime("%Y-%m-%d"),
                'last_login': owner.last_login.strftime("%Y-%m-%d %H:%M") if owner.last_login else 'Never',
            }
        }
    except User.DoesNotExist:
        data = {
            'success': False,
            'error': 'Aircraft owner not found'
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def update_aircraft_owner(request, owner_id):
    try:
        owner = User.objects.get(id=owner_id, user_type='owner')
        owner.company_name = request.POST.get('company_name', owner.company_name)
        owner.phone_number = request.POST.get('phone_number', owner.phone_number)
        owner.address = request.POST.get('address', owner.address)
        owner.tax_id = request.POST.get('tax_id', owner.tax_id)
        owner.verified = request.POST.get('verified') == 'true'
        owner.save()
        
        data = {
            'success': True,
            'message': 'Owner updated successfully',
            'owner': {
                'id': owner.id,
                'company_name': owner.company_name,
                'verified': owner.verified,
            }
        }
    except User.DoesNotExist:
        data = {
            'success': False,
            'error': 'Aircraft owner not found'
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def delete_aircraft_owner(request, owner_id):
    try:
        owner = User.objects.get(id=owner_id, user_type='owner')
        owner.delete()
        data = {
            'success': True,
            'message': 'Owner deleted successfully'
        }
    except User.DoesNotExist:
        data = {
            'success': False,
            'error': 'Aircraft owner not found'
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import IntegrityError
import json
from .models import Aircraft, AircraftType, User

def aircraft_list(request):
    """List all aircrafts with pagination"""
    aircrafts = Aircraft.objects.select_related('owner', 'aircraft_type').all()
    
    # Filter by active status if specified
    is_active = request.GET.get('is_active')
    if is_active is not None:
        aircrafts = aircrafts.filter(is_active=is_active.lower() == 'true')
    
    # Search functionality
    search = request.GET.get('search', '')
    if search:
        aircrafts = aircrafts.filter(
            models.Q(registration_number__icontains=search) |
            models.Q(model_name__icontains=search) |
            models.Q(owner__username__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(aircrafts, 10)  # 10 aircrafts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'aircrafts': page_obj,
        'search': search,
        'is_active': is_active,
    }
    return render(request, 'aircraft/aircraft_list.html', context)

@require_http_methods(["GET"])
def aircraft_detail_ajax(request, aircraft_id):
    """Get aircraft details via AJAX"""
    try:
        aircraft = get_object_or_404(
            Aircraft.objects.select_related('owner', 'aircraft_type'),
            id=aircraft_id
        )
        
        data = {
            'id': aircraft.id,
            'registration_number': aircraft.registration_number,
            'model_name': aircraft.model_name,
            'year_manufactured': aircraft.year_manufactured,
            'base_airport': aircraft.base_airport,
            'current_location': aircraft.current_location,
            'is_active': aircraft.is_active,
            'features': aircraft.features,
            'hourly_rate': str(aircraft.hourly_rate),
            'minimum_hours': str(aircraft.minimum_hours),
            'owner_id': aircraft.owner.id,
            'owner_name': aircraft.owner.get_full_name() or aircraft.owner.username,
            'aircraft_type_id': aircraft.aircraft_type.id,
            'aircraft_type_name': aircraft.aircraft_type.name,
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Aircraft.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Aircraft not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_http_methods(["POST"])
def aircraft_update_ajax(request, aircraft_id):
    """Update aircraft via AJAX"""
    try:
        aircraft = get_object_or_404(Aircraft, id=aircraft_id)
        data = json.loads(request.body)
        
        # Update fields
        aircraft.registration_number = data.get('registration_number', aircraft.registration_number)
        aircraft.model_name = data.get('model_name', aircraft.model_name)
        aircraft.year_manufactured = int(data.get('year_manufactured', aircraft.year_manufactured))
        aircraft.base_airport = data.get('base_airport', aircraft.base_airport)
        aircraft.current_location = data.get('current_location', aircraft.current_location)
        aircraft.is_active = data.get('is_active', aircraft.is_active)
        aircraft.features = data.get('features', aircraft.features)
        aircraft.hourly_rate = float(data.get('hourly_rate', aircraft.hourly_rate))
        aircraft.minimum_hours = float(data.get('minimum_hours', aircraft.minimum_hours))
        
        # Update foreign keys if provided
        if 'owner_id' in data:
            owner = get_object_or_404(User, id=data['owner_id'])
            aircraft.owner = owner
            
        if 'aircraft_type_id' in data:
            aircraft_type = get_object_or_404(AircraftType, id=data['aircraft_type_id'])
            aircraft.aircraft_type = aircraft_type
        
        aircraft.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Aircraft updated successfully',
            'data': {
                'id': aircraft.id,
                'registration_number': aircraft.registration_number,
                'model_name': aircraft.model_name,
                'is_active': aircraft.is_active,
            }
        })
        
    except Aircraft.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Aircraft not found'})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Owner not found'})
    except AircraftType.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Aircraft type not found'})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': f'Invalid data: {str(e)}'})
    except IntegrityError as e:
        return JsonResponse({'success': False, 'error': 'Registration number already exists'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_http_methods(["DELETE"])
def aircraft_delete_ajax(request, aircraft_id):
    """Delete aircraft via AJAX"""
    try:
        aircraft = get_object_or_404(Aircraft, id=aircraft_id)
        aircraft_info = f"{aircraft.model_name} ({aircraft.registration_number})"
        aircraft.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Aircraft {aircraft_info} deleted successfully'
        })
        
    except Aircraft.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Aircraft not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def get_dropdown_data(request):
    """Get data for dropdowns (owners and aircraft types)"""
    try:
        owners = User.objects.filter(user_type__in=['owner', 'admin']).values('id', 'username', 'first_name', 'last_name')
        aircraft_types = AircraftType.objects.all().values('id', 'name')
        
        return JsonResponse({
            'success': True,
            'owners': list(owners),
            'aircraft_types': list(aircraft_types)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
# views.py
# views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings
from django.core.files.storage import default_storage
import json
import os
from .models import AircraftType


def aircraft_types_view(request):
    """Main view for aircraft types management page"""
    try:
        # Get search parameters
        search = request.GET.get('search', '')
        sort_by = request.GET.get('sort_by', 'name')
        capacity_filter = request.GET.get('capacity_filter', '')
        
        # Base queryset
        queryset = AircraftType.objects.all()
        
        # Apply search filter
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        
        # Apply capacity filter
        if capacity_filter:
            if capacity_filter == 'small':
                queryset = queryset.filter(passenger_capacity__lte=10)
            elif capacity_filter == 'medium':
                queryset = queryset.filter(passenger_capacity__gt=10, passenger_capacity__lte=50)
            elif capacity_filter == 'large':
                queryset = queryset.filter(passenger_capacity__gt=50)
        
        # Apply sorting
        valid_sort_fields = ['name', 'passenger_capacity', 'range_nautical_miles', 'speed_knots']
        if sort_by in valid_sort_fields:
            if sort_by == 'name':
                queryset = queryset.order_by('name')
            else:
                queryset = queryset.order_by(f'-{sort_by}')  # Descending for numeric fields
        
        # Convert to list of dictionaries for JavaScript
        aircraft_data = []
        for aircraft in queryset:
            aircraft_data.append({
                'id': aircraft.id,
                'name': aircraft.name,
                'description': aircraft.description,
                'image': aircraft.image.url if aircraft.image else None,
                'passenger_capacity': aircraft.passenger_capacity,
                'range_nautical_miles': aircraft.range_nautical_miles,
                'speed_knots': aircraft.speed_knots,
            })
        
        context = {
            'aircraft_types': queryset,  # For template rendering
            'aircraft_data_json': json.dumps(aircraft_data),  # For JavaScript
            'search': search,
            'sort_by': sort_by,
            'capacity_filter': capacity_filter,
        }
        
        return render(request, 'aircraft_types/aircraft_types.html', context)
    
    except Exception as e:
        # If there's an error, still render the template but with empty data
        context = {
            'aircraft_types': AircraftType.objects.none(),
            'aircraft_data_json': json.dumps([]),
            'error_message': str(e),
        }
        return render(request, 'aircraft_types/aircraft_types.html', context)


@require_http_methods(["GET"])
def aircraft_types_api_list(request):
    """API endpoint to get all aircraft types"""
    try:
        # Get search parameters
        search = request.GET.get('search', '')
        sort_by = request.GET.get('sort_by', 'name')
        capacity_filter = request.GET.get('capacity_filter', '')
        
        # Base queryset
        queryset = AircraftType.objects.all()
        
        # Apply search filter
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        
        # Apply capacity filter
        if capacity_filter:
            if capacity_filter == 'small':
                queryset = queryset.filter(passenger_capacity__lte=10)
            elif capacity_filter == 'medium':
                queryset = queryset.filter(passenger_capacity__gt=10, passenger_capacity__lte=50)
            elif capacity_filter == 'large':
                queryset = queryset.filter(passenger_capacity__gt=50)
        
        # Apply sorting
        valid_sort_fields = ['name', 'passenger_capacity', 'range_nautical_miles', 'speed_knots']
        if sort_by in valid_sort_fields:
            if sort_by == 'name':
                queryset = queryset.order_by('name')
            else:
                queryset = queryset.order_by(f'-{sort_by}')  # Descending for numeric fields
        
        # Convert to list of dictionaries
        aircraft_data = []
        for aircraft in queryset:
            aircraft_data.append({
                'id': aircraft.id,
                'name': aircraft.name,
                'description': aircraft.description,
                'image': aircraft.image.url if aircraft.image else None,
                'passenger_capacity': aircraft.passenger_capacity,
                'range_nautical_miles': aircraft.range_nautical_miles,
                'speed_knots': aircraft.speed_knots,
            })
        
        return JsonResponse(aircraft_data, safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def aircraft_type_api_detail(request, pk):
    """API endpoint to get a specific aircraft type"""
    try:
        aircraft = get_object_or_404(AircraftType, pk=pk)
        
        data = {
            'id': aircraft.id,
            'name': aircraft.name,
            'description': aircraft.description,
            'image': aircraft.image.url if aircraft.image else None,
            'passenger_capacity': aircraft.passenger_capacity,
            'range_nautical_miles': aircraft.range_nautical_miles,
            'speed_knots': aircraft.speed_knots,
        }
        
        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def aircraft_type_api_create(request):
    """API endpoint to create a new aircraft type"""
    try:
        # Get data from POST request
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        passenger_capacity = request.POST.get('passenger_capacity')
        range_nautical_miles = request.POST.get('range_nautical_miles')
        speed_knots = request.POST.get('speed_knots')
        image = request.FILES.get('image')
        
        # Validate required fields
        if not name or not passenger_capacity or not range_nautical_miles or not speed_knots:
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        try:
            passenger_capacity = int(passenger_capacity)
            range_nautical_miles = int(range_nautical_miles)
            speed_knots = int(speed_knots)
        except ValueError:
            return JsonResponse({'error': 'Invalid numeric values'}, status=400)
        
        # Validate positive values
        if passenger_capacity <= 0 or range_nautical_miles <= 0 or speed_knots <= 0:
            return JsonResponse({'error': 'Numeric values must be positive'}, status=400)
        
        # Create new aircraft type
        aircraft = AircraftType.objects.create(
            name=name,
            description=description,
            passenger_capacity=passenger_capacity,
            range_nautical_miles=range_nautical_miles,
            speed_knots=speed_knots,
            image=image
        )
        
        return JsonResponse({
            'id': aircraft.id,
            'name': aircraft.name,
            'description': aircraft.description,
            'image': aircraft.image.url if aircraft.image else None,
            'passenger_capacity': aircraft.passenger_capacity,
            'range_nautical_miles': aircraft.range_nautical_miles,
            'speed_knots': aircraft.speed_knots,
            'message': 'Aircraft type created successfully'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["PUT", "POST"])
def aircraft_type_api_update(request, pk):
    """API endpoint to update an existing aircraft type"""
    try:
        aircraft = get_object_or_404(AircraftType, pk=pk)
        
        # Get data from request
        if request.method == 'PUT':
            # For PUT requests, we need to parse the request body
            import json
            try:
                data = json.loads(request.body)
                files = {}
            except:
                # If JSON parsing fails, try to get from POST data
                data = request.POST
                files = request.FILES
        else:
            data = request.POST
            files = request.FILES
        
        # Update fields if provided
        if 'name' in data:
            aircraft.name = data['name']
        
        if 'description' in data:
            aircraft.description = data['description']
        
        if 'passenger_capacity' in data:
            try:
                capacity = int(data['passenger_capacity'])
                if capacity <= 0:
                    return JsonResponse({'error': 'Passenger capacity must be positive'}, status=400)
                aircraft.passenger_capacity = capacity
            except ValueError:
                return JsonResponse({'error': 'Invalid passenger capacity'}, status=400)
        
        if 'range_nautical_miles' in data:
            try:
                range_nm = int(data['range_nautical_miles'])
                if range_nm <= 0:
                    return JsonResponse({'error': 'Range must be positive'}, status=400)
                aircraft.range_nautical_miles = range_nm
            except ValueError:
                return JsonResponse({'error': 'Invalid range value'}, status=400)
        
        if 'speed_knots' in data:
            try:
                speed = int(data['speed_knots'])
                if speed <= 0:
                    return JsonResponse({'error': 'Speed must be positive'}, status=400)
                aircraft.speed_knots = speed
            except ValueError:
                return JsonResponse({'error': 'Invalid speed value'}, status=400)
        
        # Handle image update
        if 'image' in files:
            # Delete old image if exists
            if aircraft.image:
                old_image_path = aircraft.image.path
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            
            aircraft.image = files['image']
        
        aircraft.save()
        
        return JsonResponse({
            'id': aircraft.id,
            'name': aircraft.name,
            'description': aircraft.description,
            'image': aircraft.image.url if aircraft.image else None,
            'passenger_capacity': aircraft.passenger_capacity,
            'range_nautical_miles': aircraft.range_nautical_miles,
            'speed_knots': aircraft.speed_knots,
            'message': 'Aircraft type updated successfully'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def aircraft_type_api_delete(request, pk):
    """API endpoint to delete an aircraft type"""
    try:
        aircraft = get_object_or_404(AircraftType, pk=pk)
        
        # Delete associated image file if exists
        if aircraft.image:
            image_path = aircraft.image.path
            if os.path.exists(image_path):
                os.remove(image_path)
        
        aircraft_name = aircraft.name
        aircraft.delete()
        
        return JsonResponse({
            'message': f'Aircraft type "{aircraft_name}" deleted successfully'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Combined API view for handling multiple HTTP methods
@csrf_exempt
def aircraft_types_api(request):
    """Combined API endpoint for aircraft types"""
    if request.method == 'GET':
        return aircraft_types_api_list(request)
    elif request.method == 'POST':
        return aircraft_type_api_create(request)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt  
def aircraft_type_api(request, pk):
    """Combined API endpoint for individual aircraft type"""
    if request.method == 'GET':
        return aircraft_type_api_detail(request, pk)
    elif request.method in ['PUT', 'POST']:
        return aircraft_type_api_update(request, pk)
    elif request.method == 'DELETE':
        return aircraft_type_api_delete(request, pk)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Availability, Aircraft, Airport
from datetime import datetime

def availability_list(request):
    # Get all availabilities with related aircraft and airport info
    availabilities = Availability.objects.select_related(
        'aircraft',
        'aircraft__aircraft_type'
    ).order_by('start_datetime')
    
    # Filter by date range if provided
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            availabilities = availabilities.filter(
                start_datetime__date__gte=start_date,
                end_datetime__date__lte=end_date
            )
        except ValueError:
            pass
    
    # Pagination
    paginator = Paginator(availabilities, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'current_time': timezone.now(),
    }
    return render(request, 'availability/availability_list.html', context)

def availability_detail(request, availability_id):
    try:
        availability = Availability.objects.select_related(
            'aircraft',
            'aircraft__aircraft_type'
        ).get(id=availability_id)
        
        data = {
            'success': True,
            'availability': {
                'id': availability.id,
                'aircraft': {
                    'model_name': availability.aircraft.model_name,
                    'registration_number': availability.aircraft.registration_number,
                    'aircraft_type': availability.aircraft.aircraft_type.name,
                    'current_location': availability.aircraft.current_location,
                    'hourly_rate': str(availability.aircraft.hourly_rate),
                },
                'start_datetime': availability.start_datetime.strftime("%Y-%m-%d %H:%M"),
                'end_datetime': availability.end_datetime.strftime("%Y-%m-%d %H:%M"),
                'is_available': availability.is_available,
                'status': 'Available' if availability.is_available else 'Booked',
                'notes': availability.notes,
                'duration': (availability.end_datetime - availability.start_datetime).total_seconds() / 3600,
            }
        }
    except Availability.DoesNotExist:
        data = {
            'success': False,
            'error': 'Availability not found'
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def update_availability(request, availability_id):
    try:
        availability = Availability.objects.get(id=availability_id)
        
        # Parse datetime strings from form
        start_datetime = datetime.strptime(
            request.POST.get('start_datetime'), 
            '%Y-%m-%dT%H:%M'
        )
        end_datetime = datetime.strptime(
            request.POST.get('end_datetime'), 
            '%Y-%m-%dT%H:%M'
        )
        
        availability.start_datetime = start_datetime
        availability.end_datetime = end_datetime
        availability.is_available = request.POST.get('is_available') == 'true'
        availability.notes = request.POST.get('notes', '')
        availability.save()
        
        data = {
            'success': True,
            'message': 'Availability updated successfully',
            'availability': {
                'id': availability.id,
                'start_datetime': availability.start_datetime.strftime("%Y-%m-%d %H:%M"),
                'end_datetime': availability.end_datetime.strftime("%Y-%m-%d %H:%M"),
                'is_available': availability.is_available,
            }
        }
    except Availability.DoesNotExist:
        data = {
            'success': False,
            'error': 'Availability not found'
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def delete_availability(request, availability_id):
    try:
        availability = Availability.objects.get(id=availability_id)
        aircraft_id = availability.aircraft.id
        availability.delete()
        
        data = {
            'success': True,
            'message': 'Availability slot deleted successfully',
            'aircraft_id': aircraft_id
        }
    except Availability.DoesNotExist:
        data = {
            'success': False,
            'error': 'Availability not found'
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)



from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.db.models import Prefetch
from .models import Booking, FlightLeg, User, Aircraft
from datetime import datetime

def booking_list(request):
    # Get all bookings with related data
    bookings = Booking.objects.select_related(
        'client',
        'aircraft',
        'aircraft__aircraft_type'
    ).prefetch_related(
        Prefetch('flight_legs', queryset=FlightLeg.objects.select_related(
            'departure_airport',
            'arrival_airport'
        ))
    ).order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter and status_filter in dict(Booking.STATUS_CHOICES).keys():
        bookings = bookings.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(bookings, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_choices': Booking.STATUS_CHOICES,
    }
    return render(request, 'bookings/booking_list.html', context)

def booking_detail(request, booking_id):
    try:
        booking = Booking.objects.select_related(
            'client',
            'aircraft',
            'aircraft__aircraft_type'
        ).prefetch_related(
            Prefetch('flight_legs', queryset=FlightLeg.objects.select_related(
                'departure_airport',
                'arrival_airport'
            ))
        ).get(id=booking_id)
        
        flight_legs = []
        for leg in booking.flight_legs.all():
            flight_legs.append({
                'departure': leg.departure_airport.icao_code,
                'arrival': leg.arrival_airport.icao_code,
                'departure_datetime': leg.departure_datetime.strftime("%Y-%m-%d %H:%M"),
                'arrival_datetime': leg.arrival_datetime.strftime("%Y-%m-%d %H:%M"),
                'passenger_count': leg.passenger_count,
                'flight_hours': str(leg.flight_hours),
                'leg_price': str(leg.leg_price),
            })
        
        data = {
            'success': True,
            'booking': {
                'id': booking.id,
                'booking_order_id': booking.booking_order_id,
                'client': {
                    'name': booking.client.get_full_name(),
                    'email': booking.client.email,
                    'phone': booking.client.phone_number,
                },
                'aircraft': {
                    'model': booking.aircraft.model_name,
                    'registration': booking.aircraft.registration_number,
                    'type': booking.aircraft.aircraft_type.name,
                },
                'trip_type': booking.get_trip_type_display(),
                'status': booking.get_status_display(),
                'status_code': booking.status,
                'created_at': booking.created_at.strftime("%Y-%m-%d %H:%M"),
                'updated_at': booking.updated_at.strftime("%Y-%m-%d %H:%M"),
                'total_price': str(booking.total_price),
                'payment_status': 'Paid' if booking.payment_status else 'Pending',
                'commission_rate': str(booking.commission_rate),
                'agent_commission': str(booking.agent_commission),
                'owner_earnings': str(booking.owner_earnings),
                'special_requests': booking.special_requests or 'None',
                'flight_legs': flight_legs,
            }
        }
    except Booking.DoesNotExist:
        data = {
            'success': False,
            'error': 'Booking not found'
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def update_booking_status(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        new_status = request.POST.get('status')
        
        if new_status not in dict(Booking.STATUS_CHOICES).keys():
            raise ValueError("Invalid status")
            
        booking.status = new_status
        booking.save()
        
        data = {
            'success': True,
            'message': 'Booking status updated successfully',
            'booking': {
                'id': booking.id,
                'status': booking.get_status_display(),
                'status_code': booking.status,
            }
        }
    except Booking.DoesNotExist:
        data = {
            'success': False,
            'error': 'Booking not found'
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def delete_booking(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        booking_order_id = booking.booking_order_id
        booking.delete()
        
        data = {
            'success': True,
            'message': f'Booking {booking_order_id} deleted successfully'
        }
    except Booking.DoesNotExist:
        data = {
            'success': False,
            'error': 'Booking not found'
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)