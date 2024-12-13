import logging
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages

from registrar.forms import portfolio as portfolioForms
from registrar.models import Portfolio, User
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from registrar.utility.email import EmailSendingError
from registrar.views.utility.mixins import PortfolioMemberPermission
from registrar.views.utility.permission_views import (
    PortfolioDomainRequestsPermissionView,
    PortfolioDomainsPermissionView,
    PortfolioBasePermissionView,
    NoPortfolioDomainsPermissionView,
    PortfolioInvitationCreatePermissionView,
    PortfolioMemberDomainsPermissionView,
    PortfolioMemberDomainsEditPermissionView,
    PortfolioMemberEditPermissionView,
    PortfolioMemberPermissionView,
    PortfolioMembersPermissionView,
)
from django.views.generic import View
from django.views.generic.edit import FormMixin


logger = logging.getLogger(__name__)


class PortfolioDomainsView(PortfolioDomainsPermissionView, View):

    template_name = "portfolio_domains.html"

    def get(self, request):
        context = {}
        if self.request and self.request.user and self.request.user.is_authenticated:
            context["user_domain_count"] = self.request.user.get_user_domain_ids(request).count()
        return render(request, "portfolio_domains.html", context)


class PortfolioDomainRequestsView(PortfolioDomainRequestsPermissionView, View):

    template_name = "portfolio_requests.html"

    def get(self, request):
        return render(request, "portfolio_requests.html")


class PortfolioMemberView(PortfolioMemberPermissionView, View):

    template_name = "portfolio_member.html"

    def get(self, request, pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        member = portfolio_permission.user

        # We have to explicitely name these with member_ otherwise we'll have conflicts with context preprocessors
        member_has_view_all_requests_portfolio_permission = member.has_view_all_requests_portfolio_permission(
            portfolio_permission.portfolio
        )
        member_has_edit_request_portfolio_permission = member.has_edit_request_portfolio_permission(
            portfolio_permission.portfolio
        )
        member_has_view_members_portfolio_permission = member.has_view_members_portfolio_permission(
            portfolio_permission.portfolio
        )
        member_has_edit_members_portfolio_permission = member.has_edit_members_portfolio_permission(
            portfolio_permission.portfolio
        )

        return render(
            request,
            self.template_name,
            {
                "edit_url": reverse("member-permissions", args=[pk]),
                "domains_url": reverse("member-domains", args=[pk]),
                "portfolio_permission": portfolio_permission,
                "member": member,
                "member_has_view_all_requests_portfolio_permission": member_has_view_all_requests_portfolio_permission,
                "member_has_edit_request_portfolio_permission": member_has_edit_request_portfolio_permission,
                "member_has_view_members_portfolio_permission": member_has_view_members_portfolio_permission,
                "member_has_edit_members_portfolio_permission": member_has_edit_members_portfolio_permission,
            },
        )


class PortfolioMemberDeleteView(PortfolioMemberPermission, View):

    def post(self, request, pk):
        """
        Find and delete the portfolio member using the provided primary key (pk).
        Redirect to a success page after deletion (or any other appropriate page).
        """
        portfolio_member_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        member = portfolio_member_permission.user

        active_requests_count = member.get_active_requests_count_in_portfolio(request)

        support_url = "https://get.gov/contact/"

        error_message = ""

        if active_requests_count > 0:
            # If they have any in progress requests
            error_message = mark_safe(  # nosec
                f"This member has an active domain request and can't be removed from the organization. "
                f"<a href='{support_url}' target='_blank'>Contact the .gov team</a> to remove them."
            )
        elif member.is_only_admin_of_portfolio(portfolio_member_permission.portfolio):
            # If they are the last manager of a domain
            error_message = (
                "There must be at least one admin in your organization. Give another member admin "
                "permissions, make sure they log into the registrar, and then remove this member."
            )

        # From the Members Table page Else the Member Page
        if error_message:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"error": error_message},
                    status=400,
                )
            else:
                messages.error(request, error_message)
                return redirect(reverse("member", kwargs={"pk": pk}))

        # passed all error conditions
        portfolio_member_permission.delete()

        # From the Members Table page Else the Member Page
        success_message = f"You've removed {member.email} from the organization."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": success_message}, status=200)
        else:
            messages.success(request, success_message)
            return redirect(reverse("members"))


class PortfolioMemberEditView(PortfolioMemberEditPermissionView, View):

    template_name = "portfolio_member_permissions.html"
    form_class = portfolioForms.BasePortfolioMemberForm

    def get(self, request, pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        user = portfolio_permission.user

        form = self.form_class(instance=portfolio_permission)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "member": user,
            },
        )

    def post(self, request, pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        user = portfolio_permission.user
        form = self.form_class(request.POST, instance=portfolio_permission)
        if form.is_valid():
            # Check if user is removing their own admin or edit role
            removing_admin_role_on_self = (
                request.user == user
                and UserPortfolioRoleChoices.ORGANIZATION_ADMIN in portfolio_permission.roles
                and UserPortfolioRoleChoices.ORGANIZATION_ADMIN not in form.cleaned_data.get("role", [])
            )
            form.save()
            messages.success(self.request, "The member access and permission changes have been saved.")
            return redirect("member", pk=pk) if not removing_admin_role_on_self else redirect("home")

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "member": user,  # Pass the user object again to the template
            },
        )


class PortfolioMemberDomainsView(PortfolioMemberDomainsPermissionView, View):

    template_name = "portfolio_member_domains.html"

    def get(self, request, pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        member = portfolio_permission.user

        return render(
            request,
            self.template_name,
            {
                "portfolio_permission": portfolio_permission,
                "member": member,
            },
        )


class PortfolioMemberDomainsEditView(PortfolioMemberDomainsEditPermissionView, View):

    template_name = "portfolio_member_domains_edit.html"

    def get(self, request, pk):
        portfolio_permission = get_object_or_404(UserPortfolioPermission, pk=pk)
        member = portfolio_permission.user

        return render(
            request,
            self.template_name,
            {
                "portfolio_permission": portfolio_permission,
                "member": member,
            },
        )


class PortfolioInvitedMemberView(PortfolioMemberPermissionView, View):

    template_name = "portfolio_member.html"
    # form_class = PortfolioInvitedMemberForm

    def get(self, request, pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)
        # form = self.form_class(instance=portfolio_invitation)

        # We have to explicitely name these with member_ otherwise we'll have conflicts with context preprocessors
        member_has_view_all_requests_portfolio_permission = (
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS in portfolio_invitation.get_portfolio_permissions()
        )
        member_has_edit_request_portfolio_permission = (
            UserPortfolioPermissionChoices.EDIT_REQUESTS in portfolio_invitation.get_portfolio_permissions()
        )
        member_has_view_members_portfolio_permission = (
            UserPortfolioPermissionChoices.VIEW_MEMBERS in portfolio_invitation.get_portfolio_permissions()
        )
        member_has_edit_members_portfolio_permission = (
            UserPortfolioPermissionChoices.EDIT_MEMBERS in portfolio_invitation.get_portfolio_permissions()
        )

        return render(
            request,
            self.template_name,
            {
                "edit_url": reverse("invitedmember-permissions", args=[pk]),
                "domains_url": reverse("invitedmember-domains", args=[pk]),
                "portfolio_invitation": portfolio_invitation,
                "member_has_view_all_requests_portfolio_permission": member_has_view_all_requests_portfolio_permission,
                "member_has_edit_request_portfolio_permission": member_has_edit_request_portfolio_permission,
                "member_has_view_members_portfolio_permission": member_has_view_members_portfolio_permission,
                "member_has_edit_members_portfolio_permission": member_has_edit_members_portfolio_permission,
            },
        )


class PortfolioInvitedMemberDeleteView(PortfolioMemberPermission, View):

    def post(self, request, pk):
        """
        Find and delete the portfolio invited member using the provided primary key (pk).
        Redirect to a success page after deletion (or any other appropriate page).
        """
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)

        portfolio_invitation.delete()

        success_message = f"You've removed {portfolio_invitation.email} from the organization."
        # From the Members Table page Else the Member Page
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": success_message}, status=200)
        else:
            messages.success(request, success_message)
            return redirect(reverse("members"))


class PortfolioInvitedMemberEditView(PortfolioMemberEditPermissionView, View):

    template_name = "portfolio_member_permissions.html"
    form_class = portfolioForms.BasePortfolioMemberForm

    def get(self, request, pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)
        form = self.form_class(instance=portfolio_invitation)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "invitation": portfolio_invitation,
            },
        )

    def post(self, request, pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)
        form = self.form_class(request.POST, instance=portfolio_invitation)
        if form.is_valid():
            form.save()
            messages.success(self.request, "The member access and permission changes have been saved.")
            return redirect("invitedmember", pk=pk)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "invitation": portfolio_invitation,  # Pass the user object again to the template
            },
        )


class PortfolioInvitedMemberDomainsView(PortfolioMemberDomainsPermissionView, View):

    template_name = "portfolio_member_domains.html"

    def get(self, request, pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)

        return render(
            request,
            self.template_name,
            {
                "portfolio_invitation": portfolio_invitation,
            },
        )


class PortfolioInvitedMemberDomainsEditView(PortfolioMemberDomainsEditPermissionView, View):

    template_name = "portfolio_member_domains_edit.html"

    def get(self, request, pk):
        portfolio_invitation = get_object_or_404(PortfolioInvitation, pk=pk)

        return render(
            request,
            self.template_name,
            {
                "portfolio_invitation": portfolio_invitation,
            },
        )


class PortfolioNoDomainsView(NoPortfolioDomainsPermissionView, View):
    """Some users have access to the underlying portfolio, but not any domains.
    This is a custom view which explains that to the user - and denotes who to contact.
    """

    model = Portfolio
    template_name = "portfolio_no_domains.html"

    def get(self, request):
        return render(request, self.template_name, context=self.get_context_data())

    def get_context_data(self, **kwargs):
        """Add additional context data to the template."""
        # We can override the base class. This view only needs this item.
        context = {}
        portfolio = self.request.session.get("portfolio")
        if portfolio:
            admin_ids = UserPortfolioPermission.objects.filter(
                portfolio=portfolio,
                roles__overlap=[
                    UserPortfolioRoleChoices.ORGANIZATION_ADMIN,
                ],
            ).values_list("user__id", flat=True)

            admin_users = User.objects.filter(id__in=admin_ids)
            context["portfolio_administrators"] = admin_users
        return context


class PortfolioNoDomainRequestsView(NoPortfolioDomainsPermissionView, View):
    """Some users have access to the underlying portfolio, but not any domain requests.
    This is a custom view which explains that to the user - and denotes who to contact.
    """

    model = Portfolio
    template_name = "portfolio_no_requests.html"

    def get(self, request):
        return render(request, self.template_name, context=self.get_context_data())

    def get_context_data(self, **kwargs):
        """Add additional context data to the template."""
        # We can override the base class. This view only needs this item.
        context = {}
        portfolio = self.request.session.get("portfolio")
        if portfolio:
            admin_ids = UserPortfolioPermission.objects.filter(
                portfolio=portfolio,
                roles__overlap=[
                    UserPortfolioRoleChoices.ORGANIZATION_ADMIN,
                ],
            ).values_list("user__id", flat=True)

            admin_users = User.objects.filter(id__in=admin_ids)
            context["portfolio_administrators"] = admin_users
        return context


class PortfolioOrganizationView(PortfolioBasePermissionView, FormMixin):
    """
    View to handle displaying and updating the portfolio's organization details.
    """

    model = Portfolio
    template_name = "portfolio_organization.html"
    form_class = portfolioForms.PortfolioOrgAddressForm
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs):
        """Add additional context data to the template."""
        context = super().get_context_data(**kwargs)
        portfolio = self.request.session.get("portfolio")
        context["has_edit_org_portfolio_permission"] = self.request.user.has_edit_org_portfolio_permission(portfolio)
        return context

    def get_object(self, queryset=None):
        """Get the portfolio object based on the session."""
        portfolio = self.request.session.get("portfolio")
        if portfolio is None:
            raise Http404("No organization found for this user")
        return portfolio

    def get_form_kwargs(self):
        """Include the instance in the form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs

    def get(self, request, *args, **kwargs):
        """Handle GET requests to display the form."""
        self.object = self.get_object()
        form = self.get_form()
        return self.render_to_response(self.get_context_data(form=form))

    def post(self, request, *args, **kwargs):
        """Handle POST requests to process form submission."""
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Handle the case when the form is valid."""
        self.object = form.save(commit=False)
        self.object.creator = self.request.user
        self.object.save()
        messages.success(self.request, "The organization information for this portfolio has been updated.")
        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle the case when the form is invalid."""
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        """Redirect to the overview page for the portfolio."""
        return reverse("organization")


class PortfolioSeniorOfficialView(PortfolioBasePermissionView, FormMixin):
    """
    View to handle displaying and updating the portfolio's senior official details.
    For now, this view is readonly.
    """

    model = Portfolio
    template_name = "portfolio_senior_official.html"
    form_class = portfolioForms.PortfolioSeniorOfficialForm
    context_object_name = "portfolio"

    def get_object(self, queryset=None):
        """Get the portfolio object based on the session."""
        portfolio = self.request.session.get("portfolio")
        if portfolio is None:
            raise Http404("No organization found for this user")
        return portfolio

    def get_form_kwargs(self):
        """Include the instance in the form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object().senior_official
        return kwargs

    def get(self, request, *args, **kwargs):
        """Handle GET requests to display the form."""
        self.object = self.get_object()
        form = self.get_form()
        return self.render_to_response(self.get_context_data(form=form))


class PortfolioMembersView(PortfolioMembersPermissionView, View):

    template_name = "portfolio_members.html"

    def get(self, request):
        """Add additional context data to the template."""
        return render(request, "portfolio_members.html")


class NewMemberView(PortfolioInvitationCreatePermissionView):
    template_name = "portfolio_members_add_new.html"
    form_class = portfolioForms.NewMemberForm

    def get_form_kwargs(self):
        """Pass request and portfolio to form."""
        kwargs = super().get_form_kwargs()
        kwargs["portfolio"] = self.request.session.get("portfolio")
        return kwargs

    def get_success_url(self):
        return reverse("members")

    def form_valid(self, form):
        """Create portfolio invitation from form data."""
        if self.is_ajax():
            return JsonResponse({"is_valid": True})

        # TODO: #3019 - this will probably have to be a small try/catch. Stub for posterity.
        # requested_email = form.cleaned_data.get("email")
        # send_success = self.send_portfolio_invitation_email(requested_email)
        # if not send_success:
        #     return

        # Create instance using form's mapping method.
        # Pass in a new object since we are adding a new record.
        self.object = form.map_cleaned_data_to_instance(form.cleaned_data, PortfolioInvitation())
        self.object.save()
        messages.success(self.request, f"{self.object.email} has been invited.")
        return redirect(self.get_success_url())

    # TODO: #3019
    # def send_portfolio_invitation_email(self, email):
    #     pass

    def form_invalid(self, form):
        if self.is_ajax():
            return JsonResponse({"is_valid": False})
        return super().form_invalid(form)

    def is_ajax(self):
        return self.request.headers.get("X-Requested-With") == "XMLHttpRequest"
