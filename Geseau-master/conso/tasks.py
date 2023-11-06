# tasks.py

from django.shortcuts import get_object_or_404
from celery import shared_task
from django.utils import timezone
from .models import Alert, Consommation, Entreprise

from celery import Celery
from celery.schedules import crontab

@shared_task
def generate_weekly_alert(request):
    try:
        # Récupérez la date et l'heure actuelles
        user_id = request.user.id
        user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
        now = timezone.now()

        # Vérifiez si nous sommes un lundi à 09h
        if now.weekday() == 0 and now.hour == 9:
            # Effectuez les calculs pour obtenir les statistiques de la semaine précédente
            start_of_week = now - timezone.timedelta(days=7)
            end_of_week = now - timezone.timedelta(hours=1)  # Jusqu'à 08h59 le lundi actuel

            consommation_totale = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise_id, created_at__range=(date_debut, date_fin))
            df_consommation = pd.DataFrame(list(consommation_totale.values()))

            # Convertissez la colonne 'created_at' en type datetime
            df_consommation['created_at'] = pd.to_datetime(df_consommation['created_at'])

            # Regroupez les données par jour et calculez les statistiques
            daily_stats = df_consommation.groupby(df_consommation['created_at'].dt.date).agg({
                'quantite': ['mean', 'sum', 'min', 'max']
            })
            daily_stats.columns = ['Moyenne quotidienne', 'Total quotidien', 'Minimum quotidien', 'Maximum quotidien']
            daily_stats.reset_index(inplace=True)

            # Trouvez le jour avec la consommation minimale et maximale
            min_day = daily_stats[daily_stats['Total quotidien'] == daily_stats['Total quotidien'].min()]
            max_day = daily_stats[daily_stats['Total quotidien'] == daily_stats['Total quotidien'].max()]

            # Récupérez la date et la quantité correspondantes
            min_date = min_day['created_at'].iloc[0]
            min_quantity = min_day['Total quotidien'].iloc[0]
            max_date = max_day['created_at'].iloc[0]
            max_quantity = max_day['Total quotidien'].iloc[0]

            moyenne = df_consommation['quantite'].mean()  # Moyenne globale
            total = df_consommation['quantite'].sum()    # Total globale

            moyenne_formatted = "{:.2f}".format(moyenne)
            total_formatted = "{:.2f}".format(total)
            min_val_formatted = "{:.2f}".format(min_quantity)
            max_val_formatted = "{:.2f}".format(max_quantity)

            min_value = min_val_formatted
            max_value = max_val_formatted
            total_value = total_formatted
            average_value = moyenne_formatted


            # Créez une nouvelle alerte avec ces statistiques
            alert = Alert.objects.create(
                intitule="Statistiques hebdomadaires de consommation",
                message=f"Semaine du {start_of_week} au {end_of_week}: Min: {min_value} observé le {min_date}, Max: {max_value} observé le {max_date}, Total: {total_value}, Moyenne: {average_value}",
            )

            # Envoyez cette alerte à l'utilisateur ou stockez-la dans la base de données

    except Exception as e:
        # Gérez les exceptions ici
        pass

# tasks.py



app = Celery('Geseau')

@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Exécutez la tâche chaque lundi à 09h00
    sender.add_periodic_task(
        crontab(hour=9, minute=0, day_of_week=1),  # Chaque lundi (1) à 09h00 (9:00)
        generate_weekly_alert.s(),
    )
