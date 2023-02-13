# Generated by Django 4.1.4 on 2022-12-14 20:48

from django.db import migrations
import phonenumber_field.modelfields  # type: ignore


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0005_domainapplication_city_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contact",
            name="phone",
            field=phonenumber_field.modelfields.PhoneNumberField(
                blank=True,
                db_index=True,
                help_text="Phone",
                max_length=128,
                null=True,
                region=None,
            ),
        ),
    ]
