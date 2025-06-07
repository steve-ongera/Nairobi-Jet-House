"""
Django Management Command: Generate Simple Aircraft Tracking Data
Place this file in: myapplication/management/commands/generate_tracking.py

Usage:
    python manage.py generate_tracking
    python manage.py generate_tracking --flights 8 --ground 6
    python manage.py generate_tracking --clear-existing
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

from myapplication.models import Aircraft, AircraftTracking


class Command(BaseCommand):
    help = 'Generate simple aircraft tracking data for demonstration and testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flights',
            type=int,
            default=6,
            help='Number of flight paths to generate (default: 6)'
        )
        parser.add_argument(
            '--ground',
            type=int,
            default=4,
            help='Number of ground tracking sequences to generate (default: 4)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear all existing tracking data before generating new data'
        )
        parser.add_argument(
            '--hours-back',
            type=int,
            default=12,
            help='Maximum hours back to start generating data (default: 12)'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Simple airport coordinates
        self.airports = [
            {'lat': 40.641311, 'lon': -73.778139, 'name': 'JFK New York'},
            {'lat': 33.943399, 'lon': -118.410042, 'name': 'LAX Los Angeles'},
            {'lat': 41.979595, 'lon': -87.904464, 'name': 'ORD Chicago'},
            {'lat': 39.858844, 'lon': -104.667656, 'name': 'DEN Denver'},
            {'lat': 25.793449, 'lon': -80.290556, 'name': 'MIA Miami'},
            {'lat': 33.636719, 'lon': -84.428067, 'name': 'ATL Atlanta'},
        ]
        
        # Tracking data sources
        self.sources = ['ADS-B', 'Radar', 'GPS', 'Satellite', 'ACARS']

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🛩️  Aircraft Tracking Data Generator'))
        self.stdout.write('=' * 50)

        # Clear existing data if requested
        if options['clear_existing']:
            self.clear_existing_data()

        # Validate aircraft availability
        aircraft_count = Aircraft.objects.count()
        if aircraft_count == 0:
            raise CommandError('No aircraft found in database. Please create some aircraft first.')

        total_needed = options['flights'] + options['ground']
        if aircraft_count < total_needed:
            self.stdout.write(
                self.style.WARNING(
                    f'Only {aircraft_count} aircraft available for {total_needed} requested sequences.'
                )
            )
            options['flights'] = min(options['flights'], aircraft_count)
            options['ground'] = min(options['ground'], aircraft_count - options['flights'])

        # Generate tracking data
        try:
            with transaction.atomic():
                tracking_data = self.generate_all_tracking_data(
                    num_flights=options['flights'],
                    num_ground=options['ground'],
                    hours_back=options['hours_back']
                )
                
                # Bulk create all tracking data
                self.stdout.write(f'💾 Saving {len(tracking_data)} tracking points to database...')
                AircraftTracking.objects.bulk_create([
                    AircraftTracking(**data) for data in tracking_data
                ])

            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Successfully generated {len(tracking_data)} tracking records!'
                )
            )
            
            # Print summary
            self.print_summary()

        except Exception as e:
            raise CommandError(f'Error generating tracking data: {e}')

    def clear_existing_data(self):
        """Clear all existing tracking data"""
        count = AircraftTracking.objects.count()
        if count > 0:
            AircraftTracking.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'🗑️  Cleared {count} existing tracking records')
            )
        else:
            self.stdout.write('ℹ️  No existing tracking data to clear')

    def generate_flight_tracking(self, aircraft, hours_back):
        """Generate simple flight tracking data"""
        tracking_points = []
        current_time = timezone.now() - timedelta(hours=random.randint(1, hours_back))
        
        # Pick random start and end airports
        start_airport = random.choice(self.airports)
        end_airport = random.choice([a for a in self.airports if a != start_airport])
        
        # Generate 20-50 tracking points for the flight
        num_points = random.randint(20, 50)
        
        for i in range(num_points):
            # Simple interpolation between airports
            progress = i / (num_points - 1)
            
            lat = start_airport['lat'] + (end_airport['lat'] - start_airport['lat']) * progress
            lon = start_airport['lon'] + (end_airport['lon'] - start_airport['lon']) * progress
            
            # Add some random variation
            lat += random.uniform(-0.1, 0.1)
            lon += random.uniform(-0.1, 0.1)
            
            # Simple altitude profile - start low, go high, then descend
            if progress < 0.2:  # Takeoff
                altitude = int(progress * 5 * 35000)  # 0 to 35000
            elif progress > 0.8:  # Landing
                altitude = int((1 - progress) * 5 * 35000)  # 35000 to 0
            else:  # Cruise
                altitude = random.randint(30000, 40000)
            
            # Simple speed - faster at cruise, slower at takeoff/landing
            if progress < 0.2 or progress > 0.8:
                speed = random.randint(150, 250)
            else:
                speed = random.randint(400, 550)
            
            tracking_points.append({
                'aircraft': aircraft,
                'timestamp': current_time,
                'latitude': Decimal(f"{lat:.6f}"),
                'longitude': Decimal(f"{lon:.6f}"),
                'altitude': altitude,
                'heading': random.randint(0, 359),
                'speed': speed,
                'source': random.choice(self.sources)
            })
            
            current_time += timedelta(minutes=random.randint(2, 8))
        
        return tracking_points

    def generate_ground_tracking(self, aircraft, hours_back):
        """Generate simple ground tracking data"""
        tracking_points = []
        current_time = timezone.now() - timedelta(hours=random.randint(1, hours_back))
        
        # Pick a random airport
        airport = random.choice(self.airports)
        
        # Generate 10-20 tracking points on ground
        num_points = random.randint(10, 20)
        
        for i in range(num_points):
            # Small movements around airport
            lat = airport['lat'] + random.uniform(-0.01, 0.01)
            lon = airport['lon'] + random.uniform(-0.01, 0.01)
            
            tracking_points.append({
                'aircraft': aircraft,
                'timestamp': current_time,
                'latitude': Decimal(f"{lat:.6f}"),
                'longitude': Decimal(f"{lon:.6f}"),
                'altitude': random.randint(0, 100),  # Ground level
                'heading': random.randint(0, 359),
                'speed': random.randint(0, 30),  # Taxi speed
                'source': random.choice(self.sources)
            })
            
            current_time += timedelta(minutes=random.randint(10, 30))
        
        return tracking_points

    def generate_all_tracking_data(self, num_flights, num_ground, hours_back):
        """Generate all tracking data"""
        aircraft_list = list(Aircraft.objects.all())
        tracking_data = []
        
        # Generate flight tracking data
        self.stdout.write(f'✈️  Generating {num_flights} flight paths...')
        for i in range(num_flights):
            aircraft = aircraft_list[i]
            self.stdout.write(f'   📍 Generating flight for {aircraft}')
            
            flight_tracking = self.generate_flight_tracking(aircraft, hours_back)
            tracking_data.extend(flight_tracking)
        
        # Generate ground tracking data
        self.stdout.write(f'🏢 Generating {num_ground} ground tracking sequences...')
        for i in range(num_ground):
            aircraft = aircraft_list[num_flights + i]
            self.stdout.write(f'   🚁 Generating ground tracking for {aircraft}')
            
            ground_tracking = self.generate_ground_tracking(aircraft, hours_back)
            tracking_data.extend(ground_tracking)
        
        return tracking_data

    def print_summary(self):
        """Print summary of generated data"""
        total_tracking = A