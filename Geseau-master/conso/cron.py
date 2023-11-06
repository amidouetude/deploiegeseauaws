from django_cron import CronJobBase, Schedule
from datetime import datetime

from conso.models import Entreprise
from conso.utils import traiter_surconsommation

class SurconsommationCronJob(CronJobBase):
    RUN_EVERY = Schedule(run_at_times=["07:00"])

    def do(self):
        user_ids = Entreprise.objects.values_list('user_id', flat=True)
        for user_id in user_ids:
            traiter_surconsommation(user_id)
