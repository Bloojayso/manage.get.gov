from django.db import models
from django_fsm import FSMField  # type: ignore

from registrar.models.domain_request import DomainRequest
from registrar.models.federal_agency import FederalAgency
from registrar.models.domain import State

from .utility.time_stamped_model import TimeStampedModel


class Organization(TimeStampedModel):
    """
    TODO:
    """

    class Meta:
        """Contains meta information about this class"""

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["email"]),
        ]

    # federal agency - FK to fed agency table (Not nullable, should default to the Non-federal agency value in the fed agency table)
    federal_agency = models.ForeignKey(
        "registrar.FederalAgency",
        on_delete=models.PROTECT,
        help_text="Associated federal agency",
        unique=False,
        default=FederalAgency.objects.filter(agency="Non-Federal Agency").first()
    )

    # creator- user foreign key- stores who created this model 
    # should get the user who is adding it via django admin if there
    # is a user (aka not done via commandline/ manual means)
    # TODO: auto-populate
    creator = models.ForeignKey(
        "registrar.User",
        on_delete=models.PROTECT,
        help_text="Associated user",
        unique=False
    )

    # organization type- should match organization types allowed on domain info
    organization_type = models.CharField(
        max_length=255,
        choices=DomainRequest.OrgChoicesElectionOffice.choices,
        null=True,
        blank=True,
        help_text='"Election" appears after the org type if it\'s an election office.',
    )

    # organization name
    # TODO: org name will be the same as federal agency, if it is federal,
    # otherwise it will be the actual org name. If nothing is entered for
    # org name and it is a federal organization, have this field fill with
    # the federal agency text name.
    organization_name = models.CharField(
        null=True,
        blank=True,
    )

    # address_line1
    address_line1 = models.CharField(
        null=True,
        blank=True,
        verbose_name="address line 1",
    )
    # address_line2
    address_line2 = models.CharField(
        null=True,
        blank=True,
        verbose_name="address line 2",
    )
    # city
    city = models.CharField(
        null=True,
        blank=True,
    )
    # state (copied from domain.py -- imports enums from domain.py)
    state = FSMField(
        max_length=21,
        choices=State.choices,
        default=State.UNKNOWN,
        # cannot change state directly, particularly in Django admin
        protected=True,
        # This must be defined for custom state help messages,
        # as otherwise the view will purge the help field as it does not exist.
        help_text=" ",
        verbose_name="domain state",
    )
    # zipcode
    zipcode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name="zip code",
    )
    # urbanization
    urbanization = models.CharField(
        null=True,
        blank=True,
        help_text="Required for Puerto Rico only",
        verbose_name="urbanization",
    )

    # security_contact_email
    security_contact_email = models.EmailField(
        null=True,
        blank=True,
        verbose_name="security contact e-mail",
        max_length=320,
    )

    # def save(self, *args, **kwargs):
    #     # Call the parent class's save method to perform the actual save
    #     super().save(*args, **kwargs)

    #     if self.user:
    #         updated = False

    #         # Update first name and last name if necessary
    #         if not self.user.first_name or not self.user.last_name:
    #             self.user.first_name = self.first_name
    #             self.user.last_name = self.last_name
    #             updated = True

    #         # Update phone if necessary
    #         if not self.user.phone:
    #             self.user.phone = self.phone
    #             updated = True

    #         # Save user if any updates were made
    #         if updated:
    #             self.user.save()

    # def __str__(self):
    #     if self.first_name or self.last_name:
    #         return self.get_formatted_name()
    #     elif self.email:
    #         return self.email
    #     elif self.pk:
    #         return str(self.pk)
    #     else:
    #         return ""
