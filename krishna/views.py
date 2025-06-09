from functools import wraps
from multiprocessing import context
from sqlite3 import IntegrityError
from django.http import Http404,HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed , HttpResponseRedirect, JsonResponse
import pytz
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from user.models import HotelStaff
from .forms import HotelAssignmentForm, RoomForm
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
import logging
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from datetime import datetime, timedelta
from .models import Rooms, Hotels, Reservation 



User = get_user_model()
User.objects.all()  
# Configure logging
logger = logging.getLogger(__name__)


def login_required_with_message(message="You have to signin first.", login_url=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, message)
                return redirect(login_url or 'user:signin')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def homepage(request):
    """
    Display hotels filtered by hotel_type, sorted by rank (descending) and name, with default check-in (tomorrow) and checkout (next Thursday).
    Handles search filters and stores them in session.
    """
    logger.debug(f"Processing homepage, request.GET={request.GET}")

    # Fetch all hotels for dropdown, ordered by name
    all_hotels = Hotels.objects.all().distinct().order_by('name')
    hotels_with_counts = []

    # Get today's date
    today = timezone.now().date()

    # Set default check-in (tomorrow) and checkout (next Thursday)
    default_check_in = today + timedelta(days=1)
    days_to_thursday = (3 - default_check_in.weekday()) % 7
    if days_to_thursday == 0:
        days_to_thursday = 7
    default_check_out = default_check_in + timedelta(days=days_to_thursday)

    # Initialize filters, prioritizing GET over session
    location = request.GET.get('search_location') or request.session.get('location')
    check_in = request.GET.get('cin') or request.session.get('check_in')
    check_out = request.GET.get('cout') or request.session.get('check_out')
    capacity = request.GET.get('capacity') or request.session.get('capacity', '1')
    min_price = request.GET.get('min_price') or request.session.get('min_price')
    max_price = request.GET.get('max_price') or request.session.get('max_price')
    hotel_type = request.GET.get('hotel_type') or request.session.get('hotel_type')  # Preserve session hotel_type

    # Amenity filters
    amenities = ['ac', 'fan', 'wifi', 'parking', 'heater', 'food_facility']
    active_amenities = {amenity: request.GET.get(amenity) or request.session.get('amenities', {}).get(amenity) for amenity in amenities}

    # Only reset hotel_type if explicitly cleared (e.g., via "All Types")
    if request.GET.get('clear_filters'):
        hotel_type = None
        request.session['hotel_type'] = None

    # Validate and parse dates
    formatted_check_in = None
    formatted_check_out = None
    check_in_date = None
    check_out_date = None

    try:
        if check_in:
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            if check_in_date < today:
                messages.error(request, "Check-in date cannot be in the past")
                check_in_date = default_check_in
                check_in = default_check_in.strftime('%Y-%m-%d')
        else:
            check_in_date = default_check_in
            check_in = default_check_in.strftime('%Y-%m-%d')

        formatted_check_in = check_in_date.strftime('%d %B %Y')

        if check_out:
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            if check_out_date <= check_in_date:
                messages.error(request, "Check-out date must be after check-in date")
                check_out_date = default_check_out
                check_out = default_check_out.strftime('%Y-%m-%d')
        else:
            check_out_date = default_check_out
            check_out = default_check_out.strftime('%Y-%m-%d')

        formatted_check_out = check_out_date.strftime('%d %B %Y')

    except ValueError as e:
        logger.error(f"Invalid date format: {str(e)}")
        messages.error(request, f"Invalid date format: {str(e)}")
        check_in_date = default_check_in
        check_out_date = default_check_out
        check_in = default_check_in.strftime('%Y-%m-%d')
        check_out = default_check_out.strftime('%Y-%m-%d')
        formatted_check_in = default_check_in.strftime('%d %B %Y')
        formatted_check_out = default_check_out.strftime('%d %B %Y')

    # Store search criteria in session
    request.session['check_in'] = check_in
    request.session['check_out'] = check_out
    request.session['capacity'] = capacity
    request.session['location'] = location
    request.session['min_price'] = str(min_price) if min_price else None
    request.session['max_price'] = str(max_price) if max_price else None
    request.session['hotel_type'] = hotel_type
    request.session['amenities'] = {k: v for k, v in active_amenities.items() if v}
    request.session.modified = True

    # Base query for rooms
    rooms_query = Rooms.objects.filter(status='1')

    # Apply hotel_type filter if provided
    logger.debug(f"Applying hotel_type filter: {hotel_type}")
    if hotel_type and hotel_type in dict(Hotels.HOTEL_TYPE_CHOICES):
        rooms_query = rooms_query.filter(hotel__hotel_type=hotel_type)

    # Apply other filters
    if location:
        rooms_query = rooms_query.filter(hotel__id=location)

    if check_in_date and check_out_date:
        try:
            reserved_rooms = Reservation.objects.filter(
                check_in__lt=check_out_date,
                check_out__gt=check_in_date
            ).values_list('room_id', flat=True)
            rooms_query = rooms_query.exclude(id__in=reserved_rooms)
        except Exception as e:
            logger.error(f"Error filtering rooms by date: {str(e)}")
            messages.error(request, f"Error filtering rooms by date: {str(e)}")

    if capacity:
        try:
            capacity = int(capacity)
            if capacity <= 0:
                raise ValueError("Capacity must be positive")
            rooms_query = rooms_query.filter(capacity__gte=capacity)
        except ValueError:
            logger.error(f"Invalid capacity value: {capacity}")
            messages.error(request, "Invalid capacity value")

    if min_price and max_price:
        try:
            min_price = Decimal(min_price)
            max_price = Decimal(max_price)
            if min_price < 0 or max_price < min_price:
                raise ValueError("Invalid price range")
            rooms_query = rooms_query.filter(price__gte=min_price, price__lte=max_price)
        except ValueError:
            logger.error(f"Invalid price range - min: {min_price}, max: {max_price}")
            messages.error(request, "Invalid price range")

    for amenity, value in active_amenities.items():
        if value == '1':
            rooms_query = rooms_query.filter(**{amenity: True})

    # Log query results
    logger.debug(f"Rooms after filtering: {rooms_query.count()}")

    # Get hotels with available rooms
    available_hotel_ids = rooms_query.values_list('hotel_id', flat=True).distinct()
    hotels = Hotels.objects.filter(id__in=available_hotel_ids)
    logger.debug(f"Hotels after filtering: {hotels.count()}")

    for hotel in hotels:
        available_rooms_count = rooms_query.filter(hotel=hotel).count()
        hotels_with_counts.append({
            'hotel': hotel,
            'available_rooms_count': available_rooms_count
        })

    # Provide feedback if no hotels are found
    if not hotels.exists():
        if hotel_type:
            messages.info(request, f"No available rooms for {dict(Hotels.HOTEL_TYPE_CHOICES).get(hotel_type, 'selected type')}.")
        else:
            messages.warning(request, "No hotels have available rooms for the selected criteria.")

    context = {
        'hotels': hotels_with_counts,
        'all_hotels': all_hotels,
        'flag': True if request.method == "POST" or request.GET.get('cin') else False,
        'check_in': check_in,
        'check_out': check_out,
        'formatted_check_in': formatted_check_in,
        'formatted_check_out': formatted_check_out,
        'capacity': capacity,
        'location': location,
        'min_price': min_price,
        'max_price': max_price,
        'hotel_type': hotel_type,
        'hotel_type_label': dict(Hotels.HOTEL_TYPE_CHOICES).get(hotel_type, 'All Types') if hotel_type else 'All Types',
        'active_amenities': active_amenities
    }
    return render(request, 'rooms/index.html', context)

def view_rooms(request, hotel_id):
    """
    Display rooms for a specific hotel, respecting applied filters.
    """
    logger.debug(f"Processing view_rooms for hotel_id={hotel_id}, request.GET={request.GET}")

    # Retrieve filters from GET or session
    hotel_type = request.GET.get('hotel_type') or request.session.get('hotel_type')
    check_in = request.GET.get('cin') or request.session.get('check_in')
    check_out = request.GET.get('cout') or request.session.get('check_out')
    capacity = request.GET.get('capacity') or request.session.get('capacity', '1')
    min_price = request.GET.get('min_price') or request.session.get('min_price')
    max_price = request.GET.get('max_price') or request.session.get('max_price')
    amenities = ['ac', 'fan', 'wifi', 'parking', 'heater', 'food_facility']
    active_amenities = {amenity: request.GET.get(amenity) or request.session.get('amenities', {}).get(amenity) for amenity in amenities}

    # Validate dates
    today = timezone.now().date()
    default_check_in = today + timedelta(days=1)
    days_to_thursday = (3 - default_check_in.weekday()) % 7
    if days_to_thursday == 0:
        days_to_thursday = 7
    default_check_out = default_check_in + timedelta(days=days_to_thursday)

    try:
        check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date() if check_in else default_check_in
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date() if check_out else default_check_out
        if check_in_date < today:
            messages.error(request, "Check-in date cannot be in the past")
            check_in_date = default_check_in
        if check_out_date <= check_in_date:
            messages.error(request, "Check-out date must be after check-in date")
            check_out_date = default_check_out
    except ValueError as e:
        logger.error(f"Invalid date format: {str(e)}")
        messages.error(request, f"Invalid date format: {str(e)}")
        check_in_date = default_check_in
        check_out_date = default_check_out

    # Base query for rooms
    rooms_query = Rooms.objects.filter(status='1', hotel_id=hotel_id)

    # Apply hotel_type filter
    if hotel_type and hotel_type in dict(Hotels.HOTEL_TYPE_CHOICES):
        rooms_query = rooms_query.filter(hotel__hotel_type=hotel_type)

    # Apply other filters
    if check_in_date and check_out_date:
        try:
            reserved_rooms = Reservation.objects.filter(
                check_in__lt=check_out_date,
                check_out__gt=check_in_date
            ).values_list('room_id', flat=True)
            rooms_query = rooms_query.exclude(id__in=reserved_rooms)
        except Exception as e:
            logger.error(f"Error filtering rooms by date: {str(e)}")
            messages.error(request, f"Error filtering rooms by date: {str(e)}")

    if capacity:
        try:
            capacity = int(capacity)
            if capacity <= 0:
                raise ValueError("Capacity must be positive")
            rooms_query = rooms_query.filter(capacity__gte=capacity)
        except ValueError:
            logger.error(f"Invalid capacity value: {capacity}")
            messages.error(request, "Invalid capacity value")

    if min_price and max_price:
        try:
            min_price = Decimal(min_price)
            max_price = Decimal(max_price)
            if min_price < 0 or max_price < min_price:
                raise ValueError("Invalid price range")
            rooms_query = rooms_query.filter(price__gte=min_price, price__lte=max_price)
        except ValueError:
            logger.error(f"Invalid price range - min: {min_price}, max: {max_price}")
            messages.error(request, "Invalid price range")

    for amenity, value in active_amenities.items():
        if value == '1':
            rooms_query = rooms_query.filter(**{amenity: True})

    # Get hotel details
    try:
        hotel = Hotels.objects.get(id=hotel_id)
    except Hotels.DoesNotExist:
        messages.error(request, "Hotel not found")
        return redirect('homepage')

    context = {
        'hotel': hotel,
        'rooms': rooms_query,
        'check_in': check_in_date.strftime('%Y-%m-%d'),
        'check_out': check_out_date.strftime('%Y-%m-%d'),
        'formatted_check_in': check_in_date.strftime('%d %B %Y'),
        'formatted_check_out': check_out_date.strftime('%d %B %Y'),
        'capacity': capacity,
        'min_price': min_price,
        'max_price': max_price,
        'hotel_type': hotel_type,
        'active_amenities': active_amenities
    }
    return render(request, 'rooms/view_rooms.html', context)



@login_required(login_url='user:signin')
def add_new_location(request):
    if not request.user.is_staff or not hasattr(request.user, 'hotel_staff_profile'):
        return HttpResponseForbidden("Not Allowed - Only hotel staff can add locations")

    if request.method == "POST":
        try:
            name = request.POST.get('hotel_name', '').strip()
            owner = request.POST.get('new_owner', '').strip()
            location = request.POST.get('new_city', '').strip()
            state = request.POST.get('new_state', '').strip()
            country = request.POST.get('new_country', '').strip()
            hotel_type = request.POST.get('hotel_type', '').strip()
            other_heading = request.POST.get('other_heading', '').strip()
            description_map = request.POST.get('description_map', '').strip()
            heading_map = request.POST.get('heading_map', '').strip()
            embedded_map_link = request.POST.get('embedded_map_link', '').strip()
            rank = request.POST.get('rank', '0').strip()
            rank = int(rank) if rank.isdigit() else 0
            image_1 = request.FILES.get('image_1')
            image_2 = request.FILES.get('image_2')
            image_3 = request.FILES.get('image_3')
            image_4 = request.FILES.get('image_4')
            image_5 = request.FILES.get('image_5')
            image_6 = request.FILES.get('image_6')

            if not all([name, owner, location, state, country, hotel_type]):
                messages.error(request, "All required fields must be filled")
                return redirect("staffpanel")

            if hotel_type not in dict(Hotels.HOTEL_TYPE_CHOICES).keys():
                messages.error(request, "Invalid hotel type selected.")
                return redirect("staffpanel")

            if Hotels.objects.filter(location=location, name=name, owner=owner, state=state, country=country).exists():
                messages.warning(request, "A hotel with these details already exists")
                return redirect("staffpanel")

            new_hotel = Hotels.objects.create(
                name=name,
                owner=owner,
                location=location,
                state=state,
                country=country,
                hotel_type=hotel_type,
                other_heading=other_heading if hotel_type == 'other' else '',
                description_map=description_map,
                heading_map=heading_map,
                embedded_map_link=embedded_map_link,
                rank=rank,
                image_1=image_1,
                image_2=image_2,
                image_3=image_3,
                image_4=image_4,
                image_5=image_5,
                image_6=image_6,
                created_by=request.user.hotel_staff_profile
            )
            new_hotel.assigned_staff.add(request.user.hotel_staff_profile)
            messages.success(request, f"{name} in {location} added successfully!")
            messages.warning(request, f"Hello {name}, please wait for admin approval to manage {location}.")
            return redirect("staffpanel")

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect("staffpanel")

    return render(request, 'hotel_staff/viewroom.html')


logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def view_hotel_rooms(request, hotel_id):
    """
    Display available rooms for a specific hotel with full filtering capabilities.
    Supports date changes, capacity, price range, and amenity filters from GET or session.
    Identifies the cheapest room and computes facilities available in at least one room.
    """
    logger.debug(f"Processing view_hotel_rooms for hotel_id={hotel_id}, request.GET={request.GET}")

    try:
        hotel = Hotels.objects.get(id=hotel_id)
        logger.debug(f"Found hotel: {hotel.name} (ID:case {hotel_id})")

        # Get filter criteria from GET parameters, falling back to session
        check_in = request.GET.get('cin', request.session.get('check_in'))
        check_out = request.GET.get('cout', request.session.get('check_out'))
        capacity = request.GET.get('capacity', request.session.get('capacity', '1'))
        min_price = request.GET.get('min_price', request.session.get('min_price', '0'))
        max_price = request.GET.get('max_price', request.session.get('max_price', '10000'))
        location = request.GET.get('search_location', request.session.get('location'))

        # Amenity filters: Check for '1' in GET parameters
        amenities = ['ac', 'fan', 'wifi', 'parking', 'heater', 'food_facility', 'convenient_location',
                     'comfortable_bed', 'private_bathroom', 'cleanliness', 'safety_security',
                     'entertainment_options', 'laundry_facility', 'outdoor_balcony', 'concierge_service']
        active_amenities = {
            amenity: '1' if request.GET.get(amenity) == '1' else '0'
            for amenity in amenities
        }

        logger.debug(f"Filters - check_in: {check_in}, check_out: {check_out}, capacity: {capacity}, "
                     f"min_price: {min_price}, max_price: {max_price}, location: {location}, "
                     f"amenities: {active_amenities}")

        # Initialize default dates if none provided
        today = timezone.now().date()
        default_check_in = today + timedelta(days=1)
        days_to_thursday = (3 - default_check_in.weekday()) % 7 or 7
        default_check_out = default_check_in + timedelta(days=days_to_thursday)

        # Validate dates
        formatted_check_in = None
        formatted_check_out = None
        check_in_date = None
        check_out_date = None

        try:
            if check_in:
                check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
                if check_in_date < today:
                    logger.warning(f"Check-in date {check_in_date} is in the past")
                    messages.warning(request, "Check-in date cannot be in the past.")
                    check_in_date = default_check_in
                    check_in = default_check_in.strftime('%Y-%m-%d')
            else:
                check_in_date = default_check_in
                check_in = default_check_in.strftime('%Y-%m-%d')

            formatted_check_in = check_in_date.strftime('%d %B %Y')

            if check_out:
                check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
                if check_out_date <= check_in_date:
                    logger.warning(f"Check-out date {check_out_date} is not after check-in date {check_in_date}")
                    messages.warning(request, "Check-out date must be after check-in date.")
                    check_out_date = default_check_out
                    check_out = default_check_out.strftime('%Y-%m-%d')
            else:
                check_out_date = default_check_out
                check_out = default_check_out.strftime('%Y-%m-%d')

            formatted_check_out = check_out_date.strftime('%d %B %Y')

        except ValueError as e:
            logger.error(f"Invalid date format - check_in: {check_in}, check_out: {check_out}, error: {str(e)}")
            messages.warning(request, "Invalid date format. Please select valid dates.")
            check_in_date = default_check_in
            check_out_date = default_check_out
            check_in = default_check_in.strftime('%Y-%m-%d')
            check_out = default_check_out.strftime('%Y-%m-%d')
            formatted_check_in = default_check_in.strftime('%d %B %Y')
            formatted_check_out = default_check_out.strftime('%d %B %Y')

        # Initialize rooms query
        rooms = Rooms.objects.filter(hotel=hotel, status='1')
        logger.debug(f"Initial room count for hotel_id={hotel_id}: {rooms.count()}")

        # Apply location filter
        if location and str(hotel.id) != location:
            logger.warning(f"Location filter {location} does not match hotel_id={hotel_id}")
            messages.warning(request, "Selected location does not match the hotel.")
            rooms = rooms.none()
        else:
            # Apply date-based availability filter
            if check_in_date and check_out_date:
                try:
                    reserved_rooms = Reservation.objects.filter(
                        check_in__lt=check_out_date,
                        check_out__gt=check_in_date
                    ).values_list('room_id', flat=True)
                    rooms = rooms.exclude(id__in=reserved_rooms)
                    logger.debug(f"Rooms after excluding reserved: {rooms.count()}")
                except Exception as e:
                    logger.error(f"Error filtering rooms by date: {str(e)}")
                    messages.error(request, f"Error filtering rooms by date: {str(e)}")

            # Apply capacity filter
            if capacity:
                try:
                    capacity = int(capacity)
                    if capacity <= 0:
                        raise ValueError("Capacity must be positive")
                    rooms = rooms.filter(capacity__gte=capacity)
                    logger.debug(f"Rooms after capacity filter (>= {capacity}): {rooms.count()}")
                except ValueError as e:
                    logger.error(f"Invalid capacity value: {capacity}, error: {str(e)}")
                    messages.error(request, "Invalid capacity value.")

            # Apply price range filter
            if min_price and max_price:
                try:
                    min_price_decimal = Decimal(min_price)
                    max_price_decimal = Decimal(max_price)
                    if min_price_decimal < 0 or max_price_decimal < min_price_decimal:
                        raise ValueError("Invalid price range")
                    rooms = rooms.filter(price__gte=min_price_decimal, price__lte=max_price_decimal)
                    logger.debug(f"Rooms after price filter ({min_price_decimal} to {max_price_decimal}): {rooms.count()}")
                except ValueError as e:
                    logger.error(f"Invalid price range - min: {min_price}, max: {max_price}, error: {str(e)}")
                    messages.error(request, "Invalid price range.")

            # Apply amenity filters
            for amenity, value in active_amenities.items():
                if value == '1':
                    rooms = rooms.filter(**{amenity: True})
                    logger.debug(f"Rooms after {amenity} filter: {rooms.count()}")

        # Identify the cheapest room
        cheapest_room = None
        if rooms.exists():
            cheapest_room = rooms.order_by('price').first()
            logger.debug(f"Cheapest room: ID={cheapest_room.id}, Price={cheapest_room.price}")

        # Compute available facilities (amenities available in at least one room)
        available_facilities = {
            'wifi': rooms.count() > 0 and any(room.wifi for room in rooms),
            'ac': rooms.count() > 0 and any(room.ac for room in rooms),
            'parking': rooms.count() > 0 and any(room.parking for room in rooms),
            'convenient_location': rooms.count() > 0 and any(room.convenient_location for room in rooms),
            'food_facility': rooms.count() > 0 and any(room.food_facility for room in rooms),
            'comfortable_bed': rooms.count() > 0 and any(room.comfortable_bed for room in rooms),
            'private_bathroom': rooms.count() > 0 and any(room.private_bathroom for room in rooms),
            'fan': rooms.count() > 0 and any(room.fan for room in rooms),
            'heater': rooms.count() > 0 and any(room.heater for room in rooms),
            'cleanliness': rooms.count() > 0 and any(room.cleanliness for room in rooms),
            'safety_security': rooms.count() > 0 and any(room.safety_security for room in rooms),
            'entertainment_options': rooms.count() > 0 and any(room.entertainment_options for room in rooms),
            'laundry_facility': rooms.count() > 0 and any(room.laundry_facility for room in rooms),
            'outdoor_balcony': rooms.count() > 0 and any(room.outdoor_balcony for room in rooms),
            'concierge_service': rooms.count() > 0 and any(room.concierge_service for room in rooms),
        }

        # Optionally, retain common facilities (amenities available in all rooms)
        common_facilities = {
            'wifi': rooms.count() > 0 and all(room.wifi for room in rooms),
            'ac': rooms.count() > 0 and all(room.ac for room in rooms),
            'parking': rooms.count() > 0 and all(room.parking for room in rooms),
            'convenient_location': rooms.count() > 0 and all(room.convenient_location for room in rooms),
            'food_facility': rooms.count() > 0 and all(room.food_facility for room in rooms),
            'comfortable_bed': rooms.count() > 0 and all(room.comfortable_bed for room in rooms),
            'private_bathroom': rooms.count() > 0 and all(room.private_bathroom for room in rooms),
            'fan': rooms.count() > 0 and all(room.fan for room in rooms),
            'heater': rooms.count() > 0 and all(room.heater for room in rooms),
            'cleanliness': rooms.count() > 0 and all(room.cleanliness for room in rooms),
            'safety_security': rooms.count() > 0 and all(room.safety_security for room in rooms),
            'entertainment_options': rooms.count() > 0 and all(room.entertainment_options for room in rooms),
            'laundry_facility': rooms.count() > 0 and all(room.laundry_facility for room in rooms),
            'outdoor_balcony': rooms.count() > 0 and all(room.outdoor_balcony for room in rooms),
            'concierge_service': rooms.count() > 0 and all(room.concierge_service for room in rooms),
        }

        # Update session with current filters
        request.session['check_in'] = check_in
        request.session['check_out'] = check_out
        request.session['capacity'] = str(capacity)
        request.session['location'] = location
        request.session['min_price'] = str(min_price) if min_price else '0'
        request.session['max_price'] = str(max_price) if max_price else '10000'
        request.session['amenities'] = {k: v for k, v in active_amenities.items() if v == '1'}
        request.session.modified = True

        logger.debug(f"Final room count for hotel_id={hotel_id}: {rooms.count()}")
        logger.debug(f"Available facilities: {available_facilities}")
        logger.debug(f"Common facilities: {common_facilities}")

        total_hotels = Hotels.objects.count()
        total_rooms = Rooms.objects.filter(hotel=hotel).count()

        # Prepare context
        context = {
            'hotel': hotel,
            'rooms': rooms,
            'cheapest_room': cheapest_room,
            'all_rooms': True,
            'check_in': check_in,
            'check_out': check_out,
            'formatted_check_in': formatted_check_in,
            'formatted_check_out': formatted_check_out,
            'capacity': capacity,
            'min_price': min_price or '0',
            'max_price': max_price or '10000',
            'location': location,
            'active_amenities': active_amenities,
            'total_hotels': total_hotels,
            'total_rooms': total_rooms,
            'common_facilities': common_facilities,
            'available_facilities': available_facilities,  # Add available facilities to context
        }

        return render(request, 'rooms/hotel_rooms.html', context)

    except Hotels.DoesNotExist:
        logger.error(f"Hotel not found for hotel_id={hotel_id}")
        messages.error(request, "Hotel not found.")
        return redirect('homepage')
    except Exception as e:
        logger.exception(f"Unexpected error in view_hotel_rooms for hotel_id={hotel_id}: {str(e)}")
        messages.error(request, "An unexpected error occurred. Please try again.")
        return redirect('homepage')
    
def hotel_staff_add_room(request):
    """
    Allows hotel staff to add rooms to their assigned hotels
    - Only shows hotels the staff is assigned to
    - Handles file uploads and room creation
    - Validates all inputs
    """
    if not hasattr(request.user, 'hotel_staff_profile'):
        return HttpResponseForbidden('Access Denied - Hotel Staff Only')

    staff = request.user.hotel_staff_profile
    assigned_hotels = staff.assigned_hotels.all()

    if request.method == "POST":
        try:
            hotel_id = int(request.POST.get('hotel'))
            hotel = assigned_hotels.get(id=hotel_id)  # Ensures staff has access
            
            # Create room with basic info and all amenities
            new_room = Rooms(
                hotel=hotel,
                room_number=request.POST.get('room_number', '').strip(),
                room_type=request.POST.get('roomtype'),
                capacity=int(request.POST.get('capacity', 1)),
                size=int(request.POST.get('size', 0)),
                price=Decimal(request.POST.get('price', 0.0)),
                discount=Decimal(request.POST.get('discount', 0.0)),
                status=request.POST.get('status', '1'),  # Default to available
                description=request.POST.get('description', '').strip(),
                heading=request.POST.get('heading', '').strip(),
                food_facility=request.POST.get('food_facility') == 'on',
                parking=request.POST.get('parking') == 'on',
                comfortable_bed=request.POST.get('comfortable_bed') == 'on',
                private_bathroom=request.POST.get('private_bathroom') == 'on',
                wifi=request.POST.get('wifi') == 'on',
                ac=request.POST.get('ac') == 'on',
                fan=request.POST.get('fan') == 'on',
                heater=request.POST.get('heater') == 'on',
                cleanliness=request.POST.get('cleanliness') == 'on',
                safety_security=request.POST.get('safety_security') == 'on',
                entertainment_options=request.POST.get('entertainment_options') == 'on',
                laundry_facility=request.POST.get('laundry_facility') == 'on',
                outdoor_balcony=request.POST.get('outdoor_balcony') == 'on',
                convenient_location=request.POST.get('convenient_location') == 'on',
                concierge_service=request.POST.get('concierge_service') == 'on',
            )

            # Handle time fields
            if check_in := request.POST.get('check_in_time'):
                new_room.check_in_time = check_in
            if check_out := request.POST.get('check_out_time'):
                new_room.check_out_time = check_out

            # Handle image uploads (up to 15 images)
            for i in range(1, 16):
                if f'image{i}' in request.FILES:
                    setattr(new_room, f'image{i}', request.FILES[f'image{i}'])

            new_room.full_clean()
            new_room.save()
            messages.success(request, f"Room {new_room.room_number} added successfully!")
            
        except Hotels.DoesNotExist:
            messages.error(request, "Invalid hotel selection")
        except ValueError as e:
            messages.error(request, f"Invalid input: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error adding room: {str(e)}")
        
        return redirect('staffpanel')

    # GET request - show form
    context = {
        'hotels': assigned_hotels.values_list('name', 'id'),
        'room_types': Rooms.ROOM_TYPE,
        'room_statuses': Rooms.ROOM_STATUS
    }
    return render(request, 'hotel_staff/add_room.html', context)




def check_hotel_management_authority(user):
    """Check if user has authority to manage hotels"""
    if not user.is_authenticated:
        return False
    return user.is_superuser or getattr(user, 'is_authority_to_manage_hotel', False)

def assign_hotel_to_staff(request):
    if not check_hotel_management_authority(request.user):
        messages.error(request, "You don't have permission to manage hotel assignments")
        return redirect('maintainer_panel')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'assign':
            staff_id = request.POST.get('staff_id')
            hotel_ids = request.POST.getlist('hotel_ids')  # Get list of hotel IDs

            try:
                staff = HotelStaff.objects.get(staff_id=staff_id)
                hotels = Hotels.objects.filter(id__in=hotel_ids)

                if len(hotels) != len(hotel_ids):
                    messages.error(request, "One or more hotels not found")
                    return redirect('assign-hotel')

                # Add staff to the hotels' assigned_staff
                for hotel in hotels:
                    hotel.assigned_staff.add(staff)
                
                hotel_names = ", ".join(hotel.name for hotel in hotels)
                messages.success(request, f"Assigned {staff.user.get_full_name()} to {hotel_names}")

            except HotelStaff.DoesNotExist:
                messages.error(request, f"Staff member {staff_id} not found")
            
            return redirect('assign-hotel')

        elif action == 'unassign':
            staff_id = request.POST.get('staff_id')
            hotel_id = request.POST.get('hotel_id')

            try:
                staff = HotelStaff.objects.get(staff_id=staff_id)
                hotel = Hotels.objects.get(id=hotel_id)
                
                if staff in hotel.assigned_staff.all():
                    hotel.assigned_staff.remove(staff)
                    messages.success(request, f"Unassigned {staff.user.get_full_name()} from {hotel.name}")
                else:
                    messages.warning(request, f"{staff.user.get_full_name()} is not assigned to {hotel.name}")
                    
            except HotelStaff.DoesNotExist:
                messages.error(request, f"Staff member {staff_id} not found")
            except Hotels.DoesNotExist:
                messages.error(request, f"Hotel {hotel_id} not found")
            
            return redirect('assign-hotel')

    # GET request handling
    unassigned_hotels = Hotels.objects.filter(assigned_staff__isnull=True)
    
  

    context = {
        'assigned_staff': HotelStaff.objects.filter(assigned_hotels__isnull=False).distinct()
                         .select_related('user'),
        'unassigned_staff': HotelStaff.objects.filter(assigned_hotels__isnull=True)
                           .select_related('user'),
        'available_hotels': unassigned_hotels,  # Hotels with no staff
        'all_hotels': Hotels.objects.all(),    # All hotels for assignment selection
        'assignment_counts': {
            'total_staff': HotelStaff.objects.count(),
            'assigned_staff': HotelStaff.objects.filter(assigned_hotels__isnull=False).distinct().count(),
            'available_hotels': unassigned_hotels.count(),
            'total_hotels': Hotels.objects.count(),
        },
    }
    return render(request, 'admin/assign_hotel.html', context)

@user_passes_test(lambda u: u.is_authority_to_manage_hotel, login_url='home')
def manage_hotel_assignments(request):
    assignments = HotelStaff.objects.filter(hotel__isnull=False) \
                     .select_related('user', 'hotel') \
                     .order_by('hotel__name')
    
    unassigned_hotels = Hotels.objects.exclude(
        id__in=assignments.values('hotel_id')
    )
    
    return render(request, 'admin/manage_assignments.html', {
        'assignments': assignments,
        'unassigned_hotels': unassigned_hotels,
    })



@user_passes_test(lambda u: u.is_authority_to_manage_hotel, login_url='home')
def edit_hotel_assignment(request, pk):  # Changed from assignment_id to pk
    assignment = get_object_or_404(HotelStaff, pk=pk)
    
    if request.method == 'POST':
        form = HotelAssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            messages.success(request, "Assignment updated successfully")
            return redirect('manage-hotel')
    else:
        form = HotelAssignmentForm(instance=assignment)
    
    return render(request, 'admin/edit_assignment.html', {
        'form': form,
        'assignment': assignment,
    })

@user_passes_test(lambda u: u.is_authority_to_manage_hotel, login_url='home')
def unassign_staff(request, pk):  # Changed from assignment_id to pk
    if request.method == 'POST':
        assignment = get_object_or_404(HotelStaff, pk=pk)
        if assignment.hotel:
            messages.success(request, 
                f"Unassigned {assignment.user.get_full_name()} from {assignment.hotel.name}"
            )
            assignment.hotel = None
            assignment.save()
        else:
            messages.warning(request, "No assignment found")
    
    return redirect('manage-hotel')

@user_passes_test(lambda u: u.is_authority_to_manage_hotel, login_url='home')
def unassign_staff(request, pk):
    if request.method == 'POST':
        assignment = get_object_or_404(HotelStaff, pk=pk)
        if assignment.hotel:
            messages.success(request, 
                f"Unassigned {assignment.user.get_full_name()} from {assignment.hotel.name}"
            )
            assignment.hotel = None
            assignment.save()
        else:
            messages.warning(request, "No assignment found")
    
    return redirect('manage-hotel')

@user_passes_test(lambda u: u.is_authority_to_manage_hotel, login_url='home')
def staff_list(request):
    staff_members = HotelStaff.objects.select_related('user', 'hotel').all()
    return render(request, 'admin/staff_list.html', {
        'staff_members': staff_members
    })



@login_required(login_url='user:signin')
def hotel_staff_edit_room(request, room_id):
    if not request.user.is_staff:
        return HttpResponse('Access Denied')  # Staff-only access

    try:
        room = get_object_or_404(Rooms, id=room_id)
        
        if request.method == 'POST':
            form = RoomForm(request.POST, request.FILES, instance=room)
            
            if form.is_valid():
                form.save()  # Save the updated room to the database
                messages.success(request, "Room details updated successfully.")
                return redirect('staffpanel')
            else:
                messages.error(request, "Form validation failed. Please correct the errors below.")
                hotels = Hotels.objects.all()  # Get hotels for select options
                return render(request, 'hotel_staff/edit_room.html', {
                    'form': form,
                    'room': room,
                    'hotels': hotels
                })

        else:  # GET request
            form = RoomForm(instance=room)  # Pre-populate form with existing data
            hotels = Hotels.objects.all()  # Get all hotels for select options
            return render(request, 'hotel_staff/edit_room.html', {
                'form': form,
                'hotels': hotels,
                'room': room
            })

    except Exception as e:
        messages.error(request, f"Error processing request: {e}")
        return redirect('staffpanel')

# @login_required(login_url='user:signin')
# def hotel_staff_edit_location(request):
#     if not hasattr(request.user, 'hotel_staff_profile'):
#         return HttpResponse('Access Denied - Not a Hotel Staff')

#     if request.method == "POST":
#         try:
#             hotel_id = request.POST.get('hotel_id')
#             if hotel_id:
#                 hotel = Hotels.objects.get(id=hotel_id, created_by=request.user.hotel_staff_profile)
#             else:
#                 hotel = Hotels(created_by=request.user.hotel_staff_profile)

#             hotel.name = request.POST['hotel_name']
#             hotel.owner = request.POST['owner']
#             hotel.location = request.POST['location']
#             hotel.state = request.POST['state']
#             hotel.country = request.POST['country']
#             hotel.description_map = request.POST.get('description_map', '')
#             hotel.heading_map = request.POST.get('heading_map', '')
#             hotel.embedded_map_link = request.POST.get('embedded_map_link', '')
#             hotel.rank = int(request.POST.get('rank', '0')) if request.POST.get('rank', '').isdigit() else 0
            
#             # Handle hotel_type and other_heading
#             hotel_type = request.POST.get('hotel_type', '')
#             if hotel_type not in dict(Hotels.HOTEL_TYPE_CHOICES).keys():
#                 messages.error(request, "Invalid hotel type selected.")
#                 return redirect('staffpanel')
#             hotel.hotel_type = hotel_type
#             hotel.other_heading = request.POST.get('other_heading', '') if hotel_type == 'other' else ''

#             # Handle image uploads
#             for i in range(1, 7):
#                 image_field = f'image_{i}'
#                 if request.FILES.get(image_field):
#                     setattr(hotel, image_field, request.FILES.get(image_field))

#             hotel.full_clean()
#             hotel.save()
#             if not hotel_id:  # New hotel
#                 hotel.assigned_staff.add(request.user.hotel_staff_profile)
#             messages.success(request, f"Hotel {hotel.name} updated successfully.")
#             return redirect('staffpanel')
#         except Hotels.DoesNotExist:
#             messages.error(request, "Hotel not found or you don't have permission to edit it.")
#         except Exception as e:
#             messages.error(request, f"Error updating location: {e}")
#             return redirect('staffpanel')

#     # For GET request, render the edit form with hotel data
#     hotel_id = request.GET.get('hotel_id')
#     context = {'hotel': None}
#     if hotel_id:
#         try:
#             hotel = Hotels.objects.get(id=hotel_id, created_by=request.user.hotel_staff_profile)
#             # Prepare list of image URLs
#             images = [
#                 hotel.image_1.url if hotel.image_1 else '',
#                 hotel.image_2.url if hotel.image_2 else '',
#                 hotel.image_3.url if hotel.image_3 else '',
#                 hotel.image_4.url if hotel.image_4 else '',
#                 hotel.image_5.url if hotel.image_5 else '',
#                 hotel.image_6.url if hotel.image_6 else '',
#             ]
#             context = {'hotel': hotel, 'images': images}
#         except Hotels.DoesNotExist:
#             messages.error(request, "Hotel not found or you don't have permission to edit it.")
#             return redirect('staffpanel')
#     return render(request, 'hotel_staff/edit_locations.html', context)

@login_required(login_url='user:signin')
def add_new_location(request):
    if not request.user.is_staff or not hasattr(request.user, 'hotel_staff_profile'):
        return HttpResponseForbidden("Not Allowed - Only hotel staff can add locations")

    if request.method == "POST":
        try:
            name = request.POST.get('hotel_name', '').strip()
            owner = request.POST.get('new_owner', '').strip()
            location = request.POST.get('new_city', '').strip()
            state = request.POST.get('new_state', '').strip()
            country = request.POST.get('new_country', '').strip()
            hotel_type = request.POST.get('hotel_type', '').strip()
            other_heading = request.POST.get('other_heading', '').strip()
            description_map = request.POST.get('description_map', '').strip()
            heading_map = request.POST.get('heading_map', '').strip()
            embedded_map_link = request.POST.get('embedded_map_link', '').strip()
            rank = request.POST.get('rank', '0').strip()
            rank = int(rank) if rank.isdigit() else 0
            image_1 = request.FILES.get('image_1')
            image_2 = request.FILES.get('image_2')
            image_3 = request.FILES.get('image_3')
            image_4 = request.FILES.get('image_4')
            image_5 = request.FILES.get('image_5')
            image_6 = request.FILES.get('image_6')

            if not all([name, owner, location, state, country, hotel_type]):
                messages.error(request, "All required fields must be filled")
                return redirect("staffpanel")

            if hotel_type not in dict(Hotels.HOTEL_TYPE_CHOICES).keys():
                messages.error(request, "Invalid hotel type selected.")
                return redirect("staffpanel")

            if Hotels.objects.filter(location=location, name=name, owner=owner, state=state, country=country).exists():
                messages.warning(request, "A hotel with these details already exists")
                return redirect("staffpanel")

            new_hotel = Hotels.objects.create(
                name=name,
                owner=owner,
                location=location,
                state=state,
                country=country,
                hotel_type=hotel_type,
                other_heading=other_heading if hotel_type == 'other' else '',
                description_map=description_map,
                heading_map=heading_map,
                embedded_map_link=embedded_map_link,
                rank=rank,
                image_1=image_1,
                image_2=image_2,
                image_3=image_3,
                image_4=image_4,
                image_5=image_5,
                image_6=image_6,
                created_by=request.user.hotel_staff_profile
            )
            new_hotel.assigned_staff.add(request.user.hotel_staff_profile)
            messages.success(request, f"{name} in {location} added successfully!")
            messages.warning(request, f"Hello {name}, please wait for admin approval to manage {location}.")
            return redirect("staffpanel")

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect("staffpanel")

    return render(request, 'hotel_staff/viewroom.html')


def contactpage(request):
    messages.warning(request, f"Hello, user you don't have permissions to change this essential data pls contact to administrator.")
    return HttpResponse(render(request,'admin/contact-admin.html'))

@login_required(login_url='user:signin')
def hotel_view_hotels(request):
    if not request.user.is_staff or not hasattr(request.user, 'hotel_staff_profile'):
        return HttpResponseForbidden("Contact administrator")
    
    staff = request.user.hotel_staff_profile
    hotels = Hotels.objects.filter(created_by=staff)
    return render(request, 'hotel_staff/hotels.html', {'hotels': hotels})

@login_required(login_url='user:signin')
def view_room(request, room_id):
    if not (hasattr(request.user, 'hotel_staff_profile') or hasattr(request.user, 'maintainer_profile')):
        return HttpResponseForbidden('Access Denied - Hotel Staff or Maintainer Only')

    try:
        room = Rooms.objects.get(id=room_id)
    except Rooms.DoesNotExist:
        raise Http404("Room not found")
    reservations = Reservation.objects.filter(room=room)
    current_date = datetime.now().date()
    for reservation in reservations:
        if reservation.check_out < current_date:
            reservation.status = 'past'
        elif reservation.check_in <= current_date and reservation.check_out >= current_date:
            reservation.status = 'current'
        else:
            reservation.status = 'future'
    return render(request, 'hotel_staff/viewroom.html', {
        'room': room,
        'reservations': reservations,
        'current_date': current_date
    })



@login_required(login_url='user:signin')
def hotel_staff_panel(request):
    """
    Displays the hotel staff panel with statistics for assigned hotels, with optional room filtering
    """
    if not hasattr(request.user, 'hotel_staff_profile'):
        return render(request, 'hotel_staff/panel.html', {
            'error_title': 'Access Denied',
            'error_message': 'This page is only accessible to hotel staff members.'
        }, status=403)
    
    try:
        staff = request.user.hotel_staff_profile
        
        # Check if all required fields are filled
        required_fields = [
            staff.user.first_name,
            staff.user.last_name,
            staff.user.phone,
            staff.hotel_name,
            staff.location,
            staff.state,
            staff.country,
            staff.hotel_gst_no,
            staff.shop_main_image,
            staff.shop_license_image,
            staff.shop_aadhar_image,
            staff.owner_pan_image,
            staff.owner_aadhar_image
        ]
        
        if any(field is None or field == '' for field in required_fields):
            messages.info(request, 'Please complete your profile before accessing the dashboard.')
            return redirect('user:staff_profile_edit')
        
        # Get all hotels the staff is assigned to
        assigned_hotels = Hotels.objects.filter(assigned_staff=staff)
        
        if not assigned_hotels.exists():
            messages.warning(request, 'Hello, you need to add your hotel and rooms to increase your business.')
            return redirect('add_hotel') 
            
        # Get filter parameters from GET request
        hotel_filter = request.GET.get('hotel_filter', 'all')
        status_filter = request.GET.get('status_filter', 'all')
        
        # Fetch rooms for assigned hotels with optional filters
        rooms = Rooms.objects.filter(hotel__in=assigned_hotels).select_related('hotel')
        if hotel_filter != 'all':
            rooms = rooms.filter(hotel__name=hotel_filter)
        if status_filter != 'all':
            rooms = rooms.filter(status=status_filter)
        
        total_rooms = rooms.count()
        available_rooms = rooms.filter(status='1').count() if total_rooms else 0
        unavailable_rooms = rooms.filter(status='2').count() if total_rooms else 0
        
        current_date = datetime.now().date()
        current_month = current_date.month
        current_year = current_date.year
        
        # Fetch all bookings for stats (filtered by hotel if hotel_filter is applied)
        all_bookings = Reservation.objects.filter(room__hotel__in=assigned_hotels)
        if hotel_filter != 'all':
            all_bookings = all_bookings.filter(room__hotel__name=hotel_filter)
        
        # Calculate counts
        total_bookings = all_bookings.count()
        bookings_today = all_bookings.filter(booking_time__date=current_date).count()
        bookings_this_month = all_bookings.filter(booking_time__month=current_month, booking_time__year=current_year).count()
        active_bookings = all_bookings.filter(check_in__lte=current_date, check_out__gte=current_date).count()
        check_ins_today = all_bookings.filter(check_in=current_date).count()
        check_outs_today = all_bookings.filter(check_out=current_date).count()
        check_ins_this_month = all_bookings.filter(check_in__month=current_month, check_in__year=current_year).count()
        check_outs_this_month = all_bookings.filter(check_out__month=current_month, check_out__year=current_year).count()
        
        # Calculate revenues
        def calculate_revenue(queryset):
            return sum(booking.total_price for booking in queryset)
        
        total_revenue = calculate_revenue(all_bookings)
        today_revenue = calculate_revenue(all_bookings.filter(booking_time__date=current_date))
        this_month_revenue = calculate_revenue(all_bookings.filter(booking_time__month=current_month, booking_time__year=current_year))
        active_bookings_revenue = calculate_revenue(all_bookings.filter(check_in__lte=current_date, check_out__gte=current_date))
        check_ins_today_revenue = calculate_revenue(all_bookings.filter(check_in=current_date))
        check_outs_today_revenue = calculate_revenue(all_bookings.filter(check_out=current_date))
        check_ins_month_revenue = calculate_revenue(all_bookings.filter(check_in__month=current_month, check_in__year=current_year))
        check_outs_month_revenue = calculate_revenue(all_bookings.filter(check_out__month=current_month, check_out__year=current_year))

        # Calculate percentages
        total_rooms_nonzero = total_rooms or 1
        available_percent = (available_rooms / total_rooms_nonzero * 100)
        unavailable_percent = (unavailable_rooms / total_rooms_nonzero * 100)
        total_bookings_percent = (total_bookings / total_rooms_nonzero * 100) if total_bookings else 0
        active_bookings_percent = (active_bookings / total_rooms_nonzero * 100) if total_bookings else 0
        bookings_today_percent = (bookings_today / total_bookings * 100) if total_bookings else 0
        check_ins_today_percent = (check_ins_today / total_bookings * 100) if total_bookings else 0
        check_outs_today_percent = (check_outs_today / total_bookings * 100) if total_bookings else 0
        bookings_this_month_percent = (bookings_this_month / total_bookings * 100) if total_bookings else 0
        check_ins_this_month_percent = (check_ins_this_month / total_bookings * 100) if total_bookings else 0
        check_outs_this_month_percent = (check_outs_this_month / total_bookings * 100) if total_bookings else 0

        context = {
            'hotels': assigned_hotels,
            'rooms': rooms,
            'selected_hotel': hotel_filter,
            'selected_status': status_filter,
            'total_rooms': total_rooms,
            'available_rooms': available_rooms,
            'available_percent': available_percent,
            'unavailable_rooms': unavailable_rooms,
            'unavailable_percent': unavailable_percent,
            'total_bookings': total_bookings,
            'total_bookings_percent': total_bookings_percent,
            'bookings_today': bookings_today,
            'bookings_this_month': bookings_this_month,
            'active_bookings': active_bookings,
            'active_bookings_percent': active_bookings_percent,
            'check_ins_today': check_ins_today,
            'check_outs_today': check_outs_today,
            'check_ins_this_month': check_ins_this_month,
            'check_outs_this_month': check_outs_this_month,
            'current_date': current_date,
            'bookings_today_percent': bookings_today_percent,
            'check_ins_today_percent': check_ins_today_percent,
            'check_outs_today_percent': check_outs_today_percent,
            'bookings_this_month_percent': bookings_this_month_percent,
            'check_ins_this_month_percent': check_ins_this_month_percent,
            'check_outs_this_month_percent': check_outs_this_month_percent,
            'total_revenue': total_revenue,
            'today_revenue': today_revenue,
            'this_month_revenue': this_month_revenue,
            'active_bookings_revenue': active_bookings_revenue,
            'check_ins_today_revenue': check_ins_today_revenue,
            'check_outs_today_revenue': check_outs_today_revenue,
            'check_ins_this_month_revenue': check_ins_month_revenue,
            'check_outs_this_month_revenue': check_outs_month_revenue,
        }

        return render(request, 'hotel_staff/panel.html', context)
        
    except HotelStaff.DoesNotExist:
        return render(request, 'hotel_staff/panel.html', {
            'error_title': 'Profile Not Found',
            'error_message': 'Your staff profile could not be found. Please contact administration.'
        }, status=404)
    except Exception as e:
        return render(request, 'hotel_staff/panel.html', {
            'error_title': 'An error occurred',
            'error_message': f'An unexpected error occurred: {str(e)}'
        }, status=500)
    
# def hotel_staff_edit_location(request):
#     if not hasattr(request.user, 'hotel_staff_profile'):
#         return HttpResponse('Access Denied - Not a Hotel Staff')

#     if request.method == "POST":
#         try:
#             hotel_id = request.POST.get('hotel_id')
#             if hotel_id:
#                 hotel = Hotels.objects.get(id=hotel_id, created_by=request.user.hotel_staff_profile)
#             else:
#                 hotel = Hotels(created_by=request.user.hotel_staff_profile)

#             hotel.name = request.POST['hotel_name']
#             hotel.owner = request.POST['owner']
#             hotel.location = request.POST['location']
#             hotel.state = request.POST['state']
#             hotel.country = request.POST['country']
#             hotel.description_map = request.POST.get('description_map', '')
#             hotel.heading_map = request.POST.get('heading_map', '')
#             hotel.embedded_map_link = request.POST.get('embedded_map_link', '')
#             hotel.rank = int(request.POST.get('rank', '0')) if request.POST.get('rank', '').isdigit() else 0
            
#             # Handle hotel_type and other_heading
#             hotel_type = request.POST.get('hotel_type', '')
#             if hotel_type not in dict(Hotels.HOTEL_TYPE_CHOICES).keys():
#                 messages.error(request, "Invalid hotel type selected.")
#                 return redirect('staffpanel')
#             hotel.hotel_type = hotel_type
#             hotel.other_heading = request.POST.get('other_heading', '') if hotel_type == 'other' else ''

#             # Handle image uploads
#             for i in range(1, 7):
#                 image_field = f'image_{i}'
#                 if request.FILES.get(image_field):
#                     setattr(hotel, image_field, request.FILES.get(image_field))

#             hotel.full_clean()
#             hotel.save()
#             if not hotel_id:  # New hotel
#                 hotel.assigned_staff.add(request.user.hotel_staff_profile)
#             messages.success(request, f"Hotel {hotel.name} updated successfully.")
#             return redirect('staffpanel')
#         except Hotels.DoesNotExist:
#             messages.error(request, "Hotel not found or you don't have permission to edit it.")
#         except Exception as e:
#             messages.error(request, f"Error updating location: {e}")
#             return redirect('staffpanel')

#     # For GET request, render the edit form with hotel data
#     hotel_id = request.GET.get('hotel_id')
#     context = {'hotel': None}
#     if hotel_id:
#         try:
#             hotel = Hotels.objects.get(id=hotel_id, created_by=request.user.hotel_staff_profile)
#             # Prepare list of image URLs
#             images = [
#                 hotel.image_1.url if hotel.image_1 else '',
#                 hotel.image_2.url if hotel.image_2 else '',
#                 hotel.image_3.url if hotel.image_3 else '',
#                 hotel.image_4.url if hotel.image_4 else '',
#                 hotel.image_5.url if hotel.image_5 else '',
#                 hotel.image_6.url if hotel.image_6 else '',
#             ]
#             context = {'hotel': hotel, 'images': images}
#         except Hotels.DoesNotExist:
#             messages.error(request, "Hotel not found or you don't have permission to edit it.")
#             return redirect('staffpanel')
#     return render(request, 'hotel_staff/edit_locations.html', context)

# @login_required(login_url='user:signin')
# def add_new_location(request):
#     if not request.user.is_staff or not hasattr(request.user, 'hotel_staff_profile'):
#         return HttpResponseForbidden("Not Allowed - Only hotel staff can add locations")

#     if request.method == "POST":
#         try:
#             name = request.POST.get('hotel_name', '').strip()
#             owner = request.POST.get('new_owner', '').strip()
#             location = request.POST.get('new_city', '').strip()
#             state = request.POST.get('new_state', '').strip()
#             country = request.POST.get('new_country', '').strip()
#             hotel_type = request.POST.get('hotel_type', '').strip()
#             other_heading = request.POST.get('other_heading', '').strip()
#             description_map = request.POST.get('description_map', '').strip()
#             heading_map = request.POST.get('heading_map', '').strip()
#             embedded_map_link = request.POST.get('embedded_map_link', '').strip()
#             rank = request.POST.get('rank', '0').strip()
#             rank = int(rank) if rank.isdigit() else 0
#             image_1 = request.FILES.get('image_1')
#             image_2 = request.FILES.get('image_2')
#             image_3 = request.FILES.get('image_3')
#             image_4 = request.FILES.get('image_4')
#             image_5 = request.FILES.get('image_5')
#             image_6 = request.FILES.get('image_6')

#             if not all([name, owner, location, state, country, hotel_type]):
#                 messages.error(request, "All required fields must be filled")
#                 return redirect("staffpanel")

#             if hotel_type not in dict(Hotels.HOTEL_TYPE_CHOICES).keys():
#                 messages.error(request, "Invalid hotel type selected.")
#                 return redirect("staffpanel")

#             if Hotels.objects.filter(location=location, name=name, owner=owner, state=state, country=country).exists():
#                 messages.warning(request, "A hotel with these details already exists")
#                 return redirect("staffpanel")

#             new_hotel = Hotels.objects.create(
#                 name=name,
#                 owner=owner,
#                 location=location,
#                 state=state,
#                 country=country,
#                 hotel_type=hotel_type,
#                 other_heading=other_heading if hotel_type == 'other' else '',
#                 description_map=description_map,
#                 heading_map=heading_map,
#                 embedded_map_link=embedded_map_link,
#                 rank=rank,
#                 image_1=image_1,
#                 image_2=image_2,
#                 image_3=image_3,
#                 image_4=image_4,
#                 image_5=image_5,
#                 image_6=image_6,
#                 created_by=request.user.hotel_staff_profile
#             )
#             new_hotel.assigned_staff.add(request.user.hotel_staff_profile)
#             messages.success(request, f"{name} in {location} added successfully!")
#             messages.warning(request, f"Hello {name}, please wait for admin approval to manage {location}.")
#             return redirect("staffpanel")

#         except Exception as e:
#             messages.error(request, f"Error: {str(e)}")
#             return redirect("staffpanel")

#     return render(request, 'hotel_staff/viewroom.html')

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect
from .models import Hotels

@login_required(login_url='user:signin')
def hotel_staff_edit_location(request):
    # Allow access for users with either hotel_staff_profile or maintainer_profile
    if not (hasattr(request.user, 'hotel_staff_profile') or hasattr(request.user, 'maintainer_profile')):
        return HttpResponse('Access Denied - Not a Hotel Staff or Maintainer')

    if request.method == "POST":
        try:
            hotel_id = request.POST.get('hotel_id')
            if not hotel_id:
                if request.user.is_staff:
                    messages.error(request, "Staff members cannot create new hotels from this panel.")
                    return redirect('staffpanel')
                elif request.user.is_maintainer:
                    messages.error(request, "Maintainers cannot create new hotels from this panel.")
                    return redirect('maintainer_panel')
                else:
                    hotel = Hotels(created_by=request.user.hotel_staff_profile)
            else:
                # Maintainers can edit any hotel, staff can only edit hotels they created
                if request.user.is_maintainer:
                    hotel = Hotels.objects.get(id=hotel_id)
                else:
                    hotel = Hotels.objects.get(id=hotel_id, created_by=request.user.hotel_staff_profile)

            hotel.name = request.POST['hotel_name']
            hotel.owner = request.POST['owner']
            hotel.location = request.POST['location']
            hotel.state = request.POST['state']
            hotel.country = request.POST['country']
            hotel.description_map = request.POST.get('description_map', '')
            hotel.heading_map = request.POST.get('heading_map', '')
            hotel.embedded_map_link = request.POST.get('embedded_map_link', '')
            hotel.rank = int(request.POST.get('rank', '0')) if request.POST.get('rank', '').isdigit() else 0
            
            # Handle hotel_type and other_heading
            hotel_type = request.POST.get('hotel_type', '')
            if hotel_type not in dict(Hotels.HOTEL_TYPE_CHOICES).keys():
                messages.error(request, "Invalid hotel type selected.")
                return redirect('staffpanel' if not request.user.is_maintainer else 'maintainer_panel')
            hotel.hotel_type = hotel_type
            hotel.other_heading = request.POST.get('other_heading', '') if hotel_type == 'other' else ''

            # Handle image uploads
            for i in range(1, 7):
                image_field = f'image_{i}'
                if request.FILES.get(image_field):
                    setattr(hotel, image_field, request.FILES.get(image_field))

            hotel.full_clean()
            hotel.save()
            if not hotel_id:  # New hotel
                hotel.assigned_staff.add(request.user.hotel_staff_profile)
            messages.success(request, f"Hotel {hotel.name} updated successfully.")
            return redirect('staffpanel' if not request.user.is_maintainer else 'maintainer_panel')
        except Hotels.DoesNotExist:
            messages.error(request, "Hotel not found or you don't have permission to edit it.")
            return redirect('staffpanel' if not request.user.is_maintainer else 'maintainer_panel')
        except Exception as e:
            messages.error(request, f"Error updating location: {e}")
            return redirect('staffpanel' if not request.user.is_maintainer else 'maintainer_panel')

    # For GET request, render the edit form with hotel data
    hotel_id = request.GET.get('hotel_id')
    context = {'hotel': None}
    if hotel_id:
        try:
            # Maintainers can view any hotel, staff can only view hotels they created
            if request.user.is_maintainer:
                hotel = Hotels.objects.get(id=hotel_id)
            else:
                hotel = Hotels.objects.get(id=hotel_id, created_by=request.user.hotel_staff_profile)
            # Prepare list of image URLs
            images = [
                hotel.image_1.url if hotel.image_1 else '',
                hotel.image_2.url if hotel.image_2 else '',
                hotel.image_3.url if hotel.image_3 else '',
                hotel.image_4.url if hotel.image_4 else '',
                hotel.image_5.url if hotel.image_5 else '',
                hotel.image_6.url if hotel.image_6 else '',
            ]
            context = {'hotel': hotel, 'images': images}
        except Hotels.DoesNotExist:
            messages.error(request, "Hotel not found or you don't have permission to edit it.")
            return redirect('staffpanel' if not request.user.is_maintainer else 'maintainer_panel')
    return render(request, 'hotel_staff/edit_hotel.html', context)


# @login_required(login_url='user:signin')
# def add_new_location(request):
#     if not request.user.is_staff or not hasattr(request.user, 'hotel_staff_profile'):
#         return HttpResponseForbidden("Not Allowed - Only hotel staff can add locations")

#     if request.method == "POST":
#         try:
#             name = request.POST.get('hotel_name', '').strip()
#             owner = request.POST.get('new_owner', '').strip()
#             location = request.POST.get('new_city', '').strip()
#             state = request.POST.get('new_state', '').strip()
#             country = request.POST.get('new_country', '').strip()
#             hotel_type = request.POST.get('hotel_type', '').strip()
#             other_heading = request.POST.get('other_heading', '').strip()
#             description_map = request.POST.get('description_map', '').strip()
#             heading_map = request.POST.get('heading_map', '').strip()
#             embedded_map_link = request.POST.get('embedded_map_link', '').strip()
#             rank = request.POST.get('rank', '0').strip()
#             rank = int(rank) if rank.isdigit() else 0
#             image_1 = request.FILES.get('image_1')
#             image_2 = request.FILES.get('image_2')
#             image_3 = request.FILES.get('image_3')
#             image_4 = request.FILES.get('image_4')
#             image_5 = request.FILES.get('image_5')
#             image_6 = request.FILES.get('image_6')

#             if not all([name, owner, location, state, country, hotel_type]):
#                 messages.error(request, "All required fields must be filled")
#                 return redirect("staffpanel")

#             if hotel_type not in dict(Hotels.HOTEL_TYPE_CHOICES).keys():
#                 messages.error(request, "Invalid hotel type selected.")
#                 return redirect("staffpanel")

#             if Hotels.objects.filter(location=location, name=name, owner=owner, state=state, country=country).exists():
#                 messages.warning(request, "A hotel with these details already exists")
#                 return redirect("staffpanel")

#             new_hotel = Hotels.objects.create(
#                 name=name,
#                 owner=owner,
#                 location=location,
#                 state=state,
#                 country=country,
#                 hotel_type=hotel_type,
#                 other_heading=other_heading if hotel_type == 'other' else '',
#                 description_map=description_map,
#                 heading_map=heading_map,
#                 embedded_map_link=embedded_map_link,
#                 rank=rank,
#                 image_1=image_1,
#                 image_2=image_2,
#                 image_3=image_3,
#                 image_4=image_4,
#                 image_5=image_5,
#                 image_6=image_6,
#                 created_by=request.user.hotel_staff_profile
#             )
#             new_hotel.assigned_staff.add(request.user.hotel_staff_profile)
#             messages.success(request, f"{name} in {location} added successfully!")
#             messages.warning(request, f"Hello {name}, please wait for admin approval to manage {location}.")
#             return redirect("staffpanel")

#         except Exception as e:
#             messages.error(request, f"Error: {str(e)}")
#             return redirect("staffpanel")

#     return render(request, 'hotel_staff/viewroom.html')
@login_required(login_url='user:signin')
def hotel_staff_bookings(request):
    if not hasattr(request.user, 'hotel_staff_profile'):
        messages.warning(request, "You don't have permissions to access the staff panel.")
        return redirect('/')

    staff = HotelStaff.objects.get(user=request.user)
    current_date = datetime.now().date()
    current_month = current_date.month
    current_year = current_date.year
    
    # Get all hotels owned by the same owner as the staff's hotel
    owner_hotels = Hotels.objects.filter(owner=staff.hotel.owner)
    
    # Get all hotels assigned to the staff
    assigned_hotels = staff.assigned_hotels.all()
    
    # Combine both querysets and remove duplicates
    all_accessible_hotels = (owner_hotels | assigned_hotels).distinct()
    
    # Get all bookings for all accessible hotels
    all_bookings = Reservation.objects.filter(room__hotel__in=all_accessible_hotels).order_by('-booking_time')
    
    # Calculate booking statistics for display
    total_bookings = all_bookings.count()
    bookings_today = all_bookings.filter(booking_time__date=current_date).count()
    bookings_this_month = all_bookings.filter(booking_time__month=current_month, booking_time__year=current_year).count()
    active_bookings = all_bookings.filter(check_in__lte=current_date, check_out__gte=current_date).count()
    check_ins_today = all_bookings.filter(check_in=current_date).count()
    check_outs_today = all_bookings.filter(check_out=current_date).count()
    check_ins_this_month = all_bookings.filter(check_in__month=current_month, check_in__year=current_year).count()
    check_outs_this_month = all_bookings.filter(check_out__month=current_month, check_out__year=current_year).count()
    
    # Calculate revenues
    total_revenue = sum(reservation.total_price for reservation in all_bookings)
    today_revenue = sum(
        reservation.total_price 
        for reservation in all_bookings 
        if reservation.booking_time.date() == current_date
    )
    
    # Initialize filter variables
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    month = request.GET.get('month')
    week = request.GET.get('week')
    day = request.GET.get('day')
    booking_date = request.GET.get('booking_date')
    search_name = request.GET.get('search_name')
    view_type = request.GET.get('view_type', 'all')
    hotel_filter = request.GET.get('hotel_filter')
    booking_status = request.GET.get('booking_status')
    filter_type = None

    if not any([start_date, end_date, month, week, day, booking_date, search_name, view_type, hotel_filter, booking_status]):
        day = current_date.strftime('%Y-%m-%d')
        view_type = 'active'
    
    bookings = all_bookings
    
    # Apply hotel filter if selected
    if hotel_filter:
        bookings = bookings.filter(room__hotel__id=hotel_filter)
    
    # Apply booking status filter if selected
    if booking_status:
        if booking_status == 'past':
            bookings = bookings.filter(check_out__lt=current_date)
        elif booking_status == 'current':
            bookings = bookings.filter(check_in__lte=current_date, check_out__gte=current_date)
        elif booking_status == 'future':
            bookings = bookings.filter(check_in__gt=current_date)
    
    if view_type == 'check_in':
        bookings = bookings.filter(check_in=day) if day else bookings
        filter_type = 'check_in'
    elif view_type == 'check_out':
        bookings = bookings.filter(check_out=day) if day else bookings
        filter_type = 'check_out'
    elif view_type == 'active':
        if day:
            try:
                day_date = datetime.strptime(day, '%Y-%m-%d').date()
                bookings = bookings.filter(
                    check_in__lte=day_date, check_out__gte=day_date
                )
                filter_type = 'active'
            except ValueError:
                messages.warning(request, "Invalid day format.")
                bookings = bookings
        else:
            bookings = bookings.filter(
                check_in__lte=current_date, check_out__gte=current_date
            )
            filter_type = 'active'
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            bookings = bookings.filter(check_in__gte=start_date)
            filter_type = 'check_in_range'
        except ValueError:
            messages.warning(request, "Invalid start date format.")
            start_date = None

    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            bookings = bookings.filter(check_out__lte=end_date)
            filter_type = 'check_out_range'
        except ValueError:
            messages.warning(request, "Invalid end date format.")
            end_date = None

    if month:
        try:
            month_num = datetime.strptime(month, '%B').month
            bookings = bookings.filter(
                Q(check_in__month=month_num) | Q(check_out__month=month_num)
            )
            filter_type = 'month'
        except ValueError:
            messages.warning(request, "Invalid month selected.")

    if week:
        try:
            week_num = int(week)
            bookings = bookings.filter(
                Q(check_in__week=week_num) | Q(check_out__week=week_num)
            )
            filter_type = 'week'
        except ValueError:
            messages.warning(request, "Invalid week number.")

    if booking_date:
        try:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
            bookings = bookings.filter(booking_time__date=booking_date)
            filter_type = 'booking_date'
        except ValueError:
            messages.warning(request, "Invalid booking date format.")
            booking_date = None

    if search_name:
        bookings = bookings.filter(
            Q(guest__first_name__icontains=search_name) |
            Q(guest__last_name__icontains=search_name) |
            Q(guest__username__icontains=search_name)
        )

    for booking in bookings:
        if booking.check_out < current_date:
            booking.status = 'past'
        elif booking.check_in <= current_date <= booking.check_out:
            booking.status = 'current'
        else:
            booking.status = 'future'

    # Calculate filtered revenue
    filtered_revenue = sum(reservation.total_price for reservation in bookings)
    
    months = ['January', 'February', 'March', 'April', 'May', 'June', 
              'July', 'August', 'September', 'October', 'November', 'December']
    weeks = [(i, f"Week {i}") for i in range(1, 53)]
    
    date_ranges = {
        'today': current_date,
        'tomorrow': current_date + timedelta(days=1),
        'yesterday': current_date - timedelta(days=1),
        'next_7_days': current_date + timedelta(days=7),
        'next_30_days': current_date + timedelta(days=30),
    }

    context = {
        'bookings': bookings,
        'current_date': current_date,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
        'day': day if day else current_date.strftime('%Y-%m-%d'),
        'month': month if month else '',
        'week': week if week else '',
        'booking_date': booking_date.strftime('%Y-%m-%d') if booking_date else '',
        'search_name': search_name or '',
        'hotel_filter': hotel_filter or '',
        'booking_status': booking_status or '',
        'months': months,
        'weeks': weeks,
        'date_ranges': date_ranges,
        'view_type': view_type,
        'filter_type': filter_type,
        'total_bookings': total_bookings,
        'bookings_today': bookings_today,
        'bookings_this_month': bookings_this_month,
        'active_bookings': active_bookings,
        'check_ins_today': check_ins_today,
        'check_outs_today': check_outs_today,
        'check_ins_this_month': check_ins_this_month,
        'check_outs_this_month': check_outs_this_month,
        'all_accessible_hotels': all_accessible_hotels,
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'filtered_revenue': filtered_revenue,
    }
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        action = request.GET.get('action', 'table')
        if action == 'calendar':
            return render(request, 'hotel_staff/booking_calendar.html', context)
        return render(request, 'hotel_staff/booking_table.html', context)
        
    return render(request, 'hotel_staff/bookings.html', context)



@login_required(login_url='user:signin')
def list_rooms(request):
    """
    Displays a list of rooms for hotels assigned to the logged-in staff.
    """
    if not hasattr(request.user, 'hotel_staff_profile'):
        return HttpResponseForbidden('Access Denied - Hotel Staff Only')

    staff = request.user.hotel_staff_profile
    assigned_hotels = staff.assigned_hotels.all()
    
    # Fetch all rooms from the staff's assigned hotels
    rooms = Rooms.objects.filter(hotel__in=assigned_hotels)

    # Add calculated fields for discounted price and saved money
    for room in rooms:
        room.discounted_price = room.price * (1 - room.discount / 100)
        room.saved_money = room.price - room.discounted_price

    context = {
        'rooms': rooms,
    }
    return render(request, 'hotel_staff/list_rooms.html', context)


def get_hotels_for_user(user):
    if hasattr(user, 'maintainer_profile'):
        # Maintainers see all hotels
        return Hotels.objects.all().values_list('name', 'id')
    elif hasattr(user, 'hotel_staff_profile'):
        # Staff only see hotels they're assigned to
        return user.hotel_staff_profile.assigned_hotels.all().values_list('name', 'id')
    else:
        # Regular users see all (or none)
        return Hotels.objects.none()
    
# @login_required(login_url='user:signin')
# def hotel_staff_bookings(request):
#     if not hasattr(request.user, 'hotel_staff_profile'):
#         messages.warning(request, "You don't have permissions to access the staff panel.")
#         return redirect('/')

#     staff = HotelStaff.objects.get(user=request.user)
#     current_date = datetime.now().date()
    
#     # Get all bookings for the hotel
#     all_bookings = Reservation.objects.filter(room__hotel=staff.hotel).order_by('-booking_time')
    
#     # Initialize filter variables
#     start_date = request.GET.get('start_date')
#     end_date = request.GET.get('end_date')
#     month = request.GET.get('month')
#     week = request.GET.get('week')
#     day = request.GET.get('day')
#     booking_date = request.GET.get('booking_date')
#     search_name = request.GET.get('search_name')
#     view_type = request.GET.get('view_type', 'all')  # 'all', 'check_in', 'check_out', 'active'
#     filter_type = None

#     # Set default view to today if no filters are applied
#     if not any([start_date, end_date, month, week, day, booking_date, search_name, view_type]):
#         day = current_date.strftime('%Y-%m-%d')
#         view_type = 'active'
    
#     # Apply filters based on view type
#     if view_type == 'check_in':
#         bookings = all_bookings.filter(check_in=day) if day else all_bookings
#         filter_type = 'check_in'
#     elif view_type == 'check_out':
#         bookings = all_bookings.filter(check_out=day) if day else all_bookings
#         filter_type = 'check_out'
#     elif view_type == 'active':
#         if day:
#             try:
#                 day_date = datetime.strptime(day, '%Y-%m-%d').date()
#                 bookings = all_bookings.filter(
#                     check_in__lte=day_date, check_out__gte=day_date
#                 )
#                 filter_type = 'active'
#             except ValueError:
#                 messages.warning(request, "Invalid day format.")
#                 bookings = all_bookings
#         else:
#             bookings = all_bookings.filter(
#                 check_in__lte=current_date, check_out__gte=current_date
#             )
#             filter_type = 'active'
#     else:  # 'all' view
#         bookings = all_bookings
    
#     # Apply additional filters
#     if start_date:
#         try:
#             start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
#             bookings = bookings.filter(check_in__gte=start_date)
#             filter_type = 'check_in_range'
#         except ValueError:
#             messages.warning(request, "Invalid start date format.")
#             start_date = None

#     if end_date:
#         try:
#             end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
#             bookings = bookings.filter(check_out__lte=end_date)
#             filter_type = 'check_out_range'
#         except ValueError:
#             messages.warning(request, "Invalid end date format.")
#             end_date = None

#     if month:
#         try:
#             month_num = datetime.strptime(month, '%B').month
#             bookings = bookings.filter(
#                 Q(check_in__month=month_num) | Q(check_out__month=month_num)
#             )
#             filter_type = 'month'
#         except ValueError:
#             messages.warning(request, "Invalid month selected.")

#     if week:
#         try:
#             week_num = int(week)
#             bookings = bookings.filter(
#                 Q(check_in__week=week_num) | Q(check_out__week=week_num)
#             )
#             filter_type = 'week'
#         except ValueError:
#             messages.warning(request, "Invalid week number.")

#     if booking_date:
#         try:
#             booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
#             bookings = bookings.filter(booking_time__date=booking_date)
#             filter_type = 'booking_date'
#         except ValueError:
#             messages.warning(request, "Invalid booking date format.")
#             booking_date = None

#     if search_name:
#         bookings = bookings.filter(
#             Q(guest__first_name__icontains=search_name) |
#             Q(guest__last_name__icontains=search_name) |
#             Q(guest__username__icontains=search_name)
#         )

#     # Update booking status for all bookings
#     for booking in bookings:
#         if booking.check_out < current_date:
#             booking.status = 'past'
#         elif booking.check_in <= current_date <= booking.check_out:
#             booking.status = 'current'
#         else:
#             booking.status = 'future'

#     # Prepare filter options
#     months = ['January', 'February', 'March', 'April', 'May', 'June', 
#               'July', 'August', 'September', 'October', 'November', 'December']
#     weeks = [(i, f"Week {i}") for i in range(1, 53)]
    
#     # Date ranges for quick filters
#     date_ranges = {
#         'today': current_date,
#         'tomorrow': current_date + timedelta(days=1),
#         'yesterday': current_date - timedelta(days=1),
#         'next_7_days': current_date + timedelta(days=7),
#         'next_30_days': current_date + timedelta(days=30),
#     }

#     context = {
#         'bookings': bookings,
#         'current_date': current_date,
#         'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
#         'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
#         'day': day if day else current_date.strftime('%Y-%m-%d'),
#         'month': month if month else '',
#         'week': week if week else '',
#         'booking_date': booking_date.strftime('%Y-%m-%d') if booking_date else '',
#         'search_name': search_name or '',
#         'months': months,
#         'weeks': weeks,
#         'date_ranges': date_ranges,
#         'view_type': view_type,
#         'filter_type': filter_type,
#     }
    
#     if request.headers.get('x-requested-with') == 'XMLHttpRequest':
#         # Handle both table and calendar updates
#         action = request.GET.get('action', 'table')
#         if action == 'calendar':
#             return render(request, 'hotel_staff/booking_calendar.html', context)
#         return render(request, 'hotel_staff/booking_table.html', context)
        
#     return render(request, 'hotel_staff/bookings.html', context)


from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from datetime import datetime, timedelta
from .models import Hotels, Rooms, Reservation  # Adjust imports as needed

@login_required(login_url='user:signin')
@user_passes_test(lambda u: u.is_maintainer, login_url='/')
def maintainer_panel(request):
    # Check if user has a maintainer profile
    if not hasattr(request.user, 'maintainer_profile'):
        messages.warning(request, "You need to complete your maintainer profile to access the panel.")
        return redirect('profile_edit')

    # Check if all required maintainer profile fields are complete
    maintainer = request.user.maintainer_profile
    required_fields = [
        maintainer.phone_no,
        maintainer.name,
        maintainer.designation,
        maintainer.profile_img,
        maintainer.aadhar_img,
        maintainer.pan_img
    ]
    
    if not all(required_fields):
        messages.warning(request, "Please complete all required profile fields to access the maintainer panel.")
        return redirect('user:maintainer_profile_edit')

    # Get filter parameters from GET request
    hotel_filter = request.GET.get('hotel_filter', 'all')
    status_filter = request.GET.get('status_filter', 'all')

    # Room and hotel statistics
    rooms = Rooms.objects.all().select_related('hotel')
    if hotel_filter != 'all':
        rooms = rooms.filter(hotel__name=hotel_filter)
    if status_filter != 'all':
        rooms = rooms.filter(status=status_filter)

    total_rooms = rooms.count()
    available_rooms = rooms.filter(status='1').count() if total_rooms else 0
    unavailable_rooms = rooms.filter(status='2').count() if total_rooms else 0
    total_hotels = Hotels.objects.count()
    hotels = Hotels.objects.all()  # For hotel filter dropdown
    reserved = Reservation.objects.count()
    hotel_locations = Hotels.objects.values_list('location', 'id').distinct().order_by('location')

    # Calculate percentages for room stats
    available_percent = (available_rooms / total_rooms * 100) if total_rooms else 0
    unavailable_percent = (unavailable_rooms / total_rooms * 100) if total_rooms else 0

    # Booking statistics
    current_date = datetime.now().date()
    current_month = current_date.month
    current_year = current_date.year

    all_bookings = Reservation.objects.all().select_related('guest', 'room', 'room__hotel').order_by('-booking_time')
    if hotel_filter != 'all':
        all_bookings = all_bookings.filter(room__hotel__name=hotel_filter)

    # Calculate counts
    total_bookings = all_bookings.count()
    bookings_today = all_bookings.filter(booking_time__date=current_date).count()
    bookings_this_month = all_bookings.filter(booking_time__month=current_month, booking_time__year=current_year).count()
    active_bookings = all_bookings.filter(check_in__lte=current_date, check_out__gte=current_date).count()
    check_ins_today = all_bookings.filter(check_in=current_date).count()
    check_outs_today = all_bookings.filter(check_out=current_date).count()
    check_ins_this_month = all_bookings.filter(check_in__month=current_month, check_in__year=current_year).count()
    check_outs_this_month = all_bookings.filter(check_out__month=current_month, check_out__year=current_year).count()

    # Calculate revenues
    def calculate_revenue(queryset):
        return sum(booking.total_price for booking in queryset)
    
    total_revenue = calculate_revenue(all_bookings)
    today_revenue = calculate_revenue(all_bookings.filter(booking_time__date=current_date))
    this_month_revenue = calculate_revenue(all_bookings.filter(booking_time__month=current_month, booking_time__year=current_year))
    active_bookings_revenue = calculate_revenue(all_bookings.filter(check_in__lte=current_date, check_out__gte=current_date))
    check_ins_today_revenue = calculate_revenue(all_bookings.filter(check_in=current_date))
    check_outs_today_revenue = calculate_revenue(all_bookings.filter(check_out=current_date))
    check_ins_month_revenue = calculate_revenue(all_bookings.filter(check_in__month=current_month, check_in__year=current_year))
    check_outs_month_revenue = calculate_revenue(all_bookings.filter(check_out__month=current_month, check_out__year=current_year))

    # Calculate percentages for booking stats
    total_bookings_percent = (total_bookings / total_rooms * 100) if total_rooms else 0
    active_bookings_percent = (active_bookings / total_bookings * 100) if total_bookings else 0
    bookings_today_percent = (bookings_today / total_bookings * 100) if total_bookings else 0
    check_ins_today_percent = (check_ins_today / total_bookings * 100) if total_bookings else 0
    check_outs_today_percent = (check_outs_today / total_bookings * 100) if total_bookings else 0
    bookings_this_month_percent = (bookings_this_month / total_bookings * 100) if total_bookings else 0
    check_ins_this_month_percent = (check_ins_this_month / total_bookings * 100) if total_bookings else 0
    check_outs_this_month_percent = (check_outs_this_month / total_bookings * 100) if total_bookings else 0

    # Booking filters (unchanged)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    month = request.GET.get('month')
    week = request.GET.get('week')
    day = request.GET.get('day')
    booking_date = request.GET.get('booking_date')
    search_name = request.GET.get('search_name')
    view_type = request.GET.get('view_type', 'active')
    filter_type = None

    if not any([start_date, end_date, month, week, day, booking_date, search_name]):
        day = current_date.strftime('%Y-%m-%d')
        view_type = 'active'

    if view_type == 'check_in':
        bookings = all_bookings.filter(check_in=day) if day else all_bookings
        filter_type = 'check_in'
    elif view_type == 'check_out':
        bookings = all_bookings.filter(check_out=day) if day else all_bookings
        filter_type = 'check_out'
    elif view_type == 'active':
        if day:
            try:
                day_date = datetime.strptime(day, '%Y-%m-%d').date()
                bookings = all_bookings.filter(check_in__lte=day_date, check_out__gte=day_date)
                filter_type = 'active'
            except ValueError:
                messages.warning(request, "Invalid day format.")
                bookings = all_bookings
        else:
            bookings = all_bookings.filter(check_in__lte=current_date, check_out__gte=current_date)
            filter_type = 'active'
    else:
        bookings = all_bookings

    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            bookings = bookings.filter(check_in__gte=start_date)
            filter_type = 'check_in_range'
        except ValueError:
            messages.warning(request, "Invalid start date format.")
            start_date = None

    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            bookings = bookings.filter(check_out__lte=end_date)
            filter_type = 'check_out_range'
        except ValueError:
            messages.warning(request, "Invalid end date format.")
            end_date = None

    if month:
        try:
            month_num = datetime.strptime(month, '%B').month
            bookings = bookings.filter(Q(check_in__month=month_num) | Q(check_out__month=month_num))
            filter_type = 'month'
        except ValueError:
            messages.warning(request, "Invalid month selected.")

    if week:
        try:
            week_num = int(week)
            bookings = bookings.filter(Q(check_in__week=week_num) | Q(check_out__week=week_num))
            filter_type = 'week'
        except ValueError:
            messages.warning(request, "Invalid week number.")

    if booking_date:
        try:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
            bookings = bookings.filter(booking_time__date=booking_date)
            filter_type = 'booking_date'
        except ValueError:
            messages.warning(request, "Invalid booking date format.")
            booking_date = None

    if search_name:
        bookings = bookings.filter(
            Q(guest__first_name__icontains=search_name) |
            Q(guest__last_name__icontains=search_name) |
            Q(guest__username__icontains=search_name) |
            Q(room__hotel__name__icontains=search_name)
        )

    for booking in bookings:
        if booking.check_out < current_date:
            booking.status = 'past'
        elif booking.check_in <= current_date <= booking.check_out:
            booking.status = 'current'
        else:
            booking.status = 'future'

    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    weeks = [(i, f"Week {i}") for i in range(1, 53)]

    date_ranges = {
        'today': current_date,
        'tomorrow': current_date + timedelta(days=1),
        'yesterday': current_date - timedelta(days=1),
        'next_7_days': current_date + timedelta(days=7),
        'next_30_days': current_date + timedelta(days=30),
    }

    context = {
        # Room and hotel stats
        'hotels': hotels,
        'selected_hotel': hotel_filter,
        'selected_status': status_filter,
        'location': hotel_locations,
        'reserved': reserved,
        'rooms': rooms,
        'total_rooms': total_rooms or 0,
        'available_rooms': available_rooms,
        'unavailable_rooms': unavailable_rooms,
        'total_hotels': total_hotels,
        'available_percent': available_percent,
        'unavailable_percent': unavailable_percent,
        'bookings': bookings,
        'current_date': current_date,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
        'day': day if day else current_date.strftime('%Y-%m-%d'),
        'month': month if month else '',
        'week': week if week else '',
        'booking_date': booking_date.strftime('%Y-%m-%d') if booking_date else '',
        'search_name': search_name or '',
        'months': months,
        'weeks': weeks,
        'date_ranges': date_ranges,
        'view_type': view_type,
        'filter_type': filter_type,
        'total_bookings': total_bookings,
        'bookings_today': bookings_today,
        'bookings_this_month': bookings_this_month,
        'active_bookings': active_bookings,
        'check_ins_today': check_ins_today,
        'check_outs_today': check_outs_today,
        'check_ins_this_month': check_ins_this_month,
        'check_outs_this_month': check_outs_this_month,
        'total_bookings_percent': total_bookings_percent,
        'active_bookings_percent': active_bookings_percent,
        'bookings_today_percent': bookings_today_percent,
        'check_ins_today_percent': check_ins_today_percent,
        'check_outs_today_percent': check_outs_today_percent,
        'bookings_this_month_percent': bookings_this_month_percent,
        'check_ins_this_month_percent': check_ins_this_month_percent,
        'check_outs_this_month_percent': check_outs_this_month_percent,
        # Revenue fields
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'this_month_revenue': this_month_revenue,
        'active_bookings_revenue': active_bookings_revenue,
        'check_ins_today_revenue': check_ins_today_revenue,
        'check_outs_today_revenue': check_outs_today_revenue,
        'check_ins_this_month_revenue': check_ins_month_revenue,
        'check_outs_this_month_revenue': check_outs_month_revenue,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        action = request.GET.get('action', 'table')
        if action == 'calendar':
            return render(request, 'maintainer/booking_calendar.html', context)
        return render(request, 'maintainer/booking_table.html', context)

    return render(request, 'maintainer/panel.html', context)


@login_required(login_url='user:signin')
def maintainer_all_bookings(request):
    if not hasattr(request.user, 'maintainer_profile'):
        messages.warning(request, "You don't have permissions to access the maintainer panel.")
        return redirect('/')

    current_date = datetime.now().date()
    current_month = current_date.month
    current_year = current_date.year
    
    # Get all hotels for the hotel filter dropdown
    all_hotels = Hotels.objects.all()
    
    # Get all bookings across all hotels
    all_bookings = Reservation.objects.all().select_related(
        'guest', 'room', 'room__hotel'
    ).order_by('-booking_time')
    
    # Calculate total revenue for all bookings
    total_revenue = sum(booking.total_price for booking in all_bookings)
    today_revenue = sum(
        booking.total_price 
        for booking in all_bookings 
        if booking.booking_time.date() == current_date
    )
    this_month_revenue = sum(
        booking.total_price 
        for booking in all_bookings 
        if booking.booking_time.month == current_month and booking.booking_time.year == current_year
    )
    
    # Initialize bookings with a safe default
    bookings = all_bookings if all_bookings.exists() else Reservation.objects.none()
    
    # Calculate booking statistics for display
    total_bookings = all_bookings.count()
    bookings_today = all_bookings.filter(booking_time__date=current_date).count()
    bookings_this_month = all_bookings.filter(booking_time__month=current_month, booking_time__year=current_year).count()
    active_bookings = all_bookings.filter(check_in__lte=current_date, check_out__gte=current_date).count()
    check_ins_today = all_bookings.filter(check_in=current_date).count()
    check_outs_today = all_bookings.filter(check_out=current_date).count()
    check_ins_this_month = all_bookings.filter(check_in__month=current_month, check_in__year=current_year).count()
    check_outs_this_month = all_bookings.filter(check_out__month=current_month, check_out__year=current_year).count()
    
    # Initialize filter variables
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    month = request.GET.get('month')
    week = request.GET.get('week')
    day = request.GET.get('day')
    booking_date = request.GET.get('booking_date')
    search_name = request.GET.get('search_name')
    view_type = request.GET.get('view_type', 'all')
    hotel_filter = request.GET.get('hotel_filter')
    booking_status = request.GET.get('status')
    filter_type = None

    if not any([start_date, end_date, month, week, day, booking_date, search_name, view_type, hotel_filter, booking_status]):
        day = current_date.strftime('%Y-%m-%d')
        view_type = 'active'
    
    # Apply hotel filter if selected
    if hotel_filter:
        try:
            bookings = bookings.filter(room__hotel__id=int(hotel_filter))
        except (ValueError, TypeError):
            messages.warning(request, "Invalid hotel filter selected.")
            bookings = all_bookings
    
    # Apply booking status filter if selected
    if booking_status:
        if booking_status == 'past':
            bookings = bookings.filter(check_out__lt=current_date)
        elif booking_status == 'current':
            bookings = bookings.filter(check_in__lte=current_date, check_out__gte=current_date)
        elif booking_status == 'future':
            bookings = bookings.filter(check_in__gt=current_date)
    
    if view_type == 'check_in':
        if day:
            try:
                day_date = datetime.strptime(day, '%Y-%m-%d').date()
                bookings = bookings.filter(check_in=day_date)
                filter_type = 'check_in'
            except ValueError:
                messages.warning(request, "Invalid day format.")
        else:
            bookings = bookings.filter(check_in=current_date)
            filter_type = 'check_in'
    elif view_type == 'check_out':
        if day:
            try:
                day_date = datetime.strptime(day, '%Y-%m-%d').date()
                bookings = bookings.filter(check_out=day_date)
                filter_type = 'check_out'
            except ValueError:
                messages.warning(request, "Invalid day format.")
        else:
            bookings = bookings.filter(check_out=current_date)
            filter_type = 'check_out'
    elif view_type == 'active':
        if day:
            try:
                day_date = datetime.strptime(day, '%Y-%m-%d').date()
                bookings = bookings.filter(check_in__lte=day_date, check_out__gte=day_date)
                filter_type = 'active'
            except ValueError:
                messages.warning(request, "Invalid day format.")
        else:
            bookings = bookings.filter(check_in__lte=current_date, check_out__gte=current_date)
            filter_type = 'active'
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            bookings = bookings.filter(check_in__gte=start_date)
            filter_type = 'check_in_range'
        except ValueError:
            messages.warning(request, "Invalid start date format.")
            start_date = None

    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            bookings = bookings.filter(check_out__lte=end_date)
            filter_type = 'check_out_range'
        except ValueError:
            messages.warning(request, "Invalid end date format.")
            end_date = None

    if month:
        try:
            month_num = datetime.strptime(month, '%B').month
            bookings = bookings.filter(Q(check_in__month=month_num) | Q(check_out__month=month_num))
            filter_type = 'month'
        except ValueError:
            messages.warning(request, "Invalid month selected.")

    if week:
        try:
            week_num = int(week)
            bookings = bookings.filter(Q(check_in__week=week_num) | Q(check_out__week=week_num))
            filter_type = 'week'
        except ValueError:
            messages.warning(request, "Invalid week number.")

    if booking_date:
        try:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
            bookings = bookings.filter(booking_time__date=booking_date)
            filter_type = 'booking_date'
        except ValueError:
            messages.warning(request, "Invalid booking date format.")
            booking_date = None

    if search_name:
        bookings = bookings.filter(
            Q(guest__first_name__icontains=search_name) |
            Q(guest__last_name__icontains=search_name) |
            Q(guest__username__icontains=search_name) |
            Q(room__hotel__name__icontains=search_name)
        )

    # Calculate filtered revenue
    filtered_revenue = sum(booking.total_price for booking in bookings)
    
    # Assign status to bookings
    for booking in bookings:
        if booking.check_out < current_date:
            booking.status = 'past'
        elif booking.check_in <= current_date <= booking.check_out:
            booking.status = 'current'
        else:
            booking.status = 'future'

    months = ['January', 'February', 'March', 'April', 'May', 'June', 
              'July', 'August', 'September', 'October', 'November', 'December']
    weeks = [(i, f"Week {i}") for i in range(1, 53)]
    
    date_ranges = {
        'today': current_date,
        'tomorrow': current_date + timedelta(days=1),
        'yesterday': current_date - timedelta(days=1),
        'next_7_days': current_date + timedelta(days=7),
        'next_30_days': current_date + timedelta(days=30),
    }

    context = {
        'bookings': bookings,
        'current_date': current_date,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
        'day': day if day else current_date.strftime('%Y-%m-%d'),
        'month': month if month else '',
        'week': week if week else '',
        'booking_date': booking_date.strftime('%Y-%m-%d') if booking_date else '',
        'search_name': search_name or '',
        'hotel_filter': hotel_filter or '',
        'booking_status': booking_status or '',
        'months': months,
        'weeks': weeks,
        'date_ranges': date_ranges,
        'view_type': view_type,
        'filter_type': filter_type,
        'total_bookings': total_bookings,
        'bookings_today': bookings_today,
        'bookings_this_month': bookings_this_month,
        'active_bookings': active_bookings,
        'check_ins_today': check_ins_today,
        'check_outs_today': check_outs_today,
        'check_ins_this_month': check_ins_this_month,
        'check_outs_this_month': check_outs_this_month,
        'all_hotels': all_hotels,
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'this_month_revenue': this_month_revenue,
        'filtered_revenue': filtered_revenue,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        action = request.GET.get('action', 'table')
        if action == 'events':
            events = []
            for booking in bookings:
                room_type_name = booking.room.room_type if isinstance(booking.room.room_type, str) else getattr(booking.room.room_type, 'name', 'N/A')
                events.extend([
                    {
                        'title': f'{booking.room.hotel.name}: {booking.room.room_number} - {booking.guest.get_full_name or booking.guest.username}',
                        'start': booking.booking_time.strftime('%Y-%m-%d'),
                        'url': reverse('user:user_profile_detail', kwargs={'username': booking.guest.username}),
                        'extendedProps': {
                            'type': 'booking',
                            'status': booking.status,
                            'guest': booking.guest.get_full_name or booking.guest.username,
                            'room': f'{room_type_name} (Room {booking.room.room_number})',
                            'hotel': booking.room.hotel.name,
                            'check_in': booking.check_in.strftime('%Y-%m-%d'),
                            'check_in_display': booking.check_in.strftime('%b %d, %Y'),
                            'check_out': booking.check_out.strftime('%Y-%m-%d'),
                            'check_out_display': booking.check_out.strftime('%b %d, %Y'),
                            'nights': booking.nights,
                            'amount': f'₹{booking.total_price:.2f}',
                            'booking_date': booking.booking_time.strftime('%b %d, %Y %I:%M %p')
                        },
                        'className': 'fc-event-booking',
                        'backgroundColor': '#3B82F6',
                        'textColor': 'white'
                    },
                    {
                        'title': f'Check-in: {booking.room.hotel.name} - {booking.room.room_number}',
                        'start': booking.check_in.strftime('%Y-%m-%d'),
                        'url': reverse('user:user_profile_detail', kwargs={'username': booking.guest.username}),
                        'extendedProps': {
                            'type': 'check-in',
                            'status': booking.status,
                            'guest': booking.guest.get_full_name or booking.guest.username,
                            'room': f'{room_type_name} (Room {booking.room.room_number})',
                            'hotel': booking.room.hotel.name,
                            'check_in': booking.check_in.strftime('%Y-%m-%d'),
                            'check_in_display': booking.check_in.strftime('%b %d, %Y'),
                            'check_out': booking.check_out.strftime('%Y-%m-%d'),
                            'check_out_display': booking.check_out.strftime('%b %d, %Y'),
                            'nights': booking.nights,
                            'amount': f'₹{booking.total_price:.2f}',
                            'booking_date': booking.booking_time.strftime('%b %d, %Y %I:%M %p')
                        },
                        'className': 'fc-event-check-in',
                        'backgroundColor': '#10B981',
                        'textColor': 'white'
                    },
                    {
                        'title': f'Check-out: {booking.room.hotel.name} - {booking.room.room_number}',
                        'start': booking.check_out.strftime('%Y-%m-%d'),
                        'url': reverse('user:user_profile_detail', kwargs={'username': booking.guest.username}),
                        'extendedProps': {
                            'type': 'check-out',
                            'status': booking.status,
                            'guest': booking.guest.get_full_name or booking.guest.username,
                            'room': f'{room_type_name} (Room {booking.room.room_number})',
                            'hotel': booking.room.hotel.name,
                            'check_in': booking.check_in.strftime('%Y-%m-%d'),
                            'check_in_display': booking.check_in.strftime('%b %d, %Y'),
                            'check_out': booking.check_out.strftime('%Y-%m-%d'),
                            'check_out_display': booking.check_out.strftime('%b %d, %Y'),
                            'nights': booking.nights,
                            'amount': f'₹{booking.total_price:.2f}',
                            'booking_date': booking.booking_time.strftime('%b %d, %Y %I:%M %p')
                        },
                        'className': 'fc-event-check-out',
                        'backgroundColor': '#F59E0B',
                        'textColor': 'white'
                    }
                ])
            return JsonResponse({'events': events})
        elif action == 'calendar':
            return render(request, 'maintainer/booking_calendar.html', context)
        return render(request, 'maintainer/booking_table.html', context)

    return render(request, 'maintainer/bookings.html', context)



@user_passes_test(lambda u: u.is_maintainer, login_url='/')
@login_required(login_url='user:signin')
def maintainer_view_rooms(request):
    if not hasattr(request.user, 'maintainer_profile'):
        messages.warning(request,"you don't have permissions ")
        return redirect('/')

    rooms = Rooms.objects.all()
    return render(request, 'maintainer/rooms.html', {'rooms': rooms})

@user_passes_test(lambda u: u.is_maintainer, login_url='/')
@login_required(login_url='user:signin')
def maintainer_view_hotels(request):
    if not hasattr(request.user, 'maintainer_profile'):
        messages.warning(request,"you don't have permissions ")
        return redirect('/')

    hotels = Hotels.objects.all()
    return render(request, 'maintainer/hotels.html', {'hotels': hotels})

@user_passes_test(lambda u: u.is_maintainer, login_url='/')
@login_required(login_url='user:signin')
def maintainer_edit_hotel(request, hotel_id):
    if not hasattr(request.user, 'maintainer_profile'):
        messages.warning(request,"you don't have permissions ")
        return redirect('/')

    hotels = get_object_or_404(Hotels, id=hotel_id)
    if request.method == "POST":
        try:
            hotels.name = request.POST['hotel_name'] 
            hotels.owner = request.POST['new_owner']
            hotels.location = request.POST['new_city']
            hotels.state = request.POST['new_state']
            hotels.country = request.POST['new_country']
            if 'main_image' in request.FILES:
                hotels.main_image = request.FILES['main_image']
            hotels.full_clean()
            hotels.save()
            messages.success(request, "Hotel updated successfully.")
            return redirect('maintainer_view_hotels')
        except Exception as e:
            messages.error(request, f"Error updating hotel: {e}")
    
    return render(request, 'maintainer/edit_hotels.html', {'hotel': hotels})

@user_passes_test(lambda u: u.is_maintainer, login_url='/')
@login_required(login_url='user:signin')
def maintainer_edit_room(request):
    if not hasattr(request.user, 'maintainer_profile'):
        messages.warning(request,"you don't have permissions ")
        return redirect('/')

    if request.method == 'POST':
        room_id = request.POST.get('roomid')
        
        if not room_id:
            messages.error(request, "Room ID is missing.")
            return redirect('maintainer_panel')

        try:
            room = get_object_or_404(Rooms, id=room_id)
            form = RoomForm(request.POST, request.FILES, instance=room)  # Assumes RoomForm exists

            if form.is_valid():
                form.save()
                messages.success(request, "Room details updated successfully.")
                return redirect('maintainer_panel')
            else:
                messages.error(request, "Form validation failed. Please correct the errors below.")
                return render(request, 'maintainer/edit_room.html', {'form': form, 'room': room})

        except Rooms.DoesNotExist:
            messages.error(request, "Room not found.")
            return redirect('maintainer_panel')
        except Exception as e:
            messages.error(request, f"Error updating room: {e}")
            return render(request, 'maintainer/edit_room.html', {'form': form, 'room': room})

    else:
        room_id = request.GET.get('roomid')
        if not room_id:
            messages.error(request, "Room ID is missing.")
            return redirect('maintainer_panel')

        try:
            room = get_object_or_404(Rooms, id=room_id)
            form = RoomForm(instance=room)
            hotels = Hotels.objects.all()
            return render(request, 'maintainer/edit_room.html', {'form': form, 'hotels': hotels, 'room': room})
        except Rooms.DoesNotExist:
            messages.error(request, "Room not found.")
            return redirect('maintainer_panel')

@user_passes_test(lambda u: u.is_maintainer, login_url='/')
@login_required(login_url='user:signin')
def maintainer_add_new_room(request):
    if not hasattr(request.user, 'maintainer_profile'):
        messages.warning(request,"you don't have permissions ")
        return redirect('/')

    if request.method == "POST" and request.FILES:
        try:
            hotel = Hotels.objects.get(id=int(request.POST['hotel']))
            check_in_time = request.POST.get('check_in_time')
            check_out_time = request.POST.get('check_out_time')

            new_room = Rooms(
                room_number=request.POST.get('room_number'),
                room_type=request.POST.get('roomtype'),
                capacity=int(request.POST.get('capacity', 0)),
                size=int(request.POST.get('size', 0)),
                price=float(request.POST.get('price', 0.0)),
                discount=float(request.POST.get('discount', 0.0)),
                status=request.POST.get('status'),
                hotel=hotel,
                description=request.POST.get('description'),
                heading=request.POST.get('heading'),
                food_facility=bool(request.POST.get('food_facility', False)),
                parking=bool(request.POST.get('parking', False)),
                check_in_time=check_in_time if check_in_time else None,
                check_out_time=check_out_time if check_out_time else None,
            )

            if 'image1' in request.FILES:
                new_room.image1 = request.FILES['image1']
            if 'image2' in request.FILES:
                new_room.image2 = request.FILES['image2']
            if 'image3' in request.FILES:
                new_room.image3 = request.FILES['image3']

            new_room.full_clean()
            new_room.save()
            messages.success(request, "New Room Added Successfully")
        except Exception as e:
            messages.error(request, f"Error adding room: {e}")
        return redirect('maintainer_panel')

    hotels = Hotels.objects.all()
    return render(request, 'maintainer/add_room.html', {'hotels': hotels})

@user_passes_test(lambda u: u.is_maintainer, login_url='/')
@login_required(login_url='user:signin')
def maintainer_view_room(request):
    if not hasattr(request.user, 'maintainer_profile'):
        messages.warning(request,"you don't have permissions ")
        return redirect('/')

    room_id = request.GET.get('roomid')
    if not room_id:
        messages.error(request, "Room ID is required.")
        return HttpResponse(render(request, 'maintainer/view_room.html', {'error': 'Room ID is required.'}))

    try:
        room = Rooms.objects.get(id=room_id)
    except Rooms.DoesNotExist:
        raise Http404("Room not found")

    reservations = Reservation.objects.filter(room=room)
    current_date = datetime.now().date()

    for reservation in reservations:
        if reservation.check_out < current_date:
            reservation.status = 'past'
        elif reservation.check_in <= current_date and reservation.check_out >= current_date:
            reservation.status = 'current'
        else:
            reservation.status = 'future'

    return HttpResponse(render(request, 'maintainer/view_room.html', {
        'room': room,
        'reservations': reservations,
        'current_date': current_date
    }))

@user_passes_test(lambda u: u.is_maintainer, login_url='/')
@login_required(login_url='user:signin')
def maintainer_add_new_location(request):
    # Ensure user is a maintainer
    if not getattr(request.user, 'maintainer_profile', None):
        return HttpResponseForbidden('Access Denied - Not a Maintainer')

    if request.method == "POST":
        # Safely get data from POST request
        name = request.POST.get('hotel_name', '').strip()
        owner = request.POST.get('new_owner', '').strip()
        location = request.POST.get('new_city', '').strip()
        state = request.POST.get('new_state', '').strip()
        country = request.POST.get('new_country', '').strip()

        # Validate required fields
        if not all([name, owner, location, state, country]):
            messages.error(request, "All fields are required!")
            return redirect("maintainer_panel")

        # Create and save new hotel
        try:
            Hotels.objects.create(
                name=name,
                owner=owner,
                location=location,
                state=state,
                country=country
            )
            messages.success(request, f"{name} in {location} added successfully!")
        except IntegrityError:
            messages.error(request, "Hotel with similar details already exists")
        except Exception as e:
            messages.error(request, f"Error creating hotel: {str(e)}")

        return redirect("maintainer_panel")

    # GET request - show form with all hotels
    context = {
        'all_hotels': Hotels.objects.all().values_list('name', 'id'),
        'location': Hotels.objects.all().values_list('name', 'id')  # For backward compatibility
    }
    return render(request, 'maintainer/add_location.html', context)



# userall
@login_required(login_url='user:signin')
def user_bookings(request):
    if request.user.is_authenticated == False:
        return redirect('userloginpage')
    
    user = User.objects.get(id=request.user.id)
    bookings = Reservation.objects.filter(guest=user)

    # Get the current date
    current_date = datetime.now().date()

    if not bookings:
        messages.warning(request, "No Bookings Found")

    return render(request, 'user/mybookings.html', {'bookings': bookings, 'current_date': current_date})


# def book_room_page(request):
#     room_id = request.GET.get('roomid')
#     check_in = request.GET.get('cin') or request.session.get('check_in')
#     check_out = request.GET.get('cout') or request.session.get('check_out')
    
#     try:
#         room = Rooms.objects.get(id=room_id)
#         context = {
#             'room': room,
#             'check_in': check_in,
#             'check_out': check_out,
#         }
#         return render(request, 'rooms/book_room.html', context)
#     except Rooms.DoesNotExist:
#         messages.error(request, "Room not found")
#         return redirect('homepage')

def book_room_page(request):
    try:
        room_id = request.GET.get('roomid')
        if not room_id:
            raise ValueError("Room ID is required")
            
        room = Rooms.objects.get(id=int(room_id))
        
        # Get the hotel associated with the room to access its GST rate
        try:
            hotel = room.hotel
            gst_percentage = float(hotel.gst_rate) if hotel.gst_rate else 0.0
        except Exception as e:
            gst_percentage = 0.0  # Default to 0% if hotel or GST rate not available
        
        # Check if the current user is the hotel owner
        # Compare usernames directly since owner is stored as a string
        is_owner_booking = False
        if request.user.is_authenticated:
            is_owner_booking = (request.user.username == hotel.owner)  # Compare with string
        
        # Retrieve form data from session
        check_in_str = request.session.get('check_in', '')
        check_out_str = request.session.get('check_out', '')
        capacity = request.session.get('capacity', '')

        # Initialize price variables with default values
        stay_days = 0
        base_price = 0
        gst_amount = 0
        total_price = 0
        
        # Get room price (handle both method and property cases)
        if hasattr(room, 'discounted_price'):
            if callable(room.discounted_price):
                room_price_per_night = float(room.discounted_price())
            else:
                room_price_per_night = float(room.discounted_price)
        else:
            room_price_per_night = 0.0

        if check_in_str and check_out_str:
            try:
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
                
                # Calculate stay duration (minimum 1 day)
                stay_days = max((check_out - check_in).days, 1)
                
                # Calculate prices
                base_price = room_price_per_night * stay_days
                gst_amount = (base_price * gst_percentage) / 100 if gst_percentage > 0 else 0
                total_price = base_price + gst_amount
                
            except (ValueError, TypeError) as e:
                messages.error(request, f"Invalid date format: {str(e)}")
                return redirect('homepage')

        # Get reservations
        reservations = Reservation.objects.filter(room=room).order_by('-booking_time')
        current_date = datetime.now().date()

        # Check if the current user is the hotel owner
        is_owner_booking = request.user.is_authenticated and (request.user.username == hotel.owner)
        
        # Get all hotels owned by the user if they are the owner
        owner_hotels = []
        if is_owner_booking:
            owner_hotels = Hotels.objects.filter(owner=request.user.username)

        for reservation in reservations:
            reservation.status = (
                'past' if reservation.check_out < current_date else
                'current' if reservation.check_in <= current_date <= reservation.check_out else
                'future'
            )
            # Check if the guest is the hotel owner
            reservation.is_owner_booking = (reservation.guest.username == hotel.owner)

        context = {
            'room': room,
            'hotel': hotel,
            'check_in': check_in_str,
            'check_out': check_out_str,
            'capacity': capacity,
            'reservations': reservations,
            'current_date': current_date,
            'stay_days': stay_days,
            'base_price': round(float(base_price), 2),
            'gst_percentage': gst_percentage,
            'gst_amount': round(float(gst_amount), 2),
            'total_price': round(float(total_price), 2),
            'room_price_per_night': round(float(room_price_per_night), 2),
            'has_gst': gst_percentage > 0,
            'is_owner_booking': is_owner_booking,
        }
        
        return render(request, 'user/bookroom.html', context)
        
    except (ValueError, Rooms.DoesNotExist) as e:
        messages.error(request, "Invalid room selection")
        return redirect('homepage')
    

@login_required_with_message(message="You have to login first.", login_url='user:signin')
def book_room(request):
     
    if request.method == "POST":

        room_id = request.POST['room_id']
        
        room = Rooms.objects.all().get(id=room_id)
        #for finding the reserved rooms on this time period for excluding from the query set
        for each_reservation in Reservation.objects.all().filter(room=room):
            if str(each_reservation.check_in) < str(request.POST['check_in']) and str(each_reservation.check_out) < str(request.POST['check_out']):
                pass
            elif str(each_reservation.check_in) > str(request.POST['check_in']) and str(each_reservation.check_out) > str(request.POST['check_out']):
                pass
            else:
                messages.warning(request,"Sorry This Room is unavailable for Booking")
                return redirect("homepage")
            
        current_user = request.user
        total_person = int(request.POST['person'])
        booking_id = str(room_id) + str(datetime.now())  # using datetime.now() after import

        reservation = Reservation()
        room_object = Rooms.objects.all().get(id=room_id)
        room_object.status = '2'
        
        user_object = User.objects.all().get(username=current_user)

        reservation.guest = user_object
        reservation.room = room_object
        person = total_person
        reservation.check_in = request.POST['check_in']
        reservation.check_out = request.POST['check_out']

        reservation.save()

        messages.success(request,"Congratulations! Booking Successfull")

        return redirect("homepage")
    else:
        return HttpResponse('Access Denied')



#about
def aboutpage(request):
    return HttpResponse(render(request,'about.html'))



def Check_list(request):
    hotels = Hotels.objects.all()
    rooms = Rooms.objects.filter(status='1')  
    location = request.GET.get('location')
    if location:
        rooms = rooms.filter(hotel__location=location)

    if 'ac' in request.GET:
        rooms = rooms.filter(ac=True)
    if 'fan' in request.GET:
        rooms = rooms.filter(fan=True)
    if 'wifi' in request.GET:
        rooms = rooms.filter(wifi=True)
    if 'parking' in request.GET:
        rooms = rooms.filter(parking=True)
    if 'heater' in request.GET:
        rooms = rooms.filter(heater=True)
    if 'food_facility' in request.GET:
        rooms = rooms.filter(food_facility=True)

    if request.method == 'POST':
        location = request.POST.get('search_location')
        if location:
            rooms = rooms.filter(hotel__location=location)

        check_in = request.POST.get('cin')
        check_out = request.POST.get('cout')
        capacity = request.POST.get('capacity')

        if check_in and check_out:
           
            booked_rooms = []
            for reservation in Reservation.objects.all():
                if (str(reservation.check_in) < str(check_in) and str(reservation.check_out) < str(check_out)) or \
                   (str(reservation.check_in) > str(check_in) and str(reservation.check_out) > str(check_out)):
                    pass
                else:
                    booked_rooms.append(reservation.room.id)

            rooms = rooms.exclude(id__in=booked_rooms)
        
        if capacity:
            rooms = rooms.filter(capacity__gte=int(capacity))

    context = {
        'rooms': rooms,
        'hotels': hotels,
        
    }
    return render(request, 'rooms/index.html', context)

from datetime import datetime  


def handler404(request):
    return render(request, '404.html', status=404)
