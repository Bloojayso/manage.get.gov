# Generated by Django 4.2.10 on 2024-05-02 17:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0090_waffleflag"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="domaininformation",
            name="federal_agency",
        ),
        migrations.RemoveField(
            model_name="domainrequest",
            name="federal_agency",
        ),
    ]
