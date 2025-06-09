
# myapp/context_processors.py
from .models import Advertisement

def advertisements(request):
    return {
        'advertisements': Advertisement.objects.filter(status='enable').order_by('order')
    }