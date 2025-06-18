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
            estimated_flight_hours = estimate_flight_time(departure_airport, arrival_airport, aircraft)

            
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


def estimate_flight_time(departure_airport, arrival_airport, aircraft):
    """
    Estimate flight time between two airports using aircraft-specific speed.
    Adds buffer time for taxiing, etc.
    """
    try:
        import math

        lat1, lon1 = float(departure_airport.latitude), float(departure_airport.longitude)
        lat2, lon2 = float(arrival_airport.latitude), float(arrival_airport.longitude)

        # Haversine formula for distance in nautical miles
        R = 3440  # Earth radius in nautical miles
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance_nm = R * c

        # Use actual speed from aircraft type
        speed_knots = aircraft.aircraft_type.speed_knots or 400  # Fallback in case data is missing
        flight_time = (distance_nm / speed_knots) + 0.5  # Add 30 min buffer

        return round(flight_time, 1)
    except Exception as e:
        # Log error if desired
        return 2.0  # Fallback time




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

from django.core.paginator import Paginator
from django.shortcuts import render
from .models import AircraftType, Airport

def private_jet_charter(request):
    # Get all airports for the dropdown
    airports = Airport.objects.all().order_by('name')
    
    # Get selected category from request
    selected_category = request.GET.get('category', '')
    
    # Filter aircraft by category if selected
    if selected_category:
        aircraft_list = AircraftType.objects.filter(category=selected_category).order_by('name')
    else:
        aircraft_list = AircraftType.objects.all().order_by('name')
    
    # Pagination
    paginator = Paginator(aircraft_list, 6)  # Show 6 aircraft per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'airports': airports,
        'aircraft_types': aircraft_list,  # Keeping this for backward compatibility
        'page_obj': page_obj,
        'selected_category': selected_category,
        'category_choices': AircraftType.CATEGORY_CHOICES,
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



from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os

@csrf_exempt
@require_POST
def submit_leasing_inquiry(request):
    try:
        # Get form data
        leasing_type = request.POST.get('leasing_type')
        name = request.POST.get('name')
        company = request.POST.get('company', '')
        email = request.POST.get('email')
        telephone = request.POST.get('telephone')
        requirements = request.POST.get('requirements')
        duration = request.POST.get('duration', '')
        
        # Validate required fields
        if not all([leasing_type, name, email, telephone, requirements]):
            return JsonResponse({
                'status': 'error',
                'message': 'Please fill in all required fields.'
            }, status=400)
        
        # Create the leasing inquiry object
        leasing_inquiry = AircraftLeasingInquiry(
            leasing_type=leasing_type,
            name=name,
            company=company,
            email=email,
            telephone=telephone,
            requirements=requirements,
            duration=duration
        )
        
        # Handle file uploads
        supporting_document_1 = request.FILES.get('supporting_document_1')
        supporting_document_2 = request.FILES.get('supporting_document_2')
        
        # Validate file types and sizes
        allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']
        max_file_size = 10 * 1024 * 1024  # 10MB
        
        def validate_file(file):
            if file:
                # Check file size
                if file.size > max_file_size:
                    return False, f"File {file.name} is too large. Maximum size is 10MB."
                
                # Check file extension
                file_extension = os.path.splitext(file.name)[1].lower()
                if file_extension not in allowed_extensions:
                    return False, f"File {file.name} has an invalid format. Allowed formats: PDF, DOC, DOCX, JPG, PNG."
            
            return True, None
        
        # Validate files
        if supporting_document_1:
            is_valid, error_msg = validate_file(supporting_document_1)
            if not is_valid:
                return JsonResponse({
                    'status': 'error',
                    'message': error_msg
                }, status=400)
            leasing_inquiry.supporting_document_1 = supporting_document_1
        
        if supporting_document_2:
            is_valid, error_msg = validate_file(supporting_document_2)
            if not is_valid:
                return JsonResponse({
                    'status': 'error',
                    'message': error_msg
                }, status=400)
            leasing_inquiry.supporting_document_2 = supporting_document_2
        
        # Save the inquiry
        leasing_inquiry.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Your leasing inquiry has been submitted successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)


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
    ).order_by('-timestamp')[:2]
    
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
        'verified_clients': clients.filter(verified=True, is_active=True),
        'pending_clients': clients.filter(verified=False, is_active=True),
        'inactive_clients': clients.filter(is_active=False),
        'verified_count': clients.filter(verified=True, is_active=True).count(),
        'pending_count': clients.filter(verified=False, is_active=True).count(),
        'inactive_count': clients.filter(is_active=False).count(),
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
    """Get aircraft details via AJAX with full airport information"""
    try:
        aircraft = get_object_or_404(
            Aircraft.objects.select_related('owner', 'aircraft_type'),
            id=aircraft_id
        )
        
        # Get airport details if they exist
        def get_airport_display(icao_code):
            if not icao_code:
                return None
            try:
                airport = Airport.objects.get(icao_code=icao_code)
                return f"{airport.name} ({airport.icao_code})"
            except Airport.DoesNotExist:
                return icao_code  # Return just the ICAO code if airport not found
        
        base_airport_display = get_airport_display(aircraft.base_airport)
        current_location_display = get_airport_display(aircraft.current_location)
        
        data = {
            'id': aircraft.id,
            'registration_number': aircraft.registration_number,
            'model_name': aircraft.model_name,
            'year_manufactured': aircraft.year_manufactured,
            'base_airport': aircraft.base_airport,
            'base_airport_display': base_airport_display,
            'current_location': aircraft.current_location,
            'current_location_display': current_location_display,
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


import os
import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import QueryDict
from django.core.files.uploadhandler import MemoryFileUploadHandler, TemporaryFileUploadHandler

@csrf_exempt
@require_http_methods(["PUT", "POST"])
def aircraft_type_api_update(request, pk):
    """API endpoint to update an existing aircraft type"""
    try:
        aircraft = get_object_or_404(AircraftType, pk=pk)
        
        # Handle different request methods and content types
        data = {}
        files = {}
        
        if request.method == 'PUT':
            # For PUT requests with multipart data, we need to manually parse
            if request.content_type and 'multipart/form-data' in request.content_type:
                # Parse the multipart data manually for PUT requests
                from django.http.multipartparser import MultiPartParser
                from django.http import QueryDict
                
                # Create a copy of META for the parser
                META = request.META.copy()
                META['REQUEST_METHOD'] = 'POST'  # Trick the parser
                
                # Parse the multipart data
                parser = MultiPartParser(META, request, request.upload_handlers, request.encoding)
                data, files = parser.parse()
                
            else:
                # Handle JSON data for PUT requests
                try:
                    data = json.loads(request.body)
                except json.JSONDecodeError:
                    return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        else:
            # POST request - use normal Django handling
            data = request.POST
            files = request.FILES
        
        print(f"Received data: {data}")  # Debug log
        print(f"Received files: {files}")  # Debug log
        
        # Update fields if provided
        if 'name' in data:
            aircraft.name = data['name']
            print(f"Updated name to: {aircraft.name}")  # Debug log
        
        if 'description' in data:
            aircraft.description = data['description']
            print(f"Updated description to: {aircraft.description}")  # Debug log
        
        if 'passenger_capacity' in data:
            try:
                capacity = int(data['passenger_capacity'])
                if capacity <= 0:
                    return JsonResponse({'error': 'Passenger capacity must be positive'}, status=400)
                aircraft.passenger_capacity = capacity
                print(f"Updated capacity to: {aircraft.passenger_capacity}")  # Debug log
            except ValueError:
                return JsonResponse({'error': 'Invalid passenger capacity'}, status=400)
        
        if 'range_nautical_miles' in data:
            try:
                range_nm = int(data['range_nautical_miles'])
                if range_nm <= 0:
                    return JsonResponse({'error': 'Range must be positive'}, status=400)
                aircraft.range_nautical_miles = range_nm
                print(f"Updated range to: {aircraft.range_nautical_miles}")  # Debug log
            except ValueError:
                return JsonResponse({'error': 'Invalid range value'}, status=400)
        
        if 'speed_knots' in data:
            try:
                speed = int(data['speed_knots'])
                if speed <= 0:
                    return JsonResponse({'error': 'Speed must be positive'}, status=400)
                aircraft.speed_knots = speed
                print(f"Updated speed to: {aircraft.speed_knots}")  # Debug log
            except ValueError:
                return JsonResponse({'error': 'Invalid speed value'}, status=400)
        
        # Handle image update
        if 'image' in files:
            print(f"Processing image upload: {files['image']}")  # Debug log
            # Delete old image if exists
            if aircraft.image:
                old_image_path = aircraft.image.path
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            
            aircraft.image = files['image']
        
        # Save the aircraft
        aircraft.save()
        print(f"Aircraft saved successfully with ID: {aircraft.id}")  # Debug log
        
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
        print(f"Error in aircraft_type_api_update: {str(e)}")  # Debug log
        import traceback
        traceback.print_exc()  # Print full traceback for debugging
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
    paginator = Paginator(bookings, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_choices': Booking.STATUS_CHOICES,
        'confirmed_bookings': bookings.filter(status='confirmed'),
        'pending_bookings': bookings.filter(status='pending'),
        'cancelled_bookings': bookings.filter(status='cancelled'),
        'confirmed_count': bookings.filter(status='confirmed').count(),
        'pending_count': bookings.filter(status='pending').count(),
        'cancelled_count': bookings.filter(status='cancelled').count(),
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
            )),
            Prefetch('passengers', queryset=Passenger.objects.all())
        ).get(id=booking_id)
        
        flight_legs = []
        for leg in booking.flight_legs.all():
            flight_legs.append({
                'departure_code': leg.departure_airport.icao_code,
                'departure_name': f"{leg.departure_airport.name} ({leg.departure_airport.city}, {leg.departure_airport.country})",
                'arrival_code': leg.arrival_airport.icao_code,
                'arrival_name': f"{leg.arrival_airport.name} ({leg.arrival_airport.city}, {leg.arrival_airport.country})",
                'departure_datetime': leg.departure_datetime.strftime("%Y-%m-%d %H:%M"),
                'arrival_datetime': leg.arrival_datetime.strftime("%Y-%m-%d %H:%M"),
                'passenger_count': leg.passenger_count,
                'flight_hours': str(leg.flight_hours),
                'leg_price': str(leg.leg_price),
            })
        
        passengers = []
        for passenger in booking.passengers.all():
            passengers.append({
                'name': passenger.name,
                'nationality': passenger.nationality,
                'date_of_birth': passenger.date_of_birth.strftime("%Y-%m-%d") if passenger.date_of_birth else None,
                'passport_number': passenger.passport_number,
                'order': passenger.order,
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
                'passengers': passengers,
            }
        }
    except Booking.DoesNotExist:
        data = {
            'success': False,
            'error': 'Booking not found'
        }
    return JsonResponse(data)

def booking_detail2(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related(
            'client',
            'aircraft',
            'aircraft__aircraft_type'
        ).prefetch_related(
            Prefetch('flight_legs', queryset=FlightLeg.objects.select_related(
                'departure_airport',
                'arrival_airport'
            )),
            Prefetch('passengers', queryset=Passenger.objects.all())
        ),
        id=booking_id
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return JSON response for AJAX requests
        data = {
            "success": True,
            "booking": {
                "id": booking.id,
                "booking_order_id": booking.booking_order_id,
                "client": {
                    "name": booking.client.get_full_name(),
                    "email": booking.client.email,
                    "phone": booking.client.phone_number
                },
                "aircraft": {
                    "model": booking.aircraft.model_name,
                    "registration": booking.aircraft.registration_number,
                    "type": booking.aircraft.aircraft_type.name  # Fixed this line
                },
                "trip_type": booking.get_trip_type_display(),
                "status": booking.get_status_display(),
                "status_code": booking.status,
                "created_at": booking.created_at.strftime("%Y-%m-%d %H:%M"),
                "updated_at": booking.updated_at.strftime("%Y-%m-%d %H:%M"),
                "total_price": str(booking.total_price),
                "payment_status": "Paid" if booking.payment_status else "Pending",
                "commission_rate": str(booking.commission_rate),
                "agent_commission": str(booking.agent_commission),
                "owner_earnings": str(booking.owner_earnings),
                "special_requests": booking.special_requests or "None",
                "flight_legs": [{
                    "departure_code": leg.departure_airport.icao_code,
                    "departure_name": f"{leg.departure_airport.name} ({leg.departure_airport.city}, {leg.departure_airport.country})",
                    "arrival_code": leg.arrival_airport.icao_code,
                    "arrival_name": f"{leg.arrival_airport.name} ({leg.arrival_airport.city}, {leg.arrival_airport.country})",
                    "departure_datetime": leg.departure_datetime.strftime("%Y-%m-%d %H:%M"),
                    "arrival_datetime": leg.arrival_datetime.strftime("%Y-%m-%d %H:%M"),
                    "passenger_count": leg.passenger_count,
                    "flight_hours": str(leg.flight_hours),
                    "leg_price": str(leg.leg_price)
                } for leg in booking.flight_legs.all()],
                "passengers": [{
                    "name": passenger.name,
                    "nationality": passenger.nationality,
                    "date_of_birth": passenger.date_of_birth.strftime("%Y-%m-%d") if passenger.date_of_birth else "",
                    "passport_number": passenger.passport_number or "",
                    "order": passenger.order or ""  # Fixed this line
                } for passenger in booking.passengers.all()]
            }
        }
        return JsonResponse(data)
    
    # Prepare flight legs data for template
    flight_legs = []
    for leg in booking.flight_legs.all():
        flight_legs.append({
            'departure_code': leg.departure_airport.icao_code,
            'departure_name': f"{leg.departure_airport.name} ({leg.departure_airport.city}, {leg.departure_airport.country})",
            'arrival_code': leg.arrival_airport.icao_code,
            'arrival_name': f"{leg.arrival_airport.name} ({leg.arrival_airport.city}, {leg.arrival_airport.country})",
            'departure_datetime': leg.departure_datetime.strftime("%Y-%m-%d %H:%M"),
            'arrival_datetime': leg.arrival_datetime.strftime("%Y-%m-%d %H:%M"),
            'passenger_count': leg.passenger_count,
            'flight_hours': str(leg.flight_hours),
            'leg_price': str(leg.leg_price),
        })
    
    # Prepare passengers data for template
    passengers = []
    for passenger in booking.passengers.all():
        passengers.append({
            'name': passenger.name,
            'nationality': passenger.nationality,
            'date_of_birth': passenger.date_of_birth.strftime("%Y-%m-%d") if passenger.date_of_birth else None,
            'passport_number': passenger.passport_number,
            'order': passenger.order,
        })
    
    # Prepare booking data for template
    booking_data = {
        'id': booking.id,
        'booking_order_id': booking.booking_order_id,
        'client': booking.client,
        'aircraft': booking.aircraft,
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
        'passengers': passengers,
    }
    
    # Regular HTML response
    return render(request, 'bookings/booking_detail.html', {
        'booking': booking_data
    })

@require_http_methods(["POST", "GET"])
def update_booking_status(request, booking_id):
    # Handle GET request to return current booking data (for form pre-population)
    if request.method == "GET":
        try:
            booking = Booking.objects.get(id=booking_id)
            data = {
                'success': True,
                'booking': {
                    'id': booking.id,
                    'status': booking.get_status_display(),
                    'status_code': booking.status,
                    'payment_status': booking.payment_status,
                    'payment_status_display': booking.get_payment_status_display() if hasattr(booking, 'get_payment_status_display') else booking.payment_status,
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
    
    # Handle POST request to update booking status
    try:
        booking = Booking.objects.get(id=booking_id)
        new_status = request.POST.get('status')
        
        if new_status not in dict(Booking.STATUS_CHOICES).keys():
            raise ValueError("Invalid status")
            
        # Store old status for comparison
        old_status = booking.status
        booking.status = new_status
        
        # Update payment status - handle both manual input and automatic logic
        payment_status_input = request.POST.get('payment_status')
        
        if payment_status_input is not None:
            # Manual payment status update from form
            booking.payment_status = payment_status_input.lower() == 'true'
        else:
            # Automatic payment status based on booking status (if no manual input)
            if new_status == 'confirmed':
                booking.payment_status = False  # Not paid yet, just confirmed
            elif new_status == 'completed':
                booking.payment_status = True   # Assume payment completed
            elif new_status == 'cancelled':
                booking.payment_status = False  # No payment for cancelled booking
            elif new_status == 'pending':
                booking.payment_status = False  # Not paid while pending
        
        booking.save()
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # For AJAX requests, return JSON with refresh flag
            data = {
                'success': True,
                'message': 'Booking and payment status updated successfully',
                'refresh': True,  # Flag to trigger refresh on frontend
                'booking': {
                    'id': booking.id,
                    'status': booking.get_status_display(),
                    'status_code': booking.status,
                    'payment_status': booking.payment_status,
                    'payment_status_display': 'Paid' if booking.payment_status else 'Unpaid',
                }
            }
            return JsonResponse(data)
        else:
            # For regular form submissions, redirect to refresh the page
            from django.shortcuts import redirect
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
    except Booking.DoesNotExist:
        data = {
            'success': False,
            'error': 'Booking not found'
        }
    except ValueError as e:
        data = {
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        data = {
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }
    
    # Return error response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(data)
    else:
        # For regular forms, you might want to redirect with error message
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.error(request, data.get('error', 'An error occurred'))
        return redirect(request.META.get('HTTP_REFERER', '/'))
    

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


from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from .models import Inquiry, AircraftType
from django.utils import timezone

def inquiry_list(request):
    # Get all inquiries with related aircraft type
    inquiries = Inquiry.objects.select_related('aircraft_type').order_by('-submitted_at')
    
    # Filter by processed status if provided
    processed_filter = request.GET.get('processed')
    if processed_filter in ['true', 'false']:
        inquiries = inquiries.filter(is_processed=processed_filter == 'true')
    
    # Pagination
    paginator = Paginator(inquiries, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'aircraft_types': AircraftType.objects.all(),
    }
    return render(request, 'inquiries/inquiry_list.html', context)

def inquiry_detail(request, inquiry_id):
    try:
        inquiry = Inquiry.objects.select_related('aircraft_type').get(id=inquiry_id)
        data = {
            'success': True,
            'inquiry': {
                'id': inquiry.id,
                'full_name': inquiry.full_name,
                'email': inquiry.email,
                'phone': inquiry.phone,
                'aircraft_type': inquiry.aircraft_type.name if inquiry.aircraft_type else 'Not specified',
                'departure': inquiry.departure,
                'destination': inquiry.destination,
                'passengers': inquiry.passengers,
                'travel_date': inquiry.travel_date.strftime("%Y-%m-%d"),
                'submitted_at': inquiry.submitted_at.strftime("%Y-%m-%d %H:%M"),
                'is_processed': inquiry.is_processed,
            }
        }
    except Inquiry.DoesNotExist:
        data = {
            'success': False,
            'error': 'Inquiry not found'
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def update_inquiry(request, inquiry_id):
    try:
        inquiry = Inquiry.objects.get(id=inquiry_id)
        inquiry.is_processed = request.POST.get('is_processed') == 'true'
        inquiry.save()
        
        data = {
            'success': True,
            'message': 'Inquiry updated successfully',
            'inquiry': {
                'id': inquiry.id,
                'is_processed': inquiry.is_processed,
            }
        }
    except Inquiry.DoesNotExist:
        data = {
            'success': False,
            'error': 'Inquiry not found'
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def delete_inquiry(request, inquiry_id):
    try:
        inquiry = Inquiry.objects.get(id=inquiry_id)
        inquiry.delete()
        
        data = {
            'success': True,
            'message': 'Inquiry deleted successfully'
        }
    except Inquiry.DoesNotExist:
        data = {
            'success': False,
            'error': 'Inquiry not found'
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
from django.utils import timezone
from .models import AirCargoRequest

def cargo_request_list(request):
    # Get all cargo requests
    cargo_requests = AirCargoRequest.objects.all().order_by('-created_at')
    
    # Filter by request type if provided
    request_type = request.GET.get('type')
    if request_type in dict(AirCargoRequest.REQUEST_TYPE_CHOICES).keys():
        cargo_requests = cargo_requests.filter(request_type=request_type)
    
    # Pagination
    paginator = Paginator(cargo_requests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'request_types': AirCargoRequest.REQUEST_TYPE_CHOICES,
    }
    return render(request, 'cargo/cargo_request_list.html', context)

def cargo_request_detail(request, request_id):
    try:
        cargo_request = AirCargoRequest.objects.get(id=request_id)
        data = {
            'success': True,
            'cargo_request': {
                'id': cargo_request.id,
                'request_type': cargo_request.get_request_type_display(),
                'request_type_code': cargo_request.request_type,
                'departure': cargo_request.departure,
                'destination': cargo_request.destination,
                'date': cargo_request.date.strftime("%Y-%m-%d"),
                'departure_time': cargo_request.departure_time.strftime("%H:%M") if cargo_request.departure_time else None,
                'name': cargo_request.name,
                'company': cargo_request.company,
                'email': cargo_request.email,
                'telephone': cargo_request.telephone,
                'cargo_details': cargo_request.cargo_details,
                'special_requirements': cargo_request.special_requirements or 'None',
                'created_at': cargo_request.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        }
    except AirCargoRequest.DoesNotExist:
        data = {
            'success': False,
            'error': 'Cargo request not found'
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def update_cargo_request(request, request_id):
    try:
        cargo_request = AirCargoRequest.objects.get(id=request_id)
        cargo_request.request_type = request.POST.get('request_type', cargo_request.request_type)
        cargo_request.departure = request.POST.get('departure', cargo_request.departure)
        cargo_request.destination = request.POST.get('destination', cargo_request.destination)
        cargo_request.date = request.POST.get('date', cargo_request.date)
        cargo_request.departure_time = request.POST.get('departure_time', cargo_request.departure_time)
        cargo_request.name = request.POST.get('name', cargo_request.name)
        cargo_request.company = request.POST.get('company', cargo_request.company)
        cargo_request.email = request.POST.get('email', cargo_request.email)
        cargo_request.telephone = request.POST.get('telephone', cargo_request.telephone)
        cargo_request.cargo_details = request.POST.get('cargo_details', cargo_request.cargo_details)
        cargo_request.special_requirements = request.POST.get('special_requirements', cargo_request.special_requirements)
        cargo_request.save()
        
        data = {
            'success': True,
            'message': 'Cargo request updated successfully',
            'cargo_request': {
                'id': cargo_request.id,
                'request_type': cargo_request.get_request_type_display(),
            }
        }
    except AirCargoRequest.DoesNotExist:
        data = {
            'success': False,
            'error': 'Cargo request not found'
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def delete_cargo_request(request, request_id):
    try:
        cargo_request = AirCargoRequest.objects.get(id=request_id)
        route = f"{cargo_request.departure} to {cargo_request.destination}"
        cargo_request.delete()
        
        data = {
            'success': True,
            'message': f'Cargo request {route} deleted successfully'
        }
    except AirCargoRequest.DoesNotExist:
        data = {
            'success': False,
            'error': 'Cargo request not found'
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
from django.utils import timezone
from .models import AircraftLeasingInquiry

def leasing_inquiry_list(request):
    # Get all leasing inquiries
    inquiries = AircraftLeasingInquiry.objects.all().order_by('-created_at')
    
    # Filter by leasing type if provided
    leasing_type = request.GET.get('type')
    if leasing_type in dict(AircraftLeasingInquiry.LEASING_TYPE_CHOICES).keys():
        inquiries = inquiries.filter(leasing_type=leasing_type)
    
    # Pagination
    paginator = Paginator(inquiries, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'leasing_types': AircraftLeasingInquiry.LEASING_TYPE_CHOICES,
    }
    return render(request, 'leasing/leasing_inquiry_list.html', context)

def leasing_inquiry_detail(request, inquiry_id):
    try:
        inquiry = AircraftLeasingInquiry.objects.get(id=inquiry_id)
        data = {
            'success': True,
            'inquiry': {
                'id': inquiry.id,
                'leasing_type': inquiry.get_leasing_type_display(),
                'leasing_type_code': inquiry.leasing_type,
                'name': inquiry.name,
                'company': inquiry.company,
                'email': inquiry.email,
                'telephone': inquiry.telephone,
                'requirements': inquiry.requirements,
                'duration': inquiry.duration or 'Not specified',
                'created_at': inquiry.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        }
    except AircraftLeasingInquiry.DoesNotExist:
        data = {
            'success': False,
            'error': 'Leasing inquiry not found'
        }
    return JsonResponse(data)

@login_required
def aircraft_leasing_detail(request, pk):
    """
    View to display detailed information about a specific aircraft leasing inquiry.
    Only accessible by authenticated users.
    """
    # Get the specific inquiry or return 404 if not found
    inquiry = get_object_or_404(AircraftLeasingInquiry, pk=pk)
    
    # Prepare document URLs if they exist
    documents = []
    if inquiry.supporting_document_1:
        documents.append({
            'name': inquiry.supporting_document_1.name.split('/')[-1],
            'url': inquiry.supporting_document_1.url
        })
    if inquiry.supporting_document_2:
        documents.append({
            'name': inquiry.supporting_document_2.name.split('/')[-1],
            'url': inquiry.supporting_document_2.url
        })
    
    context = {
        'inquiry': inquiry,
        'documents': documents,
        'active_tab': 'aircraft_leasing',
    }
    
    return render(request, 'leasing/aircraft_leasing_detail.html', context)

@require_http_methods(["POST"])
def update_leasing_inquiry(request, inquiry_id):
    try:
        inquiry = AircraftLeasingInquiry.objects.get(id=inquiry_id)
        inquiry.leasing_type = request.POST.get('leasing_type', inquiry.leasing_type)
        inquiry.name = request.POST.get('name', inquiry.name)
        inquiry.company = request.POST.get('company', inquiry.company)
        inquiry.email = request.POST.get('email', inquiry.email)
        inquiry.telephone = request.POST.get('telephone', inquiry.telephone)
        inquiry.requirements = request.POST.get('requirements', inquiry.requirements)
        inquiry.duration = request.POST.get('duration', inquiry.duration)
        inquiry.save()
        
        data = {
            'success': True,
            'message': 'Leasing inquiry updated successfully',
            'inquiry': {
                'id': inquiry.id,
                'leasing_type': inquiry.get_leasing_type_display(),
            }
        }
    except AircraftLeasingInquiry.DoesNotExist:
        data = {
            'success': False,
            'error': 'Leasing inquiry not found'
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def delete_leasing_inquiry(request, inquiry_id):
    try:
        inquiry = AircraftLeasingInquiry.objects.get(id=inquiry_id)
        leasing_type = inquiry.get_leasing_type_display()
        inquiry.delete()
        
        data = {
            'success': True,
            'message': f'{leasing_type} inquiry deleted successfully'
        }
    except AircraftLeasingInquiry.DoesNotExist:
        data = {
            'success': False,
            'error': 'Leasing inquiry not found'
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
from django.utils import timezone
from .models import GroupInquiry

def group_inquiry_list(request):
    # Get all group inquiries ordered by submission date
    inquiries = GroupInquiry.objects.all().order_by('-submitted_at')
    
    # Filter by date range if provided
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            inquiries = inquiries.filter(
                travel_date__gte=start_date,
                travel_date__lte=end_date
            )
        except ValueError:
            pass
    
    # Pagination
    paginator = Paginator(inquiries, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'current_date': timezone.now().date(),
    }
    return render(request, 'group_inquiries/group_inquiry_list.html', context)

def group_inquiry_detail(request, inquiry_id):
    try:
        inquiry = GroupInquiry.objects.get(id=inquiry_id)
        data = {
            'success': True,
            'inquiry': {
                'id': inquiry.id,
                'group_name': inquiry.group_name,
                'contact_email': inquiry.contact_email,
                'passenger_count': inquiry.passenger_count,
                'travel_date': inquiry.travel_date.strftime("%Y-%m-%d"),
                'submitted_at': inquiry.submitted_at.strftime("%Y-%m-%d %H:%M"),
            }
        }
    except GroupInquiry.DoesNotExist:
        data = {
            'success': False,
            'error': 'Group inquiry not found'
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def update_group_inquiry(request, inquiry_id):
    try:
        inquiry = GroupInquiry.objects.get(id=inquiry_id)
        inquiry.group_name = request.POST.get('group_name', inquiry.group_name)
        inquiry.contact_email = request.POST.get('contact_email', inquiry.contact_email)
        inquiry.passenger_count = request.POST.get('passenger_count', inquiry.passenger_count)
        inquiry.travel_date = request.POST.get('travel_date', inquiry.travel_date)
        inquiry.save()
        
        data = {
            'success': True,
            'message': 'Group inquiry updated successfully',
            'inquiry': {
                'id': inquiry.id,
                'group_name': inquiry.group_name,
            }
        }
    except GroupInquiry.DoesNotExist:
        data = {
            'success': False,
            'error': 'Group inquiry not found'
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def delete_group_inquiry(request, inquiry_id):
    try:
        inquiry = GroupInquiry.objects.get(id=inquiry_id)
        group_name = inquiry.group_name
        inquiry.delete()
        
        data = {
            'success': True,
            'message': f'Group inquiry "{group_name}" deleted successfully'
        }
    except GroupInquiry.DoesNotExist:
        data = {
            'success': False,
            'error': 'Group inquiry not found'
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
from django.utils import timezone
from .models import ContactSubmission

def contact_submission_list(request):
    # Get all contact submissions ordered by submission date
    submissions = ContactSubmission.objects.all().order_by('-submitted_at')
    
    # Filter by subject if provided
    subject_filter = request.GET.get('subject')
    if subject_filter in [choice[0] for choice in ContactSubmission._meta.get_field('subject').choices]:
        submissions = submissions.filter(subject=subject_filter)
    
    # Pagination
    paginator = Paginator(submissions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'subject_choices': ContactSubmission._meta.get_field('subject').choices,
    }
    return render(request, 'contact/contact_submission_list.html', context)

def contact_submission_detail(request, submission_id):
    try:
        submission = ContactSubmission.objects.get(id=submission_id)
        data = {
            'success': True,
            'submission': {
                'id': submission.id,
                'name': submission.name,
                'email': submission.email,
                'phone': submission.phone or 'Not provided',
                'subject': submission.subject,
                'message': submission.message,
                'submitted_at': submission.submitted_at.strftime("%Y-%m-%d %H:%M"),
            }
        }
    except ContactSubmission.DoesNotExist:
        data = {
            'success': False,
            'error': 'Contact submission not found'
        }
    return JsonResponse(data)

@require_http_methods(["POST"])
def delete_contact_submission(request, submission_id):
    try:
        submission = ContactSubmission.objects.get(id=submission_id)
        submission_info = f"{submission.name} - {submission.subject}"
        submission.delete()
        
        data = {
            'success': True,
            'message': f'Contact submission "{submission_info}" deleted successfully'
        }
    except ContactSubmission.DoesNotExist:
        data = {
            'success': False,
            'error': 'Contact submission not found'
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
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import User

@login_required
def booking_agents_list(request):
    """View to display all booking agents"""
    agents = User.objects.filter(user_type='agent').order_by('-date_joined')
    
    # Pagination
    paginator = Paginator(agents, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'agents/booking_agents_list.html', context)

@login_required
@require_http_methods(["GET"])
def agent_detail(request, agent_id):
    """AJAX view to get agent details"""
    agent = get_object_or_404(User, id=agent_id, user_type='agent')
    
    data = {
        'success': True,
        'agent': {
            'id': agent.id,
            'username': agent.username,
            'email': agent.email,
            'first_name': agent.first_name,
            'last_name': agent.last_name,
            'phone_number': agent.phone_number,
            'company_name': agent.company_name,
            'tax_id': agent.tax_id,
            'address': agent.address,
            'date_joined': agent.date_joined.strftime("%b %d, %Y %H:%M"),
            'last_login': agent.last_login.strftime("%b %d, %Y %H:%M") if agent.last_login else 'Never',
            'verified': 'Yes' if agent.verified else 'No',
        }
    }
    return JsonResponse(data)

@login_required
@require_http_methods(["POST"])
def update_agent(request, agent_id):
    """AJAX view to update agent details"""
    agent = get_object_or_404(User, id=agent_id, user_type='agent')
    
    # Update fields
    agent.first_name = request.POST.get('first_name', agent.first_name)
    agent.last_name = request.POST.get('last_name', agent.last_name)
    agent.email = request.POST.get('email', agent.email)
    agent.phone_number = request.POST.get('phone_number', agent.phone_number)
    agent.company_name = request.POST.get('company_name', agent.company_name)
    agent.tax_id = request.POST.get('tax_id', agent.tax_id)
    agent.address = request.POST.get('address', agent.address)
    agent.verified = 'verified' in request.POST
    
    try:
        agent.save()
        return JsonResponse({'success': True, 'message': 'Agent updated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def delete_agent(request, agent_id):
    """AJAX view to delete an agent"""
    agent = get_object_or_404(User, id=agent_id, user_type='agent')
    
    try:
        agent.delete()
        return JsonResponse({'success': True, 'message': 'Agent deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from .models import User

def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser

@login_required
@user_passes_test(is_superuser)
def admin_users_list(request):
    """View to display all system admins"""
    admins = User.objects.filter(user_type='admin').order_by('-date_joined')
    
    # Pagination
    paginator = Paginator(admins, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'admins/admin_users_list.html', context)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["GET"])
def admin_detail(request, admin_id):
    """AJAX view to get admin details"""
    admin = get_object_or_404(User, id=admin_id, user_type='admin')
    
    data = {
        'success': True,
        'admin': {
            'id': admin.id,
            'username': admin.username,
            'email': admin.email,
            'first_name': admin.first_name,
            'last_name': admin.last_name,
            'phone_number': admin.phone_number,
            'is_superuser': 'Yes' if admin.is_superuser else 'No',
            'is_staff': 'Yes' if admin.is_staff else 'No',
            'address': admin.address,
            'date_joined': admin.date_joined.strftime("%b %d, %Y %H:%M"),
            'last_login': admin.last_login.strftime("%b %d, %Y %H:%M") if admin.last_login else 'Never',
        }
    }
    return JsonResponse(data)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def update_admin(request, admin_id):
    """AJAX view to update admin details"""
    admin = get_object_or_404(User, id=admin_id, user_type='admin')
    
    # Update fields
    admin.first_name = request.POST.get('first_name', admin.first_name)
    admin.last_name = request.POST.get('last_name', admin.last_name)
    admin.email = request.POST.get('email', admin.email)
    admin.phone_number = request.POST.get('phone_number', admin.phone_number)
    admin.address = request.POST.get('address', admin.address)
    admin.is_superuser = 'is_superuser' in request.POST
    admin.is_staff = 'is_staff' in request.POST
    
    try:
        admin.save()
        return JsonResponse({'success': True, 'message': 'Admin updated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def delete_admin(request, admin_id):
    """AJAX view to delete an admin"""
    admin = get_object_or_404(User, id=admin_id, user_type='admin')
    
    # Prevent deleting yourself
    if admin == request.user:
        return JsonResponse({'success': False, 'message': 'You cannot delete your own account'}, status=400)
    
    try:
        admin.delete()
        return JsonResponse({'success': True, 'message': 'Admin deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
    

from django.shortcuts import render
from django.db.models import Sum, Count, F, Value, CharField
from django.db.models.functions import Concat, TruncMonth
from django.utils import timezone
from datetime import timedelta
from .models import Booking, FlightLeg, Aircraft

def financial_dashboard(request):
    # Date range setup
    end_date = timezone.now()
    start_date = end_date - timedelta(days=365)
    previous_start_date = start_date - timedelta(days=365)
    previous_end_date = start_date

    # 1. Monthly revenue
    monthly_revenue = (
        Booking.objects
        .filter(created_at__range=[start_date, end_date])
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(
            total_revenue=Sum('total_price'),
            commission=Sum('agent_commission'),
            owner_earnings=Sum('owner_earnings')
        )
        .order_by('month')
    )
    # Convert dates to strings for JSON serialization
    for item in monthly_revenue:
        item['month'] = item['month'].strftime('%Y-%m')

    # 2. Monthly travel
    monthly_travel = (
        FlightLeg.objects
        .filter(departure_datetime__range=[start_date, end_date])
        .annotate(month=TruncMonth('departure_datetime'))
        .values('month')
        .annotate(total_flights=Count('id'))
        .order_by('month')
    )
    for item in monthly_travel:
        item['month'] = item['month'].strftime('%Y-%m')

    # 3. Top performing aircraft
    top_aircraft = (
        Aircraft.objects
        .annotate(
            total_bookings=Count('bookings'),
            total_revenue=Sum('bookings__total_price')
        )
        .values('registration_number', 'model_name', 'total_revenue')
        .order_by('-total_revenue')[:5]
    )

    # 4. Most popular flight legs
    popular_legs = (
        FlightLeg.objects
        .values('departure_airport__icao_code', 'arrival_airport__icao_code')
        .annotate(
            total_flights=Count('id'),
            route_name=Concat(
                'departure_airport__icao_code',
                Value(' → '),
                'arrival_airport__icao_code',
                output_field=CharField()
            )
        )
        .order_by('-total_flights')[:10]
    )

    # 5. Extra metrics
    active_aircraft_count = Aircraft.objects.filter(is_active=True).count()

    previous_revenue = (
        Booking.objects
        .filter(created_at__range=[previous_start_date, previous_end_date])
        .aggregate(total=Sum('total_price'))['total'] or 0
    )

    previous_flights = (
        FlightLeg.objects
        .filter(departure_datetime__range=[previous_start_date, previous_end_date])
        .count()
    )

    previous_routes = (
        FlightLeg.objects
        .filter(departure_datetime__range=[previous_start_date, previous_end_date])
        .values('departure_airport__icao_code', 'arrival_airport__icao_code')
        .distinct()
        .count()
    )

    # FIXED: Pass individual variables instead of nested in dashboard_data
    context = {
        'monthly_revenue': list(monthly_revenue),
        'monthly_travel': list(monthly_travel),
        'top_aircraft': list(top_aircraft),
        'popular_legs': list(popular_legs),
        'active_aircraft_count': active_aircraft_count,
        'previous_revenue_total': previous_revenue,
        'previous_flights_total': previous_flights,
        'previous_routes_count': previous_routes,
    }

    return render(request, 'dashboard/financial_dashboard.html', context)



def custom_page_not_found(request, exception):
    return render(request, '404.html', status=404)

def custom_server_error(request):
    return render(request, '500.html', status=500)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import (
    User, Aircraft, Airport, Booking, FlightLeg, Passenger, 
    PricingRule, Availability, AircraftType
)
from .forms import (
    BookingForm, FlightLegForm, PassengerForm, ClientAccountForm
)

def check_aircraft_availability(aircraft, flight_legs):
    """
    Check if aircraft is available for all flight legs
    Returns: (is_available, message)
    """
    for leg in flight_legs:
        departure_time = leg['departure_datetime']
        arrival_time = leg['arrival_datetime']
        
        # Check for overlapping bookings
        overlapping_bookings = Booking.objects.filter(
            aircraft=aircraft,
            status__in=['confirmed', 'pending'],
            flight_legs__departure_datetime__lt=arrival_time,
            flight_legs__arrival_datetime__gt=departure_time
        ).exists()
        
        if overlapping_bookings:
            return False, f"Aircraft not available from {departure_time} to {arrival_time}"
        
        # Check availability windows if they exist
        availability_exists = Availability.objects.filter(
            aircraft=aircraft,
            start_datetime__lte=departure_time,
            end_datetime__gte=arrival_time,
            is_available=True
        ).exists()
        
        # If availability records exist, aircraft must be in an available window
        if Availability.objects.filter(aircraft=aircraft).exists() and not availability_exists:
            return False, f"Aircraft not in available window for {departure_time} to {arrival_time}"
    
    return True, "Aircraft is available"


import json
import math
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from datetime import datetime


def estimate_flight_time(departure_airport, arrival_airport, aircraft):
    """
    Estimate flight time between two airports using aircraft-specific speed.
    This matches your working implementation from the first view.
    """
    try:
        # Convert coordinates to float (handles both string and numeric inputs)
        lat1, lon1 = float(departure_airport.latitude), float(departure_airport.longitude)
        lat2, lon2 = float(arrival_airport.latitude), float(arrival_airport.longitude)

        # Haversine formula for distance in nautical miles
        R = 3440  # Earth radius in nautical miles
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance_nm = R * c

        # Use actual speed from aircraft type
        speed_knots = aircraft.aircraft_type.speed_knots or 400  # Fallback in case data is missing
        flight_time = (distance_nm / speed_knots) + 0.5  # Add 30 min buffer

        return round(flight_time, 1)
    except Exception as e:
        # Log error if desired
        return 2.0  # Fallback time


def calculate_base_price(aircraft, flight_hours, trip_type):
    """
    Calculate base price for the flight.
    This matches your working implementation from the first view.
    """
    # Convert Decimal to float to avoid type mixing
    base_rate = float(aircraft.hourly_rate)
    minimum_hours = float(aircraft.minimum_hours)
    flight_hours_float = float(flight_hours)
    
    # Use minimum hours or actual flight time, whichever is higher
    billable_hours = max(flight_hours_float, minimum_hours)
    
    base_price = base_rate * billable_hours
    
    return round(base_price, 2)


def calculate_pricing(aircraft, flight_legs, trip_type, minimum_type='smart'):
    """
    Simplified pricing calculation matching your first view's logic.
    Removed complex surcharges and discounts to match working implementation.
    
    Args:
        aircraft: Aircraft instance
        flight_legs: List of flight leg data
        trip_type: Type of trip (one_way, round_trip, multi_leg)
        minimum_type: How to apply minimum hours (kept for compatibility)
    
    Returns: pricing_details dictionary
    """
    total_price = 0.0
    total_hours = 0.0
    actual_flight_hours = 0.0
    
    # Process each flight leg using the same logic as your working view
    for leg in flight_legs:
        flight_hours = float(leg['flight_hours'])
        actual_flight_hours += flight_hours
        
        # Use the same pricing logic as your working view
        leg_base_price = calculate_base_price(aircraft, flight_hours, trip_type)
        total_price += leg_base_price
        
        # Calculate billable hours for this leg (for reporting)
        base_rate = float(aircraft.hourly_rate)
        minimum_hours = float(aircraft.minimum_hours)
        billable_hours = max(flight_hours, minimum_hours)
        total_hours += billable_hours
    
    # For round trips, double the price (matching your working view logic)
    if trip_type == 'round_trip' and len(flight_legs) == 2:
        total_price = total_price  # Already calculated per leg
    
    # Calculate commission (simple 10% like your working view)
    commission_rate = Decimal('10.00')  # 10%
    agent_commission = Decimal(str(total_price)) * (commission_rate / 100)
    owner_earnings = Decimal(str(total_price)) - agent_commission
    
    return {
        'total_price': Decimal(str(total_price)),
        'commission_rate': commission_rate,
        'agent_commission': agent_commission,
        'owner_earnings': owner_earnings,
        'total_hours': Decimal(str(total_hours)),
        'actual_flight_hours': Decimal(str(actual_flight_hours)),
        'base_hourly_rate': aircraft.hourly_rate,
        'minimum_hours_applied': minimum_type,
        'aircraft_name': f"{aircraft.model_name} ({aircraft.registration_number})",
    }


def calculate_flight_hours_haversine(departure_lat, departure_lng, arrival_lat, arrival_lng, aircraft_speed_knots):
    """
    Updated to match your working implementation's logic exactly
    """
    try:
        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [departure_lat, departure_lng, arrival_lat, arrival_lng])
        
        # Haversine formula (matching your working implementation)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # Earth's radius in nautical miles (matching your working implementation)
        r = 3440  # Same as your working implementation
        
        # Distance in nautical miles
        distance_nm = c * r
        
        # Use 30-minute buffer like your working implementation (0.5 hours)
        flight_hours = (distance_nm / aircraft_speed_knots) + 0.5
        
        return round(flight_hours, 1)  # Match your working implementation's precision
        
    except Exception as e:
        return 2.0  # Same fallback as your working implementation


def ajax_calculate_flight_hours(request):
    """
    Updated AJAX endpoint using your working implementation's logic
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            departure_airport_id = data.get('departure_airport_id')
            arrival_airport_id = data.get('arrival_airport_id')
            aircraft_id = data.get('aircraft_id')
            
            if not all([departure_airport_id, arrival_airport_id, aircraft_id]):
                return JsonResponse({
                    'error': 'Missing required parameters'
                }, status=400)
            
            # Get airports and aircraft
            departure_airport = get_object_or_404(Airport, id=departure_airport_id)
            arrival_airport = get_object_or_404(Airport, id=arrival_airport_id)
            aircraft = get_object_or_404(Aircraft, id=aircraft_id)
            
            # Check if airports have coordinates
            if not all([
                departure_airport.latitude, departure_airport.longitude,
                arrival_airport.latitude, arrival_airport.longitude
            ]):
                return JsonResponse({
                    'error': 'Airport coordinates not available'
                }, status=400)
            
            # Use your working implementation's logic
            flight_hours = estimate_flight_time(departure_airport, arrival_airport, aircraft)
            
            return JsonResponse({
                'flight_hours': flight_hours,
                'distance_info': f'Calculated using same logic as client booking with {aircraft.aircraft_type.name} speed of {aircraft.aircraft_type.speed_knots} knots',
                'aircraft_info': {
                    'name': aircraft.aircraft_type.name,
                    'speed_knots': aircraft.aircraft_type.speed_knots,
                    'hourly_rate': float(aircraft.hourly_rate),
                    'minimum_hours': float(aircraft.minimum_hours)
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error calculating flight hours: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@transaction.atomic
def new_booking(request):
    """
    Updated booking view using your working implementation's pricing logic
    """
    if request.method == 'POST':
        # Initialize forms
        booking_form = BookingForm(request.POST)
        
        # Get passenger count and create forms
        passenger_count = int(request.POST.get('passenger_count', 1))
        passenger_forms = [
            PassengerForm(request.POST, prefix=f'passenger_{i}') 
            for i in range(passenger_count)
        ]
        
        # Client handling (keeping your existing logic)
        client_selection = request.POST.get('client_selection')
        account_form = None
        client = None
        
        if client_selection == 'new':
            account_form = ClientAccountForm(request.POST)
            if account_form.is_valid():
                user = account_form.save(commit=False)
                user.user_type = 'client'
                user.is_active = True
                user.save()
                client = user
                messages.success(request, 'Client account created successfully!')
            else:
                messages.error(request, 'Please correct the client account information.')
                
        elif client_selection == 'existing':
            client_id = request.POST.get('client')
            if not client_id:
                messages.error(request, 'Please select a client.')
            else:
                try:
                    client = User.objects.get(id=client_id, user_type='client', is_active=True)
                except User.DoesNotExist:
                    messages.error(request, 'Invalid client selected.')
                    client = None
        else:
            messages.error(request, 'Please select how to handle client information.')
        
        # Continue only if we have a valid client
        if client and booking_form.is_valid():
            # Get flight leg count and create leg forms
            leg_count = int(request.POST.get('leg_count', 1))
            leg_forms = []
            valid_legs = []
            
            for i in range(leg_count):
                leg_form = FlightLegForm(request.POST, prefix=f'leg_{i}')
                leg_forms.append(leg_form)
                if leg_form.is_valid():
                    leg_data = leg_form.cleaned_data
                    
                    # Auto-calculate flight hours using your working implementation's logic
                    if not leg_data.get('flight_hours') or leg_data.get('flight_hours') == 0:
                        try:
                            departure_airport = leg_data['departure_airport']
                            arrival_airport = leg_data['arrival_airport']
                            aircraft = booking_form.cleaned_data['aircraft']
                            
                            if all([departure_airport.latitude, departure_airport.longitude,
                                   arrival_airport.latitude, arrival_airport.longitude]):
                                
                                # Use your working implementation's function
                                calculated_hours = estimate_flight_time(departure_airport, arrival_airport, aircraft)
                                leg_data['flight_hours'] = Decimal(str(calculated_hours))
                        except Exception as e:
                            messages.warning(request, f'Could not auto-calculate flight hours for leg {i+1}: {str(e)}')
                    
                    valid_legs.append(leg_data)
            
            # Validate passengers
            valid_passenger_forms = [form for form in passenger_forms if form.is_valid()]
            
            # Check all validations
            if not valid_legs:
                messages.error(request, 'Please provide at least one valid flight leg.')
            elif len(valid_passenger_forms) != passenger_count:
                messages.error(request, 'Please correct all passenger information.')
            else:
                # All forms are valid, proceed with booking creation
                booking = booking_form.save(commit=False)
                booking.client = client
                
                aircraft = booking.aircraft
                trip_type = booking.trip_type
                
                # Check aircraft availability
                available, availability_message = check_aircraft_availability(aircraft, valid_legs)
                if not available:
                    messages.error(request, f'Aircraft not available: {availability_message}')
                else:
                    # Calculate pricing using your working implementation's logic
                    try:
                        pricing_details = calculate_pricing(aircraft, valid_legs, trip_type)
                        
                        # Set booking financials
                        booking.total_price = pricing_details['total_price']
                        booking.commission_rate = pricing_details['commission_rate']
                        booking.agent_commission = pricing_details['agent_commission']
                        booking.owner_earnings = pricing_details['owner_earnings']
                        
                        # Save the booking
                        booking.save()
                        
                        # Save flight legs
                        for i, leg_data in enumerate(valid_legs):
                            FlightLeg.objects.create(
                                booking=booking,
                                sequence=i + 1,
                                departure_airport=leg_data['departure_airport'],
                                arrival_airport=leg_data['arrival_airport'],
                                departure_datetime=leg_data['departure_datetime'],
                                arrival_datetime=leg_data['arrival_datetime'],
                                flight_hours=leg_data['flight_hours'],
                                passenger_count=passenger_count,
                                leg_price=pricing_details['total_price'] / len(valid_legs)
                            )
                        
                        # Save passengers
                        for form in valid_passenger_forms:
                            passenger_data = form.cleaned_data
                            Passenger.objects.create(
                                booking=booking,
                                name=passenger_data['name'],
                                nationality=passenger_data.get('nationality', ''),
                                date_of_birth=passenger_data.get('date_of_birth'),
                                passport_number=passenger_data.get('passport_number', '')
                            )
                        
                        messages.success(
                            request, 
                            f'Booking created successfully! Booking ID: {booking.booking_order_id}. '
                            f'Total Price: ${pricing_details["total_price"]:.2f}'
                        )
                        return redirect('booking_detail2', booking_id=booking.id)
                        
                    except Exception as e:
                        messages.error(request, f'Error calculating pricing: {str(e)}')
        
        # If we reach here, there were validation errors or missing client
        if not account_form:
            account_form = ClientAccountForm()
            
        if 'leg_forms' not in locals():
            leg_count = int(request.POST.get('leg_count', 1))
            leg_forms = [FlightLegForm(request.POST, prefix=f'leg_{i}') for i in range(leg_count)]
        
        context = {
            'booking_form': booking_form,
            'passenger_forms': passenger_forms,
            'account_form': account_form,
            'leg_forms': leg_forms,
            'aircrafts': Aircraft.objects.filter(is_active=True),
            'airports': Airport.objects.all(),
            'clients': User.objects.filter(user_type='client', is_active=True).order_by('first_name', 'last_name'),
            'client_selection': client_selection,
        }
        return render(request, 'bookings/new_booking.html', context)
    
    else:
        # GET request - show empty forms
        booking_form = BookingForm()
        passenger_forms = [PassengerForm(prefix='passenger_0')]
        account_form = ClientAccountForm()
        leg_forms = [FlightLegForm(prefix='leg_0')]
    
    # Get data for dropdowns
    clients = User.objects.filter(user_type='client', is_active=True).order_by('first_name', 'last_name')
    aircrafts = Aircraft.objects.filter(is_active=True).select_related('aircraft_type', 'owner')
    airports = Airport.objects.all().order_by('city', 'name')
    
    context = {
        'booking_form': booking_form,
        'passenger_forms': passenger_forms,
        'account_form': account_form,
        'leg_forms': leg_forms,
        'clients': clients,
        'aircrafts': aircrafts,
        'airports': airports,
        'client_selection': 'existing',
    }
    
    return render(request, 'bookings/new_booking.html', context)


def ajax_calculate_price(request):
    """
    AJAX endpoint using your working implementation's pricing logic
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            aircraft_id = data.get('aircraft_id')
            flight_legs = data.get('flight_legs', [])
            trip_type = data.get('trip_type', 'one_way')
            
            aircraft = get_object_or_404(Aircraft, id=aircraft_id)
            
            # Convert string dates to datetime objects and ensure flight_hours is Decimal
            for leg in flight_legs:
                leg['departure_datetime'] = datetime.fromisoformat(leg['departure_datetime'].replace('Z', '+00:00'))
                leg['arrival_datetime'] = datetime.fromisoformat(leg['arrival_datetime'].replace('Z', '+00:00'))
                leg['flight_hours'] = Decimal(str(leg['flight_hours']))
            
            # Use your working implementation's pricing logic
            pricing_details = calculate_pricing(aircraft, flight_legs, trip_type)
            
            # Convert Decimal objects to float for JSON serialization
            response_data = {
                'total_price': float(pricing_details['total_price']),
                'commission_rate': float(pricing_details['commission_rate']),
                'agent_commission': float(pricing_details['agent_commission']),
                'owner_earnings': float(pricing_details['owner_earnings']),
                'total_hours': float(pricing_details['total_hours']),
                'base_hourly_rate': float(pricing_details['base_hourly_rate'])
            }
            
            return JsonResponse(response_data)
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error calculating price: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

def ajax_check_availability(request):
    """
    AJAX endpoint to check aircraft availability for given dates
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            aircraft_id = data.get('aircraft_id')
            flight_legs = data.get('flight_legs', [])
            
            aircraft = get_object_or_404(Aircraft, id=aircraft_id)
            
            # Convert string dates to datetime objects
            for leg in flight_legs:
                leg['departure_datetime'] = datetime.fromisoformat(leg['departure_datetime'].replace('Z', '+00:00'))
                leg['arrival_datetime'] = datetime.fromisoformat(leg['arrival_datetime'].replace('Z', '+00:00'))
            
            available, message = check_aircraft_availability(aircraft, flight_legs)
            
            return JsonResponse({
                'available': available,
                'message': message
            })
            
        except Exception as e:
            return JsonResponse({
                'available': False,
                'message': f'Error checking availability: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)



from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Airport

def airport_list(request):
    query = request.GET.get('q', '')
    airports = Airport.objects.all()
    
    if query:
        airports = airports.filter(
            Q(icao_code__icontains=query) |
            Q(iata_code__icontains=query) |
            Q(name__icontains=query) |
            Q(city__icontains=query) |
            Q(country__icontains=query)
        )
    
    paginator = Paginator(airports, 10)  # Show 10 airports per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'airports/airport_list.html', {
        'page_obj': page_obj,
        'search_query': query
    })

def airport_detail(request, pk):
    airport = get_object_or_404(Airport, pk=pk)
    data = {
        'success': True,
        'airport': {
            'id': airport.id,
            'icao_code': airport.icao_code,
            'iata_code': airport.iata_code,
            'name': airport.name,
            'city': airport.city,
            'country': airport.country,
            'latitude': float(airport.latitude),
            'longitude': float(airport.longitude),
            'is_private_aviation_friendly': airport.is_private_aviation_friendly,
        }
    }
    return JsonResponse(data)

def airport_update(request, pk):
    if request.method == 'POST':
        airport = get_object_or_404(Airport, pk=pk)
        airport.icao_code = request.POST.get('icao_code', airport.icao_code)
        airport.iata_code = request.POST.get('iata_code', airport.iata_code)
        airport.name = request.POST.get('name', airport.name)
        airport.city = request.POST.get('city', airport.city)
        airport.country = request.POST.get('country', airport.country)
        airport.latitude = request.POST.get('latitude', airport.latitude)
        airport.longitude = request.POST.get('longitude', airport.longitude)
        airport.is_private_aviation_friendly = request.POST.get('is_private_aviation_friendly', 'false') == 'true'
        airport.save()
        
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

def airport_delete(request, pk):
    if request.method == 'POST':
        airport = get_object_or_404(Airport, pk=pk)
        airport.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import FlightLeg, Booking, Airport

def flightleg_list(request):
    query = request.GET.get('q', '')
    flightlegs = FlightLeg.objects.select_related('booking', 'departure_airport', 'arrival_airport').all()
    
    if query:
        flightlegs = flightlegs.filter(
            Q(booking__booking_order_id__icontains=query) |
            Q(departure_airport__icao_code__icontains=query) |
            Q(departure_airport__name__icontains=query) |
            Q(arrival_airport__icao_code__icontains=query) |
            Q(arrival_airport__name__icontains=query)
        )
    
    paginator = Paginator(flightlegs, 10)  # Show 10 flight legs per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'flightlegs/flightleg_list.html', {
        'page_obj': page_obj,
        'search_query': query
    })

def flightleg_detail(request, pk):
    flightleg = get_object_or_404(
        FlightLeg.objects.select_related(
            'booking', 
            'departure_airport', 
            'arrival_airport'
        ), 
        pk=pk
    )
    
    data = {
        'success': True,
        'flightleg': {
            'id': flightleg.id,
            'booking_id': flightleg.booking.id,
            'booking_order_id': flightleg.booking.booking_order_id,
            'departure_airport': {
                'icao_code': flightleg.departure_airport.icao_code,
                'name': flightleg.departure_airport.name,
                'city': flightleg.departure_airport.city,
                'country': flightleg.departure_airport.country,
            },
            'arrival_airport': {
                'icao_code': flightleg.arrival_airport.icao_code,
                'name': flightleg.arrival_airport.name,
                'city': flightleg.arrival_airport.city,
                'country': flightleg.arrival_airport.country,
            },
            'departure_datetime': flightleg.departure_datetime.strftime('%Y-%m-%d %H:%M'),
            'arrival_datetime': flightleg.arrival_datetime.strftime('%Y-%m-%d %H:%M'),
            'flight_hours': float(flightleg.flight_hours),
            'passenger_count': flightleg.passenger_count,
            'leg_price': float(flightleg.leg_price),
            'sequence': flightleg.sequence,
        }
    }
    return JsonResponse(data)

def flightleg_update(request, pk):
    if request.method == 'POST':
        flightleg = get_object_or_404(FlightLeg, pk=pk)
        
        try:
            flightleg.departure_airport = Airport.objects.get(pk=request.POST.get('departure_airport'))
            flightleg.arrival_airport = Airport.objects.get(pk=request.POST.get('arrival_airport'))
            flightleg.departure_datetime = request.POST.get('departure_datetime')
            flightleg.arrival_datetime = request.POST.get('arrival_datetime')
            flightleg.flight_hours = request.POST.get('flight_hours')
            flightleg.passenger_count = request.POST.get('passenger_count')
            flightleg.leg_price = request.POST.get('leg_price')
            flightleg.sequence = request.POST.get('sequence')
            flightleg.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

def flightleg_delete(request, pk):
    if request.method == 'POST':
        flightleg = get_object_or_404(FlightLeg, pk=pk)
        booking_id = flightleg.booking.id
        flightleg.delete()
        
        # Check if booking has any legs left
        remaining_legs = FlightLeg.objects.filter(booking_id=booking_id).exists()
        if not remaining_legs:
            Booking.objects.filter(id=booking_id).delete()
        
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


def airport_list_json(request):
    airports = Airport.objects.all().values('id', 'icao_code', 'name')
    return JsonResponse({
        'success': True,
        'airports': list(airports)
    })


# views.py
# views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction
from django.contrib import messages
import json
from decimal import Decimal
from .models import PricingRule, AircraftType


def pricing_rules_list(request):
    """Main view for pricing rules management page"""
    return render(request, 'pricing/pricing_rules.html')



def api_pricing_rules_list(request):
    """API endpoint to get all pricing rules"""
    if request.method == 'GET':
        # Get search parameter
        search = request.GET.get('search', '')
        
        # Filter pricing rules
        rules = PricingRule.objects.select_related('aircraft_type').all()
        if search:
            rules = rules.filter(aircraft_type__name__icontains=search)
        
        # Pagination
        page = request.GET.get('page', 1)
        paginator = Paginator(rules, 20)
        page_obj = paginator.get_page(page)
        
        # Serialize data
        data = []
        for rule in page_obj:
            data.append({
                'id': rule.id,
                'aircraft_type': {
                    'id': rule.aircraft_type.id,
                    'name': rule.aircraft_type.name,
                    'passenger_capacity': rule.aircraft_type.passenger_capacity,
                    'range_nautical_miles': rule.aircraft_type.range_nautical_miles,
                    'speed_knots': rule.aircraft_type.speed_knots,
                },
                'base_hourly_rate': str(rule.base_hourly_rate),
                'minimum_hours': str(rule.minimum_hours),
                'empty_leg_discount': str(rule.empty_leg_discount),
                'peak_season_multiplier': str(rule.peak_season_multiplier),
                'weekend_surcharge': str(rule.weekend_surcharge),
                'last_minute_surcharge': str(rule.last_minute_surcharge),
            })
        
        return JsonResponse({
            'results': data,
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'current_page': page_obj.number,
        })


@csrf_exempt
@require_http_methods(["POST"])
def api_pricing_rule_create(request):
    """API endpoint to create a new pricing rule"""
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        required_fields = ['aircraft_type', 'base_hourly_rate']
        for field in required_fields:
            if field not in data or not data[field]:
                return JsonResponse({
                    'error': f'{field} is required'
                }, status=400)
        
        # Get aircraft type
        try:
            aircraft_type = AircraftType.objects.get(id=data['aircraft_type'])
        except AircraftType.DoesNotExist:
            return JsonResponse({
                'error': 'Invalid aircraft type'
            }, status=400)
        
        # Check if pricing rule already exists for this aircraft type
        if PricingRule.objects.filter(aircraft_type=aircraft_type).exists():
            return JsonResponse({
                'error': 'Pricing rule already exists for this aircraft type'
            }, status=400)
        
        # Create pricing rule
        with transaction.atomic():
            pricing_rule = PricingRule.objects.create(
                aircraft_type=aircraft_type,
                base_hourly_rate=Decimal(str(data['base_hourly_rate'])),
                minimum_hours=Decimal(str(data.get('minimum_hours', '1.0'))),
                empty_leg_discount=Decimal(str(data.get('empty_leg_discount', '0'))),
                peak_season_multiplier=Decimal(str(data.get('peak_season_multiplier', '1.0'))),
                weekend_surcharge=Decimal(str(data.get('weekend_surcharge', '0'))),
                last_minute_surcharge=Decimal(str(data.get('last_minute_surcharge', '0'))),
            )
        
        return JsonResponse({
            'message': 'Pricing rule created successfully',
            'id': pricing_rule.id
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': f'Invalid data: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


def api_pricing_rule_detail(request, pk):
    """API endpoint to get a specific pricing rule"""
    rule = get_object_or_404(PricingRule.objects.select_related('aircraft_type'), pk=pk)
    
    data = {
        'id': rule.id,
        'aircraft_type': {
            'id': rule.aircraft_type.id,
            'name': rule.aircraft_type.name,
            'passenger_capacity': rule.aircraft_type.passenger_capacity,
            'range_nautical_miles': rule.aircraft_type.range_nautical_miles,
            'speed_knots': rule.aircraft_type.speed_knots,
        },
        'base_hourly_rate': str(rule.base_hourly_rate),
        'minimum_hours': str(rule.minimum_hours),
        'empty_leg_discount': str(rule.empty_leg_discount),
        'peak_season_multiplier': str(rule.peak_season_multiplier),
        'weekend_surcharge': str(rule.weekend_surcharge),
        'last_minute_surcharge': str(rule.last_minute_surcharge),
    }
    
    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["PUT"])
def api_pricing_rule_update(request, pk):
    """API endpoint to update a pricing rule"""
    rule = get_object_or_404(PricingRule, pk=pk)
    
    try:
        data = json.loads(request.body)
        
        # Update fields if provided
        if 'aircraft_type' in data:
            try:
                aircraft_type = AircraftType.objects.get(id=data['aircraft_type'])
                # Check if another rule exists for this aircraft type
                existing = PricingRule.objects.filter(
                    aircraft_type=aircraft_type
                ).exclude(id=rule.id)
                if existing.exists():
                    return JsonResponse({
                        'error': 'Pricing rule already exists for this aircraft type'
                    }, status=400)
                rule.aircraft_type = aircraft_type
            except AircraftType.DoesNotExist:
                return JsonResponse({'error': 'Invalid aircraft type'}, status=400)
        
        # Update other fields
        decimal_fields = [
            'base_hourly_rate', 'minimum_hours', 'empty_leg_discount',
            'peak_season_multiplier', 'weekend_surcharge', 'last_minute_surcharge'
        ]
        
        for field in decimal_fields:
            if field in data:
                setattr(rule, field, Decimal(str(data[field])))
        
        rule.save()
        
        return JsonResponse({'message': 'Pricing rule updated successfully'})
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': f'Invalid data: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def api_pricing_rule_delete(request, pk):
    """API endpoint to delete a pricing rule"""
    rule = get_object_or_404(PricingRule, pk=pk)
    
    try:
        rule.delete()
        return JsonResponse({'message': 'Pricing rule deleted successfully'})
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


def api_aircraft_types_list(request):
    """API endpoint to get all aircraft types"""
    aircraft_types = AircraftType.objects.all().order_by('name')
    
    data = []
    for aircraft_type in aircraft_types:
        data.append({
            'id': aircraft_type.id,
            'name': aircraft_type.name,
            'description': aircraft_type.description,
            'passenger_capacity': aircraft_type.passenger_capacity,
            'range_nautical_miles': aircraft_type.range_nautical_miles,
            'speed_knots': aircraft_type.speed_knots,
        })
    
    return JsonResponse({'results': data})


# Alternative function-based views for form handling (if you prefer forms over AJAX)
def pricing_rule_create_view(request):
    """Traditional form view to create pricing rule"""
    if request.method == 'POST':
        try:
            aircraft_type = get_object_or_404(AircraftType, id=request.POST.get('aircraft_type'))
            
            # Check if pricing rule already exists
            if PricingRule.objects.filter(aircraft_type=aircraft_type).exists():
                messages.error(request, 'Pricing rule already exists for this aircraft type')
                return render(request, 'pricing/pricing_rules.html', {
                    'aircraft_types': AircraftType.objects.all()
                })
            
            pricing_rule = PricingRule.objects.create(
                aircraft_type=aircraft_type,
                base_hourly_rate=Decimal(request.POST.get('base_hourly_rate', '0')),
                minimum_hours=Decimal(request.POST.get('minimum_hours', '1.0')),
                empty_leg_discount=Decimal(request.POST.get('empty_leg_discount', '0')),
                peak_season_multiplier=Decimal(request.POST.get('peak_season_multiplier', '1.0')),
                weekend_surcharge=Decimal(request.POST.get('weekend_surcharge', '0')),
                last_minute_surcharge=Decimal(request.POST.get('last_minute_surcharge', '0')),
            )
            
            messages.success(request, 'Pricing rule created successfully')
            
        except Exception as e:
            messages.error(request, f'Error creating pricing rule: {str(e)}')
    
    return render(request, 'pricing/pricing_rules.html', {
        'aircraft_types': AircraftType.objects.all()
    })


def pricing_rule_update_view(request, pk):
    """Traditional form view to update pricing rule"""
    rule = get_object_or_404(PricingRule, pk=pk)
    
    if request.method == 'POST':
        try:
            if request.POST.get('aircraft_type'):
                aircraft_type = get_object_or_404(AircraftType, id=request.POST.get('aircraft_type'))
                # Check if another rule exists for this aircraft type
                existing = PricingRule.objects.filter(
                    aircraft_type=aircraft_type
                ).exclude(id=rule.id)
                if existing.exists():
                    messages.error(request, 'Pricing rule already exists for this aircraft type')
                else:
                    rule.aircraft_type = aircraft_type
            
            # Update fields
            rule.base_hourly_rate = Decimal(request.POST.get('base_hourly_rate', rule.base_hourly_rate))
            rule.minimum_hours = Decimal(request.POST.get('minimum_hours', rule.minimum_hours))
            rule.empty_leg_discount = Decimal(request.POST.get('empty_leg_discount', rule.empty_leg_discount))
            rule.peak_season_multiplier = Decimal(request.POST.get('peak_season_multiplier', rule.peak_season_multiplier))
            rule.weekend_surcharge = Decimal(request.POST.get('weekend_surcharge', rule.weekend_surcharge))
            rule.last_minute_surcharge = Decimal(request.POST.get('last_minute_surcharge', rule.last_minute_surcharge))
            
            rule.save()
            messages.success(request, 'Pricing rule updated successfully')
            
        except Exception as e:
            messages.error(request, f'Error updating pricing rule: {str(e)}')
    
    return render(request, 'pricing/pricing_rules.html', {
        'aircraft_types': AircraftType.objects.all(),
        'edit_rule': rule
    })


def pricing_rule_delete_view(request, pk):
    """Traditional view to delete pricing rule"""
    rule = get_object_or_404(PricingRule, pk=pk)
    
    try:
        rule.delete()
        messages.success(request, 'Pricing rule deleted successfully')
    except Exception as e:
        messages.error(request, f'Error deleting pricing rule: {str(e)}')
    
    return render(request, 'pricing/pricing_rules.html')


@login_required
def settings_view(request): 
    return render(request, 'settings.html')

@login_required
def help_support(request):
    return render(request, 'help_support.html')

@login_required
def Flight_Announcement(request):
    return render(request, 'Flight_Announcement.html')

@login_required
def operations_reports(request):
    return render(request, 'operations_reports.html')



# views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import OwnerPayout

def owner_payments_list(request):
    """List all owner payments with search and pagination"""
    
    # Get search parameter
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    # Base queryset
    payments = OwnerPayout.objects.select_related('owner', 'booking', 'booking__aircraft').all()
    
    # Apply search filter
    if search_query:
        payments = payments.filter(
            Q(owner__username__icontains=search_query) |
            Q(owner__email__icontains=search_query) |
            Q(transaction_reference__icontains=search_query) |
            Q(booking__booking_order_id__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        payments = payments.filter(status=status_filter)
    
    # Order by newest first
    payments = payments.order_by('-payout_date', '-id')
    
    # Pagination
    paginator = Paginator(payments, 20)  # 20 payments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Status choices for filter dropdown
    status_choices = OwnerPayout._meta.get_field('status').choices
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': status_choices,
    }
    
    return render(request, 'payments/owner_payments_list.html', context)


def owner_payment_detail_ajax(request, payment_id):
    """AJAX view to fetch payment details"""
    
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        payment = get_object_or_404(
            OwnerPayout.objects.select_related(
                'owner', 'booking', 'booking__aircraft', 'booking__client'
            ),
            id=payment_id
        )
        
        # Prepare response data
        data = {
            'id': payment.id,
            'amount': str(payment.amount),
            'payout_date': payment.payout_date.strftime('%Y-%m-%d'),
            'status': payment.status,
            'transaction_reference': payment.transaction_reference,
            'owner': {
                'id': payment.owner.id,
                'name': payment.owner.get_full_name() or payment.owner.username,
                'email': payment.owner.email,
                'phone': getattr(payment.owner, 'phone_number', ''),
            },
            'booking': {
                'id': payment.booking.id,
                'order_id': payment.booking.booking_order_id,
                'status': payment.booking.status,
                'trip_type': payment.booking.get_trip_type_display(),
                'total_price': str(payment.booking.total_price),
                'owner_earnings': str(payment.booking.owner_earnings),
                'agent_commission': str(payment.booking.agent_commission),
                'created_at': payment.booking.created_at.strftime('%Y-%m-%d %H:%M'),
                'client': {
                    'name': payment.booking.client.get_full_name() or payment.booking.client.username,
                    'email': payment.booking.client.email,
                },
                'aircraft': {
                    'model': payment.booking.aircraft.model_name,
                    'registration': payment.booking.aircraft.registration_number,
                    'base_airport': payment.booking.aircraft.base_airport,
                }
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Aircraft, AircraftTracking
import json
from django.core.serializers import serialize
from decimal import Decimal

@login_required
def live_tracking(request):
    # Get all active aircraft 
    aircrafts = Aircraft.objects.filter( is_active=True).select_related('aircraft_type')
    
    # Get the latest tracking data for each aircraft
    aircraft_data = []
    
    for aircraft in aircrafts:
        try:
            # Get the latest tracking data
            latest_tracking = AircraftTracking.objects.filter(aircraft=aircraft).latest('timestamp')
            
            # Safely convert coordinates to float
            try:
                latitude = float(latest_tracking.latitude) if latest_tracking.latitude else None
                longitude = float(latest_tracking.longitude) if latest_tracking.longitude else None
            except (ValueError, TypeError):
                latitude = None
                longitude = None
            
            # Only include aircraft with valid coordinates
            if latitude is not None and longitude is not None and not (latitude == 0 and longitude == 0):
                aircraft_info = {
                    'id': aircraft.id,
                    'registration': aircraft.registration_number,
                    'model': aircraft.model_name,
                    'type': aircraft.aircraft_type.name if aircraft.aircraft_type else 'Unknown',
                    'current_location': aircraft.current_location or 'Unknown',
                    'latitude': latitude,
                    'longitude': longitude,
                    'altitude': latest_tracking.altitude or 0,
                    'heading': latest_tracking.heading or 0,
                    'speed': latest_tracking.speed or 0,
                    'timestamp': latest_tracking.timestamp.isoformat(),
                    'status': 'In Flight' if (latest_tracking.altitude or 0) > 500 else 'On Ground'
                }
            else:
                # Aircraft with no valid location data
                aircraft_info = {
                    'id': aircraft.id,
                    'registration': aircraft.registration_number,
                    'model': aircraft.model_name,
                    'type': aircraft.aircraft_type.name if aircraft.aircraft_type else 'Unknown',
                    'current_location': aircraft.base_airport or 'Unknown',
                    'latitude': None,  # Don't include on map
                    'longitude': None,  # Don't include on map
                    'altitude': 0,
                    'heading': 0,
                    'speed': 0,
                    'timestamp': timezone.now().isoformat(),
                    'status': 'No Data'
                }
            
            aircraft_data.append(aircraft_info)
            
        except AircraftTracking.DoesNotExist:
            # If no tracking data exists at all
            aircraft_data.append({
                'id': aircraft.id,
                'registration': aircraft.registration_number,
                'model': aircraft.model_name,
                'type': aircraft.aircraft_type.name if aircraft.aircraft_type else 'Unknown',
                'current_location': aircraft.base_airport or 'Unknown',
                'latitude': None,  # Don't include on map
                'longitude': None,  # Don't include on map
                'altitude': 0,
                'heading': 0,
                'speed': 0,
                'timestamp': timezone.now().isoformat(),
                'status': 'No Data'
            })
    
    # Filter aircraft with valid coordinates for the map
    map_aircraft_data = [aircraft for aircraft in aircraft_data if aircraft['latitude'] is not None and aircraft['longitude'] is not None]
    
    context = {
        'aircraft_json': json.dumps(map_aircraft_data),  # Only aircraft with valid coordinates for map
        'aircraft_list': aircrafts,
        'tracking_data': aircraft_data,  # All aircraft for the table
    }
    
    return render(request, 'aircraft/live_tracking.html', context)