from django.apps import AppConfig


class ConsoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'conso'

    def ready(self):
        import conso.signals
