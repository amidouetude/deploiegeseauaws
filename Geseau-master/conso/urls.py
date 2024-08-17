from django.urls import include, path
from . import views
from django.contrib.auth import views as auth_views
from rest_framework import routers


router = routers.SimpleRouter()
router.register('consommation', views.ConsommationViewset, basename='consommation')
chemin = routers.SimpleRouter()
chemin.register('localisation', views.LocalisationViewset, basename='localisation')


#router = DefaultRouter()
#router.register(r'sections', SectionViewSet, basename='section')




urlpatterns = [
    path('api/', include(router.urls)),
    path('api/', include(chemin.urls)),
#    path('api/', include(router.urls)),


    path('acceuil/', views.index, name="index"),
    path('acceuil/conso_section/<str:pk>/', views.ConsSection, name="graphe_section"),
    path('acceuil/conso_dispo/<str:pk>/', views.ConsDispo, name="graphe_dispo"),

    ###Vues vers les statistiques descriptives des historiques
    path('historique/',views.historique,name="historique"),
    path('historique/section/<str:pk>/',views.hist_section,name="historique_section"),
    
    ###Vues vers les differentes previsions
    path('prevision/',views.prevision,name="prevision"),
    path('prevision/section/<int:pk>/', views.prevision_section, name="prevision_section"),

    ###Toute les vues liées à la table section
    path('section/',views.section,name="section"),
    path('section/add_section/',views.add_section,name="add_section"),
    path('section/detail_section/<str:pk>/',views.detail_section,name="detail_section"),
    path('section/update_section/<str:pk>/',views.update_section,name="update_section"),
    path('section/delete_section/<str:pk>/',views.delete_section,name="delete_section"),
    
    ###Toute les vues liées à la table section
    path('dispo/add_dispo/<str:section_pk>/',views.add_dispo,name="add_dispositif"),
    path('dispo/update_dispo/<str:pk>/',views.update_dispo,name="update_dispositif"),
    path('dispo/delete_dispo/<str:pk>/',views.delete_dispo,name="delete_dispositif"),
    path('dispo/localisation/<str:pk>/', views.localisation, name='localisation'),
    #path('dispo/update_coordinates/<str:pk>/', views.update_coordinates, name='update_coordinates'),


    ###Toute les vues liées à la table client
    path('client/',views.client,name="client"),
    path('client/add_client/',views.add_client,name="add_client"),
    path('client/detail_client/<str:pk>/',views.detail_client,name="detail_client"),
    path('client/update_client/<str:pk>/',views.update_client,name="update_client"),
    #path('client/delete_client/<str:pk>/',views.delete_client,name="delete_client"),
    


    ###Vue liée à la table foire aux questions
    path('faq/',views.faq,name="faq"),
    #path('download/',views.download,name="download"),
    path('alert/',views.alert,name="alert"),
    #path('alert/',views.message,name="message"),
    path('alert/<str:pk>/', views.read_alert, name='read_alert'),
    path('budget/',views.budget,name="budget"),
    path('fuite/',views.fuite,name="fuite"),
    #path('fuite/section/<str:pk>/',views.fuite_section,name="fuite_section"),


    

    ###Vue vers la gestion de profil
    path('profil/',views.profil_views,name="profil"),
    path('profil/dispo/',views.dispo,name="dispo"),
    path('login',views.login_views,name="login"),
    path('',views.chargement,name="charge"),
    path('logout/',views.logout_views,name="logout"),
    path('register/',views.register,name="register"),
    path('profil/password/', views.change_password, name='change_password'),
    
    
    
    
    # URL pour la réinitialisation de mot de passe
    path('reset_password/', auth_views.PasswordResetView.as_view(template_name='conso/profil/password_reset.html'), name='password_reset'),
    path('reset_password/done/', auth_views.PasswordResetDoneView.as_view(template_name='conso/profil/password_reset_done.html'), name='password_reset_done'),
    path('reset_password/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='conso/profil/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset_password/complete/', auth_views.PasswordResetCompleteView.as_view(template_name='conso/profil/password_reset_complet.html'), name='password_reset_complete'),


    ###Vue vers la consommation
    path('conso/section',views.ConsSection,name='cons_section'),
    path('conso/dispositif',views.ConsDispo,name='cons_dispo'),
    
    
]
