from django.contrib import admin
from django.utils.html import format_html
from .models import Image, Comment, Advertisement

class ImageAdmin(admin.ModelAdmin):
    list_display = ('heading', 'description', 'created_at', 'updated_at')
    search_fields = ('heading', 'description')
    list_filter = ('created_at',)

class CommentAdmin(admin.ModelAdmin):
    list_display = ('name', 'image', 'comment', 'created_at', 'parent')
    search_fields = ('name', 'email', 'comment')
    list_filter = ('created_at',)

class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_google_adsense', 'colored_position', 'colored_status')
    list_filter = ('is_google_adsense', 'position', 'status')
    search_fields = ('title', 'google_adsense_code', 'site_link')

    def colored_position(self, obj):
        # Define color codes for different positions
        position_colors = {
            'upper-menu': '#28a745',  # Green
            'below-menu': '#007bff',  # Blue
            'left-side-of-page': '#ffc107',  # Yellow
            'right-side-of-page': "#e8069c",  # Red
            'below-page': '#6c757d',  # Gray
            'below-footer': '#17a2b8',  # Cyan
        }
        color = position_colors.get(obj.position, '#6c757d')  # Default to gray
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_position_display()  # Use display value for readability
        )
    colored_position.short_description = 'Position'

    def colored_status(self, obj):
        # Display status with green for 'enable' and red for 'disable'
        color = "#28a745" if obj.status == 'enable' else '#dc3545'
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()  # Use display value for readability
        )
    colored_status.short_description = 'Status'

admin.site.register(Image, ImageAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Advertisement, AdvertisementAdmin)