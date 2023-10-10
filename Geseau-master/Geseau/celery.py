import os
from celery import Celery

# Réglez la variable d'environnement DJANGO_SETTINGS_MODULE
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Geseau.settings')

app = Celery('Geseau')

# Chargez la configuration de Celery depuis les paramètres Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Chargez les tâches depuis tous les modules Django de l'application.
app.autodiscover_tasks()

# Configuration du backend de la file d'attente (par exemple, Redis)
app.conf.broker_url = 'redis://localhost:6379/0'