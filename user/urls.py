from django.urls import path, include
from . import views
from django.contrib.auth.views import (
    LogoutView, 
    PasswordResetView, 
    PasswordResetDoneView, 
    PasswordResetConfirmView,
    PasswordResetCompleteView
)

app_name = 'user'

urlpatterns = [
    path('signups/', views.staff_signup, name='staff_signup'),
    path('signins/', views.staff_signin, name='staff_signin'),
    path('logout/', views.staff_logout_view, name='staff_logout'),
    
    # Uncommented and fixed staff_verify_email URL
    path('staff/verify-email/<uidb64>/<token>/', views.staff_verify_email, name='staff_verify_email'),

    # Staff Password Reset
    path('password-resets/', views.StaffCustomPasswordResetView.as_view(), name='staff_password_reset'),
    path('password-resets/done/', PasswordResetDoneView.as_view(template_name='staff_login/staff_password_reset_done.html'), name='staff_password_reset_done'),
    path('staff/password/reset/<uidb64>/<token>/', views.StaffCustomPasswordResetConfirmView.as_view(
    template_name='staff_login/staff_password_reset_confirm.html'
    ), name='staff_password_reset_confirm'),
    path('password-reset-completes/', PasswordResetCompleteView.as_view(template_name='staff_login/staff_password_reset_complete.html'), name='staff_password_reset_complete'),

    # User-related paths (non-staff)
    path('signup', views.signup, name='signup'),
    path('user/signin/', views.signin, name='signin'),
    path('logout', views.logout_view, name='user_logout'),
    path('verify_email/<str:uidb64>/<str:token>/', views.verify_email, name='verify_email'),

    # User Password Reset
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password-reset'),
    path('password-reset/done/', PasswordResetDoneView.as_view(template_name='user_login/password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset-complete/', PasswordResetCompleteView.as_view(template_name='user_login/password_reset_complete.html'), name='password_reset_complete'),


    # New Profile URLs
    # Profile URLs
    path('user/profile/', views.user_profile, name='user_profile'),
    path('user/profile/edit/', views.user_profile_edit, name='user_profile_edit'),
    path('user/profile/edit/form_userside/', views.user_profile_edit_form_userside, name='user_profile_edit_form_userside'),
    path('staff/profile/', views.staff_profile, name='staff_profile'),
    path('staff/profile/edit/', views.staff_profile_edit, name='staff_profile_edit'),
    path('profile/', views.user_profile, name='user_profile'),
    path('<str:username>/', views.user_profile_detail, name='user_profile_detail'),

    path('user/maintainer_signup/', views.maintainer_signup, name='maintainer_signup'),
    path('user/maintainer_verify-email/<uidb64>/<token>/', views.maintainer_verify_email, name='maintainer_verify_email'),
    path('user/maintainer_signin/', views.maintainer_signin, name='maintainer_signin'),
    path('user/maintainer_profile/', views.maintainer_profile, name='maintainer_profile'),
    path('user/maintainer_profile/edit/', views.maintainer_profile_edit, name='maintainer_profile_edit'),
    path('user/maintainer_logout/', views.maintainer_logout, name='maintainer_logout'),
    path('user/maintainer/password/reset/', views.MaintainerPasswordResetView.as_view(), name='maintainer_password_reset'),
    path('user/maintainer/password/reset/done/', views.PasswordResetView.as_view(template_name='maintainer_login/maintainer_password_reset_done.html'), name='maintainer_password_reset_done'),
    path('user/maintainer/reset/<uidb64>/<token>/', views.MaintainerPasswordResetConfirmView.as_view(), name='maintainer_password_reset_confirm'),
    path('user/maintainer/password/reset/complete/', views.PasswordResetView.as_view(template_name='maintainer_login/maintainer_password_reset_complete.html'), name='maintainer_password_reset_complete'),
]
