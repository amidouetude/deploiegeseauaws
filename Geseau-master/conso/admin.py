from django.contrib import admin
from conso.models import Section, Variable, Dispositif, Consommation, Entreprise

admin.site.register(Entreprise)
admin.site.register(Section)
admin.site.register(Variable)
admin.site.register(Dispositif)
admin.site.register(Consommation)