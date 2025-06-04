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
    path('financial-dashboard/', views.financial_dashboard, name='financial_dashboard'),
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

     path('leasing-inquiries/', views.leasing_inquiry_list, name='leasing_inquiry_list'),
    path('leasing-inquiries/<int:inquiry_id>/detail/', views.leasing_inquiry_detail, name='leasing_inquiry_detail'),
    path('leasing-inquiries/<int:inquiry_id>/update/', views.update_leasing_inquiry, name='update_leasing_inquiry'),
    path('leasing-inquiries/<int:inquiry_id>/delete/', views.delete_leasing_inquiry, name='delete_leasing_inquiry'),

    path('group-inquiries/', views.group_inquiry_list, name='group_inquiry_list'),
    path('group-inquiries/<int:inquiry_id>/detail/', views.group_inquiry_detail, name='group_inquiry_detail'),
    path('group-inquiries/<int:inquiry_id>/update/', views.update_group_inquiry, name='update_group_inquiry'),
    path('group-inquiries/<int:inquiry_id>/delete/', views.delete_group_inquiry, name='delete_group_inquiry'),

    path('contact-submissions/', views.contact_submission_list, name='contact_submission_list'),
    path('contact-submissions/<int:submission_id>/detail/', views.contact_submission_detail, name='contact_submission_detail'),
    path('contact-submissions/<int:submission_id>/delete/', views.delete_contact_submission, name='delete_contact_submission'),

    path('agents/', views.booking_agents_list, name='booking_agents_list'),
    path('agents/<int:agent_id>/detail/', views.agent_detail, name='agent_detail'),
    path('agents/<int:agent_id>/update/', views.update_agent, name='update_agent'),
    path('agents/<int:agent_id>/delete/', views.delete_agent, name='delete_agent'),

    path('admins/', views.admin_users_list, name='admin_users_list'),
    path('admins/<int:admin_id>/detail/', views.admin_detail, name='admin_detail'),
    path('admins/<int:admin_id>/update/', views.update_admin, name='update_admin'),
    path('admins/<int:admin_id>/delete/', views.delete_admin, name='delete_admin'),

    path('bookings/new/', views.new_booking, name='new_booking'),
    
    # AJAX endpoints for dynamic functionality
    path('ajax/check-availability/', views.ajax_check_availability, name='ajax_check_availability'),
    path('ajax/calculate-price/', views.ajax_calculate_price, name='ajax_calculate_price'),

    path('airports/', views.airport_list, name='airport_list'),
    path('airports/<int:pk>/detail/', views.airport_detail, name='airport_detail'),
    path('airports/<int:pk>/update/', views.airport_update, name='airport_update'),
    path('airports/<int:pk>/delete/', views.airport_delete, name='airport_delete'),

    path('flightlegs/', views.flightleg_list, name='flightleg_list'),
    path('flightlegs/<int:pk>/detail/', views.flightleg_detail, name='flightleg_detail'),
    path('flightlegs/<int:pk>/update/', views.flightleg_update, name='flightleg_update'),
    path('flightlegs/<int:pk>/delete/', views.flightleg_delete, name='flightleg_delete'),
    # Add this for the airport dropdowns in edit modal
    path('airports/list/', views.airport_list_json, name='airport_list_json'),

    # Main page view
    path('pricing-rules/', views.pricing_rules_list, name='pricing_rules_list'),
    
    # API endpoints for AJAX operations
    path('api/pricing-rules/', views.api_pricing_rules_list, name='api_pricing_rules_list'),
    path('api/pricing-rules/create/', views.api_pricing_rule_create, name='api_pricing_rule_create'),
    path('api/pricing-rules/<int:pk>/', views.api_pricing_rule_detail, name='api_pricing_rule_detail'),
    path('api/pricing-rules/<int:pk>/update/', views.api_pricing_rule_update, name='api_pricing_rule_update'),
    path('api/pricing-rules/<int:pk>/delete/', views.api_pricing_rule_delete, name='api_pricing_rule_delete'),
    path('api/aircraft-types/', views.api_aircraft_types_list, name='api_aircraft_types_list'),

    path('settings/', views.settings_view, name='settings'),
    path('help-support/', views.help_support, name='help_support'),
    path('flight-announcement/', views.Flight_Announcement, name='flight_announcement'),
    path('operations-reports/', views.operations_reports, name='operations_reports'),
    
    
]
