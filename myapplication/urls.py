from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('about-us/', views.about_us, name='about-us'),
    path('contact-us/', views.contact_us, name='contact-us'),
    path('find-aircraft/', views.find_aircraft, name='find_aircraft'),
    path('search-airports/', views.search_airports, name='search_airports'),
    path('api/check-auth/', views.check_auth, name='check_auth'),
    path('api/login/', views.api_login, name='api_login'),
    path('api/create-booking/', views.create_booking, name='create_booking'),
]
