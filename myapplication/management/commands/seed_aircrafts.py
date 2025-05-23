from myapplication.models import Aircraft, AircraftType, User
from decimal import Decimal
import random

# Sample data
model_names = [
    "Gulfstream G650", "Cessna Citation X", "Embraer Phenom 300", "Bombardier Global 7500",
    "Dassault Falcon 900", "Learjet 75", "Cirrus Vision Jet", "HondaJet Elite", 
    "Beechcraft King Air 350i", "Pilatus PC-24"
]

icao_airports = ['HKJK', 'KJFK', 'EGLL', 'OMDB', 'LFPG', 'EDDF', 'VHHH', 'YSSY', 'RJTT', 'FAOR']

# Get the first 10 owners and at least 6 aircraft types
owners = list(User.objects.filter(user_type='owner')[:10])
aircraft_types = list(AircraftType.objects.all())

for i in range(10):
    aircraft = Aircraft.objects.create(
        owner=owners[i],
        aircraft_type=aircraft_types[i % len(aircraft_types)],
        registration_number=f"5Y-AX{i+1}",
        model_name=model_names[i],
        year_manufactured=random.randint(2005, 2022),
        base_airport=icao_airports[i % len(icao_airports)],
        current_location=icao_airports[(i + 1) % len(icao_airports)],
        is_active=True,
        features="Wi-Fi, Leather seats, Satellite phone",
        hourly_rate=Decimal(random.randint(2500, 10000)),
        minimum_hours=Decimal("1.5")
    )
    print(f"Created Aircraft: {aircraft}")
