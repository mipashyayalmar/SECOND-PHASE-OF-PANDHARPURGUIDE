from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.forms import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.core.mail import EmailMultiAlternatives
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib import messages
from .models import User, HotelStaff, Maintainer
import random
import logging
from django.utils import timezone
import pytz
from django.contrib.auth.decorators import login_required





# Set up logging for debugging
logger = logging.getLogger(__name__)

# Get the custom user model
User = get_user_model()

# Staff Signup
def staff_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        name = request.POST['name']
        phone = request.POST['phone']
        password1 = request.POST['password1']
        password2 = request.POST['password2']

        if password1 != password2:
            messages.error(request, "Passwords don't match")
            return redirect('user:staff_signup')

        if User.objects.filter(username=username).exists():
            messages.warning(request, "Username already exists")
            return redirect('user:staff_signup')

        user = User.objects.create_user(
            username=username,
            password=password1,
            name=name,
            email=username,
            phone=phone,
            is_staff=True,
            is_superuser=False,
            is_active=False  # Inactive until verified
        )

        staff_id = f"HSTF{random.randint(100, 999)}"
        HotelStaff.objects.create(user=user, staff_id=staff_id, department='reception')

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        verification_url = request.build_absolute_uri(reverse('user:staff_verify_email', args=[uid, token]))

        subject = 'Welcome to Hotel Staff - Verify Your Account'
        html_message = render_to_string('staff_login/staff_verification_email.html', {
            'name': name,
            'username': username,
            'verification_url': verification_url,
            'domain': request.get_host(),
            'protocol': 'https' if request.is_secure() else 'http',
        })
        plain_message = strip_tags(html_message)

        try:
            email = EmailMultiAlternatives(
                subject,
                plain_message,
                settings.EMAIL_HOST_USER,
                [username],
            )
            email.attach_alternative(html_message, "text/html")
            email.send()
            messages.success(request, "Registration successful. Please check your email for verification.")
        except Exception as e:
            user.delete()
            messages.error(request, f"Failed to send verification email: {str(e)}")
            return redirect('user:staff_signup')

        return redirect('user:staff_signin')

    return render(request, 'staff_login/staff_signup.html')

# Staff Email Verification
def staff_verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        if default_token_generator.check_token(user, token) and user.is_staff:
            user.is_active = True
            user.save()
            return render(request, 'staff_login/staff_verification_success.html', {'message': 'Email verified successfully. You can now sign in.'})
        else:
            return render(request, 'staff_login/staff_verification_failure.html', {'message': 'Invalid verification link or account is not a staff account.'})
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return render(request, 'staff_login/staff_verification_failure.html', {'message': 'Verification failed due to an invalid or expired link.'})

# Staff Signin
def staff_signin(request):
    if request.user.is_authenticated and request.user.is_staff and request.user.is_active:
        return redirect('/')  # Redirect to staff dashboard if verified


    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        if not User.objects.filter(username=username).exists():
            return render(request, 'staff_login/staff_signup.html', {'message': "Staff doesn't exist. Please sign up"})

        user = User.objects.get(username=username)

        if not user.is_staff:
            return render(request, 'staff_login/staff_signin.html', {'message': 'This is may be User account. Please use a staff username.'})

        if not user.is_active:
            return render(request, 'staff_login/verification_prompt.html', {'email': username, 'message': 'Your staff account is not verified yet. Please check your email.'})
        

        authenticated_user = authenticate(request, username=username, password=password)

        if authenticated_user is not None:
            if authenticated_user.is_staff and authenticated_user.is_active:
                request.session['username'] = username
                login(request, authenticated_user)
                ist = pytz.timezone('Asia/Kolkata')
                signin_time = timezone.now().astimezone(ist).strftime('%Y-%m-%d %H:%M:%S')

                messages.success(request, f'Welcome {username}, your Staff login was successful at {signin_time}.')

                return redirect('user:staff_profile_edit')
            else:
                return render(request, 'staff_login/staff_signin.html', {'message': 'Account is not authorized for staff access.'})

        return render(request, 'staff_login/staff_signin.html', {'message': 'Incorrect username or password'})

    return render(request, 'staff_login/staff_signin.html')


# Staff Logout View
def staff_logout_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        username = request.user.username  # Get the username for the message
        logout(request)
        request.session.flush()
        # Add the message with the username dynamically
        messages.warning(request, f'Goodbye {username}, you’ve logged out successfully as a Staff.')
        return redirect('user:staff_signin')  # Redirect to the sign-in page
    return redirect('user:staff_signin') 

 

# Staff Password Reset View
class StaffCustomPasswordResetView(PasswordResetView):
    template_name = 'staff_login/staff_password_reset.html'
    form_class = PasswordResetForm
    success_url = reverse_lazy('user:staff_password_reset_done')
    email_template_name = 'staff_login/staff_password_reset_email.txt'
    html_email_template_name = 'staff_login/staff_password_reset_email.html'

    def form_valid(self, form):
        email = form.cleaned_data['email']
        if not User.objects.filter(email=email, is_staff=True).exists():
            return render(self.request, self.template_name, {
                'form': form,
                'error': 'No staff account found with this email.'
            })

        # Only allow reset for active staff users
        user = User.objects.get(email=email)
        if not user.is_active:
            return render(self.request, 'staff_login/verification_prompt.html', {
                'email': email,
                'message': 'Your staff account is not verified yet. Please verify your email before resetting your password.'
            })

        protocol = 'https' if self.request.is_secure() else 'http'
        domain = self.request.get_host()

        opts = {
            'use_https': self.request.is_secure(),
            'from_email': settings.EMAIL_HOST_USER,
            'request': self.request,
            'email_template_name': self.email_template_name,
            'html_email_template_name': self.html_email_template_name,
            'extra_email_context': {
                'protocol': protocol,
                'domain': domain,
            },
        }

        form.save(**opts)
        return super().form_valid(form)

# Staff Password Reset Confirm View
class StaffCustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'staff_login/staff_password_reset_confirm.html'
    form_class = SetPasswordForm
    success_url = reverse_lazy('user:staff_password_reset_complete')

    def dispatch(self, *args, **kwargs):
        uidb64 = kwargs.get('uidb64')
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            if not user.is_staff:
                return render(self.request, 'staff_login/staff_password_reset_failure.html', {
                    'message': 'This is not a staff account.'
                })
            if not user.is_active:
                return render(self.request, 'staff_login/verification_prompt.html', {
                    'email': user.email,
                    'message': 'Your staff account is not verified yet. Please verify your email before resetting your password.'
                })
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return render(self.request, 'staff_login/staff_password_reset_failure.html', {
                'message': 'Invalid reset link.'
            })
        return super().dispatch(*args, **kwargs)

# User Signup
def signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        name = request.POST['name']
        phone = request.POST['phone']
        password = request.POST['password']

        if User.objects.filter(username=username).exists():
            return render(request, 'user_login/signin.html', {'message': 'User already exists with that username. Please sign in.'})

        user = User.objects.create_user(username=username, password=password, name=name, phone=phone, email=username, is_active=False)

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        verification_url = request.build_absolute_uri(reverse('user:verify_email', args=[uid, token]))

        subject = 'Welcome to PandharpurGuide, Verify your account'
        html_message = render_to_string('user_login/verification_email.html', {
            'name': user.name,
            'username': user.username,
            'email': user.email,
            'phone': user.phone,
            'password': password,  
            'verification_url': verification_url,
            'domain': request.get_host(),
            'protocol': 'https' if request.is_secure() else 'http',
        })
        plain_message = strip_tags(html_message)

        email = EmailMultiAlternatives(subject, plain_message, settings.EMAIL_HOST_USER, [user.email])
        email.attach_alternative(html_message, "text/html")

        try:
            email.send()
        except Exception as e:
            user.delete()
            return render(request, 'user_login/signup.html', {'message': f'Error sending verification email: {str(e)}'})

        user.save()
        return render(request, 'user_login/signin.html', {'message': 'User created successfully. Please check your email for verification instructions.'})

    return render(request, 'user_login/signup.html')

def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save()

            # Automatically log the user in after email verification
            authenticated_user = authenticate(request, username=user.username, password=user.password)
            if authenticated_user is not None:
                login(request, authenticated_user)

            # Optional: Log the time when the user is logged in
            ist = pytz.timezone('Asia/Kolkata')
            signin_time = timezone.now().astimezone(ist).strftime('%Y-%m-%d %H:%M:%S')
            messages.success(request, f'Account verified successfully and logged in at {signin_time}')

            return redirect('user:signin')  # Redirect to a page after successful login

        else:
            return render(request, 'user_login/verification_failure.html')
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return render(request, 'user_login/verification_failure.html')

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.utils import timezone
import pytz
from django.contrib.auth.models import User

# User Signin
def signin(request):
    if request.user.is_authenticated and request.user.is_active:
        return redirect('/')

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        if not User.objects.filter(username=username).exists():
            return render(request, 'user_login/signup.html', {'message': "User doesn't exist. Please sign up"})

        user = User.objects.get(username=username)

        if not user.is_active:
            return render(request, 'user_login/verification_prompt.html', {'email': username, 'message': 'Your account is not verified yet. Please check your email.'})

        authenticated_user = authenticate(request, username=username, password=password)

        if authenticated_user is not None and authenticated_user.is_active:
            request.session['username'] = username
            login(request, authenticated_user)

            ist = pytz.timezone('Asia/Kolkata')
            signin_time = timezone.now().astimezone(ist).strftime('%Y-%m-%d %H:%M:%S')

            messages.success(request, f'Signin successful at {signin_time}')

            if hasattr(authenticated_user, 'is_maintainer') and authenticated_user.is_maintainer:
                # Assuming is_maintainer is a custom field in the User model
                return redirect('maintainer_panel')  # Redirect maintainer to maintainer_panel
            elif authenticated_user.is_staff:
                return redirect('staffpanel')  
            else:
                return redirect('myapp:home')  # Redirect regular user to home page
        
        return render(request, 'user_login/signin.html', {'message': 'Incorrect username or password'})

    return render(request, 'user_login/signin.html')
# User Logout
def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        request.session.flush()
        
        messages.warning(request, 'Logged out successfully')
        
        return redirect('user:signin')  
    return redirect('user:signin') 

class CustomPasswordResetView(PasswordResetView):
    template_name = 'user_login/password_reset.html'
    success_url = reverse_lazy('user:password_reset_done')
    email_template_name = 'user_login/reset_password.txt'
    html_email_template_name = 'user_login/reset_password.html'

    def form_valid(self, form): 
        email = form.cleaned_data['email']
        if not User.objects.filter(email=email, is_maintainer=False, is_staff=False).exists():
            messages.error(self.request, 'No account found with this email.')
            return self.render_to_response(self.get_context_data(form=form))

        user = User.objects.get(email=email)
        if user.is_staff:
            messages.error(self.request, 'This is a staff account. Please use the staff password reset page.')
            return self.render_to_response(self.get_context_data(form=form))

        if not user.is_active:
            return render(self.request, 'user_login/verification_prompt.html', {
                'email': email,
                'message': 'Your account is not verified yet. Please verify your email before resetting your password.'
            })

        protocol = 'https' if self.request.is_secure() else 'http'
        domain = self.request.get_host()

        opts = {
            'use_https': self.request.is_secure(),
            'from_email': settings.EMAIL_HOST_USER,
            'request': self.request,
            'email_template_name': self.email_template_name,
            'html_email_template_name': self.html_email_template_name,
            'extra_email_context': {
                'protocol': protocol,
                'domain': domain,
            },
        }

        form.save(**opts)
        return super().form_valid(form)
    
    # User Password Reset Confirm View
class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'user_login/password_reset_confirm.html'
    success_url = reverse_lazy('user:password_reset_complete')
    form_class = SetPasswordForm

    def dispatch(self, *args, **kwargs):
        uidb64 = kwargs.get('uidb64')
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            if user.is_staff:
                return render(self.request, 'user_login/password_reset_failure.html', {
                    'message': 'This is a staff account. Please use the staff password reset page.'
                })
            if not user.is_active:
                return render(self.request, 'user_login/verification_prompt.html', {
                    'email': user.email,
                    'message': 'Your account is not verified yet. Please verify your email before resetting your password.'
                })
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return render(self.request, 'user_login/password_reset_failure.html', {
                'message': 'Invalid reset link.'
            })
        return super().dispatch(*args, **kwargs)
    




def generate_staff_id():
    while True:
        staff_id = f"HSTF{random.randint(100, 999)}"
        if not HotelStaff.objects.filter(staff_id=staff_id).exists():
            return staff_id
        
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from allauth.socialaccount.models import SocialAccount
from django.core.validators import validate_email, RegexValidator
@login_required(login_url='/')
def user_profile(request):
    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to view your profile.")
        return redirect('user:signin')
    
    if request.user.is_staff:
        messages.error(request, "Staff accounts cannot access user profiles.")
        return redirect('user:staff_signin')

    user = request.user

    # Try to get social account data
    social_data = {}
    try:
        social_account = SocialAccount.objects.get(user=user, provider='google')
        social_data = {
            'full_name': social_account.extra_data.get('name'),
            'email': social_account.extra_data.get('email'),
            'picture': social_account.extra_data.get('picture'),
        }
    except SocialAccount.DoesNotExist:
        # User may have signed up with regular email/password
        social_data = {
            'full_name': user.get_full_name() or user.username,
            'email': user.email,
            'picture': None
        }

    context = {
        'user': user,
        'social_data': social_data
    }
    
    return render(request, 'user_login/user_profile.html', context)
# Set up logging
logger = logging.getLogger(__name__)
@login_required(login_url='/')
def user_profile_edit(request):
    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to edit your profile.")
        return redirect('user:signin')
    
    if request.user.is_staff:
        messages.error(request, "Staff accounts cannot edit user profiles.")
        return redirect('user:staff_signin')
    
    user = request.user
    social_data = {}

    try:
        # Fetch Google social account data
        social_account = SocialAccount.objects.get(user=user, provider='google')
        extra_data = social_account.extra_data
        
        # Extract all available fields from Google OAuth
        social_data = {
            'google_id': extra_data.get('sub'),  # Unique Google ID
            'email': extra_data.get('email'),
            'email_verified': extra_data.get('email_verified', False),
            'full_name': extra_data.get('name'),
            'first_name': extra_data.get('given_name'),
            'last_name': extra_data.get('family_name'),
            'picture': extra_data.get('picture'),
            'locale': extra_data.get('locale'),
            'hosted_domain': extra_data.get('hd'),  # For Google Workspace accounts
        }
        logger.debug(f"Google social data: {social_data}")

    except SocialAccount.DoesNotExist:
        # Fallback for non-Google login
        social_data = {
            'google_id': None,
            'email': user.email,
            'email_verified': False,
            'full_name': user.get_full_name() or user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'picture': None,
            'locale': None,
            'hosted_domain': None,
        }
        logger.debug(f"Non-Google user data: {social_data}")

    # Check if all required fields are already filled
    required_fields_filled = all([
        user.name,
        user.phone,
        user.email,
        user.aadhar_image,
        user.profile_image,
        user.pancard_image
    ])
    
    if required_fields_filled and request.method != 'POST':
        return redirect('myapp:home')

    if request.method == 'POST':
        logger.debug(f"POST data: {request.POST}")
        logger.debug(f"FILES data: {request.FILES}")

        # Mandatory email field
        email = request.POST.get('email')
        if not email:
            messages.error(request, "Email is required.")
            return render(request, 'user_login/user_profile_edit.html', {
                'user': user,
                'social_data': social_data
            })

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email format.")
            return render(request, 'user_login/user_profile_edit.html', {
                'user': user,
                'social_data': social_data
            })

        # Check for email uniqueness (excluding current user)
        if email != user.email and request.user.__class__.objects.filter(email=email).exclude(pk=user.pk).exists():
            messages.error(request, "This email is already in use.")
            return render(request, 'user_login/user_profile_edit.html', {
                'user': user,
                'social_data': social_data
            })

        # Update user fields
        user.email = email
        user.name = request.POST.get('name', user.name)
        user.phone = request.POST.get('phone', user.phone)

        # Handle file uploads with validation
        if 'profile_image' in request.FILES:
            profile_image = request.FILES['profile_image']
            if not profile_image.content_type.startswith('image/'):
                messages.error(request, "Profile image must be a valid image file.")
                return render(request, 'user_login/user_profile_edit.html', {
                    'user': user,
                    'social_data': social_data
                })
            user.profile_image = profile_image
            logger.info(f"Profile image uploaded: {user.profile_image}")

        if 'aadhar_image' in request.FILES:
            aadhar_image = request.FILES['aadhar_image']
            if not aadhar_image.content_type.startswith('image/'):
                messages.error(request, "Aadhar image must be a valid image file.")
                return render(request, 'user_login/user_profile_edit.html', {
                    'user': user,
                    'social_data': social_data
                })
            user.aadhar_image = aadhar_image
            logger.info(f"Aadhar image uploaded: {user.aadhar_image}")

        if 'pancard_image' in request.FILES:
            pancard_image = request.FILES['pancard_image']
            if not pancard_image.content_type.startswith('image/'):
                messages.error(request, "Pancard image must be a valid image file.")
                return render(request, 'user_login/user_profile_edit.html', {
                    'user': user,
                    'social_data': social_data
                })
            user.pancard_image = pancard_image
            logger.info(f"Pancard image uploaded: {user.pancard_image}")

        try:
            user.save()
            messages.success(request, "Profile updated successfully.")
            
            # Check again if all required fields are filled after update
            if all([
                user.name,
                user.phone,
                user.email,
                user.aadhar_image,
                user.profile_image,
                user.pancard_image
            ]):
                return redirect('myapp:home')
            else:
                return redirect('user:user_profile')
                
        except Exception as e:
            logger.error(f"Error saving user profile: {str(e)}")
            messages.error(request, "An error occurred while updating your profile.")
            return render(request, 'user_login/user_profile_edit.html', {
                'user': user,
                'social_data': social_data
            })

    return render(request, 'user_login/user_profile_edit.html', {
        'user': user,
        'social_data': social_data
    })


@login_required(login_url='/')
def staff_profile(request):
    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to view your staff profile.")
        return redirect('user:staff_signin')
    
    if not request.user.is_staff:
        messages.error(request, "Only staff can access this page.")
        return redirect('user:signin')
    
    try:
        staff = request.user.hotel_staff_profile
    except HotelStaff.DoesNotExist:
        staff = HotelStaff.objects.create(
            user=request.user,
            staff_id=generate_staff_id(),
            department='reception',
            hotel_name=request.user.username + "'s Hotel",  # Set default hotel name
            location='pandharpur',  # Default location
            state='maharashtra',   # Default state
            country='india'        # Default country
        )
        messages.warning(request, "Staff profile was missing and has been created with default values.")
    
    return render(request, 'staff_login/staff_profile.html', {
        'staff': staff,
        'user': request.user,
        'departments': [choice[1] for choice in HotelStaff._meta.get_field('department').choices]
    })

@login_required(login_url='/')
def staff_profile_edit(request):
    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to edit your staff profile.")
        return redirect('user:staff_signin')
    
    if not request.user.is_staff:
        messages.error(request, "Only staff can access this page.")
        return redirect('user:signin')
    
    if not request.user.is_verified:
        messages.warning(request, "Your staff account is not verified. Please contact pandharpurguide team.")
        return redirect('user:staff_profile')
    
    try:
        staff = request.user.hotel_staff_profile
    except HotelStaff.DoesNotExist:
        staff = HotelStaff.objects.create(
            user=request.user,
            staff_id=generate_staff_id(),
            department='reception',
            hotel_name=request.user.username + "'s Hotel",
            location='pandharpur',
            state='maharashtra',
            country='india'
        )
        messages.warning(request, "Staff profile was missing and has been created with default values.")
    
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.phone = request.POST.get('phone', user.phone)
        user.email = request.POST.get('email', user.email)
        
        staff.department = request.POST.get('department', staff.department)
        staff.userf_name = request.POST.get('userf_name', staff.userf_name)
        staff.hotel_gst_no = request.POST.get('hotel_gst_no', staff.hotel_gst_no)
        staff.alternate_mobile_no = request.POST.get('alternate_mobile_no', staff.alternate_mobile_no)
        staff.landline_no = request.POST.get('landline_no', staff.landline_no)
        
        # Hotel information fields
        staff.hotel_name = request.POST.get('hotel_name', staff.hotel_name)
        staff.location = request.POST.get('location', staff.location)
        staff.state = request.POST.get('state', staff.state)
        staff.country = request.POST.get('country', staff.country)
        
        # Handle file uploads
        for field in ['shop_main_image', 'shop_license_image', 'shop_aadhar_image', 
                     'owner_pan_image', 'owner_aadhar_image']:
            if field in request.FILES:
                setattr(staff, field, request.FILES[field])
        
        user.save()
        staff.save()
        messages.success(request, "Staff profile updated successfully.")
        return redirect('user:staff_profile')
    
    return render(request, 'staff_login/staff_profile_edit.html', {
        'staff': staff,
        'user': request.user,
        'department_choices': HotelStaff._meta.get_field('department').choices
    })


logger = logging.getLogger(__name__)
User = get_user_model()

def generate_maintainer_id():
    while True:
        maintainer_id = f"MTNR{random.randint(100, 999)}"
        if not Maintainer.objects.filter(maintainer_id=maintainer_id).exists():
            return maintainer_id

def maintainer_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        name = request.POST.get('name')
        phone_no = request.POST.get('phone_no')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords don't match.")
            return redirect('user:maintainer_signup')

        if User.objects.filter(username=username).exists():
            messages.warning(request, "Username already exists.")
            return redirect('user:maintainer_signup')

        user = User.objects.create_user(
            username=username,
            password=password1,
            name=name,
            phone=phone_no,
            email=username,  # Using username as email for simplicity
            is_staff=True,
            is_superuser=False,
            is_active=False
        )

        Maintainer.objects.create(
            user=user,
            maintainer_id=generate_maintainer_id(),
            name=name,
            phone_no=phone_no,
            designation='technician'
        )

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        verification_url = request.build_absolute_uri(reverse('user:maintainer_verify_email', args=[uid, token]))

        subject = 'Welcome to PandharpurGuide Maintainer - Verify Your Account'
        html_message = render_to_string('maintainer_login/maintainer_verification_email.html', {
            'name': name,
            'username': username,
            'verification_url': verification_url,
            'domain': request.get_host(),
            'protocol': 'https' if request.is_secure() else 'http',
        })
        plain_message = strip_tags(html_message)

        try:
            email = EmailMultiAlternatives(subject, plain_message, settings.EMAIL_HOST_USER, [username])
            email.attach_alternative(html_message, "text/html")
            email.send()
            messages.success(request, "Registration successful. Please check your email for verification by the PandharpurGuide team.")
        except Exception as e:
            user.delete()
            messages.error(request, f"Failed to send verification email: {str(e)}")
            return redirect('user:maintainer_signup')

        return redirect('user:maintainer_signin')

    return render(request, 'maintainer_login/maintainer_signup.html')

def maintainer_verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        if default_token_generator.check_token(user, token) and user.is_staff:
            user.is_active = True
            user.is_verified = True
            user.is_maintainer = True
            maintainer = user.maintainer_profile
            maintainer.is_verified = True
            maintainer.is_maintainer = True
            user.save()
            maintainer.save()
            messages.success(request, "Email verified successfully by PandharpurGuide team. You can now sign in.")
            return render(request, 'maintainer_login/maintainer_verification_success.html')
        else:
            messages.error(request, "Invalid verification link or account is not a maintainer account.")
            return render(request, 'maintainer_login/maintainer_verification_failure.html')
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        messages.error(request, "Verification failed due to an invalid or expired link.")
        return render(request, 'maintainer_login/maintainer_verification_failure.html')
    
  
def maintainer_signin(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Authenticate the user
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Check if the user has a Maintainer profile
            try:
                maintainer = user.is_maintainer  # Adjust based on your related_name
                if not user.is_active:
                    messages.error(request, "Your account is not yet verified. Please check your email.")
                    return redirect('user:maintainer_signin')
                if not user.is_maintainer:
                    messages.error(request, "Your account is not maintainer Please check your account.")
                    return redirect('user:maintainer_signin')
                login(request, user)
                ist = pytz.timezone('Asia/Kolkata')
                signin_time = timezone.now().astimezone(ist).strftime('%Y-%m-%d %H:%M:%S')

                messages.success(request, f'Welcome {username}, your Website Maintainer login was successful at {signin_time}')

                return redirect( 'user:maintainer_profile_edit')
            except Maintainer.DoesNotExist:
                messages.error(request, "No maintainer profile found for this user.")
                return redirect('user:maintainer_signin')
        else:
            messages.error(request, "Invalid username or password.")
            return redirect('user:maintainer_signin')
    
    return render(request, 'maintainer_login/maintainer_signin.html')

def maintainer_logout(request):
    if request.user.is_authenticated and request.user.is_maintainer:
        logout(request)
        messages.success(request, "Logged out successfully.")
    return redirect('user:maintainer_signin')


# def maintainer_logout(request):
#     if request.user.is_authenticated and request.user.is_staff:
#         logout(request)
#         messages.success(request, "Logged out successfully.")
#     return redirect('user:maintainer_signin')


def user_profile_detail(request, username):
    user = get_object_or_404(User, username=username)
    return render(request,'authenticated_check/check_user_profile.html',{'user':user})


@login_required(login_url='/')
def maintainer_profile(request):
    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to view your maintainer profile.")
        return redirect('user:maintainer_signin')
    
    if not request.user.is_staff:
        messages.error(request, "Only maintainers can access this page.")
        return redirect('user:signin')
    
    try:
        maintainer = request.user.maintainer_profile
    except Maintainer.DoesNotExist:
        maintainer = Maintainer.objects.create(
            user=request.user,
            maintainer_id=generate_maintainer_id(),
            name=request.user.name,
            phone_no=request.user.phone,
            designation='technician'
        )
        messages.warning(request, "Maintainer profile was missing and has been created with default values.")
    
    return render(request, 'maintainer_login/maintainer_profile.html', {'maintainer': maintainer, 'user': request.user})

@login_required(login_url='/')
def maintainer_profile_edit(request):
    if not request.user.is_authenticated:
        messages.error(request, "Please sign in to edit your maintainer profile.")
        return redirect('user:maintainer_signin')
    
    if not request.user.is_staff:
        messages.error(request, "Only maintainers can access this page.")
        return redirect('user:signin')
    
    if not request.user.is_maintainer:
        messages.warning(request, "Your maintainer account is not verified. Please contact the PandharpurGuide team.")
        return render(request, 'maintainer_login/maintainer_profile_edit.html', {'user': request.user, 'maintainer': request.user.maintainer_profile})

    try:
        maintainer = request.user.maintainer_profile
    except Maintainer.DoesNotExist:
        maintainer = Maintainer.objects.create(
            user=request.user,
            maintainer_id=generate_maintainer_id(),
            name=request.user.name,
            phone_no=request.user.phone,
            designation='technician'
        )
        messages.warning(request, "Maintainer profile was missing and has been created with default values.")

    if request.method == 'POST':
        user = request.user
        maintainer.name = request.POST.get('name', maintainer.name)
        maintainer.phone_no = request.POST.get('phone_no', maintainer.phone_no)
        maintainer.alternate_phone_no = request.POST.get('alternate_phone_no', maintainer.alternate_phone_no)
        user.email = request.POST.get('email', user.email)
        maintainer.designation = request.POST.get('designation', maintainer.designation)
        if 'profile_img' in request.FILES:
            maintainer.profile_img = request.FILES['profile_img']
        if 'aadhar_img' in request.FILES:
            maintainer.aadhar_img = request.FILES['aadhar_img']
        if 'pan_img' in request.FILES:
            maintainer.pan_img = request.FILES['pan_img']
        user.save()
        maintainer.save()
        messages.success(request, "Maintainer profile updated successfully.")
        return redirect('user:maintainer_profile')
    
    return render(request, 'maintainer_login/maintainer_profile_edit.html', {'maintainer': maintainer, 'user': request.user})

class MaintainerPasswordResetView(PasswordResetView):
    template_name = 'maintainer_login/maintainer_password_reset.html'
    form_class = PasswordResetForm
    success_url = reverse_lazy('user:maintainer_password_reset_done')
    email_template_name = 'maintainer_login/maintainer_password_reset_email.txt'
    html_email_template_name = 'maintainer_login/maintainer_password_reset_email.html'

    def form_valid(self, form):
        email = form.cleaned_data['email']
        if not User.objects.filter(email=email, is_staff=True).exists():
            messages.error(self.request, "No maintainer account found with this email.")
            return render(self.request, self.template_name, {'form': form})

        user = User.objects.get(email=email)
        if not user.is_active or not user.maintainer_profile.is_verified:
            messages.warning(self.request, "Your maintainer account is not verified yet. Please contact the PandharpurGuide team.")
            return render(self.request, 'maintainer_login/verification_prompt.html', {'email': email})

        protocol = 'https' if self.request.is_secure() else 'http'
        domain = self.request.get_host()

        opts = {
            'use_https': self.request.is_secure(),
            'from_email': settings.EMAIL_HOST_USER,
            'request': self.request,
            'email_template_name': self.email_template_name,
            'html_email_template_name': self.html_email_template_name,
            'extra_email_context': {'protocol': protocol, 'domain': domain},
        }

        form.save(**opts)
        return super().form_valid(form)

class MaintainerPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'maintainer_login/maintainer_password_reset_confirm.html'
    form_class = SetPasswordForm
    success_url = reverse_lazy('user:maintainer_password_reset_complete')

    def dispatch(self, *args, **kwargs):
        uidb64 = kwargs.get('uidb64')
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            if not user.is_staff:
                messages.error(self.request, "This is not a maintainer account.")
                return render(self.request, 'maintainer_login/maintainer_password_reset_failure.html')
            if not user.is_active or not user.maintainer_profile.is_verified:
                messages.warning(self.request, "Your maintainer account is not verified yet. Please contact the PandharpurGuide team.")
                return render(self.request, 'maintainer_login/verification_prompt.html', {'email': user.email})
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            messages.error(self.request, "Invalid reset link.")
            return render(self.request, 'maintainer_login/maintainer_password_reset_failure.html')
        return super().dispatch(*args, **kwargs)