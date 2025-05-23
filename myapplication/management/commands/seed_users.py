from django.contrib.auth import get_user_model
User = get_user_model()

users = [
    {"username": "maria.sullivan", "user_type": "admin"},
    {"username": "david.kim", "user_type": "owner"},
    {"username": "carla.thomas", "user_type": "owner"},
    {"username": "henry.nguyen", "user_type": "owner"},
    {"username": "isabella.owens", "user_type": "owner"},
    {"username": "george.mwangi", "user_type": "owner"},
    {"username": "paul.mitchell", "user_type": "owner"},
    {"username": "nina.mendez", "user_type": "owner"},
    {"username": "owen.karanja", "user_type": "owner"},
    {"username": "linda.okech", "user_type": "owner"},
    {"username": "brian.choi", "user_type": "owner"},
    {"username": "ashley.morgan", "user_type": "client"},
    {"username": "joseph.kamau", "user_type": "client"},
    {"username": "emily.njoroge", "user_type": "client"},
    {"username": "steve.lee", "user_type": "client"},
    {"username": "grace.owino", "user_type": "client"},
    {"username": "kevin.adams", "user_type": "agent"},
    {"username": "lucy.wanjiru", "user_type": "agent"},
]

for user in users:
    u, created = User.objects.get_or_create(
        username=user['username'],
        defaults={
            'user_type': user['user_type'],
            'phone_number': '0712345678',
            'address': 'Nairobi, Kenya',
            'company_name': 'Skylink Ltd',
            'tax_id': 'TX123456',
            'verified': True
        }
    )
    if created:
        u.set_password('cp7kvt')
        u.save()
        print(f"Created user: {u.username}")
    else:
        print(f"User already exists: {u.username}")
