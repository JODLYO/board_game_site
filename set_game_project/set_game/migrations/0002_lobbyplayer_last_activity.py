# Generated by Django 5.0.6 on 2025-03-21 18:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('set_game', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='lobbyplayer',
            name='last_activity',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
