from rest_framework.serializers import ModelSerializer
from rest_framework.permissions import BasePermission
from conso.models import Consommation, Localisation, Section, Dispositif


class SectionSerializer(ModelSerializer):
    class Meta:
        model = Section
        fields = '__all__'



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
        serializer.save() """



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