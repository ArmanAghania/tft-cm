# Generated by Django 4.2.1 on 2023-08-30 10:27

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0007_banknumbers_agent'),
    ]

    operations = [
        migrations.AddField(
            model_name='banknumbers',
            name='date_added',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
