from django import forms
from .models import Rooms, Hotels, Reservation
from user.models import HotelStaff


class RoomForm(forms.ModelForm):
    class Meta:
        model = Rooms
        fields = [
            'hotel', 'room_type', 'room_number', 'capacity', 'extra_capacity', 'price', 'discount',
            'size', 'status', 'description', 'heading', 'extra_person_charges',
            'food_facility', 'parking', 'comfortable_bed', 'private_bathroom', 'wifi', 'ac', 'fan',
            'heater', 'cleanliness', 'safety_security', 'entertainment_options', 'laundry_facility',
            'outdoor_balcony', 'convenient_location', 'concierge_service', 'check_in_time',
            'check_out_time', 'languages_spoken', 'image1', 'image2', 'image3', 'image4', 'image5',
            'image6', 'image7', 'image8', 'image9', 'image10', 'image11', 'image12', 'image13',
            'image14', 'image15',
        ]
        widgets = {
            'check_in_time': forms.TimeInput(attrs={'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'hotel': forms.Select(attrs={'class': 'form-control'}),
            'room_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'languages_spoken': forms.Select(attrs={'class': 'form-control'}),
        }

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

    def clean_extra_capacity(self):
        extra_capacity = self.cleaned_data.get('extra_capacity')
        if extra_capacity < 0:
            raise forms.ValidationError("Extra capacity cannot be negative.")
        return extra_capacity

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

    def clean_extra_person_charges(self):
        extra_person_charges = self.cleaned_data.get('extra_person_charges')
        if extra_person_charges < 0:
            raise forms.ValidationError("Extra person charges cannot be negative.")
        return extra_person_charges

    def clean(self):
        cleaned_data = super().clean()
        extra_capacity = cleaned_data.get('extra_capacity')
        extra_person_charges = cleaned_data.get('extra_person_charges')
        check_in_time = cleaned_data.get('check_in_time')
        check_out_time = cleaned_data.get('check_out_time')

        if extra_capacity == 0 and extra_person_charges > 0:
            self.add_error('extra_person_charges', "Extra person charges should be 0 if extra capacity is 0.")
        if check_in_time and check_out_time and check_in_time >= check_out_time:
            self.add_error('check_out_time', "Check-out time must be after check-in time.")

        return cleaned_data


class HotelAssignmentForm(forms.Form):
    staff = forms.ModelChoiceField(queryset=HotelStaff.objects.all(), label='Hotel Staff', widget=forms.Select(attrs={'class': 'form-control'}))
    hotel = forms.ModelChoiceField(queryset=Hotels.objects.all(), label='Assigned Hotel', widget=forms.Select(attrs={'class': 'form-control'}))

    def save(self):
        staff = self.cleaned_data['staff']
        hotel = self.cleaned_data['hotel']
        hotel.assigned_staff.add(staff)
        return hotel
from django import forms
from .models import Reservation

class ReservationForm(forms.ModelForm):
    apply_gst = forms.BooleanField(required=False, label="Apply GST")
    gst_number = forms.CharField(max_length=15, required=False, label="GST Number")
    is_direct_booking = forms.BooleanField(required=False, label="Direct Booking")

    class Meta:
        model = Reservation
        fields = ['room', 'check_in', 'check_out', 'number_of_guests', 'apply_gst', 'gst_number', 'is_direct_booking']
        widgets = {
            'check_in': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'check_out': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'room': forms.HiddenInput(),
            'apply_gst': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '15'}),
            'is_direct_booking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get('room')
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')
        number_of_guests = cleaned_data.get('number_of_guests')
        apply_gst = cleaned_data.get('apply_gst')
        gst_number = cleaned_data.get('gst_number')

        if room and check_in and check_out:
            if Reservation.objects.filter(
                room=room,
                check_in__lt=check_out,
                check_out__gt=check_in,
                is_cancelled=False
            ).exists():
                self.add_error(None, "Room is not available for the selected dates.")

        if apply_gst and not gst_number:
            self.add_error('gst_number', "GST number is required if GST is applied.")
        if gst_number and not apply_gst:
            self.add_error('gst_number', "GST number should not be provided if GST is not applied.")

        if number_of_guests and room:
            max_capacity = room.capacity + room.extra_capacity
            if number_of_guests > max_capacity:
                self.add_error('number_of_guests', f"Number of guests ({number_of_guests}) exceeds room's maximum capacity ({max_capacity}).")

        return cleaned_data