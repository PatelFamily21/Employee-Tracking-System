# Generated by Django 5.1.6 on 2025-04-13 15:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0016_requests_response_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='requests',
            name='requester_feedback',
            field=models.TextField(blank=True, help_text="Feedback from the requester in response to the recipient's clarification.", null=True),
        ),
    ]
