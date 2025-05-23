from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from myapplication.models import Availability, Aircraft  # Adjust 'myapplication' to your actual app name
import random

class Command(BaseCommand):
    help = 'Seed availability periods for aircraft'

    def handle(self, *args, **kwargs):
        aircraft_list = list(Aircraft.objects.all())
        if not aircraft_list:
            self.stdout.write(self.style.ERROR("No aircraft found in the database."))
            return

        for index, aircraft in enumerate(aircraft_list[:5]):  # Seed for first 5 aircrafts
            for i in range(3):  # Create 3 availability periods per aircraft
                start_time = timezone.now() + timedelta(days=random.randint(1, 30))
                end_time = start_time + timedelta(days=random.randint(1, 5))

                availability = Availability.objects.create(
                    aircraft=aircraft,
                    start_datetime=start_time,
                    end_datetime=end_time,
                    is_available=True,
                    notes=f"Availability slot {i+1} for aircraft {aircraft.id}"
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Added availability for {aircraft} from {start_time} to {end_time}"
                ))
