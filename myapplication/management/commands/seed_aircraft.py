from django.core.management.base import BaseCommand
from myapplication.models import AircraftType

class Command(BaseCommand):
    help = 'Seed the database with initial aircraft types'

    def handle(self, *args, **kwargs):
        aircraft_data = [
            {
                'name': 'Gulfstream G650',
                'description': 'Long-range business jet with luxurious interiors.',
                'passenger_capacity': 18,
                'range_nautical_miles': 7500,
                'speed_knots': 516,
            },
            {
                'name': 'Bombardier Global 7500',
                'description': 'Ultra long-range jet known for performance and comfort.',
                'passenger_capacity': 19,
                'range_nautical_miles': 7700,
                'speed_knots': 513,
            },
            {
                'name': 'Cessna Citation XLS+',
                'description': 'Mid-size business jet with great speed and range.',
                'passenger_capacity': 9,
                'range_nautical_miles': 2100,
                'speed_knots': 441,
            },
            {
                'name': 'Airbus H145 Helicopter',
                'description': 'Multi-role twin-engine helicopter used for various missions.',
                'passenger_capacity': 9,
                'range_nautical_miles': 351,
                'speed_knots': 137,
            },
            {
                'name': 'Sikorsky S-76D',
                'description': 'Popular corporate and utility helicopter.',
                'passenger_capacity': 12,
                'range_nautical_miles': 441,
                'speed_knots': 155,
            },
            {
                'name': 'Embraer Phenom 300E',
                'description': 'Popular light jet ideal for short to medium routes.',
                'passenger_capacity': 8,
                'range_nautical_miles': 1971,
                'speed_knots': 453,
            },
        ]

        for data in aircraft_data:
            obj, created = AircraftType.objects.get_or_create(
                name=data['name'],
                defaults={
                    'description': data['description'],
                    'passenger_capacity': data['passenger_capacity'],
                    'range_nautical_miles': data['range_nautical_miles'],
                    'speed_knots': data['speed_knots'],
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Added aircraft: {obj.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Aircraft already exists: {obj.name}"))
