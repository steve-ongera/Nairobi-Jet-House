from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date
from .models import Booking, OwnerPayout
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Booking)
def create_owner_payout(sender, instance, created, **kwargs):
    """
    Automatically create OwnerPayout when a booking is confirmed
    """
    # Add debugging
    print(f"Signal triggered! Created: {created}, Status: {instance.status}")
    logger.info(f"Booking signal: created={created}, status={instance.status}")
    
    # Create payout for confirmed bookings (new or updated)
    if instance.status == 'confirmed':
        print(f"Booking is confirmed, checking for existing payout...")
        
        # Check if payout already exists to avoid duplicates
        existing_payout = OwnerPayout.objects.filter(booking=instance).first()
        
        if not existing_payout:
            try:
                payout = OwnerPayout.objects.create(
                    owner=instance.aircraft.owner,
                    booking=instance,
                    amount=instance.owner_earnings,
                    payout_date=date.today(),
                    transaction_reference=f"PAYOUT-{instance.booking_order_id}",
                    status='pending'
                )
                print(f"OwnerPayout created successfully: {payout}")
                logger.info(f"OwnerPayout created for booking {instance.id}")
            except Exception as e:
                print(f"Error creating OwnerPayout: {e}")
                logger.error(f"Error creating OwnerPayout: {e}")
        else:
            print(f"OwnerPayout already exists for this booking: {existing_payout}")
            logger.info(f"OwnerPayout already exists for booking {instance.id}")