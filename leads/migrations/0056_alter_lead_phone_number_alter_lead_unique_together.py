# Generated by Django 4.2.1 on 2023-10-15 16:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0055_agent_is_available_for_leads'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lead',
            name='phone_number',
            field=models.CharField(max_length=20, verbose_name='Phone Number'),
        ),
        migrations.AlterUniqueTogether(
            name='lead',
            unique_together={('phone_number', 'organisation')},
        ),
    ]
