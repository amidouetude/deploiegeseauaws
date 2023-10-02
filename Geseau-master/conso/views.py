import calendar
from django.db.models.signals import post_save
from django.dispatch import receiver
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone, time
from decimal import Decimal
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
import numpy as np
from scipy import stats
from conso.models import Alert, Budget, Depense, Section, Dispositif, Entreprise, Consommation
from conso.serializers import ConsommationSerializer
from .forms import SectionForm, DispositifForm, EntrepriseForm, UserProfileForm
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
import statsmodels.api as sm
from django.contrib import messages



##### Accès vers la page d'acceuil
#Code pour le calcul de la consommation totale

#Affichage de la conso dans l'index
def index(request):
    try:
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

            # Créez une liste des noms des jours de la semaine pour les six derniers jours
            # Créez une liste de noms de jours pour les 7 derniers jours
            dayli = datetime.today()
            last_seven_days = [dayli - timedelta(days=i) for i in range(6, -1, -1)]
            days_of_week = [day.strftime("%A") for day in last_seven_days]
            
            #determination de la consommation du jour
            daily_consommation = (Consommation.objects
                                .filter(dispositif__section__entreprise=user_entreprise_id,created_at__date__range=(start_of_day, end_of_day))
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
            twelve_months_ago = today - timedelta(days=365)
            monthly_data = (
                        Consommation.objects
                        .filter(dispositif__section__entreprise=user_entreprise_id,created_at__date__range=(twelve_months_ago, today))
                        .values('created_at__date')
                        .annotate(quantite_sum=Sum('quantite'))
                    )
        data_list = [{'day': item['created_at__date'], 'quantite_sum': item['quantite_sum']} for item in data]
        context = {
            'data': data_list,
            "sections": sections,
            "today": today,
            "days_of_week":days_of_week,
            "daily_consommation": daily_consommation,
            "weekly_consommation": weekly_consommation,
            "monthly_consommation": monthly_consommation,
            "daily_consommation_section": daily_consommation_section,
            "weekly_consommation_section": weekly_consommation_section,
            "monthly_consommation_section": monthly_consommation_section,
        }   
        
        return render(request, 'conso/index.html', context)
    except Exception as e:
        # Gérez l'exception ici, par exemple, affichez un message d'erreur ou redirigez l'utilisateur vers une page d'erreur.
        error_message = f"Une exception s'est produite : {e}"
        return render(request, 'conso/error.html', {'error_message': error_message})

##### Accès vers la vue des sections

#Accès vers la liste des sections
@login_required
def section(request):
    try:
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
                'total_consommation': total_consommation,
                'daily_consommation': daily_consommation,
                'weekly_consommation': weekly_consommation,
                'monthly_consommation': monthly_consommation
            })
        ahmed={'consom':consom}
        return render(request,'conso/section/sections.html',ahmed)
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})

#Creer une nouvelle section
@login_required
def add_section(request):
    try:
        if request.method == "POST":
            form=SectionForm(request.POST)
            if form.is_valid():
                section = form.save(commit = False)
                section.entreprise = Entreprise.objects.get(user_id=request.user.id)
                section.save()
                return redirect('section')
            else:
                return render(request,'conso/section/add_section.html',{'form':form})
        else:
            form = SectionForm()
        return render(request,'conso/section/add_section.html',{'form':form})
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})

#Modifier une section existante
@login_required
def update_section(request, pk):
    try:
        section = Section.objects.get(id=pk)
        form=SectionForm(instance=section)
        if request.method=="POST":
            form = SectionForm(request.POST,instance=section)
            if form.is_valid():
                form.save()
                return redirect('section')
            else:
                return render(request,'conso/section/update_update.html',{'form':form, 'section':section})
        else:
            form = SectionForm(instance=section)
        return render(request,'conso/section/update_section.html',{'form':form,'section':section})
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})

#Supprimer une section
@login_required
def delete_section(request, pk):
    try:
        section = Section.objects.get(id=pk)
        if request.method=="POST":
            section.delete()
            return redirect('section')
        context={'item':section}
        return render(request,'conso/section/delete_section.html',context)
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})

#Details sur une section
@login_required
def detail_section(request, pk):
    try:
        section = Section.objects.get(id=pk)
        dispos = Dispositif.objects.filter(section=section)
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
                    'total_consommation_dispositif': total_consommation_dispositif,
                    'daily_consommation_dispositif': daily_consommation_dispositif,
                    'weekly_consommation_dispositif': weekly_consommation_dispositif,
                    'monthly_consommation_dispositif': monthly_consommation_dispositif,
                })
        actuel = {
            'section': section,
            'consom_by_dispositif': consom_by_dispositif,
        }    
        return render(request, 'conso/section/detail_section.html', actuel) 
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})


##### Accès vers la vue des dispositifs
#Accès vers la liste des dispositifs
@login_required
def dispo(request):
    try:
        client = request.user
        dispos = Dispositif.objects.filter(section__entreprise__user=client)
        return render(request,'conso/dispositif/dispo.html',{'dispos':dispos})
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})

#Ajout d'un nouveau dispositf
@login_required
def add_dispo(request, section_pk):
    try:
        section = Section.objects.get(id=section_pk)
        if request.method == "POST":
            form=DispositifForm(request.POST)
            if form.is_valid():
                dispo=form.save(commit=False)
                dispo.section=section
                dispo.save()
                dispo_enr = form.cleaned_data.get('nom_lieu')
                return redirect('section')
            else:
                return render(request,'conso/dispositif/add_dispositif.html',{'form':form})
        else:
            initial_data = {'section': section.id}
            form = DispositifForm(initial=initial_data)
        return render(request,'conso/dispositif/add_dispositif.html',{'form':form})
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})

#Modifier un dispositif
@login_required
def update_dispo(request, pk):
    try:
        dispo = Dispositif.objects.get(id=pk)
        form=DispositifForm(instance=dispo)
        if request.method=="POST":
            form = DispositifForm(request.POST, instance=dispo)
            if form.is_valid():
                form.save()
                return redirect('section')
            else:
                return render(request,'conso/dispositif/update_dispositif.html',{'form':form,'dispo':dispo})
        return render(request,'conso/dispositif/update_dispositif.html',{'form':form,'dispo':dispo})
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})

#Supprimer un dispositif
@login_required
def delete_dispo(request, pk):
    try:
        dispo = Dispositif.objects.get(id=pk)
        if request.method == "POST":
            dispo.delete()
            return redirect('section')
        context={'item':dispo}
        return render(request,'conso/dispositif/delete_dispositif.html',context)
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})


##### Accès vers la vue de FAQ
def faq(request):
    return render(request,'conso/faq.html')

##### Accès vers la vue d'inscription sur la plateforme
def register(request):
    form = forms.UserRegistrationForm()
    if request.method == 'POST':
        form = forms.UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Entreprise.objects.create(user=user)
            # auto-login user
            login(request, user)
            return redirect('login')
    return render(request, 'conso/profil/register.html', context={'form': form})


#### Accès vers la vue de connexion
def login_views(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request,username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            return redirect('login')
    return render(request, 'conso/profil/login.html')


##### Accès vers la vue de deconnexion
@login_required
def logout_views(request):
    logout(request)
    return redirect('login')


##### Accès vers la vue du profil utilisateur
@login_required(login_url='login')
def profil_views(request):
    entreprise = Entreprise.objects.get(user=request.user)
    consommation = Consommation.objects.filter(dispositif__section__entreprise=entreprise).aggregate(Sum('quantite'))['quantite__sum']
    consommation_ONEA = Consommation.objects.filter(dispositif__source_eau="ONEA", dispositif__section__entreprise=entreprise).aggregate(Sum('quantite'))['quantite__sum']
    consommation_Forage = Consommation.objects.filter(dispositif__source_eau="Forage", dispositif__section__entreprise=entreprise).aggregate(Sum('quantite'))['quantite__sum']
    
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
    context = {
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
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Mettre à jour la session de l'utilisateur pour éviter la déconnexion
            update_session_auth_hash(request, user)
            return redirect('profil')  # Rediriger vers la page de profil ou une autre page de confirmation
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'conso/profil/password.html', {'form': form})


#####Accès aux vues vers le calcul de la consommation

@login_required

##### Accès vers la vue des historiques
# Historique consommation générale
def historique(request):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    mega = {}

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

        context = {
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

    return render(request, 'conso/suivi/historique.html', {'mega': mega})


@login_required
def ConsDispo(request,pk):
    try:
        dispositif = Dispositif.objects.get(id=pk)
        client = request.user
        dispos = Dispositif.objects.filter(section__entreprise__user=client)
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
        #Consommation des 12 derniers mois
        ahmed = {'data': data_list,
                "dispositif":dispositif,
                "dispos":dispos,
                "today":today,
                "daily_consommation":daily_consommation,
                "weekly_consommation":weekly_consommation,
                "monthly_consommation":monthly_consommation,
                }
        return render(request,'conso/consommation/dispositif.html',ahmed)
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})

@login_required
def ConsSection(request, pk):
    try:
        section = Section.objects.get(id=pk)
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

        for dispo in dispositifs:
            monthly_consommation_dispositif.append(Consommation.objects.filter(dispositif=dispo, created_at__date__range=(month_start, month_end)).aggregate(Sum('quantite'))['quantite__sum'])
            weekly_consommation_dispositif.append(Consommation.objects.filter(dispositif=dispo, created_at__date__range=(start_of_week, end_of_week)).aggregate(Sum('quantite'))['quantite__sum'])
            daily_consommation_dispositif.append(Consommation.objects.filter(dispositif=dispo, created_at__date__range=(start_of_day, end_of_day)).aggregate(Sum('quantite'))['quantite__sum'])
        rachid = {'data': data_list,
                "section":section,
                "sections":sections,
                "dispositifs":dispositifs,
                "today":today,
                "daily_consommation":daily_consommation,
                "weekly_consommation":weekly_consommation,
                "monthly_consommation":monthly_consommation,
                "daily_consommation_dispositif":daily_consommation_dispositif,
                "weekly_consommation_dispositif":weekly_consommation_dispositif,
                "monthly_consommation_dispositif":monthly_consommation_dispositif,
                }
        return render(request,'conso/consommation/section.html',rachid)
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})

def is_stationary(series):
    # Vous pouvez utiliser un test de stationnarité comme le test ADF ici
    # Retourne True si la série est stationnaire, False sinon
    # Par exemple, si vous utilisez statsmodels:
    from statsmodels.tsa.stattools import adfuller
    result = adfuller(series)
    return result[1] <= 0.05



def prevision(request):
    try:
        user_id = request.user.id
        user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
        consommations = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise_id)
        
        if not consommations:
            messages.warning(request, "Aucune donnée de consommation disponible pour cette entreprise.")
            return render(request, "conso/suivi/prevision.html")
        
        df = pd.DataFrame(list(consommations.values('created_at', 'quantite')))

        if len(df) < 5:
            messages.warning(request, "Le nombre d'observations de consommation est insuffisant pour effectuer une prévision.")
            return render(request, "conso/suivi/prevision.html")
        
        # Agrégation quotidienne des données
        df['created_at'] = pd.to_datetime(df['created_at'])
        df.set_index('created_at', inplace=True)
        df_daily = df.resample('D').sum()

        # Gestion des données manquantes (interpolation linéaire)
        df_daily['quantite'].interpolate(method='linear', inplace=True)
        
        # Utilisez pmdarima pour trouver les meilleurs paramètres p, d, et q
        model = pm.auto_arima(df_daily['quantite'], seasonal=False, stepwise=True, trace=True)

        # Utilisez les paramètres trouvés pour ajuster le modèle ARIMA
        best_p, best_d, best_q = model.order
        results = arima_model(df_daily['quantite'], order=(best_p, best_d, best_q)).fit()

        # Prévision pour les 7 prochains jours
        forecast_days = 7
        forecast = results.forecast(steps=forecast_days)

        # Dates correspondantes
        start_date = df_daily.index[-1] + pd.DateOffset(days=1)
        end_date = start_date + pd.DateOffset(days=forecast_days - 1)
        date_range = pd.date_range(start_date, end_date)
        forecast_confidence = results.get_forecast(steps=forecast_days).conf_int()
        lower_values = forecast_confidence.iloc[:, 0]
        upper_values = forecast_confidence.iloc[:, 1]

        """ # Contrainte : Remplacer les valeurs négatives par zéro
        lower_values = lower_values.apply(lambda x: max(x, 0))
        upper_values = upper_values.apply(lambda x: max(x, 0))

        # Contrainte : Limiter l'écart à 10 % des valeurs prédites
        max_deviation = 0.1  # 10% de variation
        for i in range(len(forecast)):
            deviation = forecast[i] * max_deviation
            lower_bound = max(forecast[i] - deviation, 0)
            upper_bound = forecast[i] + deviation
            lower_values[i] = max(lower_values[i], lower_bound)
            upper_values[i] = upper_bound """

        # Créez une liste de tuples avec les dates et les prévisions
        forecast_data = list(zip(date_range, forecast, lower_values, upper_values))

        # Évaluation de la précision
        actual_values = df_daily['quantite'][-forecast_days:]
        mae = mean_absolute_error(actual_values, forecast)
        mse = mean_squared_error(actual_values, forecast)
        rmse_value = rmse(actual_values, forecast)
        pourcentage = mae/rmse_value
        pourcentage_mae = (mae / actual_values.mean()) * 100
        pourcentage_mse = (mse / (actual_values.mean() ** 2)) * 100
        pourcentage_rmse_value = (rmse_value / actual_values.mean()) * 100

        # Passer les données à la template
        context = {
            'forecast_data': forecast_data,
            'mae': pourcentage_mae,
            'mse': pourcentage_mse,
            'rmse': pourcentage_rmse_value,
            'pourcentage':pourcentage * 100,
        }
        return render(request, "conso/suivi/prevision.html",context)
    except Exception as e:
        # Gérer l'exception, par exemple, rediriger vers une page d'erreur
        return render(request, 'conso/error.html', {'error_message': str(e)})




def prevision_section(request,pk):
    ## 1. Obtenez toutes les données de consommation pour l'utilisateur connecté
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    consommations = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise_id)
    if not consommations:
        return None, None
    # 2. Agrégez les données de consommation par jour (sommation)
    consommations_par_jour = consommations.values('created_at__date').annotate(total_consommation=Sum('quantite'))
    # 3. Créez un DataFrame pandas à partir des données agrégées
    df = pd.DataFrame(consommations_par_jour)
    df.set_index('created_at__date', inplace=True)
    # 4. Analyse préliminaire de la série temporelle
    tendance = tendance = df.rolling(window=7).mean()  # Calcul de la tendance (par exemple, moyenne mobile)
    saisonnalite_hebdo = df - tendance  
    #Test de Duckey Fuller augmente
    result = sm.tsa.adfuller(saisonnalite_hebdo.dropna())
    p_value = result[1]
    if p_value < 0.05:
        has_trend_seasonality = True
    else:
        has_trend_seasonality = False
    
    if has_trend_seasonality:
    # Lissage exponentiel double (Holt-Winters) pour les séries avec tendance et saisonnalité
        model = sm.tsa.ExponentialSmoothing(df, seasonal='add', seasonal_periods=7, trend='add')
        fitted = model.fit()
    else:
    # Lissage exponentiel simple pour les séries sans tendance ni saisonnalité
        model = sm.tsa.ExponentialSmoothing(df, trend=None, seasonal=None)
        fitted = model.fit()

    residuals = df - fitted.fittedvalues
    steps=2
    forecast = fitted.forecast(steps=steps)
    if len(residuals) > 0 and isinstance(residuals.iloc[-1], (int, float)):
        prevision = forecast + residuals.iloc[-1]
    else :
        prevision = forecast
    return render(request, "conso/suivi/prevision_sect.html",{"forecast":prevision})
    

def prevision_best(request):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    consommations = Consommation.objects.filter(dispositif__section__entreprise=user_entreprise_id)
    
    if not consommations:
        return None, None
    
    df = pd.DataFrame(list(consommations.values('created_at', 'quantite')))
    
    # Agrégation quotidienne des données
    df['created_at'] = pd.to_datetime(df['created_at'])
    df.set_index('created_at', inplace=True)
    df_daily = df.resample('D').sum()

    # Utilisez pmdarima pour trouver les meilleurs paramètres p, d, et q
    model = pm.auto_arima(df_daily['quantite'], seasonal=False, stepwise=True, trace=True)

    # Utilisez les paramètres trouvés pour ajuster le modèle ARIMA
    best_p, best_d, best_q = model.order
    results = arima_model(df_daily['quantite'], order=(best_p, best_d, best_q)).fit()

    # Prévision pour les 7 prochains jours
    forecast_days = 7
    forecast = results.forecast(steps=forecast_days)

    # Dates correspondantes
    start_date = df_daily.index[-1] + pd.DateOffset(days=1)
    end_date = start_date + pd.DateOffset(days=forecast_days - 1)
    date_range = pd.date_range(start_date, end_date)
    forecast_confidence = results.get_forecast(steps=forecast_days).conf_int()
    lower_values = forecast_confidence.iloc[:, 0]
    upper_values = forecast_confidence.iloc[:, 1]

    # Créez une liste de tuples avec les dates et les prévisions
    forecast_data = list(zip(date_range, forecast, lower_values, upper_values))

    # Passer les données à la template
    context = {
        'forecast_data': forecast_data,
    }

    return render(request, 'conso/forecast/daily.html', context)


class ConsommationViewset(ModelViewSet): 
    serializer_class = ConsommationSerializer
    def get_queryset(self):
        return Consommation.objects.all()

@login_required
def budget(request):
    try:
        user = request.user
        user_entreprise = get_object_or_404(Entreprise, user=user)
        today = date.today()
        start_of_month = today.replace(day=1)
        end_of_month = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        start_of_period = datetime.combine(start_of_month, datetime.min.time())
        end_of_period = datetime.combine(end_of_month, datetime.max.time())

        total_consommation = (Consommation.objects
                                    .filter(dispositif__source_eau="ONEA", dispositif__section__entreprise=user_entreprise, created_at__date__range=(start_of_period, end_of_period))
                                    .aggregate(Sum('quantite'))['quantite__sum'] or Decimal('0'))
        montant_consommation = Decimal('500') * Decimal(total_consommation)

        # Obtenez ou créez le budget pour le mois en cours
        budget_obj, created = Budget.objects.get_or_create(
            entreprise=user_entreprise,
            date_debut=start_of_month,
            date_fin=end_of_month,
            defaults={'montant': Decimal('0')}
        )

        # Récupérez ou créez la dépense pour le mois en cours
        depense_obj, created = Depense.objects.get_or_create(
            entreprise=user_entreprise,
            date_debut=start_of_month,
            date_fin=end_of_month,
            defaults={'montant': Decimal('0')}
        )

        if request.method == 'POST':
            if 'budget' in request.POST:
                montant_budget = Decimal(request.POST['budget'])
                budget_obj.montant += montant_budget
                budget_obj.save()
                request.session['montant_budget'] = str(montant_budget)
                return HttpResponseRedirect(request.path)
            
            elif 'depense' in request.POST:
                montant_depense = Decimal(request.POST['depense'])
                depense_obj.montant += montant_depense
                depense_obj.save()
                request.session['montant_depense'] = str(montant_depense)
                return HttpResponseRedirect(request.path)

        reste_budget = budget_obj.montant - (montant_consommation + depense_obj.montant)

        seuils = [30, 50, 70, 80, 90, 95, 99, 100, 101]

        alertes = {}
        for seuil in seuils:
            if total_consommation <= Decimal(seuil):
                alertes[seuil] = f"Consommation inférieure ou égale à {seuil}%"
                # Envoyez l'alerte à l'utilisateur s'il atteint le seuil spécifique
                if total_consommation <= Decimal(seuil) and not Alert.objects.filter(intitule=f"Alerte budget : {seuil}%", entreprise=user_entreprise).exists():
                    alert = Alert(intitule=f"Alerte budget : {seuil}%", message=f"Consommation inférieure ou égale à {seuil}%", entreprise=user_entreprise)
                    alert.save()
            else:
                alertes[seuil] = f"Consommation supérieure à {seuil}%"

        context = {
            'budget_defini': True,
            'montant_budget': budget_obj.montant,
            'depense_defini': depense_obj.montant > 0,
            'montant_depense': depense_obj.montant,
            'period_consommation': total_consommation,
            'montant_consommation': montant_consommation,
            'reste_budget': reste_budget,
            'alertes': alertes,
            "start_of_period": start_of_period,
            "end_of_period": end_of_period,
        }
        return render(request, 'conso/suivi/budget.html', context)
    except Exception as e:
        return render(request, 'conso/error.html', {'error_message': str(e)})


@login_required
def fuite(request):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    sections = Section.objects.filter(entreprise_id=user_entreprise_id)

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

        total_consommation = (Consommation.objects
                              .filter(dispositif__section=section, created_at__date=datetime.now().date(),
                                      created_at__time__gte=heure_debut, created_at__time__lte=heure_fin)
                              .aggregate(Sum('quantite'))['quantite__sum'])

        if total_consommation is None:
            total_consommation = 0

        if total_consommation > 0:
            message_alerte = f"Alerte de fuite dans la section {section.nom_section}. Une consommation de {total_consommation} litres a été enregistrée."
            alert = Alert(entreprise=user_entreprise_id, intitule="Fuite", message=message_alerte)
            alert.save()

        context = {
            "entreprise": user_entreprise_id,
            "sections": sections,
            "section": section,
            "total_consommation": total_consommation,
            "heure_debut": heure_debut,
            "heure_fin": heure_fin,
        }
        return render(request, 'conso/suivi/fuite.html', context)

    context = {
        "entreprise": user_entreprise_id,
        "sections": sections,
    }
    return render(request, 'conso/suivi/fuite.html', context)




@login_required
def alert(request):
    user_id = request.user.id
    user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
    alerts = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).order_by('-date_creation')
    alert_count = alerts.count()
    return render(request, 'conso/alert.html', {'alerts': alerts, 'alert_count': alert_count})
    

@login_required
def read_alert(request, pk):
    try:
        user_id = request.user.id
        user_entreprise_id = get_object_or_404(Entreprise, user_id=user_id)
        alert = get_object_or_404(Alert, id=pk)
        alert.is_read = True
        alert.save()
        alerts_count = Alert.objects.filter(entreprise=user_entreprise_id, is_read=False).count()
        return render(request, 'conso/lecture.html', {'alert': alert, 'alerts_count': alerts_count})
    except Exception as e:
        return render(request, 'conso/error.html', {'error_message': str(e)})

@login_required
def marquer_lue(request, pk):
    try:
        alert = get_object_or_404(Alert, id=pk)
        alert.is_read = True
        alert.save()
        return redirect('alert')
    except Exception as e:
        return render(request, 'conso/error.html', {'error_message': str(e)})
