# Generated by Django 4.2.1 on 2023-09-16 19:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0024_sale_remove_sales_agent_remove_sales_lead_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='total_sale',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
    ]
