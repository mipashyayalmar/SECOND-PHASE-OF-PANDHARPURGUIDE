from django import forms
from .models import Image, Advertisement

# Form for uploading images
class ImageForm(forms.ModelForm):
    class Meta:
        model = Image
        fields = ['image', 'heading', 'description']
        widgets = {
            'heading': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter heading'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter description'}),
        }


# Form for creating or editing advertisements
class AdvertisementForm(forms.ModelForm):
    class Meta:
        model = Advertisement
        fields = ['title', 'image', 'order', 'is_google_adsense', 'position', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter title'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Order'}),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
