# user/context_processors.py
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model

def social_data_processor(request):
    context = {}
    if request.user.is_authenticated:
        user = request.user
        try:
            social_account = SocialAccount.objects.get(user=user, provider='google')
            extra_data = social_account.extra_data
            context['social_data'] = {
                'picture': extra_data.get('picture'),
                'email': extra_data.get('email'),
                'name': extra_data.get('name'),
            }
        except SocialAccount.DoesNotExist:
            context['social_data'] = {
                'picture': None,
                'email': user.email,
                'name': user.get_full_name(),
            }
    return context