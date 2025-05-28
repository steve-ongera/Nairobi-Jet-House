from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('about-us/', views.about_us, name='about-us'),
    path('contact-us/', views.contact_us, name='contact-us'),
    path('services/', views.services, name='services'),
    path('aircraft-leasing/', views.aircraft_leasing, name='aircraft_leasing'),
    path('air-cargo/', views.air_cargo, name='air_cargo'),
    path('private-jet-charter/', views.private_jet_charter, name='private_jet_charter'),
    path('group-charter/', views.group_charter, name='group_charter'),
    path('find-aircraft/', views.find_aircraft, name='find_aircraft'),
    path('search-airports/', views.search_airports, name='search_airports'),
    path('api/check-auth/', views.check_auth, name='check_auth'),
    path('api/login/', views.api_login, name='api_login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/create-booking/', views.create_booking, name='create_booking'),
    path('api/signup/', views.api_signup, name='api_signup'),
    path('api/check-username/', views.check_username_availability, name='check_username'),
    path('api/check-email/', views.check_email_availability, name='check_email'),
]
