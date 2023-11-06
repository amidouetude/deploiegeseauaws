from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404
from .models import Entreprise, Consommation, Alert  # Assurez-vous d'importer vos modèles Django
import pandas as pd  # Si vous utilisez pandas pour les calculs
from django.contrib import messages


def traiter_surconsommation(user_id):
    user_entreprise = get_object_or_404(Entreprise, user_id=user_id)
    #Détermination des statistique de la semaine precedente
    today = datetime.now()
    last_week_start = today - timedelta(days=(today.weekday() + 7))
    last_week_start = last_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    last_week_end = last_week_start + timedelta(days=6)
    last_week_end = last_week_end.replace(hour=23, minute=59, second=59, microsecond=999999)
    consommation_totale_last_week = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise, created_at__date__range=(last_week_start, last_week_end))
    df_consommation_last_week = pd.DataFrame(list(consommation_totale_last_week.values()))
    
    df_consommation_last_week['created_at'] = pd.to_datetime(df_consommation_last_week['created_at'])
    daily_stats_last_week = df_consommation_last_week .groupby(df_consommation_last_week['created_at'].dt.date).agg({
        'quantite': ['mean', 'sum', 'min', 'max']
    })
    daily_stats_last_week.columns = ['Moyenne quotidienne', 'Total quotidien', 'Minimum quotidien', 'Maximum quotidien']
    daily_stats_last_week.reset_index(inplace=True)
    min_day_last_week = daily_stats_last_week[daily_stats_last_week['Total quotidien'] == daily_stats_last_week['Total quotidien'].min()]
    max_day_last_week = daily_stats_last_week[daily_stats_last_week['Total quotidien'] == daily_stats_last_week['Total quotidien'].max()]
    min_date_last_week = min_day_last_week['created_at'].iloc[0]
    min_quantity_last_week = min_day_last_week['Total quotidien'].iloc[0]
    max_date_last_week = max_day_last_week['created_at'].iloc[0]
    max_quantity_last_week = max_day_last_week['Total quotidien'].iloc[0]
    moyenne_last_week = df_consommation_last_week['quantite'].mean()
    total_last_week = df_consommation_last_week['quantite'].sum()
    moyenne_formatted = "{:.2f}".format(moyenne_last_week)
    total_formatted = "{:.2f}".format(total_last_week)
    min_val_formatted = "{:.2f}".format(min_quantity_last_week)
    max_val_formatted = "{:.2f}".format(max_quantity_last_week)
    alert_message = f"Statistiques de consommation de la semaine passée:\n" \
                    f"Consommation moyenne : {moyenne_formatted}\n" \
                    f"Consommation totale : {total_formatted}\n" \
                    f"Consommation minimale observée le ({min_date_last_week}) d'une quantité de {min_val_formatted}\n" \
                    f"Consommation maximale observée le ({max_date_last_week}) d'une quantité de {max_val_formatted}\n"
    
    alert = Alert.objects.create(
        intitule="Consommation semaine précédente",
        message=alert_message,
    )
    alert.save()

    #Determination des consommations d'il y'a deux sémaine
    two_weeks_ago_start = last_week_start - timedelta(days=7)
    two_weeks_ago_end = last_week_end - timedelta(days=7)
    consommation_totale_two_weeks_ago = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise, created_at__date__range=(two_weeks_ago_start, two_weeks_ago_end))
    df_consommation_two_weeks_ago = pd.DataFrame(list(consommation_totale_two_weeks_ago.values()))
    
    df_consommation_two_weeks_ago['created_at'] = pd.to_datetime(df_consommation_two_weeks_ago['created_at'])
    daily_stats_two_weeks_ago = df_consommation_two_weeks_ago .groupby(df_consommation_two_weeks_ago['created_at'].dt.date).agg({
        'quantite': ['mean', 'sum', 'min', 'max']
    })
    daily_stats_two_weeks_ago.columns = ['Moyenne quotidienne', 'Total quotidien', 'Minimum quotidien', 'Maximum quotidien']
    daily_stats_two_weeks_ago.reset_index(inplace=True)
    min_day_two_weeks_ago = daily_stats_two_weeks_ago[daily_stats_two_weeks_ago['Total quotidien'] == daily_stats_two_weeks_ago['Total quotidien'].min()]
    max_day_two_weeks_ago = daily_stats_two_weeks_ago[daily_stats_two_weeks_ago['Total quotidien'] == daily_stats_two_weeks_ago['Total quotidien'].max()]
    min_date_two_weeks_ago = min_day_two_weeks_ago['created_at'].iloc[0]
    min_quantity_two_weeks_ago = min_day_two_weeks_ago['Total quotidien'].iloc[0]
    max_date_two_weeks_ago = max_day_two_weeks_ago['created_at'].iloc[0]
    max_quantity_two_weeks_ago = max_day_two_weeks_ago['Total quotidien'].iloc[0]
    moyenne_two_weeks_ago = df_consommation_two_weeks_ago['quantite'].mean()
    total_two_weeks_ago = df_consommation_two_weeks_ago['quantite'].sum()
    moyenne_formatted_1 = "{:.2f}".format(moyenne_two_weeks_ago)
    total_formatted_1 = "{:.2f}".format(total_two_weeks_ago)
    min_val_formatted_1 = "{:.2f}".format(min_quantity_two_weeks_ago)
    max_val_formatted_1 = "{:.2f}".format(max_quantity_two_weeks_ago)
    # Comparer les statistiques entre la semaine précédente et la semaine encore avant
    if not df_consommation_last_week.empty and not df_consommation_two_weeks_ago.empty:
        # Comparer les statistiques et générez un message d'alerte si nécessaire
        alert_message = "Comparaison des statistiques de consommation :\n"
        if moyenne_last_week > moyenne_two_weeks_ago:
            alert_message += "La moyenne de la semaine précédente ({{moyenne_formatted}}) est supérieure à la semaine encore avant ({{moyenne_formatted_1}}).\n"
        elif moyenne_last_week < moyenne_two_weeks_ago:
            alert_message += "La moyenne de la semaine précédente ({{moyenne_formatted}}) est inférieure à la semaine encore avant ({{moyenne_formatted_1}}).\n"
        
        if total_last_week > total_two_weeks_ago:
            alert_message += "Le total de la semaine précédente ({{total_formatted}}) est supérieur à la semaine encore avant ({{total_formatted_1}}).\n"
        elif total_last_week < total_two_weeks_ago:
            alert_message += "Le total de la semaine précédente ({{total_formatted}}) est inférieur à la semaine encore avant ({{total_formatted_1}}).\n"
        
        if min_quantity_last_week > min_quantity_two_weeks_ago:
            alert_message += "La consommation minimale de la semaine précédente ({{min_val_formatted}}) est supérieure à la semaine encore avant ({{min_val_formatted_1}}).\n"
        elif min_quantity_last_week < min_quantity_two_weeks_ago:
            alert_message += "La consommation minimale de la semaine précédente ({{min_val_formatted}}) est inférieure à la semaine encore avant ({{min_val_formatted_1}}).\n"
        
        if max_quantity_last_week > max_quantity_two_weeks_ago:
            alert_message += "La consommation maximale de la semaine précédente ({{max_val_formatted}}) observée le ({{min_date_last_week}}) est supérieure à la semaine encore avant ({{max_val_formatted_1}}) observée le ({{min_date_two_weeks_ago}}).\n"
        elif max_quantity_last_week < max_quantity_two_weeks_ago:
            alert_message += "La consommation maximale de la semaine précédente ({{max_val_formatted}}) observée le ({{max_date_last_week}}) est inférieure à la semaine encore avant ({{max_val_formatted_1}}) observée le ({{max_date_two_weeks_ago}})..\n"
        
        # Créez une alerte si une comparaison est différente
        if "supérieure" in alert_message or "inférieure" in alert_message:
            alert = Alert.objects.create(
                intitule="Alerte de comparaison de consommation",
                message=alert_message,
            )
            alert.save()

def surconsommation(user_id):
    traiter_surconsommation.delay(user_id)  # Appel à la tâche asynchrone

# Fonction pour planifier l'exécution de surconsommation
def planifier_surconsommation():
    now = datetime.today()
    heure_execution = now.replace(hour=11, minute=10, second=0, microsecond=0)
    
    # Planifier l'exécution de traiter_surconsommation à 21h00 tous les jours
    traiter_surconsommation.apply_async(eta=heure_execution)