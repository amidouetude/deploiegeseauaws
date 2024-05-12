from rest_framework.serializers import ModelSerializer
from conso.models import Consommation, Localisation

class ConsommationSerializer(ModelSerializer):
 
    class Meta:
        model = Consommation
        fields = ['id','quantite', 'created_at', 'dispositif']


class LocalSerializer(ModelSerializer):
 
    class Meta:
        model = Localisation
        fields = ['id','latitude', 'longitude','dispositif']