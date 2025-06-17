from functools import wraps
from multiprocessing import context
from sqlite3 import IntegrityError
from django.http import Http404,HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed , HttpResponseRedirect, JsonResponse
import pytz
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth import get_user_model
from django.db.models import Q, F
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
            # Get active reservations
            reserved_rooms = Reservation.objects.filter(
                check_in__lt=check_out_date,
                check_out__gt=check_in_date,
                is_cancelled=False  # Only consider non-cancelled bookings
            ).values_list('room_id', flat=True)
            
            # Get recently cancelled reservations (within last 30 minutes)
            recently_cancelled = Reservation.objects.filter(
                check_in__lt=check_out_date,
                check_out__gt=check_in_date,
                is_cancelled=True,
                cancelled_at__gte=timezone.now() - timedelta(minutes=30)
            ).values_list('room_id', flat=True)
            
            # Exclude rooms with active reservations but include recently cancelled ones
            rooms_query = rooms_query.exclude(
                id__in=reserved_rooms
            ).filter(
                Q(id__in=recently_cancelled) | ~Q(id__in=reserved_rooms)
            )
            
        except Exception as e:
            logger.error(f"Error filtering rooms by date: {str(e)}")
            messages.error(request, f"Error filtering rooms by date: {str(e)}")

    if capacity:
        try:
            capacity = int(capacity)
            if capacity <= 0:
                raise ValueError("Capacity must be positive")
            # Filter rooms where total capacity (base + extra) is >= requested capacity
            rooms_query = rooms_query.annotate(
                total_capacity=F('capacity') + F('extra_capacity')
            ).filter(total_capacity__gte=capacity)
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

    # Highlight recently cancelled rooms
    recently_cancelled_rooms = []
    if check_in_date and check_out_date:
        recently_cancelled_reservations = Reservation.objects.filter(
            check_in__lt=check_out_date,
            check_out__gt=check_in_date,
            is_cancelled=True,
            cancelled_at__gte=timezone.now() - timedelta(minutes=30))
            
        recently_cancelled_rooms = [r.room_id for r in recently_cancelled_reservations]

    for hotel in hotels:
        available_rooms = rooms_query.filter(hotel=hotel)
        available_rooms_count = available_rooms.count()
        
        # Get recently cancelled rooms for this hotel
        hotel_recently_cancelled = [
            room for room in available_rooms 
            if room.id in recently_cancelled_rooms
        ]
        
        hotels_with_counts.append({
            'hotel': hotel,
            'available_rooms_count': available_rooms_count,
            'has_recently_cancelled': len(hotel_recently_cancelled) > 0
        })

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
        'active_amenities': active_amenities,
        'show_recently_available': True  ,# Flag to enable the "Recently Available" display
        'show_social_picture': True  # Add this line
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
    Supports date changes, capacity (including extra capacity), price range, and amenity filters.
    Identifies the cheapest room and computes facilities available in at least one room.
    Shows recently cancelled rooms as available.
    """
    logger.debug(f"Processing view_hotel_rooms for hotel_id={hotel_id}, request.GET={request.GET}")

    try:
        hotel = Hotels.objects.get(id=hotel_id)
        logger.debug(f"Found hotel: {hotel.name} (ID: {hotel_id})")

        # Get filter criteria from GET parameters, falling back to session
        check_in = request.GET.get('cin', request.session.get('check_in'))
        check_out = request.GET.get('cout', request.session.get('check_out'))
        capacity = request.GET.get('capacity', request.session.get('capacity', '1'))
        min_price = request.GET.get('min_price', request.session.get('min_price', '0'))
        max_price = request.GET.get('max_price', request.session.get('max_price', '10000'))
        location = request.GET.get('search_location', request.session.get('location'))

        # Amenity filters
        amenities = ['ac', 'fan', 'wifi', 'parking', 'heater', 'food_facility', 'convenient_location',
                    'comfortable_bed', 'private_bathroom', 'cleanliness', 'safety_security',
                    'entertainment_options', 'laundry_facility', 'outdoor_balcony', 'concierge_service']
        active_amenities = {
            amenity: '1' if request.GET.get(amenity) == '1' else '0'
            for amenity in amenities
        }

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
                    messages.warning(request, "Check-out date must be after check-in date.")
                    check_out_date = default_check_out
                    check_out = default_check_out.strftime('%Y-%m-%d')
            else:
                check_out_date = default_check_out
                check_out = default_check_out.strftime('%Y-%m-%d')

            formatted_check_out = check_out_date.strftime('%d %B %Y')

        except ValueError as e:
            messages.warning(request, "Invalid date format. Please select valid dates.")
            check_in_date = default_check_in
            check_out_date = default_check_out
            check_in = default_check_in.strftime('%Y-%m-%d')
            check_out = default_check_out.strftime('%Y-%m-%d')
            formatted_check_in = default_check_in.strftime('%d %B %Y')
            formatted_check_out = default_check_out.strftime('%d %B %Y')

        # Initialize rooms query with annotation for total capacity
        rooms = Rooms.objects.filter(hotel=hotel, status='1').annotate(
            total_capacity=F('capacity') + F('extra_capacity')
        )
        logger.debug(f"Initial room count for hotel_id={hotel_id}: {rooms.count()}")

        # Apply location filter
        if location and str(hotel.id) != location:
            messages.warning(request, "Selected location does not match the hotel.")
            rooms = rooms.none()
        else:
            # Apply date-based availability filter
            if check_in_date and check_out_date:
                try:
                    # Get rooms with active reservations
                    reserved_rooms = Reservation.objects.filter(
                        check_in__lt=check_out_date,
                        check_out__gt=check_in_date,
                        is_cancelled=False
                    ).values_list('room_id', flat=True)
                    
                    # Get rooms with recently cancelled reservations (within last 30 minutes)
                    recently_cancelled_rooms = Reservation.objects.filter(
                        check_in__lt=check_out_date,
                        check_out__gt=check_in_date,
                        is_cancelled=True,
                        cancelled_at__gte=timezone.now() - timedelta(minutes=30)
                    ).values_list('room_id', flat=True)
                    
                    # Exclude rooms with active reservations but include recently cancelled ones
                    rooms = rooms.exclude(
                        id__in=reserved_rooms
                    ).filter(
                        Q(id__in=recently_cancelled_rooms) | ~Q(id__in=reserved_rooms)
                    )
                    
                    logger.debug(f"Rooms after availability filtering: {rooms.count()}")
                    
                    # Get list of recently cancelled room IDs for highlighting
                    recently_cancelled_room_ids = list(recently_cancelled_rooms)
                except Exception as e:
                    logger.error(f"Error filtering rooms by date: {str(e)}")
                    messages.error(request, f"Error filtering rooms by date: {str(e)}")

            # Apply capacity filter - now using total_capacity (base + extra)
            if capacity:
                try:
                    capacity = int(capacity)
                    if capacity <= 0:
                        raise ValueError("Capacity must be positive")
                    rooms = rooms.filter(total_capacity__gte=capacity)
                    logger.debug(f"Rooms after capacity filter: {rooms.count()}")
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
                    logger.debug(f"Rooms after price filter: {rooms.count()}")
                except ValueError as e:
                    logger.error(f"Invalid price range - min: {min_price}, max: {max_price}, error: {str(e)}")
                    messages.error(request, "Invalid price range.")

            # Apply amenity filters
            for amenity, value in active_amenities.items():
                if value == '1':
                    rooms = rooms.filter(**{amenity: True})
                    logger.debug(f"Rooms after {amenity} filter: {rooms.count()}")

        # Prepare room data with capacity display information
        room_list = []
        for room in rooms:
            room_data = {
                'id': room.id,
                'room_number': room.room_number,
                'room_type': room.get_room_type_display(),
                'base_capacity': room.capacity,
                'extra_capacity': room.extra_capacity,
                'total_capacity': room.total_capacity,
                'capacity_display': f"{room.capacity}+{room.extra_capacity}" if room.extra_capacity > 0 else str(room.capacity),
                'extra_person_charges': room.extra_person_charges,
                'price': room.price,
                'discount': room.discount,
                'discounted_price': room.discounted_price(),
                'image1': room.image1,
                'heading': room.heading,
                'description': room.description,
                'amenities': {amenity: getattr(room, amenity) for amenity in amenities},
                'is_recently_available': room.id in recently_cancelled_room_ids if 'recently_cancelled_room_ids' in locals() else False
            }
            room_list.append(room_data)

        # Identify the cheapest room
        cheapest_room = None
        if room_list:
            cheapest_room = min(room_list, key=lambda x: x['discounted_price'])
            logger.debug(f"Cheapest room: ID={cheapest_room['id']}, Price={cheapest_room['discounted_price']}")

        # Compute available facilities
        available_facilities = {}
        for amenity in amenities:
            available_facilities[amenity] = any(room['amenities'][amenity] for room in room_list)

        # Update session with current filters
        request.session['check_in'] = check_in
        request.session['check_out'] = check_out
        request.session['capacity'] = str(capacity)
        request.session['location'] = location
        request.session['min_price'] = str(min_price) if min_price else '0'
        request.session['max_price'] = str(max_price) if max_price else '10000'
        request.session['amenities'] = {k: v for k, v in active_amenities.items() if v == '1'}
        request.session.modified = True

        # Prepare context
        context = {
            'hotel': hotel,
            'rooms': room_list,  # Now using our prepared room data
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
            'available_facilities': available_facilities,
            'recently_cancelled_room_ids': recently_cancelled_room_ids if 'recently_cancelled_room_ids' in locals() else [],
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
    





from django.db.models import Q
from decimal import Decimal
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Hotels, Rooms, Reservation

@login_required(login_url='user:signin')
def rooms_status(request):
    """
    Displays the rooms status dashboard with filtering capabilities and handles direct room booking.
    Shows detailed pricing information including base price, discount, and GST.
    Includes all bookings (past, current, and future) for the bookings section.
    """
    if not hasattr(request.user, 'hotel_staff_profile'):
        return render(request, 'hotel_staff/panel.html', {
            'error_title': 'Access Denied',
            'error_message': 'This page is only accessible to hotel staff members.',
            'current_date': datetime.now().date(),
            'tomorrow_date': (datetime.now().date() + timedelta(days=1))
        }, status=403)
    
    try:
        staff = request.user.hotel_staff_profile
        assigned_hotels = Hotels.objects.filter(assigned_staff=staff)
        
        if not assigned_hotels.exists():
            messages.warning(request, 'Please add your hotel and rooms to manage bookings.')
            return redirect('add_hotel')
        
        # Handle POST request for booking
        if request.method == 'POST':
            try:
                room_id = request.POST.get('room_id')
                check_in_str = request.POST.get('check_in')
                check_out_str = request.POST.get('check_out')
                person = request.POST.get('person')
                
                if not all([room_id, check_in_str, check_out_str, person]):
                    messages.error(request, 'All fields are required.')
                    return redirect(request.get_full_path())
                
                room = Rooms.objects.get(id=int(room_id))
                if not assigned_hotels.filter(id=room.hotel.id).exists():
                    messages.error(request, 'Permission denied to book this room.')
                    return redirect(request.get_full_path())
                
                # Validate dates
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
                current_date = datetime.now().date()
                
                if check_in < current_date:
                    messages.error(request, 'Check-in date cannot be in the past.')
                    return redirect(request.get_full_path())
                
                if check_out <= check_in:
                    messages.error(request, 'Check-out date must be after check-in date.')
                    return redirect(request.get_full_path())
                
                # Validate guest count
                person = int(person)
                if person <= 0 or person > room.capacity:
                    messages.error(request, f'Guest count must be between 1 and {room.capacity}.')
                    return redirect(request.get_full_path())
                
                # Check room availability
                conflicting_bookings = Reservation.objects.filter(
                    room=room,
                    check_in__lt=check_out,
                    check_out__gt=check_in,
                    is_cancelled=False
                ).exists()
                
                if conflicting_bookings or room.status == '2':
                    messages.error(request, 'Room is not available for the selected dates.')
                    return redirect(request.get_full_path())
                
                # Calculate pricing with discount and GST
                stay_days = max((check_out - check_in).days, 1)
                discounted_price_per_night = room.discounted_price()
                base_price = discounted_price_per_night * stay_days
                
                # Add extra person charges if applicable
                if person > 1 and room.extra_person_charges:
                    base_price += room.extra_person_charges * (person - 1)

                # In your booking view
                if person > room.total_capacity():
                    messages.error(request, 
                        f"This room can accommodate {room.capacity} guests (with {room.extra_capacity} extra). "
                        f"Please select a different room or reduce your guest count."
                    )
                    return redirect('index', room_id=room.id)
                
                # Calculate GST
                gst_percentage = room.hotel.gst_rate if room.hotel.gst_rate else Decimal('12.00')
                gst_amount = (base_price * gst_percentage) / Decimal('100')
                total_price = base_price + gst_amount
                
                # Create reservation
                reservation = Reservation(
                    room=room,
                    guest=request.user,
                    check_in=check_in,
                    check_out=check_out,
                    number_of_guests=person,
                    base_price_value=base_price,  # Store the calculated base price
                    gst_amount_value=gst_amount   # Store the calculated GST
                )
                reservation.save()
                
                messages.success(request, 'Room booked successfully!')
                return redirect(request.get_full_path())
                
            except (ValueError, Rooms.DoesNotExist) as e:
                messages.error(request, f'Invalid booking request: {str(e)}')
                return redirect(request.get_full_path())
            except Exception as e:
                messages.error(request, f'An error occurred during booking: {str(e)}')
                return redirect(request.get_full_path())
        
        # Handle GET request for dashboard
        hotel_filter = request.GET.get('hotel_filter', 'all')
        status_filter = request.GET.get('status_filter', 'all')
        date_filter = request.GET.get('date_filter')
        
        # Parse date filter or use today
        try:
            selected_date = datetime.strptime(date_filter, '%Y-%m-%d').date() if date_filter else datetime.now().date()
        except ValueError:
            selected_date = datetime.now().date()
        
        # Fetch rooms
        rooms = Rooms.objects.filter(hotel__in=assigned_hotels).select_related('hotel')
        
        # Apply hotel filter
        if hotel_filter != 'all':
            rooms = rooms.filter(hotel__name=hotel_filter)
        
        # Fetch all reservations for the assigned hotels
        reservations = Reservation.objects.filter(
            room__hotel__in=assigned_hotels
        ).select_related('guest', 'room').order_by('-check_in')
        
        # Process rooms with pricing information
        current_date = datetime.now().date()
        tomorrow_date = current_date + timedelta(days=1)
        processed_rooms = []
        for room in rooms:
            room.current_booking = Reservation.objects.filter(
                room=room,
                check_in__lte=selected_date,
                check_out__gt=selected_date,
                is_cancelled=False
            ).select_related('guest').first()
            
            # Determine display status
            if room.status == '2':
                room.display_status = '2'  # Unavailable
            elif room.current_booking:
                room.display_status = '3'  # Booked
            else:
                room.display_status = '1'  # Available
            
            # Calculate pricing information
            room.discounted_price_value = room.discounted_price()
            room.saved_amount = room.saved_money()
            room.gst_rate = room.hotel.gst_rate if room.hotel.gst_rate else Decimal('12.00')
            
            if room.display_status == '3' and room.current_booking:
                room.gst_amount = room.current_booking.gst_amount
                room.total_price = room.current_booking.total_price
            else:
                room.gst_amount = (room.discounted_price_value * room.gst_rate) / Decimal('100')
                room.total_price = room.discounted_price_value + room.gst_amount
            
            room.is_past_date = selected_date < current_date
            processed_rooms.append(room)
        
        # Apply status filter
        if status_filter == 'available':
            processed_rooms = [room for room in processed_rooms if room.display_status == '1']
        elif status_filter == 'booked':
            processed_rooms = [room for room in processed_rooms if room.display_status == '3']
        elif status_filter == 'unavailable':
            processed_rooms = [room for room in processed_rooms if room.display_status == '2']
        
        # Calculate summary statistics
        total_rooms = len(processed_rooms)
        available_rooms = len([room for room in processed_rooms if room.display_status == '1'])
        booked_rooms = len([room for room in processed_rooms if room.display_status == '3'])
        unavailable_rooms = len([room for room in processed_rooms if room.display_status == '2'])
        
        context = {
            'hotels': assigned_hotels,
            'rooms': processed_rooms,
            'reservations': reservations,
            'selected_hotel': hotel_filter,
            'selected_status': status_filter,
            'selected_date': selected_date,
            'current_date': current_date,
            'tomorrow_date': tomorrow_date,
            'total_rooms': total_rooms,
            'available_rooms': available_rooms,
            'booked_rooms': booked_rooms,
            'unavailable_rooms': unavailable_rooms,
        }

        return render(request, 'hotel_staff/rooms_status.html', context)
        
    except Exception as e:
        return render(request, 'hotel_staff/rooms_status.html', {
            'error_title': 'An Error Occurred',
            'error_message': f'An unexpected error occurred: {str(e)}',
            'current_date': datetime.now().date(),
            'tomorrow_date': (datetime.now().date() + timedelta(days=1))
        }, status=500)

@login_required
@require_POST
def update_room_status(request, room_id):
    """
    AJAX view to update room status (Available/Unavailable).
    Validates staff permission and ensures no booking conflicts.
    """
    try:
        room = Rooms.objects.get(id=room_id)
        if not Hotels.objects.filter(assigned_staff=request.user.hotel_staff_profile, id=room.hotel.id).exists():
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        new_status = request.POST.get('status')
        if new_status not in ('1', '2'):
            return JsonResponse({'error': 'Invalid status'}, status=400)
        
        # Check for bookings if marking unavailable
        if new_status == '2':
            selected_date = request.POST.get('selected_date', datetime.now().date())
            try:
                selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date() if isinstance(selected_date, str) else selected_date
            except ValueError:
                selected_date = datetime.now().date()
            
            booking = Reservation.objects.filter(
                room=room,
                check_in__lte=selected_date,
                check_out__gt=selected_date,
                is_cancelled=False
            ).exists()
            if booking:
                return JsonResponse({'error': 'Cannot mark a booked room as unavailable'}, status=400)
        
        room.status = new_status
        room.save()
        return JsonResponse({
            'success': True,
            'new_status': 'Available' if new_status == '1' else 'Unavailable'
        })
            
    except Rooms.DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)




from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from datetime import datetime, timedelta
from .models import Hotels, Rooms, Reservation
from decimal import Decimal

@login_required(login_url='user:signin')
def maintainer_rooms_status(request):
    """
    Displays the rooms status dashboard for maintainers with full access to all hotels.
    Shows detailed pricing information including base price, discount, and GST.
    """
    if not hasattr(request.user, 'maintainer_profile'):
        return render(request, 'maintainer/panel.html', {
            'error_title': 'Access Denied',
            'error_message': 'This page is only accessible to maintainers.',
            'current_date': datetime.now().date(),
            'tomorrow_date': (datetime.now().date() + timedelta(days=1))
        }, status=403)
    
    try:
        # Maintainers have access to all hotels
        all_hotels = Hotels.objects.all()
        
        # Handle POST request for booking
        if request.method == 'POST':
            try:
                room_id = request.POST.get('room_id')
                check_in_str = request.POST.get('check_in')
                check_out_str = request.POST.get('check_out')
                person = request.POST.get('person')
                
                if not all([room_id, check_in_str, check_out_str, person]):
                    messages.error(request, 'All fields are required.')
                    return redirect(request.get_full_path())
                
                room = Rooms.objects.get(id=int(room_id))
                
                # Validate dates
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
                current_date = datetime.now().date()
                
                if check_in < current_date:
                    messages.error(request, 'Check-in date cannot be in the past.')
                    return redirect(request.get_full_path())
                
                if check_out <= check_in:
                    messages.error(request, 'Check-out date must be after check-in date.')
                    return redirect(request.get_full_path())
                
                # Validate guest count
                person = int(person)
                if person <= 0 or person > room.capacity:
                    messages.error(request, f'Guest count must be between 1 and {room.capacity}.')
                    return redirect(request.get_full_path())
                
                # Check room availability
                conflicting_bookings = Reservation.objects.filter(
                    room=room,
                    check_in__lt=check_out,
                    check_out__gt=check_in
                ).exists()
                
                if conflicting_bookings or room.status == '2':
                    messages.error(request, 'Room is not available for the selected dates.')
                    return redirect(request.get_full_path())
                
                # Calculate pricing with discount and GST
                stay_days = max((check_out - check_in).days, 1)
                
                # Get discounted price
                discounted_price_per_night = room.discounted_price()
                base_price = discounted_price_per_night * stay_days
                
                # Add extra person charges if applicable
                if person > 1 and room.extra_person_charges:
                    base_price += room.extra_person_charges * (person - 1)
                
                # Calculate GST
                gst_percentage = Decimal(room.hotel.gst_rate) if room.hotel.gst_rate else Decimal('12.00')
                gst_amount = (base_price * gst_percentage) / Decimal('100')
                total_price = base_price + gst_amount
                
                # Create reservation
                reservation = Reservation(
                    room=room,
                    guest=request.user,
                    check_in=check_in,
                    check_out=check_out,
                    total_price=total_price,
                    number_of_guests=person
                )
                reservation.save()
                
                messages.success(request, 'Room booked successfully!')
                return redirect(request.get_full_path())
                
            except (ValueError, Rooms.DoesNotExist) as e:
                messages.error(request, f'Invalid booking request: {str(e)}')
                return redirect(request.get_full_path())
            except Exception as e:
                messages.error(request, f'An error occurred during booking: {str(e)}')
                return redirect(request.get_full_path())
        
        # Handle GET request for dashboard
        # Get filter parameters
        hotel_filter = request.GET.get('hotel_filter', 'all')
        status_filter = request.GET.get('status_filter', 'all')
        date_filter = request.GET.get('date_filter')
        
        # Parse date filter or use today
        try:
            selected_date = datetime.strptime(date_filter, '%Y-%m-%d').date() if date_filter else datetime.now().date()
        except ValueError:
            selected_date = datetime.now().date()
        
        # Fetch all rooms (maintainer has access to all)
        rooms = Rooms.objects.all().select_related('hotel')
        
        # Apply hotel filter
        if hotel_filter != 'all':
            rooms = rooms.filter(hotel__name=hotel_filter)
        
        # Process rooms with pricing information
        current_date = datetime.now().date()
        tomorrow_date = current_date + timedelta(days=1)
        processed_rooms = []
        for room in rooms:
            # Fetch reservations individually
            room.current_booking = Reservation.objects.filter(
                room=room,
                check_in__lte=selected_date,
                check_out__gt=selected_date
            ).select_related('guest').first()
            
            # Determine display status
            if room.status == '2':
                room.display_status = '2'  # Unavailable
            elif room.current_booking:
                room.display_status = '3'  # Booked
            else:
                room.display_status = '1'  # Available
            
            # Calculate and attach pricing information
            room.discounted_price_value = room.discounted_price()
            room.saved_amount = room.saved_money()
            room.gst_rate = room.hotel.gst_rate if room.hotel.gst_rate else Decimal('12.00')
            
            room.is_past_date = selected_date < current_date
            processed_rooms.append(room)
        
        # Apply status filter
        if status_filter == 'available':
            processed_rooms = [room for room in processed_rooms if room.display_status == '1']
        elif status_filter == 'booked':
            processed_rooms = [room for room in processed_rooms if room.display_status == '3']
        elif status_filter == 'unavailable':
            processed_rooms = [room for room in processed_rooms if room.display_status == '2']
        
        # Calculate summary statistics
        total_rooms = len(processed_rooms)
        available_rooms = len([room for room in processed_rooms if room.display_status == '1'])
        booked_rooms = len([room for room in processed_rooms if room.display_status == '3'])
        unavailable_rooms = len([room for room in processed_rooms if room.display_status == '2'])
        
        context = {
            'hotels': all_hotels,
            'rooms': processed_rooms,
            'selected_hotel': hotel_filter,
            'selected_status': status_filter,
            'selected_date': selected_date,
            'current_date': current_date,
            'tomorrow_date': tomorrow_date,
            'total_rooms': total_rooms,
            'available_rooms': available_rooms,
            'booked_rooms': booked_rooms,
            'unavailable_rooms': unavailable_rooms,
        }

        return render(request, 'maintainer/rooms_status.html', context)
        
    except Exception as e:
        return render(request, 'maintainer/rooms_status.html', {
            'error_title': 'An Error Occurred',
            'error_message': f'An unexpected error occurred: {str(e)}',
            'current_date': datetime.now().date(),
            'tomorrow_date': (datetime.now().date() + timedelta(days=1))
        }, status=500)

@login_required
@require_POST
def maintainer_update_room_status(request, room_id):
    """
    AJAX view for maintainers to update room status (Available/Unavailable).
    """
    try:
        if not hasattr(request.user, 'maintainer_profile'):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        room = Rooms.objects.get(id=room_id)
        new_status = request.POST.get('status')
        if new_status not in ('1', '2'):
            return JsonResponse({'error': 'Invalid status'}, status=400)
        
        # Check for bookings if marking unavailable
        if new_status == '2':
            selected_date = request.POST.get('selected_date', datetime.now().date())
            try:
                selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date() if isinstance(selected_date, str) else selected_date
            except ValueError:
                selected_date = datetime.now().date()
            
            booking = Reservation.objects.filter(
                room=room,
                check_in__lte=selected_date,
                check_out__gt=selected_date
            ).exists()
            if booking:
                return JsonResponse({'error': 'Cannot mark a booked room as unavailable'}, status=400)
        
        room.status = new_status
        room.save()
        return JsonResponse({
            'success': True,
            'new_status': 'Available' if new_status == '1' else 'Unavailable'
        })
            
    except Rooms.DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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




logger = logging.getLogger(__name__)

@login_required(login_url='user:signin')
def hotel_staff_bookings(request):
    if not hasattr(request.user, 'hotel_staff_profile'):
        messages.warning(request, "You don't have permissions to access the staff panel.")
        return redirect('/')

    try:
        staff = HotelStaff.objects.get(user=request.user)
    except HotelStaff.DoesNotExist:
        messages.warning(request, "Staff profile not found.")
        return redirect('/')

    current_date = datetime.now().date()
    current_month = current_date.month
    current_year = current_date.year
    
    # Initialize accessible hotels
    all_accessible_hotels = Hotels.objects.none()
    
    if staff.hotel:
        owner_hotels = Hotels.objects.filter(owner=staff.hotel.owner)
        all_accessible_hotels = owner_hotels
    
    if hasattr(staff, 'assigned_hotels'):
        assigned_hotels = staff.assigned_hotels.all()
        all_accessible_hotels = (all_accessible_hotels | assigned_hotels).distinct()
    
    if not all_accessible_hotels.exists():
        messages.warning(request, "No hotels assigned to your staff account.")
        return redirect('/')
    
    all_bookings = Reservation.objects.filter(
        room__hotel__in=all_accessible_hotels
    ).select_related('guest', 'room', 'room__hotel').order_by('-booking_time')
    
    # Calculate booking statistics
    total_bookings = all_bookings.count()
    bookings_today = all_bookings.filter(booking_time__date=current_date).count()
    bookings_this_month = all_bookings.filter(
        booking_time__month=current_month, booking_time__year=current_year
    ).count()
    active_bookings = all_bookings.filter(
        check_in__lte=current_date, check_out__gte=current_date, is_cancelled=False
    ).count()
    check_ins_today = all_bookings.filter(check_in=current_date, is_cancelled=False).count()
    check_outs_today = all_bookings.filter(check_out=current_date, is_cancelled=False).count()
    check_ins_this_month = all_bookings.filter(
        check_in__month=current_month, check_in__year=current_year, is_cancelled=False
    ).count()
    check_outs_this_month = all_bookings.filter(
        check_out__month=current_month, check_out__year=current_year, is_cancelled=False
    ).count()
    cancelled_bookings = all_bookings.filter(is_cancelled=True).count()
    
    total_revenue = sum(reservation.total_price for reservation in all_bookings if not reservation.is_cancelled)
    today_revenue = sum(
        reservation.total_price 
        for reservation in all_bookings 
        if reservation.booking_time.date() == current_date and not reservation.is_cancelled
    )
    this_month_revenue = sum(
        reservation.total_price 
        for reservation in all_bookings 
        if reservation.booking_time.month == current_month and 
           reservation.booking_time.year == current_year and 
           not reservation.is_cancelled
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
    
    if hotel_filter:
        try:
            bookings = bookings.filter(room__hotel__id=int(hotel_filter))
        except (ValueError, TypeError):
            messages.warning(request, "Invalid hotel filter selected.")
    
    if booking_status:
        if booking_status == 'past':
            bookings = bookings.filter(check_out__lt=current_date, is_cancelled=False)
        elif booking_status == 'current':
            bookings = bookings.filter(check_in__lte=current_date, check_out__gte=current_date, is_cancelled=False)
        elif booking_status == 'future':
            bookings = bookings.filter(check_in__gt=current_date, is_cancelled=False)
        elif booking_status == 'cancelled':
            bookings = bookings.filter(is_cancelled=True)
    
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
                bookings = bookings.filter(check_in__lte=day_date, check_out__gte=day_date, is_cancelled=False)
                filter_type = 'active'
            except ValueError:
                messages.warning(request, "Invalid day format.")
        else:
            bookings = bookings.filter(check_in__lte=current_date, check_out__gte=current_date, is_cancelled=False)
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
            Q(guest__username__icontains=search_name)
        )

    # Assign status and calculate guest details for each booking
    for booking in bookings:
        if booking.is_cancelled:
            booking.status = 'cancelled'
        elif booking.check_out < current_date:
            booking.status = 'past'
        elif booking.check_in <= current_date <= booking.check_out:
            booking.status = 'current'
        else:
            booking.status = 'future'
        # Calculate guest details
        booking.total_guests = booking.number_of_guests
        booking.extra_persons = max(0, booking.number_of_guests - booking.room.capacity)
        booking.max_capacity = booking.room.capacity + booking.room.extra_capacity

    # Calculate filtered revenue
    filtered_revenue = sum(reservation.total_price for reservation in bookings if not reservation.is_cancelled)
    
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
        'cancelled_bookings': cancelled_bookings,
        'all_accessible_hotels': all_accessible_hotels,
        'total_revenue': float(total_revenue),
        'today_revenue': float(today_revenue),
        'this_month_revenue': float(this_month_revenue),
        'filtered_revenue': float(filtered_revenue),
    }
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        action = request.GET.get('action', 'table')
        if action == 'events':
            events = []
            for booking in bookings:
                room_type_name = booking.room.get_room_type_display()
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
                            'total_guests': booking.number_of_guests,
                            'extra_persons': booking.extra_persons,
                            'max_capacity': booking.max_capacity,
                            'amount': f'₹{booking.total_price:.2f}',
                            'booking_date': booking.booking_time.strftime('%b %d, %Y %I:%M %p'),
                            'cancellation_reason': booking.cancellation_reason or 'N/A',
                        },
                        'className': 'fc-event-booking',
                        'backgroundColor': '#DC3545' if booking.status == 'cancelled' else '#3B82F6',
                        'textColor': 'white'
                    },
                    # Check-in and check-out events remain the same
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
                            'total_guests': booking.number_of_guests,
                            'extra_persons': booking.extra_persons,
                            'max_capacity': booking.max_capacity,
                            'amount': f'₹{booking.total_price:.2f}',
                            'booking_date': booking.booking_time.strftime('%b %d, %Y %I:%M %p'),
                            'cancellation_reason': booking.cancellation_reason or 'N/A',
                        },
                        'className': 'fc-event-check-in',
                        'backgroundColor': '#DC3545' if booking.status == 'cancelled' else '#10B981',
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
                            'total_guests': booking.number_of_guests,
                            'extra_persons': booking.extra_persons,
                            'max_capacity': booking.max_capacity,
                            'amount': f'₹{booking.total_price:.2f}',
                            'booking_date': booking.booking_time.strftime('%b %d, %Y %I:%M %p'),
                            'cancellation_reason': booking.cancellation_reason or 'N/A',
                        },
                        'className': 'fc-event-check-out',
                        'backgroundColor': '#DC3545' if booking.status == 'cancelled' else '#F59E0B',
                        'textColor': 'white'
                    }
                ])
            return JsonResponse({'events': events})
        elif action == 'calendar':
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
    
    # Get all bookings, including cancelled ones
    all_bookings = Reservation.objects.all().select_related(
        'guest', 'room', 'room__hotel'
    ).order_by('-booking_time')
    
    # Calculate total revenue for all non-cancelled bookings
    total_revenue = sum(booking.total_price for booking in all_bookings if not booking.is_cancelled)
    today_revenue = sum(
        booking.total_price 
        for booking in all_bookings 
        if booking.booking_time.date() == current_date and not booking.is_cancelled
    )
    this_month_revenue = sum(
        booking.total_price 
        for booking in all_bookings 
        if booking.booking_time.month == current_month and 
           booking.booking_time.year == current_year and 
           not booking.is_cancelled
    )
    
    # Initialize bookings
    bookings = all_bookings if all_bookings.exists() else Reservation.objects.none()
    
    # Calculate booking statistics for display
    total_bookings = all_bookings.count()
    bookings_today = all_bookings.filter(booking_time__date=current_date).count()
    bookings_this_month = all_bookings.filter(booking_time__month=current_month, booking_time__year=current_year).count()
    active_bookings = all_bookings.filter(check_in__lte=current_date, check_out__gte=current_date, is_cancelled=False).count()
    check_ins_today = all_bookings.filter(check_in=current_date, is_cancelled=False).count()
    check_outs_today = all_bookings.filter(check_out=current_date, is_cancelled=False).count()
    check_ins_this_month = all_bookings.filter(check_in__month=current_month, check_in__year=current_year, is_cancelled=False).count()
    check_outs_this_month = all_bookings.filter(check_out__month=current_month, check_out__year=current_year, is_cancelled=False).count()
    cancelled_bookings = all_bookings.filter(is_cancelled=True).count()
    
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
            bookings = bookings.filter(check_out__lt=current_date, is_cancelled=False)
        elif booking_status == 'current':
            bookings = bookings.filter(check_in__lte=current_date, check_out__gte=current_date, is_cancelled=False)
        elif booking_status == 'future':
            bookings = bookings.filter(check_in__gt=current_date, is_cancelled=False)
        elif booking_status == 'cancelled':
            bookings = bookings.filter(is_cancelled=True)
    
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
                bookings = bookings.filter(check_in__lte=day_date, check_out__gte=day_date, is_cancelled=False)
                filter_type = 'active'
            except ValueError:
                messages.warning(request, "Invalid day format.")
        else:
            bookings = bookings.filter(check_in__lte=current_date, check_out__gte=current_date, is_cancelled=False)
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

    # Calculate filtered revenue (exclude cancelled bookings)
    filtered_revenue = sum(booking.total_price for booking in bookings if not booking.is_cancelled)
    
    # Assign status to bookings
    for booking in bookings:
        if booking.is_cancelled:
            booking.status = 'cancelled'
        elif booking.check_out < current_date:
            booking.status = 'past'
        elif booking.check_in <= current_date <= booking.check_out:
            booking.status = 'current'
        else:
            booking.status = 'future'

        # Calculate extra person charges
        extra_persons = max(0, booking.number_of_guests - booking.room.capacity)
        booking.extra_persons = extra_persons
        booking.extra_charges = extra_persons * booking.room.extra_person_charges * booking.nights
        booking.total_price_with_extras = booking.total_price

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
        'cancelled_bookings': cancelled_bookings,
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
            # In the view where you process bookings
            for booking in bookings:
                # Calculate extra person charges
                room_capacity = booking.room.capacity
                extra_persons = max(0, booking.number_of_guests - booking.room.capacity)
                booking.extra_persons = extra_persons
                booking.extra_charges = extra_persons * booking.room.extra_person_charges * booking.nights
                booking.total_price_with_extras = booking.total_price + booking.extra_charges
                
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
                            'base_price': f'₹{(booking.total_price - booking.gst_amount):.2f}',
                            'gst_amount': f'₹{booking.gst_amount:.2f}',
                            'extra_charges': f'₹{extra_charges:.2f}',
                            'extra_persons': extra_persons,
                            'booking_date': booking.booking_time.strftime('%b %d, %Y %I:%M %p'),
                            'cancellation_reason': booking.cancellation_reason or 'N/A',
                        },
                        'className': 'fc-event-booking',
                        'backgroundColor': '#DC3545' if booking.status == 'cancelled' else '#3B82F6',
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
                            'base_price': f'₹{(booking.total_price - booking.gst_amount):.2f}',
                            'gst_amount': f'₹{booking.gst_amount:.2f}',
                            'extra_charges': f'₹{extra_charges:.2f}',
                            'extra_persons': extra_persons,
                            'booking_date': booking.booking_time.strftime('%b %d, %Y %I:%M %p'),
                            'cancellation_reason': booking.cancellation_reason or 'N/A',
                        },
                        'className': 'fc-event-check-in',
                        'backgroundColor': '#DC3545' if booking.status == 'cancelled' else '#10B981',
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
                            'base_price': f'₹{(booking.total_price - booking.gst_amount):.2f}',
                            'gst_amount': f'₹{booking.gst_amount:.2f}',
                            'extra_charges': f'₹{extra_charges:.2f}',
                            'extra_persons': extra_persons,
                            'booking_date': booking.booking_time.strftime('%b %d, %Y %I:%M %p'),
                            'cancellation_reason': booking.cancellation_reason or 'N/A',
                        },
                        'className': 'fc-event-check-out',
                        'backgroundColor': '#DC3545' if booking.status == 'cancelled' else '#F59E0B',
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



from decimal import Decimal


from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from decimal import Decimal
from datetime import datetime
import logging
from .models import Rooms, Hotels, Reservation

# Set up logging
logger = logging.getLogger(__name__)

def book_room_page(request):
    try:
        room_id = request.GET.get('roomid')
        if not room_id:
            raise ValueError("Room ID is required")
            
        room = Rooms.objects.get(id=int(room_id))
        
        # Get the hotel associated with the room to access its GST rate
        try:
            hotel = room.hotel
            gst_percentage = Decimal(hotel.gst_rate) if hotel.gst_rate else Decimal('0.0')
        except Exception as e:
            gst_percentage = Decimal('0.0')  # Default to 0% if hotel or GST rate not available
        
        # Check if the current user is the hotel owner
        is_owner_booking = False
        if request.user.is_authenticated:
            is_owner_booking = (request.user.username == hotel.owner)
            # Check if all required profile fields are filled
            required_fields_filled = all([
                request.user.name,
                request.user.phone,
                request.user.email,
                request.user.aadhar_image,
                request.user.profile_image,
                request.user.pancard_image
            ])
            if not required_fields_filled and not request.user.is_staff and not request.is_maintainer:
                # Store the current URL in the session and redirect to profile edit
                request.session['next'] = request.get_full_path()
                messages.info(request, "Your profile needs a few more details. Complete it now to get started")
        else:
            # Store the current URL in the session for redirection after login
            request.session['next'] = request.get_full_path()

        # Retrieve form data from session
        check_in_str = request.session.get('check_in', '')
        check_out_str = request.session.get('check_out', '')
        capacity = int(request.session.get('capacity', room.capacity))

        # Initialize price variables with Decimal
        stay_days = 0
        base_price = Decimal('0.0')
        extra_person_charges = Decimal('0.0')
        gst_amount = Decimal('0.0')
        total_price = Decimal('0.0')
        
        # Get room price as Decimal
        if hasattr(room, 'discounted_price'):
            if callable(room.discounted_price):
                room_price_per_night = Decimal(str(room.discounted_price()))
            else:
                room_price_per_night = Decimal(str(room.discounted_price))
        else:
            room_price_per_night = Decimal('0.0')

        if check_in_str and check_out_str:
            try:
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
                
                # Calculate stay duration (minimum 1 day)
                stay_days = max((check_out - check_in).days, 1)
                
                # Calculate base price
                base_price = room_price_per_night * Decimal(str(stay_days))
                
                # Calculate extra person charges if applicable
                extra_persons = max(0, capacity - room.capacity)
                if extra_persons > 0 and room.extra_capacity > 0:
                    extra_persons = min(extra_persons, room.extra_capacity)
                    extra_person_charges = Decimal(str(room.extra_person_charges)) * Decimal(str(extra_persons)) * Decimal(str(stay_days))
                
                # Calculate GST and total price
                taxable_amount = base_price + extra_person_charges
                gst_amount = (taxable_amount * gst_percentage) / Decimal('100') if gst_percentage > Decimal('0.0') else Decimal('0.0')
                total_price = taxable_amount + gst_amount
                
            except (ValueError, TypeError) as e:
                messages.error(request, f"Invalid date format: {str(e)}")
                return redirect('homepage')

        # Get reservations
        reservations = Reservation.objects.filter(room=room).order_by('-booking_time')
        current_date = datetime.now().date()

        # Prepare context with Decimal values converted to float for template
        context = {
            'room': room,
            'hotel': hotel,
            'check_in': check_in_str,
            'check_out': check_out_str,
            'capacity': capacity,
            'reservations': reservations,
            'current_date': current_date,
            'stay_days': stay_days,
            'base_price': float(base_price),
            'extra_person_charges': float(extra_person_charges),
            'extra_persons': max(0, min(capacity - room.capacity, room.extra_capacity)),
            'gst_percentage': float(gst_percentage),
            'gst_amount': float(gst_amount),
            'total_price': float(total_price),
            'room_price_per_night': float(room_price_per_night),
            'has_gst': gst_percentage > Decimal('0.0'),
            'is_owner_booking': is_owner_booking,
            'max_capacity': room.capacity + room.extra_capacity,
        }
        
        return render(request, 'user/bookroom.html', context)

    except Hotels.DoesNotExist:
        messages.error(request, "Hotel not found.")
        return redirect('homepage')
    except Rooms.DoesNotExist:
        messages.error(request, "Room not found.")
        return redirect('homepage')
    except Exception as e:
        logger.exception(f"Error in book_room_page: {str(e)}")
        messages.error(request, "An error occurred while processing your request.")
        return redirect('homepage')



# Existing user_bookings view
@login_required(login_url='user:signin')
def user_bookings(request):
    if not request.user.is_authenticated:
        return redirect('userloginpage')
    
    user = User.objects.get(id=request.user.id)
    bookings = Reservation.objects.filter(guest=user)

    # Get the current date
    current_date = datetime.now().date()

    if not bookings:
        messages.warning(request, "No Bookings Found")

    return render(request, 'user/mybookings.html', {'bookings': bookings, 'current_date': current_date})

# Existing cancel_booking view
@login_required(login_url='user:signin')
def cancel_booking(request, booking_id):
    if request.method == 'POST':
        try:
            booking = Reservation.objects.get(id=booking_id, guest=request.user)
            if booking.is_cancelled:
                messages.error(request, "This booking is already cancelled.")
            elif booking.check_out < datetime.now().date():
                messages.error(request, "Cannot cancel an expired booking.")
            else:
                cancellation_reason = request.POST.get('cancellation_reason')
                if not cancellation_reason:
                    messages.error(request, "Please provide a reason for cancellation.")
                else:
                    booking.is_cancelled = True
                    booking.cancelled_at = timezone.now()
                    booking.cancellation_reason = cancellation_reason
                    booking.save()
                    messages.success(request, "Booking cancelled successfully.")
                    # Store booking details for rebooking
                    request.session['rebook_data'] = {
                        'room_id': booking.room.id,
                        'check_in': booking.check_in.strftime('%Y-%m-%d'),
                        'check_out': booking.check_out.strftime('%Y-%m-%d'),
                    }
        except Reservation.DoesNotExist:
            messages.error(request, "Booking not found or you don't have permission to cancel it.")
    else:
        messages.error(request, "Invalid request method.")
    
    return redirect('dashboard')
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Reservation, Rooms
from decimal import Decimal
from datetime import datetime

@login_required(login_url='user:signin')
def book_room(request):
    if request.method == 'POST':
        try:
            room_id = request.POST.get('room_id')
            check_in_str = request.session.get('check_in')
            check_out_str = request.session.get('check_out')
            capacity = int(request.session.get('capacity', 1))

            if not all([room_id, check_in_str, check_out_str]):
                messages.error(request, "Missing required booking details.")
                return redirect('homepage')

            room = Rooms.objects.get(id=int(room_id))
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

            # Validate number of guests
            max_capacity = room.capacity + room.extra_capacity
            if capacity > max_capacity:
                messages.error(request, f"Number of guests ({capacity}) exceeds room's maximum capacity ({max_capacity}).")
                return redirect('book_room_page', roomid=room_id)

            # Create reservation
            reservation = Reservation.objects.create(
                room=room,
                guest=request.user,
                check_in=check_in,
                check_out=check_out,
                number_of_guests=capacity,
                booking_id=f"BOOK{room.id}{request.user.id}{int(datetime.now().timestamp())}"
            )

            messages.success(request, "Booking confirmed successfully!")
            return redirect('user_bookings')  # Redirect to a bookings list page

        except Rooms.DoesNotExist:
            messages.error(request, "Room not found.")
            return redirect('homepage')
        except ValueError as e:
            messages.error(request, f"Invalid input: {str(e)}")
            return redirect('homepage')
        except Exception as e:
            logger.exception(f"Error in book_room: {str(e)}")
            messages.error(request, "An error occurred while processing your booking.")
            return redirect('homepage')
    
    return redirect('homepage')#about
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
