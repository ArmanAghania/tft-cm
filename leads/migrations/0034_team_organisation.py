# Generated by Django 4.2.1 on 2023-09-23 23:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0033_agent_is_team_leader_team'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='organisation',
            field=models.ForeignKey(default='1', on_delete=django.db.models.deletion.CASCADE, to='leads.userprofile'),
        ),
    ]
