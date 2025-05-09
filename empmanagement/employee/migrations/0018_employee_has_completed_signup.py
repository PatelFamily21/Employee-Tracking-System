# Generated by Django 5.1.6 on 2025-04-14 20:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0017_requests_requester_feedback'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='has_completed_signup',
            field=models.BooleanField(default=False, help_text='Indicates whether the employee has completed the signup process.'),
        ),
    ]
