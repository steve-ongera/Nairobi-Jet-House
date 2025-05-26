from django.shortcuts import render
from django.shortcuts import render , redirect
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Aircraft, AircraftType, Availability, Airport
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.db import models


from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from datetime import datetime, timedelta, time
from django.utils import timezone
from .models import Aircraft, Airport, Availability

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
    base_rate = aircraft.hourly_rate
    minimum_hours = aircraft.minimum_hours
    
    # Use minimum hours or actual flight time, whichever is higher
    billable_hours = max(flight_hours, minimum_hours)
    
    base_price = float(base_rate) * billable_hours
    
    # Add positioning costs if aircraft is not at departure airport
    # (This would be more sophisticated in real implementation)
    
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

def contact_us(request):
    return render(request, 'contact-us.html')  

