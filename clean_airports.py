import os
import django
from django.db.models.deletion import ProtectedError
from django.db.models import Count

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Nairobi_Jet_House.settings')
django.setup()

from myapplication.models import Airport

def clean_airports():
    # List of ICAO codes for airports that Kenyan jets would realistically service
    # This includes major international airports, regional hubs, and popular tourist destinations
    KENYAN_JET_DESTINATIONS = {
        # Africa
        'HKJK',  # Nairobi, Kenya (Jomo Kenyatta)
        'HKMO',  # Mombasa, Kenya
        'HKKI',  # Kisumu, Kenya
        'HKEL',  # Eldoret, Kenya
        'HKKT',  # Kitale, Kenya
        'HKNW',  # Nairobi Wilson, Kenya
        'HKLU',  # Lodwar, Kenya
        'HKMA',  # Malindi, Kenya
        'HKWJ',  # Wajir, Kenya
        'HKGA',  # Garissa, Kenya
        'HKMB',  # Marsabit, Kenya
        'HKUK',  # Ukunda, Kenya
        'HKLO',  # Lokichogio, Kenya
        'HKMY',  # Moyale, Kenya
        'HKIS',  # Isiolo, Kenya
        'HKLY',  # Lamu, Kenya
        
        # Middle East
        'OMDB',  # Dubai, UAE
        'OTHH',  # Doha, Qatar
        'OEJN',  # Jeddah, Saudi Arabia
        'OERK',  # Riyadh, Saudi Arabia
        'OBBI',  # Bahrain
        'OKBK',  # Kuwait
        'OLBA',  # Beirut, Lebanon
        
        # Europe
        'EGLL',  # London Heathrow, UK
        'EGKK',  # London Gatwick, UK
        'EHAM',  # Amsterdam, Netherlands
        'EDDF',  # Frankfurt, Germany
        'LFPG',  # Paris CDG, France
        'LEMD',  # Madrid, Spain
        'LIRF',  # Rome, Italy
        'LSZH',  # Zurich, Switzerland
        
        # Asia
        'VIDP',  # Delhi, India
        'VABB',  # Mumbai, India
        'VCBI',  # Colombo, Sri Lanka
        'VTBS',  # Bangkok, Thailand
        'WSSS',  # Singapore
        'ZGGG',  # Guangzhou, China
        'ZSPD',  # Shanghai, China
        'RJAA',  # Tokyo Narita, Japan
        'VHHH',  # Hong Kong
        
        # North America
        'KJFK',  # New York JFK, USA
        'KLAX',  # Los Angeles, USA
        'KORD',  # Chicago, USA
        'CYYZ',  # Toronto, Canada
        
        # Other major African airports
        'FACT',  # Cape Town, South Africa
        'FAOR',  # Johannesburg, South Africa
        'DNMM',  # Lagos, Nigeria
        'DGAA',  # Accra, Ghana
        'HECA',  # Cairo, Egypt
        'HSSS',  # Khartoum, Sudan
        'FIMP',  # Mauritius
        'FMEE',  # Reunion
        'HRYR',  # Kigali, Rwanda
        'HUEN',  # Entebbe, Uganda
        'HTDA',  # Dar es Salaam, Tanzania
        'FQMA',  # Maputo, Mozambique
        'FNLU',  # Luanda, Angola
        'GMMN',  # Casablanca, Morocco
        'DTTA',  # Tunis, Tunisia
        'DAAG',  # Algiers, Algeria
    }
    
    # First, let's analyze what we have
    print("Analyzing airport usage...")
    analyze_airport_usage()
    
    # Get all airports not in our approved list
    airports_to_delete = Airport.objects.exclude(icao_code__in=KENYAN_JET_DESTINATIONS)
    
    # Separate airports that can be safely deleted from those that are protected
    safe_to_delete = []
    protected_airports = []
    
    print("\nChecking which airports can be safely deleted...")
    for airport in airports_to_delete:
        try:
            # Check if airport has any flight leg references
            departure_count = airport.departure_legs.count() if hasattr(airport, 'departure_legs') else 0
            arrival_count = airport.arrival_legs.count() if hasattr(airport, 'arrival_legs') else 0
            
            if departure_count == 0 and arrival_count == 0:
                safe_to_delete.append(airport)
            else:
                protected_airports.append((airport, departure_count + arrival_count))
        except Exception as e:
            print(f"Error checking airport {airport.icao_code}: {e}")
            safe_to_delete.append(airport)  # Assume safe if we can't check
    
    # Count before deletion
    count_before = Airport.objects.count()
    count_safe_to_delete = len(safe_to_delete)
    count_protected = len(protected_airports)
    
    print(f"\n=== CLEANUP SUMMARY ===")
    print(f"Total airports before cleanup: {count_before}")
    print(f"Airports safe to delete: {count_safe_to_delete}")
    print(f"Airports protected (in use): {count_protected}")
    print(f"Airports that will remain: {count_before - count_safe_to_delete}")
    
    if count_protected > 0:
        print(f"\nProtected airports (currently in use):")
        for airport, usage_count in protected_airports[:10]:  # Show first 10
            print(f"  - {airport.icao_code}: {airport.name} ({usage_count} flights)")
        if len(protected_airports) > 10:
            print(f"  ... and {len(protected_airports) - 10} more")
    
    # Confirm deletion
    if count_safe_to_delete > 0:
        print(f"\nThis will delete {count_safe_to_delete} unused airports.")
        confirm = input("Proceed with safe deletion? (yes/no): ")
        
        if confirm.lower() == 'yes':
            deleted_count = 0
            for airport in safe_to_delete:
                try:
                    airport.delete()
                    deleted_count += 1
                    if deleted_count % 100 == 0:  # Progress indicator
                        print(f"Deleted {deleted_count} airports...")
                except Exception as e:
                    print(f"Error deleting {airport.icao_code}: {e}")
            
            print(f"Successfully deleted {deleted_count} airports")
            
            # Show final count
            final_count = Airport.objects.count()
            print(f"Final airport count: {final_count}")
        else:
            print("Cleanup cancelled")
    else:
        print("\nNo airports are safe to delete. All remaining airports are either:")
        print("1. In your approved destinations list, or")
        print("2. Currently being used by existing flight bookings")
    
    # Ask about handling protected airports
    if count_protected > 0:
        print(f"\nYou have {count_protected} airports that are currently in use by flight bookings.")
        print("Options for handling these:")
        print("1. Leave them (recommended)")
        print("2. View detailed usage information")
        print("3. Handle them interactively (advanced)")
        
        choice = input("Choose option (1-3): ")
        
        if choice == '2':
            show_detailed_usage(protected_airports)
        elif choice == '3':
            handle_protected_airports_interactive(protected_airports, KENYAN_JET_DESTINATIONS)

def analyze_airport_usage():
    """Analyze airport usage patterns"""
    try:
        # Get airports with usage counts
        airports_with_usage = Airport.objects.annotate(
            departure_count=Count('departure_legs', distinct=True),
            arrival_count=Count('arrival_legs', distinct=True)
        ).filter(
            departure_count__gt=0
        ).union(
            Airport.objects.annotate(
                departure_count=Count('departure_legs', distinct=True),
                arrival_count=Count('arrival_legs', distinct=True)
            ).filter(
                arrival_count__gt=0
            )
        ).order_by('-departure_count', '-arrival_count')
        
        used_count = airports_with_usage.count()
        total_count = Airport.objects.count()
        unused_count = total_count - used_count
        
        print(f"Airport Usage Analysis:")
        print(f"  Total airports: {total_count}")
        print(f"  Used in bookings: {used_count}")
        print(f"  Unused: {unused_count}")
        
        if used_count > 0:
            print(f"\nMost used airports:")
            for airport in airports_with_usage[:5]:
                dep_count = airport.departure_count if hasattr(airport, 'departure_count') else 0
                arr_count = airport.arrival_count if hasattr(airport, 'arrival_count') else 0
                total_usage = dep_count + arr_count
                print(f"  {airport.icao_code}: {airport.name} ({total_usage} flights)")
                
    except Exception as e:
        print(f"Could not analyze usage: {e}")

def show_detailed_usage(protected_airports):
    """Show detailed usage information for protected airports"""
    print(f"\nDetailed usage for protected airports:")
    print("-" * 80)
    
    for airport, usage_count in protected_airports[:20]:  # Limit to first 20
        print(f"\n{airport.icao_code} - {airport.name}")
        print(f"  Total flights: {usage_count}")
        
        try:
            # Show some example flight legs
            departure_legs = airport.departure_legs.all()[:3]
            arrival_legs = airport.arrival_legs.all()[:3]
            
            if departure_legs:
                print("  Departure flights:")
                for leg in departure_legs:
                    print(f"    → {leg.arrival_airport.icao_code} (Booking {leg.booking.id})")
            
            if arrival_legs:
                print("  Arrival flights:")
                for leg in arrival_legs:
                    print(f"    ← {leg.departure_airport.icao_code} (Booking {leg.booking.id})")
                    
        except Exception as e:
            print(f"  Error getting flight details: {e}")

def handle_protected_airports_interactive(protected_airports, approved_destinations):
    """Handle protected airports interactively"""
    print(f"\nInteractive handling of {len(protected_airports)} protected airports")
    print("For each airport, you can choose to:")
    print("1. Keep it")
    print("2. Replace it with a nearby approved airport")
    print("3. Delete associated bookings (DANGEROUS!)")
    print("4. Skip to next")
    print("5. Stop interactive mode")
    
    for airport, usage_count in protected_airports:
        print(f"\n{airport.icao_code} - {airport.name} ({usage_count} flights)")
        
        # Find nearby approved airports (this is a simplified approach)
        nearby_approved = [code for code in approved_destinations if code.startswith(airport.icao_code[:2])]
        if nearby_approved:
            print(f"  Nearby approved alternatives: {', '.join(nearby_approved[:3])}")
        
        choice = input("Action (1-5): ")
        
        if choice == '1':
            print("  Keeping airport")
            continue
        elif choice == '2':
            if nearby_approved:
                replacement_code = input(f"Enter replacement ICAO code ({', '.join(nearby_approved[:3])}): ")
                if replacement_code in approved_destinations:
                    try:
                        replacement_airport = Airport.objects.get(icao_code=replacement_code)
                        # Replace references (this is simplified - you may need more complex logic)
                        airport.departure_legs.update(departure_airport=replacement_airport)
                        airport.arrival_legs.update(arrival_airport=replacement_airport)
                        airport.delete()
                        print(f"  Replaced with {replacement_code}")
                    except Airport.DoesNotExist:
                        print(f"  Replacement airport {replacement_code} not found")
                    except Exception as e:
                        print(f"  Error replacing: {e}")
                else:
                    print("  Invalid replacement code")
            else:
                print("  No nearby approved alternatives found")
        elif choice == '3':
            confirm = input("  Are you SURE you want to delete associated bookings? (yes/no): ")
            if confirm.lower() == 'yes':
                try:
                    # Get all bookings that use this airport
                    booking_ids = set()
                    for leg in airport.departure_legs.all():
                        booking_ids.add(leg.booking.id)
                    for leg in airport.arrival_legs.all():
                        booking_ids.add(leg.booking.id)
                    
                    # Delete bookings
                    for booking_id in booking_ids:
                        try:
                            from myapplication.models import Booking
                            booking = Booking.objects.get(id=booking_id)
                            booking.delete()
                        except:
                            pass
                    
                    airport.delete()
                    print(f"  Deleted airport and {len(booking_ids)} bookings")
                except Exception as e:
                    print(f"  Error deleting: {e}")
            else:
                print("  Cancelled")
        elif choice == '4':
            print("  Skipped")
            continue
        elif choice == '5':
            print("Stopping interactive mode")
            break
        else:
            print("  Invalid choice, skipping")

if __name__ == '__main__':
    clean_airports()