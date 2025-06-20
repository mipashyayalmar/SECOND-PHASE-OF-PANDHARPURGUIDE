# Generated by Django 5.2 on 2025-05-06 12:30

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('krishna', '0009_alter_hotels_options_remove_rooms_description_map_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='hotels',
            name='image_1',
            field=models.ImageField(blank=True, help_text='First hotel image', null=True, upload_to='hotel_images/'),
        ),
        migrations.AddField(
            model_name='hotels',
            name='image_2',
            field=models.ImageField(blank=True, help_text='Second hotel image', null=True, upload_to='hotel_images/'),
        ),
        migrations.AddField(
            model_name='hotels',
            name='image_3',
            field=models.ImageField(blank=True, help_text='Third hotel image', null=True, upload_to='hotel_images/'),
        ),
        migrations.AddField(
            model_name='hotels',
            name='image_4',
            field=models.ImageField(blank=True, help_text='Fourth hotel image', null=True, upload_to='hotel_images/'),
        ),
        migrations.AddField(
            model_name='hotels',
            name='image_5',
            field=models.ImageField(blank=True, help_text='Fifth hotel image', null=True, upload_to='hotel_images/'),
        ),
        migrations.AddField(
            model_name='hotels',
            name='image_6',
            field=models.ImageField(blank=True, help_text='Sixth hotel image', null=True, upload_to='hotel_images/'),
        ),
        migrations.AlterField(
            model_name='hotels',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
    ]
