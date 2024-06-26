from datetime import date
from django.test import Client, TestCase, override_settings
from django.contrib.auth import get_user_model
from django_webtest import WebTest  # type: ignore
from django.conf import settings

from api.tests.common import less_console_noise_decorator
from registrar.models.contact import Contact
from registrar.models.domain import Domain
from registrar.models.draft_domain import DraftDomain
from registrar.models.portfolio import Portfolio
from registrar.models.public_contact import PublicContact
from registrar.models.user import User
from registrar.models.user_domain_role import UserDomainRole
from registrar.views.domain import DomainNameserversView

from .common import MockEppLib, less_console_noise  # type: ignore
from unittest.mock import patch
from django.urls import reverse

from registrar.models import (
    DomainRequest,
    DomainInformation,
    Website,
)
from waffle.testutils import override_flag
import logging

logger = logging.getLogger(__name__)


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_endpoint(self):
        response = self.client.get("/health")
        self.assertContains(response, "OK", status_code=200)

    def test_home_page(self):
        """Home page should NOT be available without a login."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)

    def test_domain_request_form_not_logged_in(self):
        """Domain request form not accessible without a logged-in user."""
        response = self.client.get("/request/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=/request/", response.headers["Location"])


class TestWithUser(MockEppLib):
    def setUp(self):
        super().setUp()
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        phone = "8003111234"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email, phone=phone
        )
        title = "test title"
        self.user.contact.title = title
        self.user.contact.save()

        username_regular_incomplete = "test_regular_user_incomplete"
        username_other_incomplete = "test_other_user_incomplete"
        first_name_2 = "Incomplete"
        email_2 = "unicorn@igorville.com"
        # in the case below, REGULAR user is 'Verified by Login.gov, ie. IAL2
        self.incomplete_regular_user = get_user_model().objects.create(
            username=username_regular_incomplete,
            first_name=first_name_2,
            email=email_2,
            verification_type=User.VerificationTypeChoices.REGULAR,
        )
        # in the case below, other user is representative of GRANDFATHERED,
        # VERIFIED_BY_STAFF, INVITED, FIXTURE_USER, ie. IAL1
        self.incomplete_other_user = get_user_model().objects.create(
            username=username_other_incomplete,
            first_name=first_name_2,
            email=email_2,
            verification_type=User.VerificationTypeChoices.VERIFIED_BY_STAFF,
        )

    def tearDown(self):
        # delete any domain requests too
        super().tearDown()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()
        User.objects.all().delete()


class TestEnvironmentVariablesEffects(TestCase):
    def setUp(self):
        self.client = Client()
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )
        self.client.force_login(self.user)

    def tearDown(self):
        super().tearDown()
        Domain.objects.all().delete()
        self.user.delete()

    @override_settings(IS_PRODUCTION=True)
    def test_production_environment(self):
        """No banner on prod."""
        home_page = self.client.get("/")
        self.assertNotContains(home_page, "You are on a test site.")

    @override_settings(IS_PRODUCTION=False)
    def test_non_production_environment(self):
        """Banner on non-prod."""
        home_page = self.client.get("/")
        self.assertContains(home_page, "You are on a test site.")

    def side_effect_raise_value_error(self):
        """Side effect that raises a 500 error"""
        raise ValueError("Some error")

    @less_console_noise_decorator
    @override_settings(IS_PRODUCTION=False)
    def test_non_production_environment_raises_500_and_shows_banner(self):
        """Tests if the non-prod banner is still shown on a 500"""
        fake_domain, _ = Domain.objects.get_or_create(name="igorville.gov")

        # Add a role
        fake_role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=fake_domain, role=UserDomainRole.Roles.MANAGER
        )

        with patch.object(DomainNameserversView, "get_initial", side_effect=self.side_effect_raise_value_error):
            with self.assertRaises(ValueError):
                contact_page_500 = self.client.get(
                    reverse("domain-dns-nameservers", kwargs={"pk": fake_domain.id}),
                )

                # Check that a 500 response is returned
                self.assertEqual(contact_page_500.status_code, 500)

                self.assertContains(contact_page_500, "You are on a test site.")

    @less_console_noise_decorator
    @override_settings(IS_PRODUCTION=True)
    def test_production_environment_raises_500_and_doesnt_show_banner(self):
        """Test if the non-prod banner is not shown on production when a 500 is raised"""

        fake_domain, _ = Domain.objects.get_or_create(name="igorville.gov")

        # Add a role
        fake_role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=fake_domain, role=UserDomainRole.Roles.MANAGER
        )

        with patch.object(DomainNameserversView, "get_initial", side_effect=self.side_effect_raise_value_error):
            with self.assertRaises(ValueError):
                contact_page_500 = self.client.get(
                    reverse("domain-dns-nameservers", kwargs={"pk": fake_domain.id}),
                )

                # Check that a 500 response is returned
                self.assertEqual(contact_page_500.status_code, 500)

                self.assertNotContains(contact_page_500, "You are on a test site.")


class HomeTests(TestWithUser):
    """A series of tests that target the two tables on home.html"""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def tearDown(self):
        super().tearDown()
        Contact.objects.all().delete()

    def test_empty_domain_table(self):
        response = self.client.get("/")
        self.assertContains(response, "You don't have any registered domains.")
        self.assertContains(response, "Why don't I see my domain when I sign in to the registrar?")

    def test_state_help_text(self):
        """Tests if each domain state has help text"""

        # Get the expected text content of each state
        deleted_text = "This domain has been removed and " "is no longer registered to your organization."
        dns_needed_text = "Before this domain can be used, "
        ready_text = "This domain has name servers and is ready for use."
        on_hold_text = "This domain is administratively paused, "
        deleted_text = "This domain has been removed and " "is no longer registered to your organization."
        # Generate a mapping of domain names, the state, and expected messages for the subtest
        test_cases = [
            ("deleted.gov", Domain.State.DELETED, deleted_text),
            ("dnsneeded.gov", Domain.State.DNS_NEEDED, dns_needed_text),
            ("unknown.gov", Domain.State.UNKNOWN, dns_needed_text),
            ("onhold.gov", Domain.State.ON_HOLD, on_hold_text),
            ("ready.gov", Domain.State.READY, ready_text),
        ]
        for domain_name, state, expected_message in test_cases:
            with self.subTest(domain_name=domain_name, state=state, expected_message=expected_message):
                # Create a domain and a UserRole with the given params
                test_domain, _ = Domain.objects.get_or_create(name=domain_name, state=state)
                test_domain.expiration_date = date.today()
                test_domain.save()

                user_role, _ = UserDomainRole.objects.get_or_create(
                    user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER
                )

                # Grab the json response for domain list
                response = self.client.get("/get-domains-json/")

                # Make sure the domain is in the list.
                self.assertContains(response, domain_name, count=1)

                # Check that we have the right text content.
                self.assertContains(response, expected_message, count=1)

                # Delete the role and domain to ensure we're testing in isolation
                user_role.delete()
                test_domain.delete()

    def test_state_help_text_expired(self):
        """Tests if each domain state has help text when expired"""
        expired_text = "This domain has expired, but it is still online. "
        test_domain, _ = Domain.objects.get_or_create(name="expired.gov", state=Domain.State.READY)
        test_domain.expiration_date = date(2011, 10, 10)
        test_domain.save()

        UserDomainRole.objects.get_or_create(user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER)

        # Grab the json response of the domains list
        response = self.client.get("/get-domains-json/")

        # Make sure the domain is in the response
        self.assertContains(response, "expired.gov", count=1)

        # Check that we have the right text content.
        self.assertContains(response, expired_text, count=1)

    def test_state_help_text_no_expiration_date(self):
        """Tests if each domain state has help text when expiration date is None"""

        # == Test a expiration of None for state ready. This should be expired. == #
        expired_text = "This domain has expired, but it is still online. "
        test_domain, _ = Domain.objects.get_or_create(name="imexpired.gov", state=Domain.State.READY)
        test_domain.expiration_date = None
        test_domain.save()

        UserDomainRole.objects.get_or_create(user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER)

        # Grab the json response of the domains list
        response = self.client.get("/get-domains-json/")

        # Make sure domain is in the response
        self.assertContains(response, "imexpired.gov", count=1)

        # Make sure the expiration date is None
        self.assertEqual(test_domain.expiration_date, None)

        # Check that we have the right text content.
        self.assertContains(response, expired_text, count=1)

        # == Test a expiration of None for state unknown. This should not display expired text. == #
        unknown_text = "Before this domain can be used, "
        test_domain_2, _ = Domain.objects.get_or_create(name="notexpired.gov", state=Domain.State.UNKNOWN)
        test_domain_2.expiration_date = None
        test_domain_2.save()

        UserDomainRole.objects.get_or_create(user=self.user, domain=test_domain_2, role=UserDomainRole.Roles.MANAGER)

        # Grab the json response of the domains list
        response = self.client.get("/get-domains-json/")

        # Make sure the response contains the domain
        self.assertContains(response, "notexpired.gov", count=1)

        # Make sure the expiration date is None
        self.assertEqual(test_domain_2.expiration_date, None)

        # Check that we have the right text content.
        self.assertContains(response, unknown_text, count=1)

    def test_home_deletes_withdrawn_domain_request(self):
        """Tests if the user can delete a DomainRequest in the 'withdrawn' status"""

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user, requested_domain=site, status=DomainRequest.DomainRequestStatus.WITHDRAWN
        )

        # Trigger the delete logic
        response = self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request.pk}), follow=True)

        self.assertNotContains(response, "igorville.gov")

        # clean up
        domain_request.delete()

    def test_home_deletes_started_domain_request(self):
        """Tests if the user can delete a DomainRequest in the 'started' status"""

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user, requested_domain=site, status=DomainRequest.DomainRequestStatus.STARTED
        )

        # Trigger the delete logic
        response = self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request.pk}), follow=True)

        self.assertNotContains(response, "igorville.gov")

        # clean up
        domain_request.delete()

    def test_home_doesnt_delete_other_domain_requests(self):
        """Tests to ensure the user can't delete domain requests not in the status of STARTED or WITHDRAWN"""

        # Given that we are including a subset of items that can be deleted while excluding the rest,
        # subTest is appropriate here as otherwise we would need many duplicate tests for the same reason.
        with less_console_noise():
            draft_domain = DraftDomain.objects.create(name="igorville.gov")
            for status in DomainRequest.DomainRequestStatus:
                if status not in [
                    DomainRequest.DomainRequestStatus.STARTED,
                    DomainRequest.DomainRequestStatus.WITHDRAWN,
                ]:
                    with self.subTest(status=status):
                        domain_request = DomainRequest.objects.create(
                            creator=self.user, requested_domain=draft_domain, status=status
                        )

                        # Trigger the delete logic
                        response = self.client.post(
                            reverse("domain-request-delete", kwargs={"pk": domain_request.pk}), follow=True
                        )

                        # Check for a 403 error - the end user should not be allowed to do this
                        self.assertEqual(response.status_code, 403)

                        desired_domain_request = DomainRequest.objects.filter(requested_domain=draft_domain)

                        # Make sure the DomainRequest wasn't deleted
                        self.assertEqual(desired_domain_request.count(), 1)

                        # clean up
                        domain_request.delete()

    def test_home_deletes_domain_request_and_orphans(self):
        """Tests if delete for DomainRequest deletes orphaned Contact objects"""

        # Create the site and contacts to delete (orphaned)
        contact = Contact.objects.create(
            first_name="Henry",
            last_name="Mcfakerson",
        )
        contact_shared = Contact.objects.create(
            first_name="Relative",
            last_name="Aether",
        )

        # Create two non-orphaned contacts
        contact_2 = Contact.objects.create(
            first_name="Saturn",
            last_name="Mars",
        )

        # Attach a user object to a contact (should not be deleted)
        contact_user, _ = Contact.objects.get_or_create(user=self.user)

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.WITHDRAWN,
            authorizing_official=contact,
            submitter=contact_user,
        )
        domain_request.other_contacts.set([contact_2])

        # Create a second domain request to attach contacts to
        site_2 = DraftDomain.objects.create(name="teaville.gov")
        domain_request_2 = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site_2,
            status=DomainRequest.DomainRequestStatus.STARTED,
            authorizing_official=contact_2,
            submitter=contact_shared,
        )
        domain_request_2.other_contacts.set([contact_shared])

        igorville = DomainRequest.objects.filter(requested_domain__name="igorville.gov")
        self.assertTrue(igorville.exists())

        # Trigger the delete logic
        self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request.pk}))

        # igorville is now deleted
        igorville = DomainRequest.objects.filter(requested_domain__name="igorville.gov")
        self.assertFalse(igorville.exists())

        # Check if the orphaned contact was deleted
        orphan = Contact.objects.filter(id=contact.id)
        self.assertFalse(orphan.exists())

        # All non-orphan contacts should still exist and are unaltered
        try:
            current_user = Contact.objects.filter(id=contact_user.id).get()
        except Contact.DoesNotExist:
            self.fail("contact_user (a non-orphaned contact) was deleted")

        self.assertEqual(current_user, contact_user)
        try:
            edge_case = Contact.objects.filter(id=contact_2.id).get()
        except Contact.DoesNotExist:
            self.fail("contact_2 (a non-orphaned contact) was deleted")

        self.assertEqual(edge_case, contact_2)

    def test_home_deletes_domain_request_and_shared_orphans(self):
        """Test the edge case for an object that will become orphaned after a delete
        (but is not an orphan at the time of deletion)"""

        # Create the site and contacts to delete (orphaned)
        contact = Contact.objects.create(
            first_name="Henry",
            last_name="Mcfakerson",
        )
        contact_shared = Contact.objects.create(
            first_name="Relative",
            last_name="Aether",
        )

        # Create two non-orphaned contacts
        contact_2 = Contact.objects.create(
            first_name="Saturn",
            last_name="Mars",
        )

        # Attach a user object to a contact (should not be deleted)
        contact_user, _ = Contact.objects.get_or_create(user=self.user)

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.WITHDRAWN,
            authorizing_official=contact,
            submitter=contact_user,
        )
        domain_request.other_contacts.set([contact_2])

        # Create a second domain request to attach contacts to
        site_2 = DraftDomain.objects.create(name="teaville.gov")
        domain_request_2 = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site_2,
            status=DomainRequest.DomainRequestStatus.STARTED,
            authorizing_official=contact_2,
            submitter=contact_shared,
        )
        domain_request_2.other_contacts.set([contact_shared])

        teaville = DomainRequest.objects.filter(requested_domain__name="teaville.gov")
        self.assertTrue(teaville.exists())

        # Trigger the delete logic
        self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request_2.pk}))

        teaville = DomainRequest.objects.filter(requested_domain__name="teaville.gov")
        self.assertFalse(teaville.exists())

        # Check if the orphaned contact was deleted
        orphan = Contact.objects.filter(id=contact_shared.id)
        self.assertFalse(orphan.exists())

    def test_domain_request_form_view(self):
        response = self.client.get("/request/", follow=True)
        self.assertContains(
            response,
            "You’re about to start your .gov domain request.",
        )

    def test_domain_request_form_with_ineligible_user(self):
        """Domain request form not accessible for an ineligible user.
        This test should be solid enough since all domain request wizard
        views share the same permissions class"""
        self.user.status = User.RESTRICTED
        self.user.save()

        with less_console_noise():
            response = self.client.get("/request/", follow=True)
            self.assertEqual(response.status_code, 403)


class FinishUserProfileTests(TestWithUser, WebTest):
    """A series of tests that target the finish setup page for user profile"""

    # csrf checks do not work well with WebTest.
    # We disable them here.
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.user.title = None
        self.user.save()
        self.client.force_login(self.user)
        self.domain, _ = Domain.objects.get_or_create(name="sampledomain.gov", state=Domain.State.READY)
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

    def tearDown(self):
        super().tearDown()
        PublicContact.objects.filter(domain=self.domain).delete()
        self.role.delete()
        self.domain.delete()
        Domain.objects.all().delete()
        Website.objects.all().delete()
        Contact.objects.all().delete()

    def _set_session_cookie(self):
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

    def _submit_form_webtest(self, form, follow=False, name=None):
        if name:
            page = form.submit(name=name)
        else:
            page = form.submit()
        self._set_session_cookie()
        return page.follow() if follow else page

    @less_console_noise_decorator
    def test_new_user_with_profile_feature_on(self):
        """Tests that a new user is redirected to the profile setup page when profile_feature is on"""
        self.app.set_user(self.incomplete_regular_user.username)
        with override_flag("profile_feature", active=True):
            # This will redirect the user to the setup page.
            # Follow implicity checks if our redirect is working.
            finish_setup_page = self.app.get(reverse("home")).follow()
            self._set_session_cookie()

            # Assert that we're on the right page
            self.assertContains(finish_setup_page, "Finish setting up your profile")

            finish_setup_page = self._submit_form_webtest(finish_setup_page.form)

            self.assertEqual(finish_setup_page.status_code, 200)

            # We're missing a phone number, so the page should tell us that
            self.assertContains(finish_setup_page, "Enter your phone number.")

            # Check for the name of the save button
            self.assertContains(finish_setup_page, "contact_setup_save_button")

            # Add a phone number
            finish_setup_form = finish_setup_page.form
            finish_setup_form["phone"] = "(201) 555-0123"
            finish_setup_form["title"] = "CEO"
            finish_setup_form["last_name"] = "example"
            save_page = self._submit_form_webtest(finish_setup_form, follow=True)

            self.assertEqual(save_page.status_code, 200)
            self.assertContains(save_page, "Your profile has been updated.")

            # Try to navigate back to the home page.
            # This is the same as clicking the back button.
            completed_setup_page = self.app.get(reverse("home"))
            self.assertContains(completed_setup_page, "Manage your domain")

    @less_console_noise_decorator
    def test_new_user_goes_to_domain_request_with_profile_feature_on(self):
        """Tests that a new user is redirected to the domain request page when profile_feature is on"""

        self.app.set_user(self.incomplete_regular_user.username)
        with override_flag("profile_feature", active=True):
            # This will redirect the user to the setup page
            finish_setup_page = self.app.get(reverse("domain-request:")).follow()
            self._set_session_cookie()

            # Assert that we're on the right page
            self.assertContains(finish_setup_page, "Finish setting up your profile")

            finish_setup_page = self._submit_form_webtest(finish_setup_page.form)

            self.assertEqual(finish_setup_page.status_code, 200)

            # We're missing a phone number, so the page should tell us that
            self.assertContains(finish_setup_page, "Enter your phone number.")

            # Check for the name of the save button
            self.assertContains(finish_setup_page, "contact_setup_save_button")

            # Add a phone number
            finish_setup_form = finish_setup_page.form
            finish_setup_form["phone"] = "(201) 555-0123"
            finish_setup_form["title"] = "CEO"
            finish_setup_form["last_name"] = "example"
            completed_setup_page = self._submit_form_webtest(finish_setup_page.form, follow=True)

            self.assertEqual(completed_setup_page.status_code, 200)

            finish_setup_form = completed_setup_page.form

            # Submit the form using the specific submit button to execute the redirect
            completed_setup_page = self._submit_form_webtest(
                finish_setup_form, follow=True, name="contact_setup_submit_button"
            )
            self.assertEqual(completed_setup_page.status_code, 200)

            # Assert that we are still on the
            # Assert that we're on the domain request page
            self.assertNotContains(completed_setup_page, "Finish setting up your profile")
            self.assertNotContains(completed_setup_page, "What contact information should we use to reach you?")

            self.assertContains(completed_setup_page, "You’re about to start your .gov domain request")

    @less_console_noise_decorator
    def test_new_user_with_profile_feature_off(self):
        """Tests that a new user is not redirected to the profile setup page when profile_feature is off"""
        with override_flag("profile_feature", active=False):
            response = self.client.get("/")
        self.assertNotContains(response, "Finish setting up your profile")

    @less_console_noise_decorator
    def test_new_user_goes_to_domain_request_with_profile_feature_off(self):
        """Tests that a new user is redirected to the domain request page
        when profile_feature is off but not the setup page"""
        with override_flag("profile_feature", active=False):
            response = self.client.get("/request/")

        self.assertNotContains(response, "Finish setting up your profile")
        self.assertNotContains(response, "What contact information should we use to reach you?")

        self.assertContains(response, "You’re about to start your .gov domain request")


class FinishUserProfileForOtherUsersTests(TestWithUser, WebTest):
    """A series of tests that target the user profile page intercept for incomplete IAL1 user profiles."""

    # csrf checks do not work well with WebTest.
    # We disable them here.
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.user.title = None
        self.user.save()
        self.client.force_login(self.user)
        self.domain, _ = Domain.objects.get_or_create(name="sampledomain.gov", state=Domain.State.READY)
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

    def tearDown(self):
        super().tearDown()
        PublicContact.objects.filter(domain=self.domain).delete()
        self.role.delete()
        Domain.objects.all().delete()
        Website.objects.all().delete()
        Contact.objects.all().delete()

    def _set_session_cookie(self):
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

    def _submit_form_webtest(self, form, follow=False):
        page = form.submit()
        self._set_session_cookie()
        return page.follow() if follow else page

    @less_console_noise_decorator
    def test_new_user_with_profile_feature_on(self):
        """Tests that a new user is redirected to the profile setup page when profile_feature is on,
        and testing that the confirmation modal is present"""
        self.app.set_user(self.incomplete_other_user.username)
        with override_flag("profile_feature", active=True):
            # This will redirect the user to the user profile page.
            # Follow implicity checks if our redirect is working.
            user_profile_page = self.app.get(reverse("home")).follow()
            self._set_session_cookie()

            # Assert that we're on the right page by testing for the modal
            self.assertContains(user_profile_page, "domain registrants must maintain accurate contact information")

            user_profile_page = self._submit_form_webtest(user_profile_page.form)

            self.assertEqual(user_profile_page.status_code, 200)

            # Assert that modal does not appear on subsequent submits
            self.assertNotContains(user_profile_page, "domain registrants must maintain accurate contact information")
            # Assert that unique error message appears by testing the message in a specific div
            html_content = user_profile_page.content.decode("utf-8")
            # Normalize spaces and line breaks in the HTML content
            normalized_html_content = " ".join(html_content.split())
            # Expected string without extra spaces and line breaks
            expected_string = "Before you can manage your domain, we need you to add contact information."
            # Check for the presence of the <div> element with the specific text
            self.assertIn(f'<div class="usa-alert__body"> {expected_string} </div>', normalized_html_content)

            # We're missing a phone number, so the page should tell us that
            self.assertContains(user_profile_page, "Enter your phone number.")

            # We need to assert that links to manage your domain are not present (in both body and footer)
            self.assertNotContains(user_profile_page, "Manage your domains")
            # Assert the tooltip on the logo, indicating that the logo is not clickable
            self.assertContains(
                user_profile_page, 'title="Before you can manage your domains, we need you to add contact information."'
            )
            # Assert that modal does not appear on subsequent submits
            self.assertNotContains(user_profile_page, "domain registrants must maintain accurate contact information")

            # Add a phone number
            finish_setup_form = user_profile_page.form
            finish_setup_form["phone"] = "(201) 555-0123"
            finish_setup_form["title"] = "CEO"
            finish_setup_form["last_name"] = "example"
            save_page = self._submit_form_webtest(finish_setup_form, follow=True)

            self.assertEqual(save_page.status_code, 200)
            self.assertContains(save_page, "Your profile has been updated.")

            # We need to assert that logo is not clickable and links to manage your domain are not present
            self.assertContains(save_page, "anage your domains", count=2)
            self.assertNotContains(
                save_page, "Before you can manage your domains, we need you to add contact information"
            )
            # Assert that modal does not appear on subsequent submits
            self.assertNotContains(save_page, "domain registrants must maintain accurate contact information")

            # Try to navigate back to the home page.
            # This is the same as clicking the back button.
            completed_setup_page = self.app.get(reverse("home"))
            self.assertContains(completed_setup_page, "Manage your domain")


class UserProfileTests(TestWithUser, WebTest):
    """A series of tests that target your profile functionality"""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.domain, _ = Domain.objects.get_or_create(name="sampledomain.gov", state=Domain.State.READY)
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

    def tearDown(self):
        super().tearDown()
        PublicContact.objects.filter(domain=self.domain).delete()
        self.role.delete()
        self.domain.delete()
        Contact.objects.all().delete()
        DraftDomain.objects.all().delete()
        DomainRequest.objects.all().delete()

    @less_console_noise_decorator
    def error_500_main_nav_with_profile_feature_turned_on(self):
        """test that Your profile is in main nav of 500 error page when profile_feature is on.

        Our treatment of 401 and 403 error page handling with that waffle feature is similar, so we
        assume that the same test results hold true for 401 and 403."""
        with override_flag("profile_feature", active=True):
            with self.assertRaises(Exception):
                response = self.client.get(reverse("home"), follow=True)
                self.assertEqual(response.status_code, 500)
                self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def error_500_main_nav_with_profile_feature_turned_off(self):
        """test that Your profile is not in main nav of 500 error page when profile_feature is off.

        Our treatment of 401 and 403 error page handling with that waffle feature is similar, so we
        assume that the same test results hold true for 401 and 403."""
        with override_flag("profile_feature", active=False):
            with self.assertRaises(Exception):
                response = self.client.get(reverse("home"), follow=True)
                self.assertEqual(response.status_code, 500)
                self.assertNotContains(response, "Your profile")

    @less_console_noise_decorator
    def test_home_page_main_nav_with_profile_feature_on(self):
        """test that Your profile is in main nav of home page when profile_feature is on"""
        with override_flag("profile_feature", active=True):
            response = self.client.get("/", follow=True)
        self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_home_page_main_nav_with_profile_feature_off(self):
        """test that Your profile is not in main nav of home page when profile_feature is off"""
        with override_flag("profile_feature", active=False):
            response = self.client.get("/", follow=True)
        self.assertNotContains(response, "Your profile")

    @less_console_noise_decorator
    def test_new_request_main_nav_with_profile_feature_on(self):
        """test that Your profile is in main nav of new request when profile_feature is on"""
        with override_flag("profile_feature", active=True):
            response = self.client.get("/request/", follow=True)
        self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_new_request_main_nav_with_profile_feature_off(self):
        """test that Your profile is not in main nav of new request when profile_feature is off"""
        with override_flag("profile_feature", active=False):
            response = self.client.get("/request/", follow=True)
        self.assertNotContains(response, "Your profile")

    @less_console_noise_decorator
    def test_user_profile_main_nav_with_profile_feature_on(self):
        """test that Your profile is in main nav of user profile when profile_feature is on"""
        with override_flag("profile_feature", active=True):
            response = self.client.get("/user-profile", follow=True)
        self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_user_profile_returns_404_when_feature_off(self):
        """test that Your profile returns 404 when profile_feature is off"""
        with override_flag("profile_feature", active=False):
            response = self.client.get("/user-profile", follow=True)
        self.assertEqual(response.status_code, 404)

    @less_console_noise_decorator
    def test_user_profile_back_button_when_coming_from_domain_request(self):
        """tests user profile when profile_feature is on,
        and when they are redirected from the domain request page"""
        with override_flag("profile_feature", active=True):
            response = self.client.get("/user-profile?redirect=domain-request:")
        self.assertContains(response, "Your profile")
        self.assertContains(response, "Go back to your domain request")
        self.assertNotContains(response, "Back to manage your domains")

    @less_console_noise_decorator
    def test_domain_detail_profile_feature_on(self):
        """test that domain detail view when profile_feature is on"""
        with override_flag("profile_feature", active=True):
            response = self.client.get(reverse("domain", args=[self.domain.pk]))
        self.assertContains(response, "Your profile")
        self.assertNotContains(response, "Your contact information")

    @less_console_noise_decorator
    def test_domain_your_contact_information_when_profile_feature_off(self):
        """test that Your contact information is accessible when profile_feature is off"""
        with override_flag("profile_feature", active=False):
            response = self.client.get(f"/domain/{self.domain.id}/your-contact-information", follow=True)
        self.assertContains(response, "Your contact information")

    @less_console_noise_decorator
    def test_domain_your_contact_information_when_profile_feature_on(self):
        """test that Your contact information is not accessible when profile feature is on"""
        with override_flag("profile_feature", active=True):
            response = self.client.get(f"/domain/{self.domain.id}/your-contact-information", follow=True)
        self.assertEqual(response.status_code, 404)

    @less_console_noise_decorator
    def test_request_when_profile_feature_on(self):
        """test that Your profile is in request page when profile feature is on"""

        contact_user, _ = Contact.objects.get_or_create(user=self.user)
        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            authorizing_official=contact_user,
            submitter=contact_user,
        )
        with override_flag("profile_feature", active=True):
            response = self.client.get(f"/domain-request/{domain_request.id}", follow=True)
            self.assertContains(response, "Your profile")
            response = self.client.get(f"/domain-request/{domain_request.id}/withdraw", follow=True)
            self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_request_when_profile_feature_off(self):
        """test that Your profile is not in request page when profile feature is off"""

        contact_user, _ = Contact.objects.get_or_create(user=self.user)
        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            authorizing_official=contact_user,
            submitter=contact_user,
        )
        with override_flag("profile_feature", active=False):
            response = self.client.get(f"/domain-request/{domain_request.id}", follow=True)
            self.assertNotContains(response, "Your profile")
            response = self.client.get(f"/domain-request/{domain_request.id}/withdraw", follow=True)
            self.assertNotContains(response, "Your profile")
        # cleanup
        domain_request.delete()
        site.delete()

    @less_console_noise_decorator
    def test_user_profile_form_submission(self):
        """test user profile form submission"""
        self.app.set_user(self.user.username)
        with override_flag("profile_feature", active=True):
            profile_page = self.app.get(reverse("user-profile"))
            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            profile_form = profile_page.form
            profile_form["title"] = "sample title"
            profile_form["phone"] = "(201) 555-1212"
            profile_page = profile_form.submit()
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            profile_page = profile_page.follow()
            self.assertEqual(profile_page.status_code, 200)
            self.assertContains(profile_page, "Your profile has been updated")


class PortfoliosTests(TestWithUser, WebTest):
    """A series of tests that target the organizations"""

    # csrf checks do not work well with WebTest.
    # We disable them here.
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.user.save()
        self.client.force_login(self.user)
        self.domain, _ = Domain.objects.get_or_create(name="sampledomain.gov", state=Domain.State.READY)
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )
        self.portfolio, _ = Portfolio.objects.get_or_create(creator=self.user, organization_name="xyz inc")

    def tearDown(self):
        Portfolio.objects.all().delete()
        super().tearDown()
        PublicContact.objects.filter(domain=self.domain).delete()
        UserDomainRole.objects.all().delete()
        Domain.objects.all().delete()
        Website.objects.all().delete()
        Contact.objects.all().delete()

    def _set_session_cookie(self):
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

    @less_console_noise_decorator
    def test_middleware_redirects_to_portfolio_homepage(self):
        """Tests that a user is redirected to the portfolio homepage when organization_feature is on and
        a portfolio belongs to the user, test for the special h1s which only exist in that version
        of the homepage"""
        self.app.set_user(self.user.username)
        with override_flag("organization_feature", active=True):
            # This will redirect the user to the portfolio page.
            # Follow implicity checks if our redirect is working.
            portfolio_page = self.app.get(reverse("home")).follow()
            self._set_session_cookie()

            # Assert that we're on the right page
            self.assertContains(portfolio_page, self.portfolio.organization_name)

            self.assertContains(portfolio_page, "<h1>Domains</h1>")

    @less_console_noise_decorator
    def test_no_redirect_when_org_flag_false(self):
        """No redirect so no follow,
        implicitely test for the presense of the h2 by looking up its id"""
        self.app.set_user(self.user.username)
        home_page = self.app.get(reverse("home"))
        self._set_session_cookie()

        self.assertNotContains(home_page, self.portfolio.organization_name)

        self.assertContains(home_page, 'id="domain-requests-header"')

    @less_console_noise_decorator
    def test_no_redirect_when_user_has_no_portfolios(self):
        """No redirect so no follow,
        implicitely test for the presense of the h2 by looking up its id"""
        self.portfolio.delete()
        self.app.set_user(self.user.username)
        with override_flag("organization_feature", active=True):
            home_page = self.app.get(reverse("home"))
            self._set_session_cookie()

            self.assertNotContains(home_page, self.portfolio.organization_name)

            self.assertContains(home_page, 'id="domain-requests-header"')
