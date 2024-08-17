from django.contrib import admin
from conso.models import Section, Dispositif, Consommation, Entreprise, Alert, OperationFinanciere, Client

admin.site.register(Entreprise)
admin.site.register(Section)
#admin.site.register(Variable)
admin.site.register(Dispositif)
admin.site.register(Consommation)
admin.site.register(Alert)
admin.site.register(OperationFinanciere)
admin.site.register(Client)

