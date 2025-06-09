from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import redirect, render
from django.utils.html import format_html
from django.contrib import messages
from django.db import IntegrityError
from .models import User, HotelStaff, Maintainer
from krishna.models import Hotels
from django.urls import path, reverse

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (                   
        'username_link',  
        'is_staff',   
        'is_employee',          
        'colored_permission_status',  
        'paid_member',    
        'is_verified_link',  
        'name',
        'phone',
        'email',
        'profile_image_preview',
        'aadhar_image_preview',
        'pancard_image_preview'
    )
    list_editable = ('name', 'phone', 'email', 'paid_member')
    list_filter = ('is_verified', 'is_staff','is_employee', 'paid_member')
    search_fields = ('username', 'email', 'name', 'phone')
    
    # Fieldsets for add and change views
    fieldsets = (
        (None, {'fields': ('username', 'password', 'name', 'phone', 'email')}),
        ('Personal Documents', {'fields': ('profile_image', 'aadhar_image', 'pancard_image')}),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_employee',
                'is_superuser',
                'is_admin',
                'is_maintainer',
                'is_verified',
                'is_authority_to_manage_hotel',
                'groups',
                'user_permissions'
            )
        }),
        ('Membership', {'fields': ('paid_member',)}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'name',
                'phone',
                'email',
                'password1',
                'password2',
                'is_staff',
                'is_verified',
                'is_authority_to_manage_hotel',
                'paid_member',
                'profile_image',
                'aadhar_image',
                'pancard_image'
            ),
        }),
    )
    
    # Actions
    actions = ['verify_users', 'unverify_users']
    
    class Media:
        css = {
            'all': ('css/admin_user_colors.css',)
        }
    
    # Custom methods for list display
    def username_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:user_user_change', args=[obj.pk]),
            obj.username
        )
    username_link.short_description = 'Username'
    username_link.admin_order_field = 'username' 
    
    
    def colored_permission_status(self, obj):
        # Admin (superuser, staff, active, verified, authority to manage hotel, admin)
        if obj.is_active and obj.is_staff and obj.is_superuser and obj.is_admin and obj.is_maintainer and obj.is_verified and obj.is_authority_to_manage_hotel :
            return format_html(
                '<span style="color: rgb(118, 196, 0); font-weight: bold;">ADMIN</span>'
            )
        
        elif obj.is_active and obj.is_staff and obj.is_superuser and obj.is_admin and obj.is_verified and obj.is_authority_to_manage_hotel :
            return format_html(
                '<span style="color: #FF0000; font-weight: bold;">Admin</span>'
            )
        
        elif obj.is_active and obj.is_staff and obj.is_employee and obj.is_verified  :
            return format_html(
                '<span style="color: #01EC67; font-weight: bold;">hotel employee</span>'
            )
        
        elif obj.is_active and obj.is_staff  and obj.is_admin and obj.is_verified and obj.is_authority_to_manage_hotel :
            return format_html(
                '<span style="color: #FF0000; font-weight: bold;">Admin</span>'
            )
        
        elif obj.is_active and obj.is_staff and obj.is_superuser and obj.is_admin and  not obj.is_verified  :
            return format_html(
                '<span style="color: black; font-weight: bold;">Admin</span>'
            )
        
        # Sup-maintainer (superuser, staff, active, verified, authority to manage hotel)
        elif obj.is_active and obj.is_staff and obj.is_superuser and obj.is_maintainer and obj.is_verified and obj.is_authority_to_manage_hotel:
            return format_html(
                '<span style="color: #FF0000; font-weight: bold;">Sup-Maintainer</span>'
            )
        
        # Maintainer (staff, active, maintainer, not authority to manage hotel, not verified)
        elif not obj.is_authority_to_manage_hotel and obj.is_maintainer and obj.is_active and obj.is_verified and obj.is_staff:
            return format_html(
                '<span style="color: #1BB537; font-weight: bold;">Maintainer (No Hotel Authority)</span>'
            )
        
        elif not obj.is_authority_to_manage_hotel and obj.is_maintainer and obj.is_active and not obj.is_verified and obj.is_staff:
            return format_html(
                '<span style="color: #1BB537; font-weight: bold;">Unverify-Maintainer (No Hotel Authority)</span>'
            )
        
        elif obj.is_authority_to_manage_hotel and obj.is_maintainer and obj.is_active and not obj.is_verified and obj.is_staff:
            return format_html(
                '<span style="color: black; font-weight: bold;">Unverify-Maintainer (No Hotel Authority)</span>'
            )
       

        elif hasattr(obj, 'maintainer_profile') and obj.is_maintainer:
            return format_html(
                '<span style="color: #FFA500; font-weight: bold;">Maintainer</span>'
            )
        
        elif obj.is_staff and obj.is_active and not obj.is_maintainer and not obj.is_verified:
            return format_html(
                '<span style="color: black; font-weight: bold;">Unverifide Staff</span>'
            )
        
        elif obj.is_staff and not obj.is_active:
            return format_html(
                '<span style="color: #000000; font-weight: bold;">Inactive Staff</span>'
            )

        # Staff (staff, active, not maintainer)
        elif obj.is_staff and obj.is_active and not obj.is_maintainer and obj.is_verified:
            return format_html(
                '<span style="color: #0066CC; font-weight: bold;">Staff</span>'
            )
        
       
        # Inactive admin/superuser
        elif obj.is_superuser and obj.is_admin and not obj.is_active:
            return format_html(
                '<span style="color: #000000; font-weight: bold;">Inactive Admin</span>'
            )
        
        # Inactive staff
        
        
        # Inactive verified user
        elif obj.is_verified and not obj.is_active:
            return format_html(
                '<span style="color: 000000; font-weight: bold;">Inactive User</span>'
            )
        
        elif not  obj.is_verified and  obj.is_active:
            return format_html(
                '<span style="color: 000000; font-weight: bold;">Unverify Regular User</span>'
            )
        
        elif   obj.is_active:
            return format_html(
                '<span style="color: rgb(83, 84, 255); font-weight: bold;">Regular User</span>'
            )
        
        # Default: Regular User
        else:
            return format_html(
                '<span style="color: hsl(300, 100%, 50%);">UNABLE TO FIND IT </span>'
            )

    colored_permission_status.short_description = 'Permission Level'
    
    def is_verified_link(self, obj):
        status = "Verified" if obj.is_verified else "Not Verified"
        action = "Unverify" if obj.is_verified else "Verify"
        return format_html(
            '<a href="{}">{}</a> ({})',
            f'/admin/user/user/{obj.pk}/toggle_verified/',
            action,
            status
        )
    is_verified_link.short_description = 'Verification'
    
    def profile_image_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.profile_image.url) if obj.profile_image else "No Image"
    profile_image_preview.short_description = 'Profile Img'
    
    def aadhar_image_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.aadhar_image.url) if obj.aadhar_image else "No Image"
    aadhar_image_preview.short_description = 'Aadhar Img'
    
    def pancard_image_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.pancard_image.url) if obj.pancard_image else "No Image"
    pancard_image_preview.short_description = 'Pancard Img'
    
    # Action methods
    def verify_users(self, request, queryset):
        updated = queryset.filter(is_verified=False).update(is_verified=True)
        self.message_user(request, f"{updated} users have been verified.")
    verify_users.short_description = "Verify selected users"
    
    def unverify_users(self, request, queryset):
        updated = queryset.filter(is_verified=True).update(is_verified=False)
        self.message_user(request, f"{updated} users have been unverified.")
    unverify_users.short_description = "Unverify selected users"
    
    # URL configuration
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:user_id>/toggle_verified/', self.admin_site.admin_view(self.toggle_verified), name='toggle_verified'),
        ]
        return custom_urls + urls
    
    def toggle_verified(self, request, user_id):
        user = self.get_object(request, user_id)
        if user:
            user.is_verified = not user.is_verified
            user.save()
            self.message_user(request, f"User {user.username} verification status updated to {user.is_verified}.")
        return redirect('admin:user_user_changelist')
    
    # Permission methods
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and request.user.is_staff:
            form.base_fields = {k: v for k, v in form.base_fields.items() if k == 'is_verified'}
        return form
    
    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser and request.user.is_staff and  request.user.is_authority_to_manage_hotel :
            return hasattr(request.user, 'maintainer_profile') and request.user.maintainer_profile.is_verified
        return super().has_change_permission(request, obj)
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    # Row styling methods
    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if 'colored_row' not in list_display:
            list_display = list(list_display)
            list_display.insert(0, 'colored_row')
        return list_display
    
    def colored_row(self, obj):
        return ''
    colored_row.short_description = ''
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['css'] = """
        <style>
            .row-superuser { background-color: #FFDDDD !important; }
            .row-staff { background-color: #DDDDFF !important; }
            .row-regular { background-color: #DDFFDD !important; }
        </style>
        """
        return super().changelist_view(request, extra_context=extra_context)
    
    def get_row_css(self, obj, index):
        if obj.is_superuser:
            return 'row-superuser'
        elif obj.is_staff:
            return 'row-staff'
        return 'row-regular'
    
    # Save and change view methods
    def save_model(self, request, obj, form, change):
        try:
            if not request.user.is_superuser and not request.user.is_admin and not (hasattr(request.user, 'maintainer_profile') and request.user.maintainer_profile.is_verified):
                self.message_user(
                    request,
                    "You are not verified or you don't have authority to make this change.",
                    level=messages.ERROR
                )
                return
            super().save_model(request, obj, form, change)
        except IntegrityError as e:
            if "FOREIGN KEY constraint failed" in str(e):
                self.message_user(
                    request,
                    "You are not verified or you don't have authority to make this change due to a foreign key issue.",
                    level=messages.ERROR
                )
            else:
                self.message_user(
                    request,
                    f"An error occurred while saving: {str(e)}",
                    level=messages.ERROR
                )
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        try:
            return super().change_view(request, object_id, form_url, extra_context)
        except IntegrityError as e:
            if "FOREIGN KEY constraint failed" in str(e):
                self.message_user(
                    request,
                    "You are not verified or you don't have authority to make this change.",
                    level=messages.ERROR
                )
            else:
                self.message_user(
                    request,
                    f"An error occurred: {str(e)}",
                    level=messages.ERROR
                )
            return redirect('admin:user_user_changelist')

# Updated HotelStaffAdmin
@admin.register(HotelStaff)
class HotelStaffAdmin(admin.ModelAdmin):
    list_display = (
        'staff_id', 'user_link', 'hotel_link', 'department', 'hire_date', 'is_active_staff', 
        'hotel_gst_no', 'alternate_mobile_no', 'landline_no', 'shop_main_image_preview', 
        'shop_license_image_preview', 'shop_aadhar_image_preview', 'owner_pan_image_preview', 
        'owner_aadhar_image_preview'
    )
    list_editable = ('department', 'is_active_staff', 'hotel_gst_no', 'alternate_mobile_no', 'landline_no')
    list_filter = ('department', 'is_active_staff')
    search_fields = ('staff_id', 'user__username', 'hotel__name', 'hotel_gst_no')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'staff_id', 'hotel', 'department', 'hotel_gst_no', 'alternate_mobile_no', 'landline_no')
        }),
        ('Hotel Details', {
            'fields': ('hotel_name', 'location', 'state', 'country')
        }),
        ('Status', {
            'fields': ('hire_date', 'is_active_staff')
        }),
        ('Images', {
            'fields': ('shop_main_image', 'shop_license_image', 'shop_aadhar_image', 'owner_pan_image', 'owner_aadhar_image')
        }),
    )
    readonly_fields = ('hire_date',)
    autocomplete_fields = ['user', 'hotel']

    def user_link(self, obj):
        return format_html('<a href="{}">{}</a>', f'/admin/user/user/{obj.user.pk}/change/', obj.user.username)
    user_link.short_description = 'User'

    def hotel_link(self, obj):
        if obj.hotel:
            return format_html('<a href="{}">{}</a>', f'/admin/krishna/hotels/{obj.hotel.pk}/change/', obj.hotel.name)
        return "No Hotel Assigned"
    hotel_link.short_description = 'Hotel'

    def shop_main_image_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.shop_main_image.url) if obj.shop_main_image else "No Image"
    shop_main_image_preview.short_description = 'Shop Main Img'

    def shop_license_image_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.shop_license_image.url) if obj.shop_license_image else "No Image"
    shop_license_image_preview.short_description = 'License Img'

    def shop_aadhar_image_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.shop_aadhar_image.url) if obj.shop_aadhar_image else "No Image"
    shop_aadhar_image_preview.short_description = 'Shop Aadhar Img'

    def owner_pan_image_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.owner_pan_image.url) if obj.owner_pan_image else "No Image"
    owner_pan_image_preview.short_description = 'Owner PAN Img'

    def owner_aadhar_image_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.owner_aadhar_image.url) if obj.owner_aadhar_image else "No Image"
    owner_aadhar_image_preview.short_description = 'Owner Aadhar Img'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user':
            kwargs['queryset'] = User.objects.filter(is_staff=True)
        elif db_field.name == 'hotel':
            kwargs['queryset'] = Hotels.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'hotel')

# Updated MaintainerAdmin
@admin.register(Maintainer)
class MaintainerAdmin(admin.ModelAdmin):
    list_display = (
        'maintainer_id', 'user_link', 'name', 'phone_no', 'alternate_phone_no', 'designation',
        'hire_date', 'is_verified_link', 'profile_img_preview', 'aadhar_img_preview', 'pan_img_preview'
    )
    list_editable = ('name', 'phone_no', 'alternate_phone_no', 'designation')
    list_filter = ('is_verified', 'designation')
    search_fields = ('maintainer_id', 'user__username', 'name', 'phone_no')
    
    fieldsets = (
        (None, {'fields': ('user', 'maintainer_id', 'name', 'phone_no', 'alternate_phone_no', 'designation')}),
        ('Documents', {'fields': ('profile_img', 'aadhar_img', 'pan_img')}),
        ('Status', {'fields': ('hire_date', 'is_verified')}),
        ('Managed Users', {'fields': ('managed_users_list',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('hire_date', 'managed_users_list')

    def managed_users_list(self, obj):
        if not obj.is_verified:
            return "Maintainer must be verified to manage users."
        users = User.objects.exclude(maintainer_profile__isnull=False).order_by('username')
        hotel_staff = HotelStaff.objects.all()
        user_list = []

        for user in users:
            status = "Verified" if user.is_verified else "Not Verified"
            toggle_url = f'/admin/user/user/{user.pk}/toggle_verified/'
            user_list.append(
                format_html('<li><a href="{}">{}</a> ({})</li>', toggle_url, user.username, status)
            )

        for staff in hotel_staff:
            hotel_status = staff.hotel.name if staff.hotel else "No Hotel Assigned"
            assign_url = f'/admin/user/hotelstaff/{staff.pk}/assign_hotel/'
            user_list.append(
                format_html(
                    '<li><a href="{}">{}</a> (Staff ID: {}) - Hotel: {} [<a href="{}">Assign/Edit Hotel</a>]</li>',
                    f'/admin/user/user/{staff.user.pk}/change/', staff.user.username, staff.staff_id, hotel_status, assign_url
                )
            )

        return format_html('<ul>{}</ul>', format_html(''.join(user_list))) if user_list else "No users or staff to manage."
    managed_users_list.short_description = "Users & Hotel Staff"

    def user_link(self, obj):
        return format_html('<a href="{}">{}</a>', f'/admin/user/user/{obj.user.pk}/change/', obj.user.username)
    user_link.short_description = 'User'

    def is_verified_link(self, obj):
        status = "Verified" if obj.is_verified else "Not Verified"
        action = "Unverify" if obj.is_verified else "Verify"
        return format_html('<a href="{}">{}</a> ({})', f'/admin/user/maintainer/{obj.pk}/toggle_verified/', action, status)
    is_verified_link.short_description = 'Verification'

    def profile_img_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.profile_img.url) if obj.profile_img else "No Image"
    profile_img_preview.short_description = 'Profile Img'

    def aadhar_img_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.aadhar_img.url) if obj.aadhar_img else "No Image"
    aadhar_img_preview.short_description = 'Aadhar Img'

    def pan_img_preview(self, obj):
        return format_html('<img src="{}" width="50" />', obj.pan_img.url) if obj.pan_img else "No Image"
    pan_img_preview.short_description = 'PAN Img'

    actions = ['verify_maintainers', 'unverify_maintainers']

    def verify_maintainers(self, request, queryset):
        if not request.user.is_admin:
            self.message_user(request, "Only superusers can verify maintainers.", level='error')
            return
        updated = 0
        for obj in queryset.filter(is_verified=False):
            obj.is_verified = True
            obj.user.is_verified = True
            obj.save()
            obj.user.save()
            updated += 1
        self.message_user(request, f"{updated} maintainers have been verified.")
    verify_maintainers.short_description = "Verify selected maintainers"

    def unverify_maintainers(self, request, queryset):
        if not request.user.is_admin:
            self.message_user(request, "Only superusers can unverify maintainers.", level='error')
            return
        updated = 0
        for obj in queryset.filter(is_verified=True):
            obj.is_verified = False
            obj.user.is_verified = False
            obj.save()
            obj.user.save()
            updated += 1
        self.message_user(request, f"{updated} maintainers have been unverified.")
    unverify_maintainers.short_description = "Unverify selected maintainers"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:maintainer_id>/toggle_verified/', self.admin_site.admin_view(self.toggle_verified), name='toggle_verified'),
            path('hotelstaff/<int:staff_id>/assign_hotel/', self.admin_site.admin_view(self.assign_hotel), name='assign_hotel'),
        ]
        return custom_urls + urls

    def toggle_verified(self, request, maintainer_id):
        if not request.user.is_admin:
            self.message_user(request, "Only superusers can toggle maintainer verification.", level='error')
            return redirect('admin:user_maintainer_changelist')
        maintainer = self.get_object(request, maintainer_id)
        if maintainer:
            maintainer.is_verified = not maintainer.is_verified
            maintainer.user.is_verified = maintainer.is_verified
            maintainer.save()
            maintainer.user.save()
            self.message_user(request, f"Maintainer {maintainer.maintainer_id} verification status updated to {maintainer.is_verified}.")
        return redirect('admin:user_maintainer_changelist')

    def assign_hotel(self, request, staff_id):
        if not request.user.is_superuser and not (hasattr(request.user, 'maintainer_profile') and request.user.maintainer_profile.is_verified):
            self.message_user(request, "Only superusers or verified maintainers can assign hotels.", level='error')
            return redirect('admin:user_maintainer_changelist')

        staff = HotelStaff.objects.get(pk=staff_id)
        if request.method == "POST":
            hotel_id = request.POST.get('hotel_id')
            try:
                hotel = Hotels.objects.get(id=hotel_id)
                staff.hotel = hotel
                staff.save()
                self.message_user(request, f"Hotel {hotel.name} assigned to staff {staff.staff_id}.")
                return redirect('admin:user_maintainer_changelist')
            except Hotels.DoesNotExist:
                self.message_user(request, "Selected hotel does not exist.", level='error')

        hotels = Hotels.objects.all()
        return render(request, 'admin/assign_hotel.html', {'staff': staff, 'hotels': hotels})

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser  and request.user.is_staff:
            if not hasattr(request.user, 'maintainer_profile') or not request.user.maintainer_profile.is_verified:
                form.base_fields = {}
            else:
                form.base_fields = {k: v for k, v in form.base_fields.items() if k == 'is_verified'}
        return form

    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser and request.user.is_staff:
            return hasattr(request.user, 'maintainer_profile') and request.user.maintainer_profile.is_verified
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        try:
            return super().change_view(request, object_id, form_url, extra_context)
        except IntegrityError as e:
            if "FOREIGN KEY constraint failed" in str(e):
                self.message_user(
                    request,
                    "You are not verified or you don't have authority to make this change.",
                    level=messages.ERROR
                )
            else:
                self.message_user(
                    request,
                    f"An error occurred: {str(e)}",
                    level=messages.ERROR
                )
            return redirect('admin:user_maintainer_changelist')