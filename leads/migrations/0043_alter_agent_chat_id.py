# Generated by Django 4.2.1 on 2023-09-26 08:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0042_alter_agent_chat_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='agent',
            name='chat_id',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
    ]