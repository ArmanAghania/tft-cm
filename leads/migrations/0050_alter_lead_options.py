# Generated by Django 4.2.1 on 2023-10-09 13:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0049_lead_is_presented'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='lead',
            options={'ordering': ['date_assigned'], 'verbose_name': 'Lead', 'verbose_name_plural': 'Leads'},
        ),
    ]
