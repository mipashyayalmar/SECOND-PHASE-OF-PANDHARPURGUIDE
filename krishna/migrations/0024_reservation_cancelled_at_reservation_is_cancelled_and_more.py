# Generated by Django 4.0.3 on 2025-06-10 09:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('krishna', '0023_remove_reservation_cancellation_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='reservation',
            name='is_cancelled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='reservation',
            name='spy',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
