# conso/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Client

@receiver(post_save, sender=Client)
def create_user_for_client(sender, instance, created, **kwargs):
    if created:
        # Créer un utilisateur associé
        user = User.objects.create_user(
            username=f"{instance.nom_client}_{instance.prenom_client}".lower(),
            first_name=instance.nom_client,
            last_name=instance.prenom_client,
            password="defaultpassword"  # Vous pouvez générer un mot de passe aléatoire ici
        )
        instance.user = user
        instance.save()
