from rest_framework.serializers import ModelSerializer
from conso.models import Consommation

class ConsommationSerializer(ModelSerializer):
 
    class Meta:
        model = Consommation
        fields = ['id','quantite', 'created_at', 'dispositif']