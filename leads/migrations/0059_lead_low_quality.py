# Generated by Django 4.2.1 on 2023-10-17 09:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0058_alter_banknumbers_number_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='low_quality',
            field=models.BooleanField(default=False, verbose_name='Low Quality?'),
        ),
    ]
