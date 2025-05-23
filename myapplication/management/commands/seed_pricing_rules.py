from django.core.management.base import BaseCommand
from decimal import Decimal
from myapplication.models import PricingRule, AircraftType  # Adjust 'myapplication' to your app name
import random

class Command(BaseCommand):
    help = 'Seed pricing rules for all aircraft types'

    def handle(self, *args, **kwargs):
        aircraft_types = AircraftType.objects.all()

        if not aircraft_types.exists():
            self.stdout.write(self.style.ERROR("No aircraft types found in the database."))
            return

        for atype in aircraft_types:
            rule, created = PricingRule.objects.get_or_create(
                aircraft_type=atype,
                defaults={
                    'base_hourly_rate': Decimal(random.randint(3000, 9000)),
                    'minimum_hours': Decimal(random.choice([1.0, 1.5, 2.0])),
                    'empty_leg_discount': Decimal(random.choice([0, 5, 10, 15])),
                    'peak_season_multiplier': Decimal(random.choice([1.0, 1.2, 1.5])),
                    'weekend_surcharge': Decimal(random.choice([0, 5, 10])),
                    'last_minute_surcharge': Decimal(random.choice([0, 10, 20])),
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created pricing rule for {atype.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Pricing rule already exists for {atype.name}"))
