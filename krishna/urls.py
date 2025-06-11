from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
import krishna.views as views
from django.urls import include, path

urlpatterns = [
    # Public Pages
    path('', views.homepage, name="homepage"),
    path('home', views.homepage, name="homepage"),
    path('about', views.aboutpage, name="aboutpage"),
    path('contact', views.contactpage, name="contactpage"),

    # User Pages
    path('user/bookings', views.user_bookings, name="dashboard"),
    path('user/book-room', views.book_room_page, name="bookroompage"),
    path('user/book-room/book', views.book_room, name="bookroom"),
    path('user/cancel-booking/<int:booking_id>/', views.cancel_booking, name="cancel_booking"),

    # Staff Pages
    path('hotel_staff/panel', views.hotel_staff_panel, name="staffpanel"),
    path('staff/allbookings', views.hotel_staff_bookings, name="allbookings"),
    path('hotel_staff/panel/add-new-location', views.add_new_location, name="addnewlocation"),
    path('hotel_staff/panel/edit-location', views.hotel_staff_edit_location, name="hotel_staff_edit_location"),
    path('hotel_staff/panel/edit-room/<int:room_id>/', views.hotel_staff_edit_room, name="editroom"),
    path('hotel_staff/panel/add-new-room', views.hotel_staff_add_room, name="addroom"),
    path('hotel_staff/panel/edit-room/edit', views.hotel_staff_edit_location, name="editroomaction"),
    path('hotel_staff/panel/view-room/<int:room_id>/', views.view_room, name='viewroom'),
    path('hotel_staff/panel/view-hotel', views.hotel_view_hotels, name='viewhotel'),
    path('staff/rooms/', views.list_rooms, name='listrooms'),
    path('contact/', views.contactpage, name='contact'),

    # Maintainer URLs
    path('maintainer/panel/', views.maintainer_panel, name='maintainer_panel'),
    path('maintainer/bookings/', views.maintainer_all_bookings, name='maintainer_all_bookings'),
    path('maintainer/rooms/', views.maintainer_view_rooms, name='maintainer_view_rooms'),
    path('maintainer/hotels/', views.maintainer_view_hotels, name='maintainer_view_hotels'),
    path('maintainer/edit-hotel/<int:hotel_id>/', views.maintainer_edit_hotel, name='maintainer_edit_hotel'),
    path('maintainer/edit-room/', views.maintainer_edit_room, name='maintainer_edit_room'),
    path('maintainer/add-room/', views.maintainer_add_new_room, name='maintainer_add_new_room'),
    path('maintainer/view-room/', views.maintainer_view_room, name='maintainer_view_room'),
    path('maintainer/add-location/', views.maintainer_add_new_location, name='maintainer_add_new_location'),
    path('maintainer/staff/', views.staff_list, name='staff-list'),
    path('maintainer/assign-hotel/', views.assign_hotel_to_staff, name='assign-hotel'),
    path('maintainer/manage-hotel/', views.manage_hotel_assignments, name='manage-hotel'),
    path('maintainer/edit-assignment/<int:pk>/', views.edit_hotel_assignment, name='edit-assignment'),
    path('maintainer/unassign-staff/<int:pk>/', views.unassign_staff, name='unassign-staff'),

    # Admin
    path('i18n/', include('django.conf.urls.i18n')),
    path('hotel/hotel/<int:hotel_id>/rooms/', views.view_hotel_rooms, name='view_hotel_rooms'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)