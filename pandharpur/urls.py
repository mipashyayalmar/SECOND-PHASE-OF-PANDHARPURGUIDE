from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls, name='admin'), 
    path('', include('myapp.urls')), 
    path('hotel/', include('krishna.urls')),
    path('user/', include('user.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('accounts/', include('allauth.urls')),  
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)