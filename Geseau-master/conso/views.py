from django.views.decorators.http import require_POST
import calendar
from prophet import Prophet
from django.utils.timezone import make_aware
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from django.db.models.signals import post_save
from collections import defaultdict
from datetime import date, datetime, timedelta
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
import numpy as np
from conso.models import Alert, OperationFinanciere, Localisation, Section, Dispositif, Entreprise, Consommation, Client
from conso.serializers import ConsommationSerializer, IsAdminUserOnly, LocalSerializer
from .forms import ClientForm, LocalisationForm, SectionForm, DispositifForm, EntrepriseForm, UpdateClientProfileForm, UpdateUserForm, UserProfileForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from rest_framework.viewsets import ModelViewSet
from . import forms
import pandas as pd
import pmdarima as pm
from statsmodels.tools.eval_measures import rmse
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.arima.model import ARIMA as arima_model
import openpyxl
from django.contrib import messages
from rest_framework.decorators import permission_classes
#import locale

from django.shortcuts import render
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

def reset_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return render(request, 'conso/profil/password_reset.html', {'error': 'Email not found.'})

        # Generate reset password token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_link = f"http://{request.get_host()}/reset_password/{uid}/{token}/"

        # Print reset link to console for debugging
        print(f"Generated reset link: {reset_link}")

        # Render the password reset done template with reset_link
        return render(request, 'conso/profil/password_reset_done.html', {'reset_link': reset_link})

    return render(request, 'conso/profil/password_reset.html')



class ConsommationViewset(ModelViewSet): 
    serializer_class = ConsommationSerializer
    permission_classes = [IsAdminUserOnly]

    def get_queryset(self):
        return Consommation.objects.all()

##### Accès vers les dashbaords et correspondants

#Accès au dashboard principale
def index(request):
    #locale.setlocale(locale.LC_TIME, 'fr_FR')
    if request.user.is_authenticated:
        user_id = request.user.id
        user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
        sections = Section.objects.filter(entreprise_id=user_entreprise_id)
        today = date.today()
        start_date = today - timedelta(days=6)
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        month_start = today.replace(day=1)
        month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        thisday = datetime.today()
        start_of_week = thisday - timedelta(days=thisday.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        data = []  
        
        #determination de la consommation du jour
        daily_consommation = (Consommation.objects
                            .filter(dispositif__section__entreprise=user_entreprise_id,created_at__range=(start_of_day, end_of_day))
                            .aggregate(Sum('quantite'))['quantite__sum'])
        if daily_consommation is None:
            daily_consommation = 0 
        
        #determination de la consommation du jour
        weekly_consommation = (Consommation.objects
                            .filter(dispositif__section__entreprise=user_entreprise_id,
                                    created_at__date__range=[start_of_week, end_of_week])
                            .aggregate(Sum('quantite'))['quantite__sum'])
        if weekly_consommation is None:
            weekly_consommation = 0

        
        daily_consommation_section = []
        weekly_consommation_section = []
        monthly_consommation_section = []
        
        for section in sections:
            monthly_consommation_section.append(Consommation.objects.filter(dispositif__section=section, created_at__date__range=(month_start, month_end)).aggregate(Sum('quantite'))['quantite__sum'])
            weekly_consommation_section.append(Consommation.objects.filter(dispositif__section=section, created_at__date__range=(start_of_week, end_of_week)).aggregate(Sum('quantite'))['quantite__sum'])
            daily_consommation_section.append(Consommation.objects.filter(dispositif__section=section, created_at__date__range=(start_of_day, end_of_day)).aggregate(Sum('quantite'))['quantite__sum'])
                
        #Determination de la consommation du mois
        monthly_consommation = (Consommation.objects
                            .filter(dispositif__section__entreprise=user_entreprise_id,
                            created_at__date__range=(month_start, month_end))
                            .aggregate(Sum('quantite'))['quantite__sum'])
        if monthly_consommation is None:
            monthly_consommation = 0

        #determination de la consommation des 07 derniers jours
        data = (
                    Consommation.objects
                    .filter(dispositif__section__entreprise=user_entreprise_id,created_at__date__range=(start_date, today))
                    .values('created_at__date')
                    .annotate(quantite_sum=Sum('quantite'))
                )
        #Consommation mensuelle
        alert_count = 0
        alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
        data_list = [{'day': item['created_at__date'], 'quantite_sum': item['quantite_sum']} for item in data]
        nom_jour = today.strftime("%A %d %B %Y")

        # Récupération des consommations
        consommations = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise_id)
        # Création du DataFrame
        df = pd.DataFrame(list(consommations.exclude(created_at__isnull=True).values('created_at', 'quantite')))
        # Vérification si le DataFrame n'est pas vide
        if not df.empty:
            # Assure-toi que 'created_at' est au format datetime
            df['created_at'] = pd.to_datetime(df['created_at'])
            # Agrégation quotidienne des données
            df.set_index('created_at', inplace=True)
            df_daily = df.resample('D').sum()
            # Obtention des dates et quantités
            raw_dates = df_daily.index.strftime('%Y-%m-%d').tolist()
            raw_quantities = df_daily['quantite'].tolist()
            # Création de la liste pour affichage
            daily = list(zip(raw_dates, raw_quantities))
        else:
            # Affecte une liste vide si le DataFrame est vide
            daily = []

        context = {
            "alert_count":alert_count,
            'data': data_list,
            "sections": sections,
            "today": nom_jour,
            "daily_consommation": round(daily_consommation,3),
            "weekly_consommation": round(weekly_consommation,3),
            "monthly_consommation": round(monthly_consommation,3),
            'daily':daily,
            "daily_consommation_section": [round(x, 3) if x is not None else 0 for x in daily_consommation_section],
            "weekly_consommation_section": [round(x, 3) if x is not None else 0 for x in weekly_consommation_section],
            "monthly_consommation_section": [round(x, 3) if x is not None else 0 for x in monthly_consommation_section],
        }   
    
    return render(request, 'conso/index.html', context)


####Accès vers la vues des dashboards
#Consommation par dispositif
@login_required
def ConsDispo(request,pk):
    #locale.setlocale(locale.LC_TIME, 'fr_FR')
    dispositif = Dispositif.objects.get(id=pk)
    client = request.user
    dispos = Dispositif.objects.filter(section__entreprise__user=client)
    alert_count = Alert.objects.filter(entreprise__user=client, is_read=False).count()
    end_date = date.today()
    start_date = end_date - timedelta(days=6)
    #determination du jour
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())
    month_start = today.replace(day=1)
    next_month = month_start.replace(month=month_start.month % 12 + 1, year=month_start.year + month_start.month // 12)
    month_end = next_month - timedelta(days=1)
    thisday = datetime.today()
    start_of_week = thisday - timedelta(days=thisday.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    #Consommation du jour
    daily_consommation = Consommation.objects.filter(dispositif=dispositif,created_at__date__range=(start_of_day, end_of_day)).aggregate(Sum('quantite'))['quantite__sum']
    if daily_consommation is None:
        daily_consommation = 0
        #determination de la consommation de la semaine
    weekly_consommation = (Consommation.objects
                            .filter(dispositif=dispositif,created_at__date__range=(start_of_week, end_of_week))
                            .aggregate(Sum('quantite'))['quantite__sum'])
    if weekly_consommation is None:
        weekly_consommation = 0 
    #Consommation du mois
    monthly_consommation = (Consommation.objects
                                .filter(dispositif=dispositif,created_at__date__range=(month_start, month_end))
                                .aggregate(Sum('quantite'))['quantite__sum'])
    if monthly_consommation is None:
        monthly_consommation = 0

    #Consommation des 07 derniers
    data = (
            Consommation.objects
            .filter(dispositif=dispositif,created_at__date__range=(start_date, end_date))
            .values('created_at__date')
            .annotate(quantite_sum=Sum('quantite'))
        )
    data_list = [{'day': item['created_at__date'], 'quantite_sum': item['quantite_sum']} for item in data]
    nom_jour = today.strftime("%A %d %B %Y")

    consommations = Consommation.objects.filter(dispositif=dispositif)
    df = pd.DataFrame(list(consommations.values('created_at', 'quantite')))
    # Agrégation quotidienne des données
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'])
        df.set_index('created_at', inplace=True)
        df_daily = df.resample('D').sum()

        raw_dates = df_daily.index.strftime('%Y-%m-%d').tolist()
        raw_quantities = df_daily['quantite'].tolist()
        daily = list(zip(raw_dates,raw_quantities))
    else:
        daily = []

    ahmed = {'data': data_list,
            'daily':daily,
            "alert_count":alert_count,
            "dispositif":dispositif,
            "dispos":dispos,
            "today":nom_jour,
            "daily_consommation":round(daily_consommation,3),
            "weekly_consommation":round(weekly_consommation,3),
            "monthly_consommation":round(monthly_consommation,3),
            }
    return render(request,'conso/consommation/dispositif.html',ahmed)

#consommation par section
@login_required
def ConsSection(request, pk):
    #locale.setlocale(locale.LC_TIME, 'fr_FR')
    section = Section.objects.get(id=pk)
    dayli = datetime.today()
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    sections = Section.objects.filter(entreprise_id=user_entreprise_id)
    dispositifs = Dispositif.objects.filter(section=section)
    end_date = date.today()
    start_date = end_date - timedelta(days=6)
    #determination du jour
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())
    month_start = today.replace(day=1)
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    thisday = datetime.today()
    start_of_week = thisday - timedelta(days=thisday.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    data = []
    #Consommation du jour
    daily_consommation = Consommation.objects.filter(dispositif__section=section,created_at__date__range=(start_of_day, end_of_day)).aggregate(Sum('quantite'))['quantite__sum']
    if daily_consommation is None:
        daily_consommation = 0
    #determination de la consommation de la semaine
    weekly_consommation = (Consommation.objects
                            .filter(dispositif__section=section,created_at__date__range=(start_of_week, end_of_week))
                            .aggregate(Sum('quantite'))['quantite__sum'])
    if weekly_consommation is None:
        weekly_consommation = 0 
    #Consommation du mois
    monthly_consommation = (Consommation.objects
                            .filter(dispositif__section=section,created_at__date__range=(month_start, month_end))
                            .aggregate(Sum('quantite'))['quantite__sum'])
    if monthly_consommation is None:
        monthly_consommation = 0
    
    #Consommation des 07 derniers jours
    data = (
            Consommation.objects
            .filter(dispositif__section=section,created_at__date__range=(start_date, end_date))
            .values('created_at__date')
            .annotate(quantite_sum=Sum('quantite'))
        )
    data_list = [{'day': item['created_at__date'], 'quantite_sum': item['quantite_sum']} for item in data]
    #Consommation des 12 derniers mois
    daily_consommation_dispositif = []
    weekly_consommation_dispositif = []
    monthly_consommation_dispositif = []
    nom_jour = today.strftime("%A %d %B %Y")
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    for dispo in dispositifs:
        monthly_consommation_dispositif.append(Consommation.objects.filter(dispositif=dispo, created_at__date__range=(month_start, month_end)).aggregate(Sum('quantite'))['quantite__sum'])
        weekly_consommation_dispositif.append(Consommation.objects.filter(dispositif=dispo, created_at__date__range=(start_of_week, end_of_week)).aggregate(Sum('quantite'))['quantite__sum'])
        daily_consommation_dispositif.append(Consommation.objects.filter(dispositif=dispo, created_at__date__range=(start_of_day, end_of_day)).aggregate(Sum('quantite'))['quantite__sum'])
    
        
    consommations = Consommation.objects.filter(dispositif__section=section)
    df = pd.DataFrame(list(consommations.values('created_at', 'quantite')))
    # Agrégation quotidienne des données
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'])
        df.set_index('created_at', inplace=True)
        df_daily = df.resample('D').sum()

        raw_dates = df_daily.index.strftime('%Y-%m-%d').tolist()
        raw_quantities = df_daily['quantite'].tolist()
        daily = list(zip(raw_dates,raw_quantities))
    else:
        daily = []
    
    rachid = {'data': data_list,
                'alert_count':alert_count,
                'daily':daily,
            "section":section,
            "sections":sections,
            "dispositifs":dispositifs,
            "today":nom_jour,
            "daily_consommation":round(daily_consommation,3),
            "weekly_consommation":round(weekly_consommation,3),
            "monthly_consommation":round(monthly_consommation,3),
            "daily_consommation_dispositif":[round(x, 3) if x is not None else 0 for x in  daily_consommation_dispositif],
            "weekly_consommation_dispositif":[round(x, 3) if x is not None else 0 for x in  weekly_consommation_dispositif],
            "monthly_consommation_dispositif":[round(x, 3) if x is not None else 0 for x in  monthly_consommation_dispositif],
            }
    return render(request,'conso/consommation/section.html',rachid)


##### Accès vers la vue des historiques
# Historique consommation générale
@login_required
def historique(request):
    user_id = request.user.id
    user_entreprise = get_object_or_404(Entreprise, user_id=user_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise, is_read=False).count()
    sections = Section.objects.filter(entreprise=user_entreprise)
    dispositifs = Dispositif.objects.filter(section__entreprise=user_entreprise)
    sources_eau = dispositifs.values('source_eau').distinct()
    mega = {}

    if request.method == 'POST':
        date_debut_str = request.POST.get('date_debut')
        date_fin_str = request.POST.get('date_fin')
        date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
        date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()

        if 'download' in request.POST:
            consommations = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise, created_at__date__range=(date_debut, date_fin))
            daily_totals = defaultdict(float)
            for consommation in consommations:
                date = consommation.created_at.date()
                key = (date, consommation.dispositif.source_eau, consommation.dispositif.nom_lieu, consommation.dispositif.section.nom_section)
                daily_totals[key] += consommation.quantite

            response = HttpResponse(content_type='application/ms-excel')
            response['Content-Disposition'] = 'attachment; filename="consommation_eau.xlsx"'
            workbook = openpyxl.Workbook()
            worksheet = workbook.active

            headers = ['Date', 'Nom Lieu', 'Nom Section', 'Source d\'Eau', 'Quantité']
            worksheet.append(headers)

            for key, total in daily_totals.items():
                date, source_eau, nom_lieu, nom_section = key
                row = [date, nom_lieu, nom_section, source_eau, total]
                worksheet.append(row)

            workbook.save(response)
            return response
        else:
            consommations = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise, created_at__date__range=(date_debut, date_fin))
            df_consommation = pd.DataFrame(list(consommations.values()))

            if df_consommation.empty:
                messages.error(request, "Aucune consommation enregistrée dans la période spécifiée.")
                return render(request, 'conso/suivi/historique.html', {'mega': mega, "alert_count": alert_count, 'sections': sections})

            df_consommation['created_at'] = pd.to_datetime(df_consommation['created_at'])

            daily_stats = df_consommation.groupby(df_consommation['created_at'].dt.date).agg({
                'quantite': ['mean', 'sum', 'min', 'max']
            })
            daily_stats.columns = ['Moyenne quotidienne', 'Total quotidien', 'Minimum quotidien', 'Maximum quotidien']
            daily_stats.reset_index(inplace=True)

            min_day = daily_stats[daily_stats['Total quotidien'] == daily_stats['Total quotidien'].min()]
            max_day = daily_stats[daily_stats['Total quotidien'] == daily_stats['Total quotidien'].max()]

            min_date = min_day['created_at'].iloc[0]
            min_quantity = min_day['Total quotidien'].iloc[0]
            max_date = max_day['created_at'].iloc[0]
            max_quantity = max_day['Total quotidien'].iloc[0]

            moyenne = df_consommation['quantite'].mean()
            total = df_consommation['quantite'].sum()

            consommation_par_section = []
            for section in sections:
                total_quantite = Consommation.objects.filter(dispositif__section=section, created_at__date__range=(date_debut, date_fin)).aggregate(total_quantite=Sum('quantite'))['total_quantite'] or 0
                consommation_par_section.append({'section': section, 'total_quantite': total_quantite})

            consommation_par_dispositif = []
            for dispositif in dispositifs:
                total_quantite = Consommation.objects.filter(dispositif=dispositif, created_at__date__range=(date_debut, date_fin)).aggregate(total_quantite=Sum('quantite'))['total_quantite'] or 0
                consommation_par_dispositif.append({'dispositif': dispositif, 'total_quantite': total_quantite})

            consommation_par_source_eau = []
            for source_eau in sources_eau:
                total_quantite = Consommation.objects.filter(dispositif__source_eau=source_eau['source_eau'], created_at__date__range=(date_debut, date_fin)).aggregate(total_quantite=Sum('quantite'))['total_quantite'] or 0
                consommation_par_source_eau.append({'source_eau': source_eau['source_eau'], 'total_quantite': total_quantite})

            context = {
                'alert_count': alert_count,
                'sections': sections,
                'moyenne': "{:.2f}".format(moyenne),
                'total': "{:.2f}".format(total),
                'min_date': min_date,
                'min_val': "{:.2f}".format(min_quantity),
                'max_date': max_date,
                'max_val': "{:.2f}".format(max_quantity),
                'daily_stats': daily_stats.to_dict(orient='records'),
                'consommation_par_section': consommation_par_section,
                'consommation_par_dispositif': consommation_par_dispositif,
                'consommation_par_source_eau': consommation_par_source_eau,
            }

            mega = {
                'context': context,
                'date_debut': date_debut,
                'date_fin': date_fin,
            }

    return render(request, 'conso/suivi/historique.html', {'mega': mega, 'alert_count': alert_count, 'sections': sections})

# Historique consommation par section
def hist_section(request,pk):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    mega = {}
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    section = get_object_or_404(Section, id=pk)
    sections = Section.objects.filter(entreprise_id=user_entreprise_id)
    if request.method == 'POST':
        date_debut_str = request.POST.get('date_debut')
        date_fin_str = request.POST.get('date_fin')
        date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
        date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()

        if 'download' in request.POST:
            # Traitement pour le téléchargement
            consommations = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise_id, created_at__date__range=(date_debut, date_fin))
            daily_totals = defaultdict(float)
            for consommation in consommations:
                date = consommation.created_at.date()
                key = (date, consommation.dispositif.source_eau, consommation.dispositif.nom_lieu, consommation.dispositif.section.nom_section)
                daily_totals[key] += consommation.quantite

            response = HttpResponse(content_type='application/ms-excel')
            response['Content-Disposition'] = 'attachment; filename="consommation_eau.xlsx"'
            workbook = openpyxl.Workbook()
            worksheet = workbook.active

            headers = ['Date', 'Nom Lieu', 'Nom Section', 'Source d\'Eau', 'Quantité']
            worksheet.append(headers)

            for key, total in daily_totals.items():
                date, source_eau, nom_lieu, nom_section = key
                row = [date, nom_lieu, nom_section, source_eau, total]
                worksheet.append(row)

            workbook.save(response)
            return response
        else:
                # Statistique descriptive quotidienne
            consommation_totale = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise_id, created_at__date__range=(date_debut, date_fin))
            df_consommation = pd.DataFrame(list(consommation_totale.values()))
            
            if df_consommation.empty:
                messages.error(request, "Aucune consommation enregistrée dans la période spécifiée.")
                return render(request, 'conso/suivi/historique.html', {'mega': mega, "alert_count":alert_count})


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

        context = {'alert_count':alert_count,
                   'section':section,
                   "sections":sections,
            'moyenne': moyenne_formatted,
            'total': total_formatted,
            'min_date': min_date,
            'min_val': min_val_formatted,
            'max_date': max_date,
            'max_val': max_val_formatted,
            'daily_stats': daily_stats.to_dict(orient='records'),
        }

        mega = {
            'context': context,
            'date_debut': date_debut,
            'date_fin': date_fin,
        }

    return render(request, 'conso/suivi/historique_section.html', {'mega': mega,"alert_count":alert_count,'section':section,"sections":sections,})

##### Accès vers la vue des previsions
# Prevision consommation générale
def prevision(request):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    consommations = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise_id)
    sections = Section.objects.filter(entreprise_id=user_entreprise_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()

    if not consommations:
        messages.warning(request, "Aucune donnée de consommation disponible pour cette entreprise.")
        return render(request, "conso/suivi/prevision.html")

    df = pd.DataFrame(list(consommations.values('created_at', 'quantite')))
    
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['created_at'] = df['created_at'].dt.tz_localize(None)  # Supprimer le fuseau horaire
    df.set_index('created_at', inplace=True)

    # Récupérer l'unité de temps depuis les paramètres GET
    unit = request.GET.get('unit', 'jour')

    # Définir les périodes minimales requises pour chaque granularité
    min_periods = {
        'heure': 24,
        'jour': 7,
        'mois': 12,
        'trimestre': 4,
        'semestre': 2,
        'année': 2
    }

    # Vérifier si les données sont suffisantes
    if unit == 'heure':
        if len(df) < min_periods['heure']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision.html")
        df_resampled = df.resample('H').sum().asfreq('H', fill_value=0).reset_index()
        periods = 24
        freq = 'H'
        titre = "Prévisions sur la consommation des 24 prochaines heures"
    elif unit == 'jour':
        if len(df) < min_periods['jour']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision.html")
        df_resampled = df.resample('D').sum().asfreq('D', fill_value=0).reset_index()
        periods = 7
        freq = 'D'
        titre = "Prévisions sur la consommation des 7 prochains jours"
    elif unit == 'mois':
        if len(df) < min_periods['mois']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision.html")
        df_resampled = df.resample('M').sum().asfreq('M', fill_value=0).reset_index()
        periods = 12
        freq = 'M'
        titre = "Prévisions sur la consommation des 12 prochains mois"
    elif unit == 'trimestre':
        if len(df) < min_periods['trimestre']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision.html")
        df_resampled = df.resample('Q').sum().asfreq('Q', fill_value=0).reset_index()
        periods = 4
        freq = 'Q'
        titre = "Prévisions sur la consommation des 4 prochains trimestres"
    elif unit == 'semestre':
        if len(df) < min_periods['semestre']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision.html")
        df_resampled = df.resample('2Q').sum().asfreq('2Q', fill_value=0).reset_index()
        periods = 2
        freq = '2Q'
        titre = "Prévisions sur la consommation des 2 prochains semestres"
    elif unit == 'année':
        if len(df) < min_periods['année']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision.html")
        df_resampled = df.resample('Y').sum().asfreq('Y', fill_value=0).reset_index()
        periods = 2
        freq = 'Y'
        titre = "Prévisions sur la consommation des 2 prochaines années"
    else:
        if len(df) < min_periods['jour']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision.html")
        df_resampled = df.resample('D').sum().asfreq('D', fill_value=0).reset_index()
        periods = 7
        freq = 'D'
        titre = "Prévisions sur la consommation des 7 prochains jours"

    # Vérifier si le DataFrame resamplé a suffisamment de données non-NaN
    if df_resampled.dropna().shape[0] < 2:
        messages.warning(request, "Le nombre de données non-NaN après resampling n'est pas suffisant pour effectuer une prévision.")
        return render(request, "conso/suivi/prevision.html")

    df_resampled.rename(columns={'created_at': 'ds', 'quantite': 'y'}, inplace=True)

    # Utilisation de Prophet pour la prévision
    model = Prophet()
    model.fit(df_resampled)
    
    future = model.make_future_dataframe(periods=periods, freq=freq)
    forecast = model.predict(future)

    # Extraction des prévisions et des intervalles de confiance
    forecast_data = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    forecast_data = forecast_data[forecast_data['ds'] > df_resampled['ds'].max()]  # Garder seulement les prévisions futures

    # Contrainte : Remplacer les valeurs négatives par zéro
    forecast_data['yhat_lower'] = forecast_data['yhat_lower'].apply(lambda x: max(x, 0))
    forecast_data['yhat_upper'] = forecast_data['yhat_upper'].apply(lambda x: max(x, 0))

    # Arrondir les valeurs à 3 décimales
    forecast_data['yhat'] = forecast_data['yhat'].round(3)
    forecast_data['yhat_lower'] = forecast_data['yhat_lower'].round(3)
    forecast_data['yhat_upper'] = forecast_data['yhat_upper'].round(3)

    # Création de la liste de tuples avec les dates et les prévisions
    forecast_data_tuples = list(zip(forecast_data['ds'], forecast_data['yhat'], forecast_data['yhat_lower'], forecast_data['yhat_upper']))
    forecast1 = list(zip(forecast_data['ds'], forecast_data['yhat']))

    # Passer les données à la template
    raw_dates = df_resampled['ds'].dt.strftime('%Y-%m-%d').tolist()
    raw_quantities = df_resampled['y'].tolist()
    daily = list(zip(raw_dates, raw_quantities))

    context = {
        'alert_count': alert_count,
        'daily': daily,
        'forecast_data': forecast_data_tuples,
        'forecast_data1': forecast1,
        'selected_unit': unit,
        'titre': titre,
        'sections':sections,
    }
    
    return render(request, "conso/suivi/prevision.html", context)

# Prevision consommation par section
def prevision_section(request, pk):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    section = get_object_or_404(Section, id=pk)
    sections = Section.objects.filter(entreprise_id=user_entreprise_id)
    consommations = Consommation.objects.filter(dispositif__section=section)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()

    if not consommations.exists():
        messages.warning(request, "Aucune donnée de consommation disponible pour cette section.")
        return render(request, "conso/suivi/prevision_section.html")
    

    df = pd.DataFrame(list(consommations.values('created_at', 'quantite')))
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['created_at'] = df['created_at'].dt.tz_localize(None)  # Supprimer le fuseau horaire
    df.set_index('created_at', inplace=True)

    # Récupérer l'unité de temps depuis les paramètres GET
    unit = request.GET.get('unit', 'jour')

    # Définir les périodes minimales requises pour chaque granularité
    min_periods = {
        'heure': 24,
        'jour': 7,
        'mois': 12,
        'trimestre': 4,
        'semestre': 2,
        'année': 2
    }

    # Vérifier si les données sont suffisantes
    if unit == 'heure':
        if len(df) < min_periods['heure']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision_section.html")
        df_resampled = df.resample('H').sum().asfreq('H', fill_value=0).reset_index()
        periods = 24
        freq = 'H'
        titre = "Prévisions sur la consommation des 24 prochaines heures"
    elif unit == 'jour':
        if len(df) < min_periods['jour']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision_section.html")
        df_resampled = df.resample('D').sum().asfreq('D', fill_value=0).reset_index()
        periods = 7
        freq = 'D'
        titre = "Prévisions sur la consommation des 7 prochains jours"
    elif unit == 'mois':
        if len(df) < min_periods['mois']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision_section.html")
        df_resampled = df.resample('M').sum().asfreq('M', fill_value=0).reset_index()
        periods = 12
        freq = 'M'
        titre = "Prévisions sur la consommation des 12 prochains mois"
    elif unit == 'trimestre':
        if len(df) < min_periods['trimestre']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision_section.html")
        df_resampled = df.resample('Q').sum().asfreq('Q', fill_value=0).reset_index()
        periods = 4
        freq = 'Q'
        titre = "Prévisions sur la consommation des 4 prochains trimestres"
    elif unit == 'semestre':
        if len(df) < min_periods['semestre']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision_section.html")
        df_resampled = df.resample('2Q').sum().asfreq('2Q', fill_value=0).reset_index()
        periods = 2
        freq = '2Q'
        titre = "Prévisions sur la consommation des 2 prochains semestres"
    elif unit == 'année':
        if len(df) < min_periods['année']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision_section.html")
        df_resampled = df.resample('Y').sum().asfreq('Y', fill_value=0).reset_index()
        periods = 2
        freq = 'Y'
        titre = "Prévisions sur la consommation des 2 prochaines années"
    else:
        if len(df) < min_periods['jour']:
            messages.warning(request, "Le nombre de vos données de consommation n'est pas suffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision_section.html")
        df_resampled = df.resample('D').sum().asfreq('D', fill_value=0).reset_index()
        periods = 7
        freq = 'D'
        titre = "Prévisions sur la consommation des 7 prochains jours"

    # Vérifier si le DataFrame resamplé a suffisamment de données non-NaN
    if df_resampled.dropna().shape[0] < 2:
        messages.warning(request, "Le nombre de données non-NaN après resampling n'est pas suffisant pour effectuer une prévision.")
        return render(request, "conso/suivi/prevision_section.html")

    df_resampled.rename(columns={'created_at': 'ds', 'quantite': 'y'}, inplace=True)

    # Utilisation de Prophet pour la prévision
    model = Prophet()
    model.fit(df_resampled)
    
    future = model.make_future_dataframe(periods=periods, freq=freq)
    forecast = model.predict(future)

    # Extraction des prévisions et des intervalles de confiance
    forecast_data = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    forecast_data = forecast_data[forecast_data['ds'] > df_resampled['ds'].max()]  # Garder seulement les prévisions futures

    # Contrainte : Remplacer les valeurs négatives par zéro
    forecast_data['yhat_lower'] = forecast_data['yhat_lower'].apply(lambda x: max(x, 0))
    forecast_data['yhat_upper'] = forecast_data['yhat_upper'].apply(lambda x: max(x, 0))

    # Arrondir les valeurs à 3 décimales
    forecast_data['yhat'] = forecast_data['yhat'].round(3)
    forecast_data['yhat_lower'] = forecast_data['yhat_lower'].round(3)
    forecast_data['yhat_upper'] = forecast_data['yhat_upper'].round(3)

    # Création de la liste de tuples avec les dates et les prévisions
    forecast_data_tuples = list(zip(forecast_data['ds'], forecast_data['yhat'], forecast_data['yhat_lower'], forecast_data['yhat_upper']))
    forecast1 = list(zip(forecast_data['ds'], forecast_data['yhat']))

    # Passer les données brutes à la template
    raw_dates = df_resampled['ds'].dt.strftime('%Y-%m-%d').tolist()
    raw_quantities = df_resampled['y'].tolist()
    daily = list(zip(raw_dates, raw_quantities))

    context = {
        'alert_count': alert_count,
        'section': section,
        'forecast_data_tuples': forecast_data_tuples,
        'forecast1': forecast1,
        'daily': daily,  # Ajout des données brutes
        'selected_unit': unit,
        'titre': titre,
        'sections': sections,
    }

    return render(request, 'conso/suivi/prevision_section.html', context)




####Api section
""" class SectionViewSet(viewsets.ModelViewSet):
    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        entreprise = self.request.user.entreprise
        return Section.objects.filter(entreprise=entreprise)

    def perform_create(self, serializer):
        serializer.save(entreprise=self.request.user.entreprise)

    def perform_update(self, serializer):
        if not check_section_access(self.request, self.get_object()):
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        serializer.save()
 """
##### Accès vers la vue des sections






#Accès vers la liste des sections
@login_required
def section(request):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    sections = Section.objects.filter(entreprise_id=user_entreprise_id)
    consom = []
    #determination du jour
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())
    #Determination de la semaine
    thisday = datetime.today()
    start_of_week = thisday - timedelta(days=thisday.weekday())
    end_of_week = start_of_week + timedelta(days=6)
#    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for section in sections:
        #Consommation générale par section
        total_consommation = Consommation.objects.filter(dispositif__section=section).aggregate(Sum('quantite'))['quantite__sum']
        if total_consommation is None:
            total_consommation = 0
        #Consommation par jour
        daily_consommation = Consommation.objects.filter(dispositif__section=section,created_at__date__range=(start_of_day, end_of_day)).aggregate(Sum('quantite'))['quantite__sum']
        if daily_consommation is None:
            daily_consommation = 0
        weekly_consommation = Consommation.objects.filter(dispositif__section=section,
            created_at__date__range=[start_of_week, end_of_week]
        ).values('created_at__date').aggregate(Sum('quantite'))['quantite__sum']
        if weekly_consommation is None:
            weekly_consommation = 0        
        month_start = today.replace(day=1)
        month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        monthly_consommation = Consommation.objects.filter(dispositif__section=section, created_at__date__range=(month_start, month_end)).aggregate(Sum('quantite'))['quantite__sum']
        if monthly_consommation is None:
            monthly_consommation = 0 


        consom.append({
            'section': section,
            'total_consommation': round(total_consommation,3),
            'daily_consommation': round(daily_consommation,3),
            'weekly_consommation': round(weekly_consommation,3),
            'monthly_consommation': round(monthly_consommation,3),
        })
    alert_count = 0
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    context={'consom':consom, 'alert_count':alert_count}
    return render(request,'conso/section/sections.html',context)

#Creer une nouvelle section
@login_required
def add_section(request):
    if request.method == "POST":
        form=SectionForm(request.POST)
        if form.is_valid():
            section = form.save(commit = False)
            section.entreprise = Entreprise.objects.get(user_id=request.user.id)
            section.save()
            return redirect('section')
        else:
            return render(request,'conso/section/add_section.html',context)
    else:
        form = SectionForm()
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    context ={'form':form,
              'alert_count':alert_count}
    return render(request,'conso/section/add_section.html',context)


def check_section_access(request, section):
    user = request.user
    if user.entreprise != section.entreprise:
        return False
    return True

#Modifier une section existante
@login_required
def update_section(request, pk):
    section = Section.objects.get(id=pk)
    if not check_section_access(request, section):
        return HttpResponseForbidden("Vous n'avez pas accès à cette section.")
    form=SectionForm(instance=section)
    if request.method=="POST":
        form = SectionForm(request.POST,instance=section)
        if form.is_valid():
            form.save()
            return redirect('section')
        else:
            return render(request,'conso/section/update_section.html',context)
    else:
        form = SectionForm(instance=section)
        user_id = request.user.id
        user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
        alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    context = {'form':form,
               'section':section,
               'alert_count':alert_count}
    return render(request,'conso/section/update_section.html',context)

#Supprimer une section
@login_required
def delete_section(request, pk):
    section = Section.objects.get(id=pk)
    if not check_section_access(request, section):
        return HttpResponseForbidden("Vous n'avez pas le droit de supprimer cette section.")
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    if request.method=="POST":
        section.delete()
        return redirect('section')
    context={'item':section,
             'alert_count':alert_count}
    return render(request,'conso/admin/delete_section.html',context)

#Details sur une section
@login_required
def detail_section(request, pk):
    section = Section.objects.get(id=pk)
    dispos = Dispositif.objects.filter(section=section)
    if not check_section_access(request, section):
        return HttpResponseForbidden("Vous n'avez pas accès à cette section.")
    consom_by_dispositif = []
    #determination du jour
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())
    #Determination de la semaine
    thisday = datetime.today()
    start_of_week = thisday - timedelta(days=thisday.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    #Determination du mois
    month_start = today.replace(day=1)
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    for dispo in dispos:
        total_consommation_dispositif = Consommation.objects.filter(dispositif=dispo).aggregate(Sum('quantite'))['quantite__sum']
        if total_consommation_dispositif is None:
            total_consommation_dispositif = 0
        #Consommation par jour
        daily_consommation_dispositif = Consommation.objects.filter(dispositif=dispo,created_at__date__range=(start_of_day, end_of_day)).aggregate(Sum('quantite'))['quantite__sum']
        if daily_consommation_dispositif is None:
            daily_consommation_dispositif = 0
        weekly_consommation_dispositif = Consommation.objects.filter(dispositif=dispo,
            created_at__date__range=[start_of_week, end_of_week]
        ).values('created_at__date').aggregate(Sum('quantite'))['quantite__sum']        
        if weekly_consommation_dispositif is None:
            weekly_consommation_dispositif = 0
        monthly_consommation_dispositif = Consommation.objects.filter(dispositif=dispo, created_at__date__range=(month_start, month_end)).aggregate(Sum('quantite'))['quantite__sum']
        if monthly_consommation_dispositif is None:
            monthly_consommation_dispositif = 0 

        consom_by_dispositif.append({
                'dispositif': dispo,
                'total_consommation_dispositif': round(total_consommation_dispositif,3),
                'daily_consommation_dispositif': round(daily_consommation_dispositif,3),
                'weekly_consommation_dispositif': round(weekly_consommation_dispositif,3),
                'monthly_consommation_dispositif': round(monthly_consommation_dispositif,3),
            })
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    context = {'alert_count':alert_count,
        'section': section,
        'consom_by_dispositif': consom_by_dispositif,
    }    
    return render(request, 'conso/section/detail_section.html', context) 
    

##### Accès vers la vue des dispositifs
#Accès vers la liste des dispositifs
@login_required
def dispo(request):
    client = request.user
    dispos = Dispositif.objects.filter(section__entreprise__user=client)
    alert_count = Alert.objects.filter(entreprise__user=client, is_read=False).count()
    localisationG = []

    # Parcourir tous les dispositifs et récupérer leur dernière localisation
    for dispo in dispos:
        # Récupérer la dernière localisation associée à ce dispositif s'il en existe
        last_localisation = Localisation.objects.filter(dispositif=dispo).order_by('-id').first()
        # Vérifier si une localisation existe pour ce dispositif
        if last_localisation:
            localisationG.append({
                'dispositif': dispo,
                'last_localisation': last_localisation
            })
    # Si des localisations ont été trouvées
    if localisationG:
        first_localisation = localisationG[0]  # Prendre le premier élément de la liste
    else:
        first_localisation = None  # Aucune localisation trouvée

    context = {
        'localisationG': localisationG,
        'first_localisation':first_localisation,
        'alert_count': alert_count
    }
    return render(request, 'conso/dispositif/dispo.html', context)

def check_dispo_access(request, dispo):
    user = request.user
    if user.entreprise != dispo.section.entreprise:
        return False
    return True

#Ajout d'un nouveau dispositf
@login_required
def add_dispo(request, section_pk):
    section = Section.objects.get(id=section_pk)
    form = None  # Initialize the form variable

    if request.method == "POST":
        form = DispositifForm(user=request.user, data=request.POST)
        if form.is_valid():
            dispo = form.save(commit=False)
            dispo.section = section
            dispo.save()
            dispo_enr = form.cleaned_data.get('nom_lieu')
            return redirect('section')
    else:
        initial_data = {'section': section.id}
        form = DispositifForm(user=request.user, initial=initial_data)

    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    context = {'form': form, 'alert_count': alert_count}
    return render(request, 'conso/dispositif/add_dispositif.html', context)

#Modifier un dispositif
@login_required
def update_dispo(request, pk):
    dispo = Dispositif.objects.get(id=pk)
    if not check_dispo_access(request, dispo):
        return HttpResponseForbidden("Vous n'avez pas accès à ce dispositif.")
    form = DispositifForm(request.user, instance=dispo)
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    if request.method=="POST":
        form = DispositifForm(request.user, request.POST, instance=dispo)
        if form.is_valid():
            form.save()
            return redirect('dispo')
        else:
            return render(request,'conso/dispositif/update_dispositif.html',context)
    context = {'form':form,
                'dispo':dispo,
                'alert_count':alert_count}
    return render(request,'conso/dispositif/update_dispositif.html',context)

#Supprimer un dispositif
@login_required
def delete_dispo(request, pk):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    dispo = Dispositif.objects.get(id=pk)
    if not check_dispo_access(request, dispo):
        return HttpResponseForbidden("Vous n'avez pas le droit de supprimer ce dispositif.")
    if request.method == "POST":
        dispo.delete()
        return redirect('section')
    context={'item':dispo,
             'alert_count':alert_count}
    return render(request,'conso/admin/delete_dispositif.html',context)


##### Accès vers la vue de FAQ
def faq(request):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    context = {'alert_count':alert_count}
    return render(request,'conso/faq.html',context)

##### Accès vers la vue d'inscription sur la plateforme
@permission_classes([IsAdminUserOnly])
def register(request):
    form = forms.UserRegistrationForm()
    if request.method == 'POST':
        form = forms.UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Entreprise.objects.create(user=user)
            # Auto-login utilisateur (vous pouvez supprimer ceci si vous ne voulez pas que l'utilisateur soit connecté automatiquement)
            login(request, user)
            return redirect('login')
    context = {'form': form}
    return render(request, 'conso/profil/register.html', context)


#### Accès vers la vue de connexion
def login_views(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_superuser:
                return redirect('/admin/')
            else:
                return redirect('index')
        else:
            return redirect('login')
    return render(request, 'conso/profil/login.html')

def chargement(request):
    return render(request, 'conso/profil/presentation.html')


##### Accès vers la vue de deconnexion
@login_required
def logout_views(request):
    logout(request)
    return redirect('charge')


##### Accès vers la vue du profil utilisateur
@login_required(login_url='login')
def profil_views(request):
    entreprise = Entreprise.objects.get(user=request.user)
    consommation = Consommation.objects.filter(dispositif__section__entreprise=entreprise).aggregate(Sum('quantite'))['quantite__sum']
    consommation = round(consommation, 3) if consommation is not None else None
    # Vérifiez si la source ONEA existe, puis calculez la consommation
    onea_exists = Consommation.objects.filter(dispositif__source_eau="ONEA", dispositif__section__entreprise=entreprise).exists()
    if onea_exists:
        consommation_ONEA = Consommation.objects.filter(dispositif__source_eau="ONEA", dispositif__section__entreprise=entreprise).aggregate(Sum('quantite'))['quantite__sum']
        consommation_ONEA = round(consommation_ONEA, 3) if consommation_ONEA is not None else None
    else:
        consommation_ONEA = "Vous n'utilisez pas encore cette source d'eau"
    
    # Vérifiez si la source Forage existe, puis calculez la consommation
    forage_exists = Consommation.objects.filter(dispositif__source_eau="Forage", dispositif__section__entreprise=entreprise).exists()
    if forage_exists:
        consommation_Forage = Consommation.objects.filter(dispositif__source_eau="Forage", dispositif__section__entreprise=entreprise).aggregate(Sum('quantite'))['quantite__sum']
        consommation_Forage = round(consommation_Forage, 3) if consommation_Forage is not None else None
    else:
        consommation_Forage = "Vous n'utilisez pas encore cette source d'eau"

    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, instance=request.user)
        entreprise_form = EntrepriseForm(request.POST, instance=request.user.entreprise)
        
        if user_form.is_valid() and entreprise_form.is_valid():
            user_form.save()
            entreprise_form.save()
            return redirect('profil')
    else:
        user_form = UserProfileForm(instance=request.user)
        entreprise_form = EntrepriseForm(instance=request.user.entreprise)
    alert_count = Alert.objects.filter(entreprise=entreprise, is_read=False).count()
    context = {'alert_count':alert_count,
        'entreprise': entreprise,
        'consommation': consommation,
        "consommation_ONEA":consommation_ONEA,
        "consommation_Forage":consommation_Forage,
        'user_form': user_form,
        'entreprise_form': entreprise_form,
    }
    return render(request, 'conso/profil/profil_views.html', context)

####Accès vers la vue de la modification du mot de passe
@login_required
def change_password(request):
    entreprise = Entreprise.objects.get(user=request.user)
    alert_count = Alert.objects.filter(entreprise=entreprise, is_read=False).count()
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Mettre à jour la session de l'utilisateur pour éviter la déconnexion
            update_session_auth_hash(request, user)
            return redirect('profil')  # Rediriger vers la page de profil ou une autre page de confirmation
    else:
        form = PasswordChangeForm(request.user)
    context = {'form': form,"alert_count":alert_count}
    return render(request, 'conso/profil/password.html', context)


#####Accès aux vues vers le calcul de la consommation




 
@login_required
def budget(request):
    user = request.user
    user_entreprise = get_object_or_404(Entreprise, user=user)
    alert_count = Alert.objects.filter(entreprise=user_entreprise, is_read=False).count()
    today = date.today()
    start_of_month = today.replace(day=1)
    end_of_month = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    start_of_period = datetime.combine(start_of_month, datetime.min.time())
    end_of_period = datetime.combine(end_of_month, datetime.max.time())

    total_consommation = (Consommation.objects
                          .filter(dispositif__source_eau="ONEA", dispositif__section__entreprise=user_entreprise)
                          .aggregate(Sum('quantite'))['quantite__sum'] or 0.0)
    montant_consommation = 1180.0 * total_consommation

    total_consommation = round(total_consommation, 3)
    montant_consommation = round(montant_consommation, 3)

    # On calcule le total du budget depuis le début
    total_budget = (OperationFinanciere.objects
                    .filter(entreprise=user_entreprise, type_operation=OperationFinanciere.BUDGET)
                    .aggregate(Sum('montant'))['montant__sum'] or 0.0)

    # On calcule le total des dépenses depuis le début
    total_depense = (OperationFinanciere.objects
                     .filter(entreprise=user_entreprise, type_operation=OperationFinanciere.DEPENSE)
                     .aggregate(Sum('montant'))['montant__sum'] or 0.0)
    
    if request.method == 'POST':
        if 'budget' in request.POST:
            montant_budget = float(request.POST['budget'])
            description_budget = request.POST.get('description_budget', '')
            OperationFinanciere.objects.create(entreprise=user_entreprise, type_operation=OperationFinanciere.BUDGET, montant=montant_budget, description=description_budget)
            request.session['montant_budget'] = str(montant_budget)
            alert_intitule = f"Nouveau budget : {montant_budget}"
            alert_contenu = f"Nouveau budget défini : {montant_budget}. Description : {description_budget}"
            if not Alert.objects.filter(intitule=alert_intitule, entreprise=user_entreprise).exists():
                alert = Alert(intitule=alert_intitule, contenu=alert_contenu, entreprise=user_entreprise)
                alert.save()
            return HttpResponseRedirect(request.path)
        
        elif 'depense' in request.POST:
            montant_depense = float(request.POST['depense'])
            description_depense = request.POST.get('description_depense', '')
            OperationFinanciere.objects.create(entreprise=user_entreprise, type_operation=OperationFinanciere.DEPENSE, montant=montant_depense, description=description_depense)
            request.session['montant_depense'] = str(montant_depense)
            alert_intitule = f"Nouvelle dépense {montant_depense}"
            alert_contenu = f"Vous venez d'effectuer une nouvelle dépense d'un montant de {montant_depense}. Description : {description_depense}"
            if not Alert.objects.filter(intitule=alert_intitule, entreprise=user_entreprise).exists():
                alert = Alert(intitule=alert_intitule, contenu=alert_contenu, entreprise=user_entreprise)
                alert.save()
            return HttpResponseRedirect(request.path)

    reste_budget = round(total_budget - (montant_consommation + total_depense), 3)

    alertes = {}

    if total_budget > 0.0:
        seuils = [30.0, 50.0, 70.0, 80.0, 90.0, 95.0, 99.0, 100.0, 101.0]
        for seuil in seuils:
            pourcentage_consomme = (total_depense + montant_consommation) / total_budget * 100
            if pourcentage_consomme >= seuil and not Alert.objects.filter(intitule=f"Alerte budget : {seuil}%", entreprise=user_entreprise).exists():
                alertes[seuil] = f"Vous venez d'atteindre {seuil}% du montant de votre budget alloué à la consommation en eau"
                alert = Alert(intitule=f"Alerte budget : {seuil}%", contenu=f"Consommation et dépenses combinées ont atteint {seuil}% du budget", entreprise=user_entreprise)
                alert.save()

    transactions = OperationFinanciere.objects.filter(entreprise=user_entreprise).order_by('-date_ajout')

    context = {
        'alert_count': alert_count,
        'budget_defini': total_budget > 0.0,
        'montant_budget': round(total_budget, 3),
        'depense_defini': round(total_depense, 3) > 0,
        'montant_depense': round(total_depense, 3),
        'alertes': alertes,
        'montant_consommation': montant_consommation,
        'reste_budget': reste_budget,
        'period_consommation': total_consommation,
        'transactions': transactions,
    }

    return render(request, 'conso/suivi/budget.html', context)



@login_required
def fuite(request):
    #locale.setlocale(locale.LC_TIME, 'fr_FR')
    today = date.today()
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    sections = Section.objects.filter(entreprise_id=user_entreprise_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()

    if request.method == 'POST':
        section_id = request.POST.get('section')
        heure_debut_str = request.POST.get('heure_debut')
        heure_fin_str = request.POST.get('heure_fin')

        section = Section.objects.filter(id=section_id).first()

        if section is None:
            return render(request, 'conso/error.html', {'error_message': "Section non trouvée."})

        try:
            heure_debut = datetime.strptime(heure_debut_str, '%H:%M')
            heure_fin = datetime.strptime(heure_fin_str, '%H:%M')
        except ValueError as e:
            return render(request, 'conso/error.html', {'error_message': "Format de l'heure invalide."})

        conso_objects = (Consommation.objects
             .filter(dispositif__section=section, created_at__date=datetime.now().date(),
                     created_at__time__gte=heure_debut, created_at__time__lte=heure_fin))

        total_consommation = conso_objects.aggregate(Sum('quantite'))['quantite__sum'] or 0
        dispositifs = Dispositif.objects.filter(id__in=conso_objects.values('dispositif'))

        total_consommation = round(total_consommation,3)


        if total_consommation > 0:
            message_alerte = (f"Bonjour, nous avons constaté une augmentation de votre consommation ce jour {today}. "
                  f"Cette augmentation a été constatée au niveau du dispositif placé {', '.join(dispo.nom_lieu for dispo in dispositifs)} de votre section nommée {section.nom_section}. "
                  f"Veuillez vérifier vos canalisations à partir de là. La quantité d'eau perdue durant la période vaut {total_consommation} mètres cubes. "
                  "Merci d'avoir fait confiance à Ges'eau et passez une agréable journée. Ges'eau, notre innovation, votre avantage.")
            alert = Alert(entreprise=user_entreprise_id, intitule="Fuite constatée", contenu=message_alerte)
            alert.save()
        else:
            message_alerte = f"Bonjour suite à votre requête, nous sommes ravis de vous informer que la section {section.nom_section} n'a pas enregistré de consommation durant la periode"
            f" de ce fait il n'y a pas de fuite à ce niveau."
            alert = Alert(entreprise=user_entreprise_id, intitule="Pas de fuite constatée", contenu=message_alerte)
            alert.save()

        context = {
            'alert_count': alert_count,
            "entreprise": user_entreprise_id,
            "sections": sections,
            "section": section,
            "total_consommation": total_consommation,
            "heure_debut": heure_debut,
            "heure_fin": heure_fin,
            "message_alerte": message_alerte,
            'alert_count': alert_count,
        }
        return render(request, 'conso/suivi/fuite.html', context)

    context = {
        'alert_count': alert_count,
        "entreprise": user_entreprise_id,
        "sections": sections,
    }
    return render(request, 'conso/suivi/fuite.html', context)


@login_required
def alert(request):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    # Récupérer toutes les alertes non lues
    alerts_nonlu = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).order_by('-date_creation')
    # Récupérer toutes les alertes
    alerts = Alert.objects.filter(entreprise=user_entreprise_id).order_by('-date_creation')
    # Compter le nombre d'alertes non lues
    alert_count = alerts_nonlu.count()
    return render(request, 'conso/alert/alert.html', {'alerts': alerts, 'alert_count': alert_count})


@login_required
def read_alert(request, pk):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alert = get_object_or_404(Alert, id=pk)
    # Marquer l'alerte comme lue si elle ne l'était pas déjà
    if not alert.is_read:
        alert.is_read = True
        alert.save()
    #Compter toutee les alertes non lues
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    return render(request, 'conso/alert/lecture.html', {'alert': alert,'alert_count':alert_count})






""" # Planifiez l'envoi de l'alerte chaque samedi à 09h
@scheduler.periodic_task(crontab(hour=9, minute=0, day_of_week=5))
def schedule_surconsommation_alert():
    send_surconsommation_alert() """



   
class LocalisationViewset(ModelViewSet): 
    serializer_class = LocalSerializer
    permission_classes = [IsAdminUserOnly]

    def get_queryset(self):
        return Localisation.objects.all()


def localisation(request, pk):
    dispositif = Dispositif.objects.get(id=pk)
    last_localisation = Localisation.objects.filter(dispositif=dispositif).order_by('-id').first()
    context = {
        'dispositif': dispositif,
        'last_localisation': last_localisation
    }

    return render(request, 'conso/dispositif/localisation.html', context)


def update_localisation(request, dispositif_id):
    dispositif = Dispositif.objects.get(id=dispositif_id)
    localisation = dispositif.localisation_set.last()
    if request.method == 'POST':
        form = LocalisationForm(request.POST, instance=localisation)
        if form.is_valid():
            form.save()
            return redirect('conso/dispositif/localisation.html', dispositif_id=dispositif_id)
    else:
        form = LocalisationForm(instance=localisation)
    context = {
        'dispositif': dispositif,
        'form': form
    }
    return render(request, 'conso/dispositif/localisation.html', context)



#Accès vers la liste des clients
@login_required
def client(request):
    user = request.user
    clients = Client.objects.filter(entreprise__user=user)
    alert_count = Alert.objects.filter(entreprise__user=user, is_read=False).count()

    consom = []
    today = datetime.now().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())
    thisday = datetime.today()
    start_of_week = thisday - timedelta(days=thisday.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    month_start = today.replace(day=1)
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])

    client_sections = defaultdict(list)

    for client in clients:
        dispositifs = Dispositif.objects.filter(client=client)
        for dispositif in dispositifs:
            section = dispositif.section.nom_section if dispositif.section else 'N/A'
            client_sections[(client, section)].append(dispositif)

    for (client, section), dispositifs in client_sections.items():
        total_consommation = Consommation.objects.filter(dispositif__in=dispositifs).aggregate(Sum('quantite'))['quantite__sum'] or 0
        daily_consommation = Consommation.objects.filter(dispositif__in=dispositifs, created_at__date__range=(start_of_day, end_of_day)).aggregate(Sum('quantite'))['quantite__sum'] or 0
        weekly_consommation = Consommation.objects.filter(dispositif__in=dispositifs, created_at__range=(start_of_week, end_of_week)).aggregate(Sum('quantite'))['quantite__sum'] or 0
        monthly_consommation = Consommation.objects.filter(dispositif__in=dispositifs, created_at__range=(month_start, month_end)).aggregate(Sum('quantite'))['quantite__sum'] or 0

        consom.append({
            'client': client,
            'section': section,
            'total_consommation': round(total_consommation, 3),
            'daily_consommation': round(daily_consommation, 3),
            'weekly_consommation': round(weekly_consommation, 3),
            'monthly_consommation': round(monthly_consommation, 3),
        })

    context = {'consom': consom, 'alert_count': alert_count}
    return render(request, 'conso/clients/liste_client.html', context)



@login_required
def add_client(request):
    user = request.user
    entreprise = user.entreprise  # Assurez-vous que l'utilisateur a une entreprise associée

    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.entreprise = entreprise
            client.save()  # Le signal post_save se chargera de créer l'utilisateur associé
            # Créer l'utilisateur associé
            user = User.objects.create_user(
                username=f"{client.nom_client}_{client.prenom_client}".lower(),
                first_name=client.nom_client,
                last_name=client.prenom_client,
                password=form.cleaned_data['password']  # Utilise le mot de passe par défaut
            )
            client.user = user
            client.save()

            return redirect('client')  # Redirigez vers la liste des clients après l'ajout
    else:
        form = ClientForm()

    return render(request, 'conso/clients/ajout_client.html', {'form': form})


def check_client_access(request, client):
    user = request.user
    if user.entreprise != client.entreprise:
        return False
    return True

#Modifier une section existante
@login_required
def update_client(request, pk):
    client = Client.objects.get(id=pk)
    if not check_client_access(request, client):
        return HttpResponseForbidden("Vous n'avez pas accès à cet client.")
    form=ClientForm(instance=client)
    if request.method=="POST":
        form = ClientForm(request.POST,instance=client)
        if form.is_valid():
            form.save()
            return redirect('client')
        else:
            return render(request,'conso/clients/update_client.html',context)
    else:
        form = ClientForm(instance=client)
        user_id = request.user.id
        user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
        alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    context = {'form':form,
               'client':client,
               'alert_count':alert_count}
    return render(request,'conso/clients/update_client.html',context)

#Supprimer un client
@login_required
def delete_client(request, pk):
    client = Client.objects.get(id=pk)
    if not check_client_access(request, client):
        return HttpResponseForbidden("Vous n'avez pas le droit de supprimer cet client.")
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    if request.method=="POST":
        client.delete()
        return redirect('client')
    context={'item':client,
             'alert_count':alert_count}
    return render(request,'conso/admin/delete_client.html',context)

#Details sur un client
@login_required
def detail_client(request, pk):
    client = Client.objects.get(id=pk)
    dispos = Dispositif.objects.filter(client=client)
    if not check_client_access(request, client):
        return HttpResponseForbidden("Vous n'avez pas accès à cet client.")
    consom_by_dispositif = []
    #determination du jour
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())
    #Determination de la semaine
    thisday = datetime.today()
    start_of_week = thisday - timedelta(days=thisday.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    #Determination du mois
    month_start = today.replace(day=1)
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    for dispo in dispos:
        total_consommation_dispositif = Consommation.objects.filter(dispositif=dispo).aggregate(Sum('quantite'))['quantite__sum']
        if total_consommation_dispositif is None:
            total_consommation_dispositif = 0
        #Consommation par jour
        daily_consommation_dispositif = Consommation.objects.filter(dispositif=dispo,created_at__date__range=(start_of_day, end_of_day)).aggregate(Sum('quantite'))['quantite__sum']
        if daily_consommation_dispositif is None:
            daily_consommation_dispositif = 0
        weekly_consommation_dispositif = Consommation.objects.filter(dispositif=dispo,
            created_at__date__range=[start_of_week, end_of_week]
        ).values('created_at__date').aggregate(Sum('quantite'))['quantite__sum']        
        if weekly_consommation_dispositif is None:
            weekly_consommation_dispositif = 0
        monthly_consommation_dispositif = Consommation.objects.filter(dispositif=dispo, created_at__date__range=(month_start, month_end)).aggregate(Sum('quantite'))['quantite__sum']
        if monthly_consommation_dispositif is None:
            monthly_consommation_dispositif = 0 

        consom_by_dispositif.append({
                'dispositif': dispo,
                'total_consommation_dispositif': round(total_consommation_dispositif,3),
                'daily_consommation_dispositif': round(daily_consommation_dispositif,3),
                'weekly_consommation_dispositif': round(weekly_consommation_dispositif,3),
                'monthly_consommation_dispositif': round(monthly_consommation_dispositif,3),
            })
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alert_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
    context = {'alert_count':alert_count,
        'client': client,
        'consom_by_dispositif': consom_by_dispositif,
    }    
    return render(request, 'conso/clients/detail_client.html', context) 
    
@login_required
def update_profile(request):
    user = request.user
    client = user.client

    if request.method == 'POST':
        user_form = UpdateUserForm(request.POST, instance=user)
        client_form = UpdateClientProfileForm(request.POST, instance=client)
        if user_form.is_valid() and client_form.is_valid():
            user_form.save()
            client_form.save()
            return redirect('client')  # Redirigez vers la liste des clients ou un autre endroit approprié
    else:
        user_form = UpdateUserForm(instance=user)
        client_form = UpdateClientProfileForm(instance=client)

    context = {
        'user_form': user_form,
        'client_form': client_form
    }

    return render(request, 'conso/clients/update_profile.html', context)


