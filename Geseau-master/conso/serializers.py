from rest_framework.serializers import ModelSerializer
from conso.models import Consommation, Dispositif

class ConsommationSerializer(ModelSerializer):
 
    class Meta:
        model = Consommation
        fields = ['id','quantite', 'created_at', 'dispositif']


class DispoSerializer(ModelSerializer):
 
    class Meta:
        model = Dispositif
        fields = ['id','latitude', 'longitude', 'altitude','precision']