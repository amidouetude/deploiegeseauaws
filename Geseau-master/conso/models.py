from datetime import date, datetime, timedelta
import random
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum

class Entreprise(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    nom_societe = models.CharField(default ="Nom de la societe", max_length=100, null=True, blank=True, verbose_name="Nom de l'entreprise ou de la société")
    telephone = models.CharField(default ="00000000", max_length=20,null=True, blank=True,verbose_name="Numéro de téléphone")
    domaine_act = models.CharField(default ="Domaine d'activité", max_length=100, null=True, blank=True, verbose_name="Domaine d'activité")
    localite = models.CharField(default ="Localite de la societe", max_length=100, null=True, blank=True, verbose_name="Localisation")






    
class Section(models.Model):
    entreprise = models.ForeignKey(Entreprise, null=True, blank=True, on_delete=models.CASCADE)
    nom_section = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nom de la section")
    description = models.TextField(null=True, blank=True, verbose_name="Description")
    class Meta:
        unique_together = ('entreprise', 'nom_section')
    def __str__(self):
        return self.nom_section
    
""" class Variable(models.Model):
    libelle = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nom de la variable")
    unite_mesure = models.CharField(max_length=100, null=True, blank=True,verbose_name="Unité de mesure de la variable")
    def __str__(self):
        return self.libelle """
    
    
class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    nom_client = models.CharField(default ="Votre nom de famille", max_length=100, null=True, blank=True, verbose_name="Votre nom")
    prenom_client = models.CharField(default ="Votre prenom", max_length=100, null=True, blank=True, verbose_name="Votre prénom")
    entreprise = models.ForeignKey(Entreprise, null=True, blank=True, on_delete=models.CASCADE)
    activite = models.CharField(default ="Quelle travail exercez-vous??", max_length=100, null=True, blank=True, verbose_name="Le travail que vous faite")
    def __str__(self):
        return f"{self.nom_client} {self.prenom_client}"
    def get_daily_consumption(self):
        today = datetime.now().date()
        return Consommation.objects.filter(dispositif=self.dispositif, created_at__date=today).aggregate(Sum('quantite'))['quantite__sum'] or 0

    def get_weekly_consumption(self):
        today = datetime.now().date()
        start_week = today - timedelta(days=today.weekday())
        return Consommation.objects.filter(dispositif=self.dispositif, created_at__date__range=[start_week, today]).aggregate(Sum('quantite'))['quantite__sum'] or 0

    def get_monthly_consumption(self):
        today = datetime.now().date()
        start_month = today.replace(day=1)
        return Consommation.objects.filter(dispositif=self.dispositif, created_at__date__range=[start_month, today]).aggregate(Sum('quantite'))['quantite__sum'] or 0
    


class Dispositif(models.Model):
    #variable = models.ForeignKey(Variable, null=True, blank=True, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.CASCADE)
    numero_serie = models.CharField(max_length=100, null=True, blank=True, verbose_name="Numéro serie")
    nom_lieu = models.CharField(max_length=100,null=True,blank=True,verbose_name="Le lieu où se trouve le dispositif")    
    source_eau = models.CharField(max_length=100,null = True, blank=True, verbose_name="Source d'eau")
    class Meta:
        unique_together = ('section', 'nom_lieu')
    def __str__(self):
        return self.nom_lieu

class Localisation(models.Model):
    latitude=models.FloatField(null=True,blank=True)
    longitude=models.FloatField(null=True,blank=True)
    """ altitude=models.FloatField(null=True,blank=True)
    precision=models.FloatField(null=True,blank=True) """
    dispositif = models.ForeignKey(Dispositif, null=True, blank=True, on_delete=models.CASCADE)

    
class Consommation(models.Model):
    dispositif = models.ForeignKey(Dispositif, null=True, blank=True, on_delete=models.CASCADE)
    quantite = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True,null=True,blank=True)

class OperationFinanciere(models.Model):
    BUDGET = 'BUDGET'
    DEPENSE = 'DEPENSE'
    TYPE_OPERATION_CHOICES = [
        (BUDGET, 'Budget'),
        (DEPENSE, 'Dépense'),
    ]
    entreprise = models.ForeignKey(Entreprise, null=True, blank=True, on_delete=models.CASCADE)
    type_operation = models.CharField(max_length=7, choices=TYPE_OPERATION_CHOICES, default=BUDGET)
    montant = models.FloatField(default=0)
    description = models.TextField(blank=True, null=True)
    date_ajout = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.get_type_operation_display()} - {self.montant}"


class Alert(models.Model):
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE, default=None)
    intitule = models.CharField(max_length=255)
    contenu = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    def __str__(self):
        return self.intitule
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save()  

""" class Message(models.Model):
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE, default=None)
    intitule = models.CharField(max_length=255)
    message = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    def __str__(self):
        return self.intitule   """


