# Generated by Django 4.2.10 on 2024-11-21 20:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0138_alter_domaininvitation_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="portfolioinvitation",
            name="portfolio",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="portfolio_invitations",
                to="registrar.portfolio",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="portfolioinvitation",
            unique_together={("email", "portfolio")},
        ),
    ]
