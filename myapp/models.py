from django.db import models
from django.utils import timezone

class Image(models.Model):
    image = models.ImageField(upload_to='images/')
    heading = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.heading

class Comment(models.Model):
    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    website = models.URLField(blank=True, null=True)
    comment = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    def __str__(self):
        return f"Comment by {self.name} on {self.image.heading}"

from django.db import models
from django.core.exceptions import ValidationError

class Advertisement(models.Model):
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='advertisements/', blank=True, null=True)
    video = models.FileField(upload_to='advertisements/videos/', blank=True, null=True, 
                           help_text="Upload video file for video ads")
    order = models.PositiveIntegerField()
    is_google_adsense = models.BooleanField(default=False)
    google_adsense_code = models.TextField(blank=True, null=True, help_text="Paste Google AdSense code here")
    site_link = models.URLField(blank=True, null=True, help_text="Enter website URL for manual ads")
    position = models.CharField(
        max_length=50,
        choices=[
            ('upper-menu', 'Upper menu'),
            ('below-menu', 'Below menu'),
            ('left-side-of-page', 'Left side of the page'),
            ('right-side-of-page', 'Right side of the page'),
            ('below-page', 'Below the page'),
            ('below-footer', 'Below footer'),
            ('full-screen-popup', 'Full Screen Popup'),
        ],
        default='upper-menu'
    )
    status = models.CharField(
        max_length=10,
        choices=[('enable', 'Enable'), ('disable', 'Disable')],
        default='enable'
    )
    display_frequency = models.CharField(
        max_length=20,
        choices=[
            ('show_once', 'Show once per session'),
            ('repeat', 'Repeat after interval'),
        ],
        default='show_once',
        help_text="How often should this ad be displayed?"
    )
    repeat_interval = models.PositiveIntegerField(
        default=20,
        help_text="Time in seconds before the ad repeats (applies only if display_frequency is 'repeat')"
    )
    countdown_mode = models.CharField(
        max_length=20,
        choices=[
            ('off', 'No countdown timer'),
            ('custom', 'Custom countdown timer'),
        ],
        default='off',
        help_text="Should a countdown timer be shown before the ad can be closed?"
    )
    countdown_duration = models.PositiveIntegerField(
        default=10,
        help_text="Countdown duration in seconds (applies only if countdown_mode is 'custom')"
    )

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['order']
        verbose_name = 'Advertisement'
        verbose_name_plural = 'Advertisements'

    def clean(self):
        """Validation to ensure proper field combinations"""
        if self.is_google_adsense and not self.google_adsense_code:
            raise ValidationError("Google AdSense code is required when using AdSense")
        if not self.is_google_adsense and not self.image and not self.site_link and not self.video:
            raise ValidationError("Either an image, video, or site link is required for manual advertisements")
        if self.repeat_interval <= 0 and self.display_frequency == 'repeat':
            raise ValidationError("Repeat interval must be a positive integer when display_frequency is 'repeat'")
        if self.countdown_duration <= 0 and self.countdown_mode == 'custom':
            raise ValidationError("Countdown duration must be a positive integer when countdown_mode is 'custom'")