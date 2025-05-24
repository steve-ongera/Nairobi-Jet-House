from django.shortcuts import render
from django.shortcuts import render , redirect
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Aircraft, AircraftType, Availability, Airport

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
        
        # Query available aircraft
        available_aircraft = Aircraft.objects.filter(
            aircraft_type__passenger_capacity__gte=passenger_count,
            current_location=departure_icao,
            is_active=True,
            availabilities__start_datetime__lte=departure_datetime,
            availabilities__end_datetime__gte=end_datetime,
            availabilities__is_available=True
        ).distinct().select_related('aircraft_type')
        
        # Get airport details
        try:
            departure_airport = Airport.objects.get(icao_code=departure_icao)
            arrival_airport = Airport.objects.get(icao_code=arrival_icao)
        except Airport.DoesNotExist:
            # Handle error - maybe redirect back with message
            pass
        
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
    return redirect('home')

def index(request):
    return render(request, 'index.html')  # Make sure you create templates/index.html

def about_us(request):
    return render(request, 'about.html')  # Make sure you create templates/index.html

