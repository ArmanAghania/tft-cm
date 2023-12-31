# Generated by Django 4.2.1 on 2023-09-16 08:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0020_alter_duplicatetofollow_date_added'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lead',
            name='deposit_amount',
        ),
        migrations.RemoveField(
            model_name='lead',
            name='sale_amount',
        ),
        migrations.AddField(
            model_name='lead',
            name='sale',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='related_sale', to='leads.sales'),
        ),
    ]
