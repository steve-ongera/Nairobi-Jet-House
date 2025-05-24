from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('about-us/', views.about_us, name='about-us'),
     path('find-aircraft/', views.find_aircraft, name='find_aircraft'),
]
