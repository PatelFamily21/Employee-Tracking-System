# Generated by Django 5.1.6 on 2025-04-04 11:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0005_auditlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='request_type',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
