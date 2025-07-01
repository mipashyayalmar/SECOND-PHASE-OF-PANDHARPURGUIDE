from django.contrib import admin
from django.utils.html import format_html
from .models import Hotels, Rooms, Comments, Replies, Reservation
from user.models import HotelStaff
from django.contrib import messages
from django.db import IntegrityError
from django.shortcuts import redirect

# Existing admin classes (unchanged)
@admin.register(Hotels)
class HotelsAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'location', 'state', 'country')
    search_fields = ('name', 'owner', 'location')
    list_filter = ('state', 'country')
@admin.register(Rooms)
class RoomsAdmin(admin.ModelAdmin):
    list_display = (
        'hotel', 'room_number', 'room_type', 'display_capacity', 'total_capacity', 
        'price', 'status', 'average_rating', 'discounted_price', 'saved_money', 'image_preview'
    )
    list_filter = ('hotel', 'room_type', 'status', 'languages_spoken', 'food_facility', 'parking', 'wifi', 'ac', 'fan', 'heater', 'cleanliness')
    search_fields = ('room_number', 'hotel__name', 'description', 'heading')
    readonly_fields = ('image_preview', 'discounted_price', 'saved_money', 'display_capacity', 'total_capacity')
    fieldsets = (
        ("Basic Information", {
            'fields': (
                'hotel', 'room_number', 'room_type', 
                'capacity', 'extra_capacity', 'display_capacity', 'total_capacity',
                'price', 'discount', 'discounted_price', 'saved_money', 'status'
            )
        }),
        ("Features and Amenities", {
            'fields': (
                'size', 'description', 'heading', 'food_facility', 'parking', 'comfortable_bed',
                'private_bathroom', 'wifi', 'ac', 'fan', 'heater', 'cleanliness', 
                'safety_security', 'entertainment_options', 'laundry_facility', 
                'outdoor_balcony', 'convenient_location', 'concierge_service'
            ),
        }),
        ("Ratings and Reviews", {
            'fields': ('average_rating', 'comments'),
        }),
        ("Images", {
            'fields': (
                'image1', 'image2', 'image3', 'image4', 'image5', 
                'image6', 'image7', 'image8', 'image9', 'image10', 
                'image11', 'image12', 'image13', 'image14', 'image15', 'image_preview'
            ),
        }),
        ("Additional Information", {
            'fields': ('extra_person_charges', 'check_in_time', 'check_out_time', 'languages_spoken'),
        }),
    )

    def image_preview(self, obj):
        if obj.image1:
            return format_html('<img src="{}" style="width: 100px; height: auto;" />'.format(obj.image1.url))
        return "No Image Available"
    image_preview.short_description = "Image Preview"

    def discounted_price(self, obj):
        return f"₹{obj.discounted_price():.2f}"
    discounted_price.short_description = "Discounted Price"

    def saved_money(self, obj):
        return f"₹{obj.saved_money():.2f}"
    saved_money.short_description = "Saved Money"

    def display_capacity(self, obj):
        return obj.display_capacity()
    display_capacity.short_description = "Display Capacity"

    def total_capacity(self, obj):
        return obj.total_capacity()
    total_capacity.short_description = "Total Capacity"

@admin.register(Comments)
class CommentsAdmin(admin.ModelAdmin):
    list_display = ('room', 'user', 'comment_text', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('room__room_number', 'user__username', 'comment_text')

@admin.register(Replies)
class RepliesAdmin(admin.ModelAdmin):
    list_display = ('comment', 'user', 'reply_text', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('comment__comment_text', 'user__username', 'reply_text')
from django.contrib import admin
from .models import Reservation, Rooms, Hotels
from django.core.exceptions import ValidationError
from decimal import Decimal

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        'booking_id', 'guest', 'room', 'hotel_name', 'check_in', 'check_out', 'nights',
        'number_of_guests', 'apply_gst', 'gst_number', 'gst_amount_value', 'total_price',
        'booking_time', 'status'
    )
    list_filter = ('apply_gst', 'is_cancelled', 'check_in', 'check_out', 'room__hotel')
    search_fields = ('booking_id', 'guest__username', 'guest__first_name', 'guest__last_name', 'gst_number')
    readonly_fields = ('booking_time', 'base_price_value', 'gst_amount_value', 'total_price')
    fields = (
        'guest', 'room', 'check_in', 'check_out', 'number_of_guests',
        'apply_gst', 'gst_number', 'is_cancelled', 'cancellation_reason',
        'spy', 'booking_id', 'booking_time', 'base_price_value', 'gst_amount_value'
    )

    def hotel_name(self, obj):
        return obj.room.hotel.name
    hotel_name.short_description = 'Hotel'

    def status(self, obj):
        if obj.is_cancelled:
            return 'Cancelled'
        elif obj.check_out < timezone.now().date():
            return 'Past'
        elif obj.check_in <= timezone.now().date() <= obj.check_out:
            return 'Current'
        else:
            return 'Future'
    status.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        """
        Override save_model to recalculate prices when apply_gst or gst_number is modified.
        """
        try:
            # Validate the object
            obj.clean()

            # Recalculate prices
            obj.base_price_value = obj.base_price
            obj.gst_amount_value = obj.gst_amount
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            form.add_error(None, str(e))
            raise

    def get_readonly_fields(self, request, obj=None):
        # Make price fields readonly to prevent manual edits
        return ('booking_time', 'base_price_value', 'gst_amount_value', 'total_price')

