from django.apps import AppConfig

class ApexfinConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apexfin'

    def ready(self):
        # You can import any signals or additional configurations here if needed
        pass
