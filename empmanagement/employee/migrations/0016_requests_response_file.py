# Generated by Django 5.1.6 on 2025-04-13 14:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0015_requests_feedback_requests_is_locked_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='requests',
            name='response_file',
            field=models.FileField(blank=True, help_text='Optional file uploaded by the requester in response to feedback.', null=True, upload_to='request_response_files/'),
        ),
    ]
