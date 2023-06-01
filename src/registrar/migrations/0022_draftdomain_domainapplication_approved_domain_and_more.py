# Generated by Django 4.2.1 on 2023-05-26 13:14

from django.db import migrations, models
import django.db.models.deletion
import registrar.models.utility.domain_helper


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0021_publiccontact_domain_publiccontact_registry_id_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DraftDomain",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    models.CharField(
                        default=None,
                        help_text="Fully qualified domain name",
                        max_length=253,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=(models.Model, registrar.models.utility.domain_helper.DomainHelper),  # type: ignore
        ),
        migrations.AddField(
            model_name="domainapplication",
            name="approved_domain",
            field=models.OneToOneField(
                blank=True,
                help_text="The approved domain",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="domain_application",
                to="registrar.domain",
            ),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="requested_domain",
            field=models.OneToOneField(
                blank=True,
                help_text="The requested domain",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="domain_application",
                to="registrar.draftdomain",
            ),
        ),
    ]
