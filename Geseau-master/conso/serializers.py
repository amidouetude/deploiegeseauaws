from rest_framework.serializers import ModelSerializer, SerializerMethodField
from rest_framework.permissions import BasePermission
from conso.models import Consommation, Localisation, Section, Dispositif, OperationFinanciere, Entreprise

from django.db.models import Sum

class WaterControlSerializer(ModelSerializer):
    remaining_budget = SerializerMethodField()
    electrovanne_status = SerializerMethodField()

    class Meta:
        model = Entreprise
        fields = ['remaining_budget', 'electrovanne_status']

    def get_remaining_budget(self, entreprise):
        # Calculer le budget total et les dépenses
        total_budget = OperationFinanciere.objects.filter(
            entreprise=entreprise, 
            type_operation=OperationFinanciere.BUDGET
        ).aggregate(Sum('montant'))['montant__sum'] or 0.0

        total_depense = OperationFinanciere.objects.filter(
            entreprise=entreprise, 
            type_operation=OperationFinanciere.DEPENSE
        ).aggregate(Sum('montant'))['montant__sum'] or 0.0

        # Calcul de la consommation totale
        total_consommation = Consommation.objects.filter(
            dispositif__source_eau="ONEA", 
            dispositif__section__entreprise=entreprise
        ).aggregate(Sum('quantite'))['quantite__sum'] or 0.0

        montant_consommation = 1180.0 * total_consommation
        remaining_budget = round(total_budget - (montant_consommation + total_depense), 3)
        
        return remaining_budget

    def get_electrovanne_status(self, entreprise):
        remaining_budget = self.get_remaining_budget(entreprise)
        
        if remaining_budget <= 0:
            # Créer une alerte si le budget est insuffisant
            Alert.objects.create(
                entreprise=entreprise,
                intitule="Electrovanne coupée",
                contenu="Le solde est insuffisant, l'électrovanne a été coupée pour limiter la consommation."
            )
            return "Fermée"
        else:
            return "Ouverte"


class SectionSerializer(ModelSerializer):
    class Meta:
        model = Section
        fields = '__all__'



class DispositifSerializer(ModelSerializer):
    class Meta:
        model = Dispositif
        fields = '__all__'


class IsAdminUserOnly(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff
    
    
class ConsommationSerializer(ModelSerializer):
 
    class Meta:
        model = Consommation
        fields = ['id','quantite', 'created_at', 'dispositif']


class LocalSerializer(ModelSerializer):
 
    class Meta:
        model = Localisation
        fields = ['id','latitude', 'longitude','dispositif']

