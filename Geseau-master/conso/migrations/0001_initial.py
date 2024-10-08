# Generated by Django 5.0.1 on 2024-08-15 00:27

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom_client', models.CharField(blank=True, default='Votre nom de famille', max_length=100, null=True, verbose_name='Votre nom')),
                ('prenom_client', models.CharField(blank=True, default='Votre prenom', max_length=100, null=True, verbose_name='Votre prénom')),
                ('activite', models.CharField(blank=True, default='Quelle travail exercez-vous??', max_length=100, null=True, verbose_name='Le travail que vous faite')),
                ('user', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Dispositif',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero_serie', models.CharField(blank=True, max_length=100, null=True, verbose_name='Numéro serie')),
                ('nom_lieu', models.CharField(blank=True, max_length=100, null=True, verbose_name='Le lieu où se trouve le dispositif')),
                ('source_eau', models.CharField(blank=True, max_length=100, null=True, verbose_name="Source d'eau")),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='conso.client')),
            ],
        ),
        migrations.CreateModel(
            name='Consommation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantite', models.FloatField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('dispositif', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='conso.dispositif')),
            ],
        ),
        migrations.CreateModel(
            name='Entreprise',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom_societe', models.CharField(blank=True, default='Nom de la societe', max_length=100, null=True, verbose_name="Nom de l'entreprise ou de la société")),
                ('telephone', models.CharField(blank=True, default='00000000', max_length=20, null=True, verbose_name='Numéro de téléphone')),
                ('domaine_act', models.CharField(blank=True, default="Domaine d'activité", max_length=100, null=True, verbose_name="Domaine d'activité")),
                ('localite', models.CharField(blank=True, default='Localite de la societe', max_length=100, null=True, verbose_name='Localisation')),
                ('user', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='client',
            name='entreprise',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='conso.entreprise'),
        ),
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intitule', models.CharField(max_length=255)),
                ('contenu', models.TextField()),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
                ('entreprise', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='conso.entreprise')),
            ],
        ),
        migrations.CreateModel(
            name='Localisation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('latitude', models.FloatField(blank=True, null=True)),
                ('longitude', models.FloatField(blank=True, null=True)),
                ('dispositif', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='conso.dispositif')),
            ],
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intitule', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
                ('entreprise', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='conso.entreprise')),
            ],
        ),
        migrations.CreateModel(
            name='OperationFinanciere',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_operation', models.CharField(choices=[('BUDGET', 'Budget'), ('DEPENSE', 'Dépense')], default='BUDGET', max_length=7)),
                ('montant', models.FloatField(default=0)),
                ('description', models.TextField(blank=True, null=True)),
                ('date_ajout', models.DateTimeField(auto_now_add=True)),
                ('entreprise', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='conso.entreprise')),
            ],
        ),
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom_section', models.CharField(blank=True, max_length=100, null=True, verbose_name='Nom de la section')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('entreprise', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='conso.entreprise')),
            ],
            options={
                'unique_together': {('entreprise', 'nom_section')},
            },
        ),
        migrations.AddField(
            model_name='dispositif',
            name='section',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='conso.section'),
        ),
        migrations.AlterUniqueTogether(
            name='dispositif',
            unique_together={('section', 'nom_lieu')},
        ),
    ]
