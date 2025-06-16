from django.db import models
from django.conf import settings  # ✅ Use this instead
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

from django.db import models



class Hotels(models.Model):
    HOTEL_TYPE_CHOICES = [
    ('hotel_restaurant', 'Hotel/Restaurant'),
    ('dormitory', 'Dormitory'),
    ('math_dharmashala', 'Math/Dharmashala'),
    ('other', 'Other'),
        ]

    name = models.CharField(max_length=130, default="tiranga", blank=False, null=False)
    owner = models.CharField(max_length=20, blank=False, null=False)
    location = models.CharField(max_length=50, blank=False, null=False)
    state = models.CharField(max_length=50, default="maharashtra", blank=False, null=False)
    country = models.CharField(max_length=50, default="india", blank=False, null=False)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12.00, help_text="GST rate in percentage (e.g., 12 for 12%)")
    
    hotel_type = models.CharField(
        max_length=20,
        choices=HOTEL_TYPE_CHOICES,
        default='hotel / restaurant',
        blank=False,
        null=False,
        help_text="Type of the hotel or accommodation"
    )
    other_heading = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Custom heading if hotel type is 'Other'"
    )

    assigned_staff = models.ManyToManyField(
        'user.HotelStaff', 
        related_name='assigned_hotels',
        blank=True
    )
    created_by = models.ForeignKey(
        'user.HotelStaff',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='created_hotels'
    )

    # New fields
    description_map = models.TextField(null=True, blank=True, help_text="Detailed description of the room")
    heading_map = models.CharField(max_length=100, null=True, blank=True, help_text="Short heading for the room")
    embedded_map_link = models.TextField(
        null=True,
        blank=True,
        help_text="Embed map link (iframe URL). Will be shown in fixed size on frontend."
    )

    # Image fields for 6 hotel images
    image_1 = models.ImageField(upload_to='hotel_images/', null=True, blank=True, help_text="First hotel image")
    image_2 = models.ImageField(upload_to='hotel_images/', null=True, blank=True, help_text="Second hotel image")
    image_3 = models.ImageField(upload_to='hotel_images/', null=True, blank=True, help_text="Third hotel image")
    image_4 = models.ImageField(upload_to='hotel_images/', null=True, blank=True, help_text="Fourth hotel image")
    image_5 = models.ImageField(upload_to='hotel_images/', null=True, blank=True, help_text="Fifth hotel image")
    image_6 = models.ImageField(upload_to='hotel_images/', null=True, blank=True, help_text="Sixth hotel image")

    rank = models.PositiveIntegerField(
        default=0,
        help_text="Higher rank means higher priority in listings"
    )

    def __str__(self):
        return f"{self.name} ({self.location})"
    

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'owner', 'state', 'country', 'location'], 
                name='unique_hotel_constraint'
            )
        ]
        ordering = ['-rank', 'name']  



class Rooms(models.Model):
    ROOM_STATUS = (
        ("1", "available"),
        ("2", "not available"),
    )

    ROOM_TYPE = (
        ("1", "premium"),
        ("2", "deluxe"),
        ("3", "basic"),
    )
    capacity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Base capacity of the room"
    )
    extra_capacity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Extra capacity beyond base (e.g., with extra beds)"
    )
    hotel = models.ForeignKey(Hotels, on_delete=models.CASCADE, related_name='rooms')
    room_type = models.CharField(max_length=50, choices=ROOM_TYPE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    size = models.IntegerField(help_text="Room size in square feet")
    hotel = models.ForeignKey('Hotels', on_delete=models.CASCADE, related_name='rooms')
    status = models.CharField(
        max_length=1,  # Fixed length to match choices
        choices=ROOM_STATUS,
        default="1"
    )
    room_number = models.CharField(max_length=10, null=True)

    discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)]
    )

    # Ratings and reviews
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
        help_text="Average rating (0-5)"
    )

    # Comments and replies
    comments = models.ManyToManyField('Comments', blank=True, related_name='rooms')

    # Room images (up to 12)
    image1 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image2 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image3 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image4 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image5 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image6 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image7 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image8 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image9 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image10 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image11 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image12 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image13 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image14 = models.ImageField(upload_to='room_images/', null=True, blank=True)
    image15 = models.ImageField(upload_to='room_images/', null=True, blank=True)

    # Additional fields
    description = models.TextField(null=True, blank=True, help_text="Detailed description of the room")
    heading = models.CharField(max_length=100, null=True, blank=True, help_text="Short heading for the room")
    extra_person_charges = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        default=0.0, 
        validators=[MinValueValidator(0.0)], 
        help_text="Charges for extra person"
    )

    # Amenities
    food_facility = models.BooleanField(default=False, help_text="Indicates if food facility is available")
    parking = models.BooleanField(default=False, help_text="Indicates if parking is available")
    comfortable_bed = models.BooleanField(default=False, help_text="Indicates if the room has a comfortable bed")
    private_bathroom = models.BooleanField(default=False, help_text="Indicates if the room has a private bathroom")
    wifi = models.BooleanField(default=False, help_text="Indicates if Wi-Fi is available")
    ac = models.BooleanField(default=False, help_text="Indicates if air conditioning is available")
    fan = models.BooleanField(default=False, help_text="Indicates if a fan is available")
    heater = models.BooleanField(default=False, help_text="Indicates if a heater is available")
    cleanliness = models.BooleanField(default=False, help_text="Indicates regular cleanliness")
    safety_security = models.BooleanField(default=False, help_text="Indicates if safety and security features are present")
    entertainment_options = models.BooleanField(default=False, help_text="Indicates if entertainment options are available")
    laundry_facility = models.BooleanField(default=False, help_text="Indicates if laundry facilities are available")
    outdoor_balcony = models.BooleanField(default=False, help_text="Indicates if an outdoor balcony is available")
    food_facility = models.BooleanField(default=False, help_text="Indicates if a food facility is available")
    convenient_location = models.BooleanField(default=False, help_text="Indicates if the location is convenient")
    concierge_service = models.BooleanField(default=False, help_text="Indicates if concierge service is available")

    # Check-in and check-out times
    check_in_time = models.TimeField(null=True, blank=True, help_text="Check-in time (HH:MM AM/PM)")
    check_out_time = models.TimeField(null=True, blank=True, help_text="Check-out time (HH:MM AM/PM)")

    # Languages spoken by staff
    LANGUAGES_SPOKEN = (
        ("english", "English"),
        ("marathi", "Marathi"),
        ("hindi", "Hindi"),
    )
    languages_spoken = models.CharField(
        max_length=50, 
        choices=LANGUAGES_SPOKEN, 
        default="marathi",
        help_text="Languages spoken by staff"
    )

    # In your Rooms model
    def display_capacity(self):
        """Display capacity as '3+2' if extra capacity exists, or just '3' if no extra"""
        if self.extra_capacity > 0:
            return f"{self.capacity}+{self.extra_capacity}"
        return str(self.capacity)

    def total_capacity(self):
        """Calculate total capacity (base + extra)"""
        return self.capacity + self.extra_capacity

    def get_extra_person_info(self):
        """Return formatted string about extra person charges if applicable"""
        if self.extra_capacity > 0 and self.extra_person_charges > 0:
            return f"Extra person charge: ${self.extra_person_charges} per person (max {self.extra_capacity})"
        return ""
    
    # In your Reservation model
    @property
    def extra_persons(self):
        return max(0, self.number_of_guests - self.room.capacity)

    def discounted_price(self):
        """Calculate price after applying the discount."""
        if self.discount > 0:
            return self.price - (self.price * (self.discount / Decimal(100)))
        return self.price

    def saved_money(self):
        """Calculate the saved amount due to the discount."""
        if self.discount > 0:
            return self.price * (self.discount / Decimal(100))
        return Decimal(0)

    def total_money(self):
        discounted_total = self.discounted_price()
        return discounted_total + (self.extra_person_charges or Decimal('0'))

    def __str__(self):
        return f"{self.hotel.name} - Room {self.room_number} ({self.get_room_type_display()})"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['hotel', 'room_type', 'room_number'], name='unique_hotel_room_type_number')
        ]


class Comments(models.Model):
    room = models.ForeignKey(Rooms, on_delete=models.CASCADE, related_name='room_comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Assuming default User model
    comment_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.room}"

class Replies(models.Model):
    comment = models.ForeignKey(Comments, on_delete=models.CASCADE, related_name='replies')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Assuming default User model
    reply_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reply by {self.user.username} on {self.comment}"




class Reservation(models.Model):
    check_in = models.DateField()
    check_out = models.DateField()
    room = models.ForeignKey(Rooms, on_delete=models.CASCADE, related_name='reservations')
    guest = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    booking_id = models.CharField(max_length=100, default="null")
    booking_time = models.DateTimeField(default=timezone.now)
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    spy = models.CharField(max_length=100, null=True, blank=True)
    number_of_guests = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)  # Added
    base_price_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Renamed field
    gst_amount_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Renamed field

    @property
    def nights(self):
        """Calculate the number of nights for the stay."""
        return max((self.check_out - self.check_in).days, 1)

    @property
    def base_price(self):
        """Calculate base price for the stay, including extra person charges."""
        return (self.room.discounted_price() * self.nights) + (self.room.extra_person_charges or Decimal('0')) * (self.number_of_guests - 1)

    @property
    def gst_rate(self):
        """Get the GST rate from the hotel, defaulting to 12%."""
        return self.room.hotel.gst_rate or Decimal('12.00')

    @property
    def gst_amount(self):
        """Calculate GST amount based on hotel's GST rate."""
        return (self.base_price * self.gst_rate) / Decimal('100')

    @property
    def total_price(self):
        """Calculate total price including GST."""
        return self.base_price + self.gst_amount

    def save(self, *args, **kwargs):
        """Override save to compute and store base_price_value and gst_amount_value."""
        self.base_price_value = self.base_price
        self.gst_amount_value = self.gst_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Reservation for {self.room} by {self.guest.username} ({self.check_in} to {self.check_out})"