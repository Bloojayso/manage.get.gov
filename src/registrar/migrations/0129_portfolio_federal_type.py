# Generated by Django 4.2.10 on 2024-09-23 15:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0128_alter_domaininformation_state_territory_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="portfolio",
            name="federal_type",
            field=models.CharField(
                blank=True,
                choices=[("executive", "Executive"), ("judicial", "Judicial"), ("legislative", "Legislative")],
                help_text="Federal agency type (executive, judicial, legislative, etc.)",
                max_length=20,
                null=True,
            ),
        ),
    ]
