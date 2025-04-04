# empmanagement/celery.py
from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'empmanagement.settings')

app = Celery('empmanagement')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()