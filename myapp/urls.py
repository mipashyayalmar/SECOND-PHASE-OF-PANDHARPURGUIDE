# This is the urls.py file for defining URL patterns in the Django app
from django.urls import path
from . import views
app_name = 'myapp'  

urlpatterns = [
    path('', views.home, name='home'),
    path('advertisement/', views.advertisement, name='advertisement'),
    path('blog/<int:image_id>/', views.blog_detail, name='blog_detail'),
]
