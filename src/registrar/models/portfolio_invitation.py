"""People are invited by email to administer domains."""

import logging
from django.contrib.auth import get_user_model
from django.db import models
from django_fsm import FSMField, transition
from registrar.models.domain_invitation import DomainInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from .utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices  # type: ignore
from .utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.contenttypes.models import ContentType


logger = logging.getLogger(__name__)


class PortfolioInvitation(TimeStampedModel):
    class Meta:
        """Contains meta information about this class"""

        indexes = [
            models.Index(fields=["status"]),
        ]

    # Constants for status field
    class PortfolioInvitationStatus(models.TextChoices):
        INVITED = "invited", "Invited"
        RETRIEVED = "retrieved", "Retrieved"

    email = models.EmailField(
        null=False,
        blank=False,
    )

    portfolio = models.ForeignKey(
        "registrar.Portfolio",
        on_delete=models.CASCADE,  # delete portfolio, then get rid of invitations
        null=False,
        related_name="portfolios",
    )

    roles = ArrayField(
        models.CharField(
            max_length=50,
            choices=UserPortfolioRoleChoices.choices,
        ),
        null=True,
        blank=True,
        help_text="Select one or more roles.",
    )

    additional_permissions = ArrayField(
        models.CharField(
            max_length=50,
            choices=UserPortfolioPermissionChoices.choices,
        ),
        null=True,
        blank=True,
        help_text="Select one or more additional permissions.",
    )

    status = FSMField(
        choices=PortfolioInvitationStatus.choices,
        default=PortfolioInvitationStatus.INVITED,
        protected=True,  # can't alter state except through transition methods!
    )

    # TODO - replace this with a "creator" field on portfolio invitation. This should be another ticket.
    @property
    def creator(self):
        """Get the user who created this invitation from the audit log"""
        content_type = ContentType.objects.get_for_model(self)
        log_entry = LogEntry.objects.filter(
            content_type=content_type,
            object_id=self.pk,
            action_flag=ADDITION
        ).order_by("action_time").first()
        
        return log_entry.user if log_entry else None


    def __str__(self):
        return f"Invitation for {self.email} on {self.portfolio} is {self.status}"

    def get_managed_domains_count(self):
        """Return the count of domain invitations managed by the invited user for this portfolio."""
        # Filter the UserDomainRole model to get domains where the user has a manager role
        managed_domains = DomainInvitation.objects.filter(
            email=self.email, domain__domain_info__portfolio=self.portfolio
        ).count()
        return managed_domains

    def get_portfolio_permissions(self):
        """
        Retrieve the permissions for the user's portfolio roles from the invite.
        """
        return UserPortfolioPermission.get_portfolio_permissions(self.roles, self.additional_permissions)

    @transition(field="status", source=PortfolioInvitationStatus.INVITED, target=PortfolioInvitationStatus.RETRIEVED)
    def retrieve(self):
        """When an invitation is retrieved, create the corresponding permission.

        Raises:
            RuntimeError if no matching user can be found.
        """

        # get a user with this email address
        User = get_user_model()
        try:
            user = User.objects.get(email=self.email)
        except User.DoesNotExist:
            # should not happen because a matching user should exist before
            # we retrieve this invitation
            raise RuntimeError("Cannot find the user to retrieve this portfolio invitation.")

        # and create a role for that user on this portfolio
        user_portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=self.portfolio, user=user, invitation=self
        )
        if self.roles and len(self.roles) > 0:
            user_portfolio_permission.roles = self.roles
        if self.additional_permissions and len(self.additional_permissions) > 0:
            user_portfolio_permission.additional_permissions = self.additional_permissions
        user_portfolio_permission.save()
