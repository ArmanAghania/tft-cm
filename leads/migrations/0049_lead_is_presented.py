# Generated by Django 4.2.1 on 2023-10-02 16:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0048_lead_proposed_price_lead_registered_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='is_presented',
            field=models.BooleanField(default=False, verbose_name='Is Presented?'),
        ),
    ]
