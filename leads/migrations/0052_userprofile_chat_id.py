# Generated by Django 4.2.1 on 2023-10-09 14:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0051_userprofile_telegram_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='chat_id',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Chat ID'),
        ),
    ]