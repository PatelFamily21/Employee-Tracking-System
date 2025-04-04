# Generated by Django 5.1.6 on 2025-04-04 16:09

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0007_notification_request_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='notice',
            name='expires_on',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notice',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='notice',
            name='is_urgent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='notice',
            name='posted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='posted_notices', to='employee.employee'),
        ),
        migrations.AlterField(
            model_name='notice',
            name='publishDate',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.CreateModel(
            name='NoticeView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('viewed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='employee.employee')),
                ('notice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='views', to='employee.notice')),
            ],
            options={
                'unique_together': {('notice', 'employee')},
            },
        ),
    ]
