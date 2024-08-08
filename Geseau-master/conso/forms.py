from django import forms
from conso.models import Localisation, Section, Dispositif, Entreprise, Client
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User


class SectionForm(forms.ModelForm):
    nom_section = forms.CharField(
        label="Nom de la section",
        widget=forms.TextInput(attrs={'placeholder': "Nom de la section"})
    )
    
    class Meta:
        model = Section
        fields = ('nom_section', 'description')


class DispositifForm(forms.ModelForm):
    nom_lieu = forms.CharField(
        label = "Le lieu où se trouve le dispositif",
        widget = forms.TextInput(attrs={'placeholder':"Ex : Toilette, Salle de reunion"})
    )
    source_eau = forms.ChoiceField(
        label = "La source d'eau utilisée par le dispositif",
        widget = forms.Select(attrs={'placeholder': "Ex : ONEA, Forage"}),
        choices=[("ONEA", "ONEA"),("Forage", "Forage")]
    )
    def __init__(self, user, *args, **kwargs):
        super(DispositifForm, self).__init__(*args, **kwargs)
        # Filtrer les sections en fonction de l'entreprise de l'utilisateur connecté
        self.fields['section'].queryset = Section.objects.filter(entreprise__user=user)
    class Meta:
        model = Dispositif
        fields = '__all__'

class UserRegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email', 'first_name', 'last_name')

class UserProfileForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('username', 'email')

class EntrepriseForm(forms.ModelForm):
    class Meta:
        model = Entreprise
        fields = ('nom_societe', 'telephone', 'domaine_act', 'localite')


class DownloadForm(forms.Form):
    start_date = forms.DateTimeField(label="Date de début",widget=forms.DateTimeInput)
    end_date = forms.DateTimeField(label="Date de fin",widget=forms.DateTimeInput)


class ConsommationAnterieureForm(forms.Form):
    section = forms.ModelChoiceField(queryset=Section.objects.all(), label="Section")
    quantite = forms.FloatField(label="Quantité")
    date = forms.DateField(label="Date", widget=forms.SelectDateWidget(years=range(2000, 2031)))


class LocalisationForm(forms.ModelForm):
    class Meta:
        model = Localisation
        fields = ['latitude', 'longitude']
        


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = '__all__'



class UpdateClientProfileForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['nom_client', 'prenom_client']

class UpdateUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


