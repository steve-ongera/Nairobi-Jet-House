from django.shortcuts import render
from django.shortcuts import render , redirect
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Aircraft, AircraftType, Availability, Airport
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.db import models


def find_aircraft(request):
    if request.method == 'POST':
        # Get form data
        departure_icao = request.POST.get('departure_airport').upper()
        arrival_icao = request.POST.get('arrival_airport').upper()
        passenger_count = int(request.POST.get('passenger_count'))
        departure_date = request.POST.get('departure_date')
        departure_time = request.POST.get('departure_time')
        trip_type = request.POST.get('trip_type')
        
        # Convert to datetime
        departure_datetime = datetime.strptime(
            f"{departure_date} {departure_time}", 
            "%Y-%m-%d %H:%M"
        )
        
        # Calculate end time (assuming 4 hour minimum booking)
        end_datetime = departure_datetime + timedelta(hours=4)
        
        # Get airport details
        try:
            departure_airport = Airport.objects.get(icao_code=departure_icao)
            arrival_airport = Airport.objects.get(icao_code=arrival_icao)
        except Airport.DoesNotExist:
            # Handle error - redirect back with error message
            messages.error(request, 'One or both airports not found. Please check the airport codes.')
            return redirect('index')
        
        # Query available aircraft (only after airports are validated)
        available_aircraft = Aircraft.objects.filter(
            aircraft_type__passenger_capacity__gte=passenger_count,
            current_location=departure_icao,
            is_active=True,
            availabilities__start_datetime__lte=departure_datetime,
            availabilities__end_datetime__gte=end_datetime,
            availabilities__is_available=True
        ).distinct().select_related('aircraft_type')
        
        context = {
            'aircraft_list': available_aircraft,
            'departure_airport': departure_airport,
            'arrival_airport': arrival_airport,
            'departure_datetime': departure_datetime,
            'passenger_count': passenger_count,
            'trip_type': trip_type,
            'client_email': request.POST.get('client_email'),
            'client_name': request.POST.get('client_name'),
            'special_requests': request.POST.get('special_requests'),
        }
        
        return render(request, 'booking/available_aircraft.html', context)
    
    # If not POST, redirect back
    return redirect('index')


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
    return render(request, 'about.html')  # Make sure you create templates/index.html

