import os
import logging

from contextlib import contextmanager
from unittest.mock import Mock
from typing import List, Dict

from django.conf import settings
from django.contrib.auth import get_user_model, login

from registrar.models import Contact, DraftDomain, Website, DomainApplication, User


def get_handlers():
    """Obtain pointers to all StreamHandlers."""
    handlers = {}

    rootlogger = logging.getLogger()
    for h in rootlogger.handlers:
        if isinstance(h, logging.StreamHandler):
            handlers[h.name] = h

    for logger in logging.Logger.manager.loggerDict.values():
        if not isinstance(logger, logging.PlaceHolder):
            for h in logger.handlers:
                if isinstance(h, logging.StreamHandler):
                    handlers[h.name] = h

    return handlers


@contextmanager
def less_console_noise():
    """
    Context manager to use in tests to silence console logging.

    This is helpful on tests which trigger console messages
    (such as errors) which are normal and expected.

    It can easily be removed to debug a failing test.
    """
    restore = {}
    handlers = get_handlers()
    devnull = open(os.devnull, "w")

    # redirect all the streams
    for handler in handlers.values():
        prior = handler.setStream(devnull)
        restore[handler.name] = prior
    try:
        # run the test
        yield
    finally:
        # restore the streams
        for handler in handlers.values():
            handler.setStream(restore[handler.name])
        # close the file we opened
        devnull.close()


class MockUserLogin:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_anonymous:
            user = None
            UserModel = get_user_model()
            username = "Testy"
            args = {
                UserModel.USERNAME_FIELD: username,
            }
            user, _ = UserModel.objects.get_or_create(**args)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            backend = settings.AUTHENTICATION_BACKENDS[-1]
            login(request, user, backend=backend)

        response = self.get_response(request)
        return response


class MockSESClient(Mock):
    EMAILS_SENT: List[Dict] = []

    def send_email(self, *args, **kwargs):
        self.EMAILS_SENT.append({"args": args, "kwargs": kwargs})


def completed_application(
    has_other_contacts=True,
    has_current_website=True,
    has_alternative_gov_domain=True,
    has_type_of_work=True,
    has_anything_else=True,
    status=DomainApplication.STARTED,
    user=False,
):
    """A completed domain application."""
    if not user:
        user = get_user_model().objects.create(username="username")
    ao, _ = Contact.objects.get_or_create(
        first_name="Testy",
        last_name="Tester",
        title="Chief Tester",
        email="testy@town.com",
        phone="(555) 555 5555",
    )
    domain, _ = DraftDomain.objects.get_or_create(name="city.gov")
    alt, _ = Website.objects.get_or_create(website="city1.gov")
    current, _ = Website.objects.get_or_create(website="city.com")
    you, _ = Contact.objects.get_or_create(
        first_name="Testy you",
        last_name="Tester you",
        title="Admin Tester",
        email="mayor@igorville.gov",
        phone="(555) 555 5556",
    )
    other, _ = Contact.objects.get_or_create(
        first_name="Testy2",
        last_name="Tester2",
        title="Another Tester",
        email="testy2@town.com",
        phone="(555) 555 5557",
    )
    domain_application_kwargs = dict(
        organization_type="federal",
        federal_type="executive",
        purpose="Purpose of the site",
        is_policy_acknowledged=True,
        organization_name="Testorg",
        address_line1="address 1",
        address_line2="address 2",
        state_territory="NY",
        zipcode="10002",
        authorizing_official=ao,
        requested_domain=domain,
        submitter=you,
        creator=user,
        status=status,
    )
    if has_type_of_work:
        domain_application_kwargs["type_of_work"] = "e-Government"
    if has_anything_else:
        domain_application_kwargs["anything_else"] = "There is more"

    application, _ = DomainApplication.objects.get_or_create(
        **domain_application_kwargs
    )

    if has_other_contacts:
        application.other_contacts.add(other)
    if has_current_website:
        application.current_websites.add(current)
    if has_alternative_gov_domain:
        application.alternative_domains.add(alt)

    return application


def mock_user():
    """A simple user."""
    user_kwargs = dict(
        id=4,
        first_name="Rachid",
        last_name="Mrad",
    )

    user, _ = User.objects.get_or_create(**user_kwargs)

    return user
