# Generated by Django 4.2.1 on 2023-09-02 13:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0013_user_alt_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='alt_name',
            field=models.CharField(blank=True, default='Persian Name', max_length=100, null=True),
        ),
    ]
