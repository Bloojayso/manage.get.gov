from registrar.utility import StrEnum
from django.db import models


class UserPortfolioRoleChoices(models.TextChoices):
    """
    Roles make it easier for admins to look at
    """

    ORGANIZATION_ADMIN = "organization_admin", "Admin"
    ORGANIZATION_MEMBER = "organization_member", "Member"

    @classmethod
    def get_user_portfolio_role_label(cls, user_portfolio_role):
        return cls(user_portfolio_role).label if user_portfolio_role else None


class UserPortfolioPermissionChoices(models.TextChoices):
    """ """

    VIEW_ALL_DOMAINS = "view_all_domains", "View all domains and domain reports"
    VIEW_MANAGED_DOMAINS = "view_managed_domains", "View managed domains"

    VIEW_MEMBERS = "view_members", "View members"
    EDIT_MEMBERS = "edit_members", "Create and edit members"

    VIEW_ALL_REQUESTS = "view_all_requests", "View all requests"
    EDIT_REQUESTS = "edit_requests", "Create and edit requests"

    VIEW_PORTFOLIO = "view_portfolio", "View organization"
    EDIT_PORTFOLIO = "edit_portfolio", "Edit organization"

    # Domain: field specific permissions
    VIEW_SUBORGANIZATION = "view_suborganization", "View suborganization"
    EDIT_SUBORGANIZATION = "edit_suborganization", "Edit suborganization"

    @classmethod
    def get_user_portfolio_permission_label(cls, user_portfolio_permission):
        return cls(user_portfolio_permission).label if user_portfolio_permission else None

    @classmethod
    def to_dict(cls):
        return {key: value.value for key, value in cls.__members__.items()}


class DomainRequestPermissionDisplay(StrEnum):
    """Stores display values for domain request permission combinations.

    Overview of values:
    - VIEWER_REQUESTER: "Viewer Requester"
    - VIEWER: "Viewer"
    - NONE: "None"
    """
    VIEWER_REQUESTER = "Viewer Requester"
    VIEWER = "Viewer"
    NONE = "None"


class MemberPermissionDisplay(StrEnum):
    """Stores display values for member permission combinations.

    Overview of values:
    - MANAGER: "Manager"
    - VIEWER: "Viewer"
    - NONE: "None"
    """
    MANAGER = "Manager"
    VIEWER = "Viewer"
    NONE = "None"
