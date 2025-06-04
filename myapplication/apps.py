from django.apps import AppConfig


class MyapplicationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapplication'

    def ready(self):
        import myapplication.signals  # Import  signals file
