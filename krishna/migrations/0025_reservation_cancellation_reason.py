# Generated by Django 4.0.3 on 2025-06-10 09:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('krishna', '0024_reservation_cancelled_at_reservation_is_cancelled_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='cancellation_reason',
            field=models.TextField(blank=True, null=True),
        ),
    ]
