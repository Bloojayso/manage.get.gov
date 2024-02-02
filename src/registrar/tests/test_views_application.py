from unittest import skip

from django.conf import settings
from django.urls import reverse

from .common import MockSESClient, completed_application  # type: ignore
from django_webtest import WebTest  # type: ignore
import boto3_mocking  # type: ignore

from registrar.models import (
    DomainApplication,
    Domain,
    DomainInformation,
    Contact,
    User,
    Website,
)
from registrar.views.application import ApplicationWizard, Step

from .common import less_console_noise
from .test_views import TestWithUser

import logging

logger = logging.getLogger(__name__)


class DomainApplicationTests(TestWithUser, WebTest):

    """Webtests for domain application to test filling and submitting."""

    # Doesn't work with CSRF checking
    # hypothesis is that CSRF_USE_SESSIONS is incompatible with WebTest
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)
        self.TITLES = ApplicationWizard.TITLES

    def test_application_form_intro_acknowledgement(self):
        """Tests that user is presented with intro acknowledgement page"""
        intro_page = self.app.get(reverse("application:"))
        self.assertContains(intro_page, "You’re about to start your .gov domain request")

    def test_application_form_intro_is_skipped_when_edit_access(self):
        """Tests that user is NOT presented with intro acknowledgement page when accessed through 'edit'"""
        completed_application(status=DomainApplication.ApplicationStatus.STARTED, user=self.user)
        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Edit" link
        detail_page = home_page.click("Edit", index=0)
        # Check that the response is a redirect
        self.assertEqual(detail_page.status_code, 302)
        # You can access the 'Location' header to get the redirect URL
        redirect_url = detail_page.url
        self.assertEqual(redirect_url, "/request/organization_type/")

    def test_application_form_empty_submit(self):
        """Tests empty submit on the first page after the acknowledgement page"""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # submitting should get back the same page if the required field is empty
        result = type_page.forms[0].submit()
        self.assertIn("What kind of U.S.-based government organization do you represent?", result)

    def test_application_multiple_applications_exist(self):
        """Test that an info message appears when user has multiple applications already"""
        # create and submit an application
        application = completed_application(user=self.user)
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                application.submit()
                application.save()

        # now, attempt to create another one
        with less_console_noise():
            intro_page = self.app.get(reverse("application:"))
            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
            intro_form = intro_page.forms[0]
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            intro_result = intro_form.submit()

            # follow first redirect
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            type_page = intro_result.follow()
            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

            self.assertContains(type_page, "You cannot submit this request yet")

    @boto3_mocking.patching
    def test_application_form_submission(self):
        """
        Can fill out the entire form and submit.
        As we add additional form pages, we need to include them here to make
        this test work.

        This test also looks for the long organization name on the summary page.

        This also tests for the presence of a modal trigger and the dynamic test
        in the modal header on the submit page.
        """
        num_pages_tested = 0
        # elections, type_of_work, tribal_government
        SKIPPED_PAGES = 3
        num_pages = len(self.TITLES) - SKIPPED_PAGES

        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----
        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "federal"
        # test next button and validate data
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()
        # should see results in db
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.organization_type, "federal")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(type_result.status_code, 302)
        self.assertEqual(type_result["Location"], "/request/organization_federal/")
        num_pages_tested += 1

        # ---- FEDERAL BRANCH PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        federal_page = type_result.follow()
        federal_form = federal_page.forms[0]
        federal_form["organization_federal-federal_type"] = "executive"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.federal_type, "executive")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(federal_result.status_code, 302)
        self.assertEqual(federal_result["Location"], "/request/organization_contact/")
        num_pages_tested += 1

        # ---- ORG CONTACT PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_page = federal_result.follow()
        org_contact_form = org_contact_page.forms[0]
        # federal agency so we have to fill in federal_agency
        org_contact_form["organization_contact-federal_agency"] = "General Services Administration"
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-address_line2"] = "address 2"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"
        org_contact_form["organization_contact-urbanization"] = "URB Royal Oaks"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.organization_name, "Testorg")
        self.assertEqual(application.address_line1, "address 1")
        self.assertEqual(application.address_line2, "address 2")
        self.assertEqual(application.city, "NYC")
        self.assertEqual(application.state_territory, "NY")
        self.assertEqual(application.zipcode, "10002")
        self.assertEqual(application.urbanization, "URB Royal Oaks")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(org_contact_result.status_code, 302)
        self.assertEqual(org_contact_result["Location"], "/request/authorizing_official/")
        num_pages_tested += 1

        # ---- AUTHORIZING OFFICIAL PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = org_contact_result.follow()
        ao_form = ao_page.forms[0]
        ao_form["authorizing_official-first_name"] = "Testy ATO"
        ao_form["authorizing_official-last_name"] = "Tester ATO"
        ao_form["authorizing_official-title"] = "Chief Tester"
        ao_form["authorizing_official-email"] = "testy@town.com"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_result = ao_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.authorizing_official.first_name, "Testy ATO")
        self.assertEqual(application.authorizing_official.last_name, "Tester ATO")
        self.assertEqual(application.authorizing_official.title, "Chief Tester")
        self.assertEqual(application.authorizing_official.email, "testy@town.com")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(ao_result.status_code, 302)
        self.assertEqual(ao_result["Location"], "/request/current_sites/")
        num_pages_tested += 1

        # ---- CURRENT SITES PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_page = ao_result.follow()
        current_sites_form = current_sites_page.forms[0]
        current_sites_form["current_sites-0-website"] = "www.city.com"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_result = current_sites_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(
            application.current_websites.filter(website="http://www.city.com").count(),
            1,
        )
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(current_sites_result.status_code, 302)
        self.assertEqual(current_sites_result["Location"], "/request/dotgov_domain/")
        num_pages_tested += 1

        # ---- DOTGOV DOMAIN PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page = current_sites_result.follow()
        dotgov_form = dotgov_page.forms[0]
        dotgov_form["dotgov_domain-requested_domain"] = "city"
        dotgov_form["dotgov_domain-0-alternative_domain"] = "city1"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_result = dotgov_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.requested_domain.name, "city.gov")
        self.assertEqual(application.alternative_domains.filter(website="city1.gov").count(), 1)
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(dotgov_result.status_code, 302)
        self.assertEqual(dotgov_result["Location"], "/request/purpose/")
        num_pages_tested += 1

        # ---- PURPOSE PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        purpose_page = dotgov_result.follow()
        purpose_form = purpose_page.forms[0]
        purpose_form["purpose-purpose"] = "For all kinds of things."

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        purpose_result = purpose_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.purpose, "For all kinds of things.")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(purpose_result.status_code, 302)
        self.assertEqual(purpose_result["Location"], "/request/your_contact/")
        num_pages_tested += 1

        # ---- YOUR CONTACT INFO PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        your_contact_page = purpose_result.follow()
        your_contact_form = your_contact_page.forms[0]

        your_contact_form["your_contact-first_name"] = "Testy you"
        your_contact_form["your_contact-last_name"] = "Tester you"
        your_contact_form["your_contact-title"] = "Admin Tester"
        your_contact_form["your_contact-email"] = "testy-admin@town.com"
        your_contact_form["your_contact-phone"] = "(201) 555 5556"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        your_contact_result = your_contact_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.submitter.first_name, "Testy you")
        self.assertEqual(application.submitter.last_name, "Tester you")
        self.assertEqual(application.submitter.title, "Admin Tester")
        self.assertEqual(application.submitter.email, "testy-admin@town.com")
        self.assertEqual(application.submitter.phone, "(201) 555 5556")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(your_contact_result.status_code, 302)
        self.assertEqual(your_contact_result["Location"], "/request/other_contacts/")
        num_pages_tested += 1

        # ---- OTHER CONTACTS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        other_contacts_page = your_contact_result.follow()

        # This page has 3 forms in 1.
        # Let's set the yes/no radios to enable the other contacts fieldsets
        other_contacts_form = other_contacts_page.forms[0]

        other_contacts_form["other_contacts-has_other_contacts"] = "True"

        other_contacts_form["other_contacts-0-first_name"] = "Testy2"
        other_contacts_form["other_contacts-0-last_name"] = "Tester2"
        other_contacts_form["other_contacts-0-title"] = "Another Tester"
        other_contacts_form["other_contacts-0-email"] = "testy2@town.com"
        other_contacts_form["other_contacts-0-phone"] = "(201) 555 5557"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        other_contacts_result = other_contacts_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(
            application.other_contacts.filter(
                first_name="Testy2",
                last_name="Tester2",
                title="Another Tester",
                email="testy2@town.com",
                phone="(201) 555 5557",
            ).count(),
            1,
        )
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(other_contacts_result.status_code, 302)
        self.assertEqual(other_contacts_result["Location"], "/request/anything_else/")
        num_pages_tested += 1

        # ---- ANYTHING ELSE PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        anything_else_page = other_contacts_result.follow()
        anything_else_form = anything_else_page.forms[0]

        anything_else_form["anything_else-anything_else"] = "Nothing else."

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        anything_else_result = anything_else_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.anything_else, "Nothing else.")
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(anything_else_result.status_code, 302)
        self.assertEqual(anything_else_result["Location"], "/request/requirements/")
        num_pages_tested += 1

        # ---- REQUIREMENTS PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_page = anything_else_result.follow()
        requirements_form = requirements_page.forms[0]

        requirements_form["requirements-is_policy_acknowledged"] = True

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        requirements_result = requirements_form.submit()
        # validate that data from this step are being saved
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(application.is_policy_acknowledged, True)
        # the post request should return a redirect to the next form in
        # the application
        self.assertEqual(requirements_result.status_code, 302)
        self.assertEqual(requirements_result["Location"], "/request/review/")
        num_pages_tested += 1

        # ---- REVIEW AND FINSIHED PAGES  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        review_page = requirements_result.follow()
        review_form = review_page.forms[0]

        # Review page contains all the previously entered data
        # Let's make sure the long org name is displayed
        self.assertContains(review_page, "Federal")
        self.assertContains(review_page, "Executive")
        self.assertContains(review_page, "Testorg")
        self.assertContains(review_page, "address 1")
        self.assertContains(review_page, "address 2")
        self.assertContains(review_page, "NYC")
        self.assertContains(review_page, "NY")
        self.assertContains(review_page, "10002")
        self.assertContains(review_page, "URB Royal Oaks")
        self.assertContains(review_page, "Testy ATO")
        self.assertContains(review_page, "Tester ATO")
        self.assertContains(review_page, "Chief Tester")
        self.assertContains(review_page, "testy@town.com")
        self.assertContains(review_page, "city.com")
        self.assertContains(review_page, "city.gov")
        self.assertContains(review_page, "city1.gov")
        self.assertContains(review_page, "For all kinds of things.")
        self.assertContains(review_page, "Testy you")
        self.assertContains(review_page, "Tester you")
        self.assertContains(review_page, "Admin Tester")
        self.assertContains(review_page, "testy-admin@town.com")
        self.assertContains(review_page, "(201) 555-5556")
        self.assertContains(review_page, "Testy2")
        self.assertContains(review_page, "Tester2")
        self.assertContains(review_page, "Another Tester")
        self.assertContains(review_page, "testy2@town.com")
        self.assertContains(review_page, "(201) 555-5557")
        self.assertContains(review_page, "Nothing else.")

        # We can't test the modal itself as it relies on JS for init and triggering,
        # but we can test for the existence of its trigger:
        self.assertContains(review_page, "toggle-submit-domain-request")
        # And the existence of the modal's data parked and ready for the js init.
        # The next assert also tests for the passed requested domain context from
        # the view > application_form > modal
        self.assertContains(review_page, "You are about to submit a domain request for city.gov")

        # final submission results in a redirect to the "finished" URL
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        with less_console_noise():
            review_result = review_form.submit()

        self.assertEqual(review_result.status_code, 302)
        self.assertEqual(review_result["Location"], "/request/finished/")
        num_pages_tested += 1

        # following this redirect is a GET request, so include the cookie
        # here too.
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        with less_console_noise():
            final_result = review_result.follow()
        self.assertContains(final_result, "Thanks for your domain request!")

        # check that any new pages are added to this test
        self.assertEqual(num_pages, num_pages_tested)

    # This is the start of a test to check an existing application, it currently
    # does not work and results in errors as noted in:
    # https://github.com/cisagov/getgov/pull/728
    @skip("WIP")
    def test_application_form_started_allsteps(self):
        num_pages_tested = 0
        # elections, type_of_work, tribal_government
        SKIPPED_PAGES = 3
        DASHBOARD_PAGE = 1
        num_pages = len(self.TITLES) - SKIPPED_PAGES + DASHBOARD_PAGE

        application = completed_application(user=self.user)
        application.save()
        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        self.assertContains(home_page, "Started")
        num_pages_tested += 1

        # TODO: For some reason this click results in a new application being generated
        # This appraoch is an alternatie to using get as is being done below
        #
        # type_page = home_page.click("Edit")

        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        url = reverse("edit-application", kwargs={"id": application.pk})
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # TODO: The following line results in a django error on middleware
        response = self.client.get(url, follow=True)
        self.assertContains(response, "Type of organization")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # TODO: Step through the remaining pages

        self.assertEqual(num_pages, num_pages_tested)

    def test_application_form_conditional_federal(self):
        """Federal branch question is shown for federal organizations."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----

        # the conditional step titles shouldn't appear initially
        self.assertNotContains(type_page, self.TITLES["organization_federal"])
        self.assertNotContains(type_page, self.TITLES["organization_election"])
        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "federal"

        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # the post request should return a redirect to the federal branch
        # question
        self.assertEqual(type_result.status_code, 302)
        self.assertEqual(type_result["Location"], "/request/organization_federal/")

        # and the step label should appear in the sidebar of the resulting page
        # but the step label for the elections page should not appear
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()
        self.assertContains(federal_page, self.TITLES["organization_federal"])
        self.assertNotContains(federal_page, self.TITLES["organization_election"])

        # continuing on in the flow we need to see top-level agency on the
        # contact page
        federal_page.forms[0]["organization_federal-federal_type"] = "executive"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_page.forms[0].submit()
        # the post request should return a redirect to the contact
        # question
        self.assertEqual(federal_result.status_code, 302)
        self.assertEqual(federal_result["Location"], "/request/organization_contact/")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = federal_result.follow()
        self.assertContains(contact_page, "Federal agency")

    def test_application_form_conditional_elections(self):
        """Election question is shown for other organizations."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----

        # the conditional step titles shouldn't appear initially
        self.assertNotContains(type_page, self.TITLES["organization_federal"])
        self.assertNotContains(type_page, self.TITLES["organization_election"])
        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "county"

        # set the session ID before .submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # the post request should return a redirect to the elections question
        self.assertEqual(type_result.status_code, 302)
        self.assertEqual(type_result["Location"], "/request/organization_election/")

        # and the step label should appear in the sidebar of the resulting page
        # but the step label for the elections page should not appear
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_page = type_result.follow()
        self.assertContains(election_page, self.TITLES["organization_election"])
        self.assertNotContains(election_page, self.TITLES["organization_federal"])

        # continuing on in the flow we need to NOT see top-level agency on the
        # contact page
        election_page.forms[0]["organization_election-is_election_board"] = "True"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_result = election_page.forms[0].submit()
        # the post request should return a redirect to the contact
        # question
        self.assertEqual(election_result.status_code, 302)
        self.assertEqual(election_result["Location"], "/request/organization_contact/")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = election_result.follow()
        self.assertNotContains(contact_page, "Federal agency")

    def test_application_form_section_skipping(self):
        """Can skip forward and back in sections"""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "federal"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()

        # Now on federal type page, click back to the organization type
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        new_page = federal_page.click(str(self.TITLES["organization_type"]), index=0)

        # Should be a link to the organization_federal page
        self.assertGreater(
            len(new_page.html.find_all("a", href="/request/organization_federal/")),
            0,
        )

    def test_application_form_nonfederal(self):
        """Non-federal organizations don't have to provide their federal agency."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = DomainApplication.OrganizationChoices.INTERSTATE
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()
        org_contact_form = contact_page.forms[0]

        self.assertNotIn("federal_agency", org_contact_form.fields)

        # minimal fields that must be filled out
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_result = org_contact_form.submit()

        # the post request should return a redirect to the
        # about your organization page if it was successful.
        self.assertEqual(contact_result.status_code, 302)
        self.assertEqual(contact_result["Location"], "/request/about_your_organization/")

    def test_application_about_your_organization_special(self):
        """Special districts have to answer an additional question."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = DomainApplication.OrganizationChoices.SPECIAL_DISTRICT
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_page.forms[0].submit()
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()

        self.assertContains(contact_page, self.TITLES[Step.ABOUT_YOUR_ORGANIZATION])

    def test_yes_no_form_inits_blank_for_new_application(self):
        """On the Other Contacts page, the yes/no form gets initialized with nothing selected for
        new applications"""
        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, None)

    def test_yes_no_form_inits_yes_for_application_with_other_contacts(self):
        """On the Other Contacts page, the yes/no form gets initialized with YES selected if the
        application has other contacts"""
        # Application has other contacts by default
        application = completed_application(user=self.user)
        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "True")

    def test_yes_no_form_inits_no_for_application_with_no_other_contacts_rationale(self):
        """On the Other Contacts page, the yes/no form gets initialized with NO selected if the
        application has no other contacts"""
        # Application has other contacts by default
        application = completed_application(user=self.user, has_other_contacts=False)
        application.no_other_contacts_rationale = "Hello!"
        application.save()
        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "False")

    def test_submitting_other_contacts_deletes_no_other_contacts_rationale(self):
        """When a user submits the Other Contacts form with other contacts selected, the application's
        no other contacts rationale gets deleted"""
        # Application has other contacts by default
        application = completed_application(user=self.user, has_other_contacts=False)
        application.no_other_contacts_rationale = "Hello!"
        application.save()
        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "False")

        other_contacts_form["other_contacts-has_other_contacts"] = "True"

        other_contacts_form["other_contacts-0-first_name"] = "Testy"
        other_contacts_form["other_contacts-0-middle_name"] = ""
        other_contacts_form["other_contacts-0-last_name"] = "McTesterson"
        other_contacts_form["other_contacts-0-title"] = "Lord"
        other_contacts_form["other_contacts-0-email"] = "testy@abc.org"
        other_contacts_form["other_contacts-0-phone"] = "(201) 555-0123"

        # Submit the now empty form
        other_contacts_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the no_other_contacts_rationale we saved earlier has been removed from the database
        application = DomainApplication.objects.get()
        self.assertEqual(
            application.other_contacts.count(),
            1,
        )

        self.assertEquals(
            application.no_other_contacts_rationale,
            None,
        )

    def test_submitting_no_other_contacts_rationale_deletes_other_contacts(self):
        """When a user submits the Other Contacts form with no other contacts selected, the application's
        other contacts get deleted for other contacts that exist and are not joined to other objects
        """
        # Application has other contacts by default
        application = completed_application(user=self.user)
        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "True")

        other_contacts_form["other_contacts-has_other_contacts"] = "False"

        other_contacts_form["other_contacts-no_other_contacts_rationale"] = "Hello again!"

        # Submit the now empty form
        other_contacts_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the no_other_contacts_rationale we saved earlier has been removed from the database
        application = DomainApplication.objects.get()
        self.assertEqual(
            application.other_contacts.count(),
            0,
        )

        self.assertEquals(
            application.no_other_contacts_rationale,
            "Hello again!",
        )

    def test_submitting_no_other_contacts_rationale_removes_reference_other_contacts_when_joined(self):
        """When a user submits the Other Contacts form with no other contacts selected, the application's
        other contacts references get removed for other contacts that exist and are joined to other objects"""
        # Populate the database with a domain application that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(555) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(555) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(555) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(other)

        # Now let's join the other contact to another object
        domain_info = DomainInformation.objects.create(creator=self.user)
        domain_info.other_contacts.set([other])

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]
        self.assertEquals(other_contacts_form["other_contacts-has_other_contacts"].value, "True")

        other_contacts_form["other_contacts-has_other_contacts"] = "False"

        other_contacts_form["other_contacts-no_other_contacts_rationale"] = "Hello again!"

        # Submit the now empty form
        other_contacts_form.submit()

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the no_other_contacts_rationale we saved earlier is no longer associated with the application
        application = DomainApplication.objects.get()
        self.assertEqual(
            application.other_contacts.count(),
            0,
        )

        # Verify that the 'other' contact object still exists
        domain_info = DomainInformation.objects.get()
        self.assertEqual(
            domain_info.other_contacts.count(),
            1,
        )
        self.assertEqual(
            domain_info.other_contacts.all()[0].first_name,
            "Testy2",
        )

        self.assertEquals(
            application.no_other_contacts_rationale,
            "Hello again!",
        )

    def test_if_yes_no_form_is_no_then_no_other_contacts_required(self):
        """Applicants with no other contacts have to give a reason."""
        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        other_contacts_form = other_contacts_page.forms[0]
        other_contacts_form["other_contacts-has_other_contacts"] = "False"
        response = other_contacts_page.forms[0].submit()

        # The textarea for no other contacts returns this error message
        # Assert that it is returned, ie the no other contacts form is required
        self.assertContains(response, "Rationale for no other employees is required.")

        # The first name field for other contacts returns this error message
        # Assert that it is not returned, ie the contacts form is not required
        self.assertNotContains(response, "Enter the first name / given name of this contact.")

    def test_if_yes_no_form_is_yes_then_other_contacts_required(self):
        """Applicants with other contacts do not have to give a reason."""
        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        other_contacts_form = other_contacts_page.forms[0]
        other_contacts_form["other_contacts-has_other_contacts"] = "True"
        response = other_contacts_page.forms[0].submit()

        # The textarea for no other contacts returns this error message
        # Assert that it is not returned, ie the no other contacts form is not required
        self.assertNotContains(response, "Rationale for no other employees is required.")

        # The first name field for other contacts returns this error message
        # Assert that it is returned, ie the contacts form is required
        self.assertContains(response, "Enter the first name / given name of this contact.")

    def test_delete_other_contact(self):
        """Other contacts can be deleted after being saved to database.

        This formset uses the DJANGO DELETE widget. We'll test that by setting 2 contacts on an application,
        loading the form and marking one contact up for deletion."""
        # Populate the database with a domain application that
        # has 2 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(201) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(201) 555 5557",
        )
        other2, _ = Contact.objects.get_or_create(
            first_name="Testy3",
            last_name="Tester3",
            title="Another Tester",
            email="testy3@town.com",
            phone="(201) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(other)
        application.other_contacts.add(other2)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded with both other contacts
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy2")
        self.assertEqual(other_contacts_form["other_contacts-1-first_name"].value, "Testy3")

        # Mark the first dude for deletion
        other_contacts_form.set("other_contacts-0-DELETE", "on")

        # Submit the form
        other_contacts_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the first dude was deleted
        application = DomainApplication.objects.get()
        self.assertEqual(application.other_contacts.count(), 1)
        self.assertEqual(application.other_contacts.first().first_name, "Testy3")

    def test_delete_other_contact_does_not_allow_zero_contacts(self):
        """Delete Other Contact does not allow submission with zero contacts."""
        # Populate the database with a domain application that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(201) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(201) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(other)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy2")

        # Mark the first dude for deletion
        other_contacts_form.set("other_contacts-0-DELETE", "on")

        # Submit the form
        other_contacts_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        # Verify that the contact was not deleted
        application = DomainApplication.objects.get()
        self.assertEqual(application.other_contacts.count(), 1)
        self.assertEqual(application.other_contacts.first().first_name, "Testy2")

    def test_delete_other_contact_sets_visible_empty_form_as_required_after_failed_submit(self):
        """When you:
            1. add an empty contact,
            2. delete existing contacts,
            3. then submit,
        The forms on page reload shows all the required fields and their errors."""

        # Populate the database with a domain application that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch so we can reuse the other contact
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(201) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(201) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(other)

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy2")

        # Set total forms to 2 indicating an additional formset was added.
        # Submit no data though for the second formset.
        # Set the first formset to be deleted.
        other_contacts_form["other_contacts-TOTAL_FORMS"] = "2"
        other_contacts_form.set("other_contacts-0-DELETE", "on")

        response = other_contacts_form.submit()

        # Assert that the response presents errors to the user, including to
        # Enter the first name ...
        self.assertContains(response, "Enter the first name / given name of this contact.")

    def test_edit_other_contact_in_place(self):
        """When you:
            1. edit an existing contact which is not joined to another model,
            2. then submit,
        The application is linked to the existing contact, and the existing contact updated."""

        # Populate the database with a domain application that
        # has 1 "other contact" assigned to it
        # We'll do it from scratch
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(201) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(201) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(other)

        # other_contact_pk is the initial pk of the other contact. set it before update
        # to be able to verify after update that the same contact object is in place
        other_contact_pk = other.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy2")

        # update the first name of the contact
        other_contacts_form["other_contacts-0-first_name"] = "Testy3"

        # Submit the updated form
        other_contacts_form.submit()

        application.refresh_from_db()

        # assert that the Other Contact is updated "in place"
        other_contact = application.other_contacts.all()[0]
        self.assertEquals(other_contact_pk, other_contact.id)
        self.assertEquals("Testy3", other_contact.first_name)

    def test_edit_other_contact_creates_new(self):
        """When you:
            1. edit an existing contact which IS joined to another model,
            2. then submit,
        The application is linked to a new contact, and the new contact is updated."""

        # Populate the database with a domain application that
        # has 1 "other contact" assigned to it, the other contact is also
        # the authorizing official initially
        # We'll do it from scratch
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(201) 555 5556",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            submitter=you,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(ao)

        # other_contact_pk is the initial pk of the other contact. set it before update
        # to be able to verify after update that the ao contact is still in place
        # and not updated, and that the new contact has a new id
        other_contact_pk = ao.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_page = self.app.get(reverse("application:other_contacts"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        other_contacts_form = other_contacts_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(other_contacts_form["other_contacts-0-first_name"].value, "Testy")

        # update the first name of the contact
        other_contacts_form["other_contacts-0-first_name"] = "Testy2"

        # Submit the updated form
        other_contacts_form.submit()

        application.refresh_from_db()

        # assert that other contact info is updated, and that a new Contact
        # is created for the other contact
        other_contact = application.other_contacts.all()[0]
        self.assertNotEquals(other_contact_pk, other_contact.id)
        self.assertEquals("Testy2", other_contact.first_name)
        # assert that the authorizing official is not updated
        authorizing_official = application.authorizing_official
        self.assertEquals("Testy", authorizing_official.first_name)

    def test_edit_authorizing_official_in_place(self):
        """When you:
            1. edit an authorizing official which is not joined to another model,
            2. then submit,
        The application is linked to the existing ao, and the ao updated."""

        # Populate the database with a domain application that
        # has an authorizing_official (ao)
        # We'll do it from scratch
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            creator=self.user,
            status="started",
        )

        # ao_pk is the initial pk of the Authorizing Official. set it before update
        # to be able to verify after update that the same Contact object is in place
        ao_pk = ao.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        ao_page = self.app.get(reverse("application:authorizing_official"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        ao_form = ao_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(ao_form["authorizing_official-first_name"].value, "Testy")

        # update the first name of the contact
        ao_form["authorizing_official-first_name"] = "Testy2"

        # Submit the updated form
        ao_form.submit()

        application.refresh_from_db()

        # assert AO is updated "in place"
        updated_ao = application.authorizing_official
        self.assertEquals(ao_pk, updated_ao.id)
        self.assertEquals("Testy2", updated_ao.first_name)

    def test_edit_authorizing_official_creates_new(self):
        """When you:
            1. edit an existing authorizing official which IS joined to another model,
            2. then submit,
        The application is linked to a new Contact, and the new Contact is updated."""

        # Populate the database with a domain application that
        # has authorizing official assigned to it, the authorizing offical is also
        # an other contact initially
        # We'll do it from scratch
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(ao)

        # ao_pk is the initial pk of the authorizing official. set it before update
        # to be able to verify after update that the other contact is still in place
        # and not updated, and that the new ao has a new id
        ao_pk = ao.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        ao_page = self.app.get(reverse("application:authorizing_official"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        ao_form = ao_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(ao_form["authorizing_official-first_name"].value, "Testy")

        # update the first name of the contact
        ao_form["authorizing_official-first_name"] = "Testy2"

        # Submit the updated form
        ao_form.submit()

        application.refresh_from_db()

        # assert that the other contact is not updated
        other_contacts = application.other_contacts.all()
        other_contact = other_contacts[0]
        self.assertEquals(ao_pk, other_contact.id)
        self.assertEquals("Testy", other_contact.first_name)
        # assert that the authorizing official is updated
        authorizing_official = application.authorizing_official
        self.assertEquals("Testy2", authorizing_official.first_name)

    def test_edit_submitter_in_place(self):
        """When you:
            1. edit a submitter (your contact) which is not joined to another model,
            2. then submit,
        The application is linked to the existing submitter, and the submitter updated."""

        # Populate the database with a domain application that
        # has a submitter
        # We'll do it from scratch
        you, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            submitter=you,
            creator=self.user,
            status="started",
        )

        # submitter_pk is the initial pk of the submitter. set it before update
        # to be able to verify after update that the same contact object is in place
        submitter_pk = you.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        your_contact_page = self.app.get(reverse("application:your_contact"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        your_contact_form = your_contact_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(your_contact_form["your_contact-first_name"].value, "Testy")

        # update the first name of the contact
        your_contact_form["your_contact-first_name"] = "Testy2"

        # Submit the updated form
        your_contact_form.submit()

        application.refresh_from_db()

        updated_submitter = application.submitter
        self.assertEquals(submitter_pk, updated_submitter.id)
        self.assertEquals("Testy2", updated_submitter.first_name)

    def test_edit_submitter_creates_new(self):
        """When you:
            1. edit an existing your contact which IS joined to another model,
            2. then submit,
        The application is linked to a new Contact, and the new Contact is updated."""

        # Populate the database with a domain application that
        # has submitter assigned to it, the submitter is also
        # an other contact initially
        # We'll do it from scratch
        submitter, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(201) 555 5555",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            submitter=submitter,
            creator=self.user,
            status="started",
        )
        application.other_contacts.add(submitter)

        # submitter_pk is the initial pk of the your contact. set it before update
        # to be able to verify after update that the other contact is still in place
        # and not updated, and that the new submitter has a new id
        submitter_pk = submitter.id

        # prime the form by visiting /edit
        self.app.get(reverse("edit-application", kwargs={"id": application.pk}))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        your_contact_page = self.app.get(reverse("application:your_contact"))
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

        your_contact_form = your_contact_page.forms[0]

        # Minimal check to ensure the form is loaded
        self.assertEqual(your_contact_form["your_contact-first_name"].value, "Testy")

        # update the first name of the contact
        your_contact_form["your_contact-first_name"] = "Testy2"

        # Submit the updated form
        your_contact_form.submit()

        application.refresh_from_db()

        # assert that the other contact is not updated
        other_contacts = application.other_contacts.all()
        other_contact = other_contacts[0]
        self.assertEquals(submitter_pk, other_contact.id)
        self.assertEquals("Testy", other_contact.first_name)
        # assert that the submitter is updated
        submitter = application.submitter
        self.assertEquals("Testy2", submitter.first_name)

    def test_application_about_your_organiztion_interstate(self):
        """Special districts have to answer an additional question."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = DomainApplication.OrganizationChoices.INTERSTATE
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        contact_page = type_result.follow()

        self.assertContains(contact_page, self.TITLES[Step.ABOUT_YOUR_ORGANIZATION])

    def test_application_tribal_government(self):
        """Tribal organizations have to answer an additional question."""
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = DomainApplication.OrganizationChoices.TRIBAL
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()
        # the tribal government page comes immediately afterwards
        self.assertIn("/tribal_government", type_result.headers["Location"])
        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        tribal_government_page = type_result.follow()

        # and the step is on the sidebar list.
        self.assertContains(tribal_government_page, self.TITLES[Step.TRIBAL_GOVERNMENT])

    def test_application_ao_dynamic_text(self):
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----
        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "federal"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # ---- FEDERAL BRANCH PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()
        federal_form = federal_page.forms[0]
        federal_form["organization_federal-federal_type"] = "executive"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_form.submit()

        # ---- ORG CONTACT PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_page = federal_result.follow()
        org_contact_form = org_contact_page.forms[0]
        # federal agency so we have to fill in federal_agency
        org_contact_form["organization_contact-federal_agency"] = "General Services Administration"
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-address_line2"] = "address 2"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"
        org_contact_form["organization_contact-urbanization"] = "URB Royal Oaks"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()

        # ---- AO CONTACT PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = org_contact_result.follow()
        self.assertContains(ao_page, "Executive branch federal agencies")

        # Go back to organization type page and change type
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page.click(str(self.TITLES["organization_type"]), index=0)
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_form["organization_type-organization_type"] = "city"
        type_result = type_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_page = type_result.follow()

        # Go back to AO page and test the dynamic text changed
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = election_page.click(str(self.TITLES["authorizing_official"]), index=0)
        self.assertContains(ao_page, "Domain requests from cities")

    def test_application_dotgov_domain_dynamic_text(self):
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        # ---- TYPE PAGE  ----
        type_form = type_page.forms[0]
        type_form["organization_type-organization_type"] = "federal"

        # test next button
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_result = type_form.submit()

        # ---- FEDERAL BRANCH PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_page = type_result.follow()
        federal_form = federal_page.forms[0]
        federal_form["organization_federal-federal_type"] = "executive"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        federal_result = federal_form.submit()

        # ---- ORG CONTACT PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_page = federal_result.follow()
        org_contact_form = org_contact_page.forms[0]
        # federal agency so we have to fill in federal_agency
        org_contact_form["organization_contact-federal_agency"] = "General Services Administration"
        org_contact_form["organization_contact-organization_name"] = "Testorg"
        org_contact_form["organization_contact-address_line1"] = "address 1"
        org_contact_form["organization_contact-address_line2"] = "address 2"
        org_contact_form["organization_contact-city"] = "NYC"
        org_contact_form["organization_contact-state_territory"] = "NY"
        org_contact_form["organization_contact-zipcode"] = "10002"
        org_contact_form["organization_contact-urbanization"] = "URB Royal Oaks"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        org_contact_result = org_contact_form.submit()

        # ---- AO CONTACT PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = org_contact_result.follow()

        # ---- AUTHORIZING OFFICIAL PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_page = org_contact_result.follow()
        ao_form = ao_page.forms[0]
        ao_form["authorizing_official-first_name"] = "Testy ATO"
        ao_form["authorizing_official-last_name"] = "Tester ATO"
        ao_form["authorizing_official-title"] = "Chief Tester"
        ao_form["authorizing_official-email"] = "testy@town.com"

        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        ao_result = ao_form.submit()

        # ---- CURRENT SITES PAGE  ----
        # Follow the redirect to the next form page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_page = ao_result.follow()
        current_sites_form = current_sites_page.forms[0]
        current_sites_form["current_sites-0-website"] = "www.city.com"

        # test saving the page
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_result = current_sites_form.submit()

        # ---- DOTGOV DOMAIN PAGE  ----
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page = current_sites_result.follow()

        self.assertContains(dotgov_page, "medicare.gov")

        # Go back to organization type page and change type
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page.click(str(self.TITLES["organization_type"]), index=0)
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_form["organization_type-organization_type"] = "city"
        type_result = type_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        election_page = type_result.follow()

        # Go back to dotgov domain page to test the dynamic text changed
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        dotgov_page = election_page.click(str(self.TITLES["dotgov_domain"]), index=0)
        self.assertContains(dotgov_page, "CityofEudoraKS.gov")
        self.assertNotContains(dotgov_page, "medicare.gov")

    def test_application_formsets(self):
        """Users are able to add more than one of some fields."""
        current_sites_page = self.app.get(reverse("application:current_sites"))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        # fill in the form field
        current_sites_form = current_sites_page.forms[0]
        self.assertIn("current_sites-0-website", current_sites_form.fields)
        self.assertNotIn("current_sites-1-website", current_sites_form.fields)
        current_sites_form["current_sites-0-website"] = "https://example.com"

        # click "Add another"
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_result = current_sites_form.submit("submit_button", value="save")
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        current_sites_form = current_sites_result.follow().forms[0]

        # verify that there are two form fields
        value = current_sites_form["current_sites-0-website"].value
        self.assertEqual(value, "https://example.com")
        self.assertIn("current_sites-1-website", current_sites_form.fields)
        # and it is correctly referenced in the ManyToOne relationship
        application = DomainApplication.objects.get()  # there's only one
        self.assertEqual(
            application.current_websites.filter(website="https://example.com").count(),
            1,
        )

    @skip("WIP")
    def test_application_edit_restore(self):
        """
        Test that a previously saved application is available at the /edit endpoint.
        """
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(555) 555 5555",
        )
        domain, _ = Domain.objects.get_or_create(name="city.gov")
        alt, _ = Website.objects.get_or_create(website="city1.gov")
        current, _ = Website.objects.get_or_create(website="city.com")
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(555) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(555) 555 5557",
        )
        application, _ = DomainApplication.objects.get_or_create(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            anything_else="No",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            requested_domain=domain,
            submitter=you,
            creator=self.user,
        )
        application.other_contacts.add(other)
        application.current_websites.add(current)
        application.alternative_domains.add(alt)

        # prime the form by visiting /edit
        url = reverse("edit-application", kwargs={"id": application.pk})
        response = self.client.get(url)

        # TODO: this is a sketch of each page in the wizard which needs to be tested
        # Django does not have tools sufficient for real end to end integration testing
        # (for example, USWDS moves radio buttons off screen and replaces them with
        # CSS styled "fakes" -- Django cannot determine if those are visually correct)
        # -- the best that can/should be done here is to ensure the correct values
        # are being passed to the templating engine

        url = reverse("application:organization_type")
        response = self.client.get(url, follow=True)
        self.assertContains(response, "<input>")
        # choices = response.context['wizard']['form']['organization_type'].subwidgets
        # radio = [ x for x in choices if x.data["value"] == "federal" ][0]
        # checked = radio.data["selected"]
        # self.assertTrue(checked)

        # url = reverse("application:organization_federal")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:organization_contact")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:authorizing_official")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:current_sites")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:dotgov_domain")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:purpose")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:your_contact")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:other_contacts")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:other_contacts")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:security_email")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:anything_else")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

        # url = reverse("application:requirements")
        # self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        # page = self.app.get(url)
        # self.assertNotContains(page, "VALUE")

    def test_long_org_name_in_application(self):
        """
        Make sure the long name is displaying in the application form,
        org step
        """
        intro_page = self.app.get(reverse("application:"))
        # django-webtest does not handle cookie-based sessions well because it keeps
        # resetting the session key on each new request, thus destroying the concept
        # of a "session". We are going to do it manually, saving the session ID here
        # and then setting the cookie on each request.
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]

        intro_form = intro_page.forms[0]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        intro_result = intro_form.submit()

        # follow first redirect
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        type_page = intro_result.follow()

        self.assertContains(type_page, "Federal: an agency of the U.S. government")

    def test_submit_modal_no_domain_text_fallback(self):
        """When user clicks on submit your domain request and the requested domain
        is null (possible through url direct access to the review page), present
        fallback copy in the modal's header.

        NOTE: This may be a moot point if we implement a more solid pattern in the
        future, like not a submit action at all on the review page."""

        review_page = self.app.get(reverse("application:review"))
        self.assertContains(review_page, "toggle-submit-domain-request")
        self.assertContains(review_page, "You are about to submit an incomplete request")


class DomainApplicationTestDifferentStatuses(TestWithUser, WebTest):
    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)
        self.client.force_login(self.user)

    def test_application_status(self):
        """Checking application status page"""
        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        application.save()

        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Manage" link
        detail_page = home_page.click("Manage", index=0)
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "city1.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
        self.assertContains(detail_page, "Admin Tester")
        self.assertContains(detail_page, "Status:")

    def test_application_status_with_ineligible_user(self):
        """Checking application status page whith a blocked user.
        The user should still have access to view."""
        self.user.status = "ineligible"
        self.user.save()

        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        application.save()

        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Manage" link
        detail_page = home_page.click("Manage", index=0)
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
        self.assertContains(detail_page, "Admin Tester")
        self.assertContains(detail_page, "Status:")

    def test_application_withdraw(self):
        """Checking application status page"""
        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        application.save()

        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Manage" link
        detail_page = home_page.click("Manage", index=0)
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "city1.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
        self.assertContains(detail_page, "Admin Tester")
        self.assertContains(detail_page, "Status:")
        # click the "Withdraw request" button
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            with less_console_noise():
                withdraw_page = detail_page.click("Withdraw request")
                self.assertContains(withdraw_page, "Withdraw request for")
                home_page = withdraw_page.click("Withdraw request")
        # confirm that it has redirected, and the status has been updated to withdrawn
        self.assertRedirects(
            home_page,
            "/",
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=True,
        )
        home_page = self.app.get("/")
        self.assertContains(home_page, "Withdrawn")

    def test_application_withdraw_no_permissions(self):
        """Can't withdraw applications as a restricted user."""
        self.user.status = User.RESTRICTED
        self.user.save()
        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        application.save()

        home_page = self.app.get("/")
        self.assertContains(home_page, "city.gov")
        # click the "Manage" link
        detail_page = home_page.click("Manage", index=0)
        self.assertContains(detail_page, "city.gov")
        self.assertContains(detail_page, "city1.gov")
        self.assertContains(detail_page, "Chief Tester")
        self.assertContains(detail_page, "testy@town.com")
        self.assertContains(detail_page, "Admin Tester")
        self.assertContains(detail_page, "Status:")
        # Restricted user trying to withdraw results in 403 error
        with less_console_noise():
            for url_name in [
                "application-withdraw-confirmation",
                "application-withdrawn",
            ]:
                with self.subTest(url_name=url_name):
                    page = self.client.get(reverse(url_name, kwargs={"pk": application.pk}))
                    self.assertEqual(page.status_code, 403)

    def test_application_status_no_permissions(self):
        """Can't access applications without being the creator."""
        application = completed_application(status=DomainApplication.ApplicationStatus.SUBMITTED, user=self.user)
        other_user = User()
        other_user.save()
        application.creator = other_user
        application.save()

        # PermissionDeniedErrors make lots of noise in test output
        with less_console_noise():
            for url_name in [
                "application-status",
                "application-withdraw-confirmation",
                "application-withdrawn",
            ]:
                with self.subTest(url_name=url_name):
                    page = self.client.get(reverse(url_name, kwargs={"pk": application.pk}))
                    self.assertEqual(page.status_code, 403)

    def test_approved_application_not_in_active_requests(self):
        """An approved application is not shown in the Active
        Requests table on home.html."""
        application = completed_application(status=DomainApplication.ApplicationStatus.APPROVED, user=self.user)
        application.save()

        home_page = self.app.get("/")
        # This works in our test environment because creating
        # an approved application here does not generate a
        # domain object, so we do not expect to see 'city.gov'
        # in either the Domains or Requests tables.
        self.assertNotContains(home_page, "city.gov")
