# Generated by Django 4.1.5 on 2023-01-10 20:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0006_alter_contact_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="domainapplication",
            name="more_organization_information",
            field=models.TextField(
                blank=True,
                help_text="Further information about the government organization",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="domainapplication",
            name="type_of_work",
            field=models.TextField(
                blank=True, help_text="Type of work of the organization", null=True
            ),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="address_line1",
            field=models.TextField(blank=True, help_text="Street address", null=True),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="address_line2",
            field=models.CharField(
                blank=True, help_text="Street address line 2", max_length=15, null=True
            ),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="federal_agency",
            field=models.TextField(blank=True, help_text="Federal agency", null=True),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="federal_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("executive", "Executive"),
                    ("judicial", "Judicial"),
                    ("legislative", "Legislative"),
                ],
                help_text="Federal government branch",
                max_length=50,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="organization_type",
            field=models.CharField(
                blank=True,
                choices=[
                    (
                        "federal",
                        "Federal: an agency of the U.S. government's executive, legislative, or judicial branches",
                    ),
                    ("interstate", "Interstate: an organization of two or more states"),
                    (
                        "state_or_territory",
                        "State or territory: one of the 50 U.S. states, the District of Columbia, American Samoa, Guam, Northern Mariana Islands, Puerto Rico, or the U.S. Virgin Islands",
                    ),
                    (
                        "tribal",
                        "Tribal: a tribal government recognized by the federal or a state government",
                    ),
                    ("county", "County: a county, parish, or borough"),
                    ("city", "City: a city, town, township, village, etc."),
                    (
                        "special_district",
                        "Special district: an independent organization within a single state",
                    ),
                    (
                        "school_district",
                        "School district: a school district that is not part of a local government",
                    ),
                ],
                help_text="Type of Organization",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="purpose",
            field=models.TextField(
                blank=True, help_text="Purpose of your domain", null=True
            ),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="state_territory",
            field=models.CharField(
                blank=True,
                help_text="State, territory, or military post",
                max_length=2,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="urbanization",
            field=models.TextField(
                blank=True, help_text="Urbanization (Puerto Rico only)", null=True
            ),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="zipcode",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Zip code",
                max_length=10,
                null=True,
            ),
        ),
    ]
