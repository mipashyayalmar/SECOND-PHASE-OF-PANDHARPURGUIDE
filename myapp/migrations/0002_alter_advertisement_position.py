# Generated by Django 5.2.1 on 2025-05-26 10:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='advertisement',
            name='position',
            field=models.CharField(choices=[('upper-menu', 'Upper menu'), ('below-menu', 'Below menu'), ('left-side-of-page', 'Left side of the page'), ('right-side-of-page', 'Right side of the page'), ('below-page', 'Below the page'), ('below-footer', 'Below footer'), ('full-screen-popup', 'Full Screen Popup')], default='upper-menu', max_length=50),
        ),
    ]
