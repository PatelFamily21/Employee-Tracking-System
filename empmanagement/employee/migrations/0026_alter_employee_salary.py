# Generated by Django 5.1.6 on 2025-04-30 15:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0025_issuecomment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employee',
            name='salary',
            field=models.CharField(max_length=6),
        ),
    ]
