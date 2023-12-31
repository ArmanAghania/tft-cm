# Generated by Django 4.2.1 on 2023-09-24 09:52

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0037_alter_lead_converted_date_alter_lead_date_assigned_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lead',
            name='converted_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='lead',
            name='date_assigned',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='lead',
            name='date_modified',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
