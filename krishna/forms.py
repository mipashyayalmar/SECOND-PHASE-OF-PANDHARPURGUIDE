from django import forms
from .models import Rooms

class RoomForm(forms.ModelForm):
    class Meta:
        model = Rooms
        fields = [
            'room_type','parking', 'capacity', 'price', 'size', 'hotel', 'status', 'room_number', 'discount', 
            'description', 'heading', 'food_facility', 'parking', 'extra_person_charges', 
            'comfortable_bed', 'private_bathroom', 'wifi', 'ac', 'fan', 'heater', 'cleanliness', 
            'safety_security', 'entertainment_options', 'laundry_facility', 'outdoor_balcony', 
            'convenient_location', 'concierge_service', 'check_in_time', 
            'check_out_time', 'languages_spoken', 'image1', 'image2', 'image3', 'image4', 'image5', 
            'image6', 'image7', 'image8', 'image9', 'image10', 'image11', 'image12', 'image13', 
            'image14', 'image15',
        ]

    def clean_discount(self):
        discount = self.cleaned_data.get('discount')
        if discount < 0 or discount > 100:
            raise forms.ValidationError("Discount must be between 0 and 100.")
        return discount

    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity < 1:
            raise forms.ValidationError("Capacity must be at least 1.")
        return capacity

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price <= 0:
            raise forms.ValidationError("Price must be greater than 0.")
        return price

    def clean_size(self):
        size = self.cleaned_data.get('size')
        if size <= 0:
            raise forms.ValidationError("Size must be greater than 0.")
        return size

    from datetime import datetime

    def clean_check_in_time(self):
        check_in_time = self.cleaned_data.get('check_in_time')
        if check_in_time:
            # Convert the time to string format (e.g., '12:00 PM')
            check_in_time_str = check_in_time.strftime('%I:%M %p')
            if not (check_in_time_str.endswith('AM') or check_in_time_str.endswith('PM')):
                raise forms.ValidationError("Check-in time must be in the correct format (e.g., '12:00 PM').")
        return check_in_time

    def clean_check_out_time(self):
        check_out_time = self.cleaned_data.get('check_out_time')
        if check_out_time:
            # Convert the time to string format (e.g., '12:00 PM')
            check_out_time_str = check_out_time.strftime('%I:%M %p')
            if not (check_out_time_str.endswith('AM') or check_out_time_str.endswith('PM')):
                raise forms.ValidationError("Check-out time must be in the correct format (e.g., '12:00 PM').")
        return check_out_time


from django import forms
from user.models import HotelStaff

class HotelAssignmentForm(forms.ModelForm):
    class Meta:
        model = HotelStaff
        fields = ['hotel']
        labels = {
            'hotel': 'Assigned Hotel'
        }
        widgets = {
            'hotel': forms.Select(attrs={'class': 'form-control'})
        }