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
    #extra api for auth
    path('api/auth/login/', views.login_view, name='login'),
    path('api/auth/register/', views.signup_view, name='signup'),
    
    path('api/create-booking/', views.create_booking, name='create_booking'),
    path('api/signup/', views.api_signup, name='api_signup'),
    path('api/check-username/', views.check_username_availability, name='check_username'),
    path('api/check-email/', views.check_email_availability, name='check_email'),
    path('submit-cargo-request/', views.submit_cargo_request, name='submit_cargo_request'),
    path('submit-leasing-inquiry/', views.submit_leasing_inquiry, name='submit_leasing_inquiry'),
    path('save-inquiry/', views.save_inquiry, name='save_inquiry'),

    #admin application development product 2
    path('admin-dashboard/' , views.admin_dashboard , name='admin_dashboard'),
    path('admin-login-dasboard/' , views.admin_login_view , name='admin-login'),
    path('adminpage/logout/', views.admin_logout_view, name='admin_logout'),
    path('clients/', views.client_list, name='client_list'),
    path('clients/<int:client_id>/detail/', views.client_detail, name='client_detail'),
    path('owners/', views.aircraft_owner_list, name='aircraft_owner_list'),
    path('owners/<int:owner_id>/detail/', views.aircraft_owner_detail, name='aircraft_owner_detail'),
    path('owners/<int:owner_id>/update/', views.update_aircraft_owner, name='update_aircraft_owner'),
    path('owners/<int:owner_id>/delete/', views.delete_aircraft_owner, name='delete_aircraft_owner'),

    # Main aircraft list view
    path('aircraft/', views.aircraft_list, name='aircraft_list'),
    
    # AJAX endpoints
    path('aircraft/<int:aircraft_id>/detail/', views.aircraft_detail_ajax, name='aircraft_detail_ajax'),
    path('aircraft/<int:aircraft_id>/update/', views.aircraft_update_ajax, name='aircraft_update_ajax'),
    path('aircraft/<int:aircraft_id>/delete/', views.aircraft_delete_ajax, name='aircraft_delete_ajax'),
    
    # Dropdown data endpoint
    path('aircraft/dropdown-data/', views.get_dropdown_data, name='aircraft_dropdown_data'),

    path('aircrafts-types', views.aircraft_types_view, name='aircraft_types'),
    
    # API endpoints
    path('api/aircraft-types/', views.aircraft_types_api, name='aircraft_types_api'),
    path('api/aircraft-types/<int:pk>/', views.aircraft_type_api, name='aircraft_type_api'),

    path('api/aircraft-types/list/', views.aircraft_types_api_list, name='aircraft_types_list'),
    path('api/aircraft-types/create/', views.aircraft_type_api_create, name='aircraft_type_create'),
    path('api/aircraft-types/<int:pk>/detail/', views.aircraft_type_api_detail, name='aircraft_type_detail'),
    path('api/aircraft-types/<int:pk>/update/', views.aircraft_type_api_update, name='aircraft_type_update'),
    path('api/aircraft-types/<int:pk>/delete/', views.aircraft_type_api_delete, name='aircraft_type_delete'),

    path('availability/', views.availability_list, name='availability_list'),
    path('availability/<int:availability_id>/detail/', views.availability_detail, name='availability_detail'),
    path('availability/<int:availability_id>/update/', views.update_availability, name='update_availability'),
    path('availability/<int:availability_id>/delete/', views.delete_availability, name='delete_availability'),

    # Booking list view - displays paginated list of bookings with optional status filter
    path('bookings/', views.booking_list, name='booking_list'),
    path('bookings/<int:booking_id>/detail/', views.booking_detail, name='booking_detail'),
    path('bookings/<int:booking_id>/update/', views.update_booking_status, name='update_booking_status'),
    path('bookings/<int:booking_id>/delete/', views.delete_booking, name='delete_booking'),

    path('inquiries/', views.inquiry_list, name='inquiry_list'),
    path('inquiries/<int:inquiry_id>/detail/', views.inquiry_detail, name='inquiry_detail'),
    path('inquiries/<int:inquiry_id>/update/', views.update_inquiry, name='update_inquiry'),
    path('inquiries/<int:inquiry_id>/delete/', views.delete_inquiry, name='delete_inquiry'),

    path('cargo-requests/', views.cargo_request_list, name='cargo_request_list'),
    path('cargo-requests/<int:request_id>/detail/', views.cargo_request_detail, name='cargo_request_detail'),
    path('cargo-requests/<int:request_id>/update/', views.update_cargo_request, name='update_cargo_request'),
    path('cargo-requests/<int:request_id>/delete/', views.delete_cargo_request, name='delete_cargo_request'),
  
]
