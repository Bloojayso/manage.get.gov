# Generated by Django 4.1.5 on 2023-01-13 01:54

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0007_domainapplication_more_organization_information_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userprofile",
            name="created_at",
        ),
        migrations.RemoveField(
            model_name="userprofile",
            name="updated_at",
        ),
        migrations.AddField(
            model_name="contact",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="contact",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="website",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="website",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
