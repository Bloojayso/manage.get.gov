from __future__ import annotations  # allows forward references in annotations
from itertools import zip_longest
import logging
from typing import Callable
from phonenumber_field.formfields import PhoneNumberField  # type: ignore

from django import forms
from django.core.validators import RegexValidator
from django.utils.safestring import mark_safe

from registrar.models import Contact, DomainApplication, Domain
from registrar.utility import errors

logger = logging.getLogger(__name__)

# no sec because this use of mark_safe does not introduce a cross-site scripting
# vulnerability because there is no untrusted content inside. It is
# only being used to pass a specific HTML entity into a template.
REQUIRED_SUFFIX = mark_safe(  # nosec
    ' <abbr class="usa-hint usa-hint--required" title="required">*</abbr>'
)


class RegistrarForm(forms.Form):
    """
    A common set of methods and configuration.

    The registrar's domain application is several pages of "steps".
    Each step is an HTML form containing one or more Django "forms".

    Subclass this class to create new forms.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        # save a reference to an application object
        self.application = kwargs.pop("application", None)
        super(RegistrarForm, self).__init__(*args, **kwargs)

    def to_database(self, obj: DomainApplication | Contact):
        """
        Adds this form's cleaned data to `obj` and saves `obj`.

        Does nothing if form is not valid.
        """
        if not self.is_valid():
            return
        for name, value in self.cleaned_data.items():
            setattr(obj, name, value)
        obj.save()

    @classmethod
    def from_database(cls, obj: DomainApplication | Contact | None):
        """Returns a dict of form field values gotten from `obj`."""
        if obj is None:
            return {}
        return {
            name: getattr(obj, name) for name in cls.declared_fields.keys()
        }  # type: ignore


class RegistrarFormSet(forms.BaseFormSet):
    """
    As with RegistrarForm, a common set of methods and configuration.

    Subclass this class to create new formsets.
    """

    def __init__(self, *args, **kwargs):
        # save a reference to an application object
        self.application = kwargs.pop("application", None)
        super(RegistrarFormSet, self).__init__(*args, **kwargs)

    def should_delete(self, cleaned):
        """Should this entry be deleted from the database?"""
        raise NotImplementedError

    def pre_update(self, db_obj, cleaned):
        """Code to run before an item in the formset is saved."""
        for key, value in cleaned.items():
            setattr(db_obj, key, value)

    def pre_create(self, db_obj, cleaned):
        """Code to run before an item in the formset is created in the database."""
        return cleaned

    def to_database(self, obj: DomainApplication):
        """
        Adds this form's cleaned data to `obj` and saves `obj`.

        Does nothing if form is not valid.

        Hint: Subclass should call `self._to_database(...)`.
        """
        raise NotImplementedError

    def _to_database(
        self,
        obj: DomainApplication,
        join: str,
        should_delete: Callable,
        pre_update: Callable,
        pre_create: Callable,
    ):
        """
        Performs the actual work of saving.

        Has hooks such as `should_delete` and `pre_update` by which the
        subclass can control behavior. Add more hooks whenever needed.
        """
        if not self.is_valid():
            return
        obj.save()

        query = getattr(obj, join).order_by("created_at").all()  # order matters

        # the use of `zip` pairs the forms in the formset with the
        # related objects gotten from the database -- there should always be
        # at least as many forms as database entries: extra forms means new
        # entries, but fewer forms is _not_ the correct way to delete items
        # (likely a client-side error or an attempt at data tampering)

        for db_obj, post_data in zip_longest(query, self.forms, fillvalue=None):

            cleaned = post_data.cleaned_data if post_data is not None else {}

            # matching database object exists, update it
            if db_obj is not None and cleaned:
                if should_delete(cleaned):
                    db_obj.delete()
                    continue
                else:
                    pre_update(db_obj, cleaned)
                    db_obj.save()

            # no matching database object, create it
            elif db_obj is None and cleaned:
                kwargs = pre_create(db_obj, cleaned)
                getattr(obj, join).create(**kwargs)

    @classmethod
    def on_fetch(cls, query):
        """Code to run when fetching formset's objects from the database."""
        return query.values()

    @classmethod
    def from_database(cls, obj: DomainApplication, join: str, on_fetch: Callable):
        """Returns a dict of form field values gotten from `obj`."""
        return on_fetch(getattr(obj, join).order_by("created_at"))  # order matters


class OrganizationTypeForm(RegistrarForm):
    organization_type = forms.ChoiceField(
        required=True,
        choices=DomainApplication.OrganizationChoices.choices,
        widget=forms.RadioSelect,
        error_messages={"required": "Select the type of organization you represent."},
    )


class OrganizationFederalForm(RegistrarForm):
    federal_type = forms.ChoiceField(
        choices=DomainApplication.BranchChoices.choices,
        widget=forms.RadioSelect,
        error_messages={
            "required": (
                "Select the part of the federal government your organization is in."
            )
        },
    )


class OrganizationElectionForm(RegistrarForm):
    is_election_board = forms.NullBooleanField(
        widget=forms.RadioSelect(
            choices=[
                (True, "Yes"),
                (False, "No"),
            ],
        ),
        required=False,  # use field validation to require an answer
    )

    def clean_is_election_board(self):
        """This box must be checked to proceed but offer a clear error."""
        # already converted to a boolean
        is_election_board = self.cleaned_data["is_election_board"]
        if is_election_board is None:
            raise forms.ValidationError(
                "Select “Yes” if you represent an election office. Select “No” if you"
                " don’t.",
                code="required",
            )
        return is_election_board


class OrganizationContactForm(RegistrarForm):
    # for federal agencies we also want to know the top-level agency.
    federal_agency = forms.ChoiceField(
        label="Federal agency",
        # not required because this field won't be filled out unless
        # it is a federal agency. Use clean to check programatically
        # if it has been filled in when required.
        required=False,
        choices=[("", "--Select--")] + DomainApplication.AGENCY_CHOICES,
        label_suffix=REQUIRED_SUFFIX,
    )
    organization_name = forms.CharField(
        label="Organization name",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={"required": "Enter the name of your organization."},
    )
    address_line1 = forms.CharField(
        label="Street address",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={"required": "Enter the street address of your organization."},
    )
    address_line2 = forms.CharField(
        required=False,
        label="Street address line 2",
    )
    city = forms.CharField(
        label="City",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={
            "required": "Enter the city where your organization is located."
        },
    )
    state_territory = forms.ChoiceField(
        label="State, territory, or military post",
        choices=[("", "--Select--")] + DomainApplication.StateTerritoryChoices.choices,
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={
            "required": (
                "Select the state, territory, or military post where your organization"
                " is located."
            )
        },
    )
    zipcode = forms.CharField(
        label="Zip code",
        label_suffix=REQUIRED_SUFFIX,
        validators=[
            RegexValidator(
                "^[0-9]{5}(?:-[0-9]{4})?$|^$",
                message="Enter a zip code in the form of 12345 or 12345-6789.",
            )
        ],
    )
    urbanization = forms.CharField(
        required=False,
        label="Urbanization (Puerto Rico only)",
    )

    def clean_federal_agency(self):
        """Require something to be selected when this is a federal agency."""
        federal_agency = self.cleaned_data.get("federal_agency", None)
        # need the application object to know if this is federal
        if self.application is None:
            # hmm, no saved application object?, default require the agency
            if not federal_agency:
                # no answer was selected
                raise forms.ValidationError(
                    "Select the federal agency your organization is in.",
                    code="required",
                )
        if self.application.is_federal():
            if not federal_agency:
                # no answer was selected
                raise forms.ValidationError(
                    "Select the federal agency your organization is in.",
                    code="required",
                )
        return federal_agency


class TypeOfWorkForm(RegistrarForm):
    type_of_work = forms.CharField(
        # label has to end in a space to get the label_suffix to show
        label="What type of work does your organization do? ",
        label_suffix=REQUIRED_SUFFIX,
        widget=forms.Textarea(),
        error_messages={"required": "Enter the type of work your organization does."},
    )

    more_organization_information = forms.CharField(
        # label has to end in a space to get the label_suffix to show
        label=(
            "Describe how your organization is a government organization that is"
            " independent of a state government. Include links to authorizing"
            " legislation, applicable bylaws or charter, or other documentation to"
            " support your claims. "
        ),
        label_suffix=REQUIRED_SUFFIX,
        widget=forms.Textarea(),
        error_messages={
            "required": (
                "Describe how your organization is independent of a state government."
            )
        },
    )


class AuthorizingOfficialForm(RegistrarForm):
    def to_database(self, obj):
        if not self.is_valid():
            return
        contact = getattr(obj, "authorizing_official", None)
        if contact is not None:
            super().to_database(contact)
        else:
            contact = Contact()
            super().to_database(contact)
            obj.authorizing_official = contact
            obj.save()

    @classmethod
    def from_database(cls, obj):
        contact = getattr(obj, "authorizing_official", None)
        return super().from_database(contact)

    first_name = forms.CharField(
        label="First name / given name",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={
            "required": (
                "Enter the first name / given name of your authorizing official."
            )
        },
    )
    middle_name = forms.CharField(
        required=False,
        label="Middle name",
    )
    last_name = forms.CharField(
        label="Last name / family name",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={
            "required": (
                "Enter the last name / family name of your authorizing official."
            )
        },
    )
    title = forms.CharField(
        label="Title or role in your organization",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={
            "required": (
                "Enter the title or role your authorizing official has in your"
                " organization (e.g., Chief Information Officer)."
            )
        },
    )
    email = forms.EmailField(
        label="Email",
        label_suffix=REQUIRED_SUFFIX,
        error_messages={
            "invalid": (
                "Enter an email address in the required format, like name@example.com."
            )
        },
    )
    phone = PhoneNumberField(
        label="Phone",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={
            "required": "Enter the phone number for your authorizing official."
        },
    )


class CurrentSitesForm(RegistrarForm):
    website = forms.URLField(
        required=False,
        label="Public website",
    )


class BaseCurrentSitesFormSet(RegistrarFormSet):
    JOIN = "current_websites"

    def should_delete(self, cleaned):
        website = cleaned.get("website", "")
        return website.strip() == ""

    def to_database(self, obj: DomainApplication):
        self._to_database(
            obj, self.JOIN, self.should_delete, self.pre_update, self.pre_create
        )

    @classmethod
    def from_database(cls, obj):
        return super().from_database(obj, cls.JOIN, cls.on_fetch)


CurrentSitesFormSet = forms.formset_factory(
    CurrentSitesForm,
    extra=1,
    absolute_max=1500,  # django default; use `max_num` to limit entries
    formset=BaseCurrentSitesFormSet,
)


class AlternativeDomainForm(RegistrarForm):
    alternative_domain = forms.CharField(
        required=False,
        label="Alternative domain",
    )

    def clean_alternative_domain(self):
        """Validation code for domain names."""
        try:
            requested = self.cleaned_data.get("alternative_domain", None)
            validated = Domain.validate(requested, blank_ok=True)
        except errors.ExtraDotsError:
            raise forms.ValidationError(
                "Please enter a domain without any periods.",
                code="invalid",
            )
        except errors.DomainUnavailableError:
            raise forms.ValidationError(
                "ERROR MESSAGE GOES HERE",
                code="invalid",
            )
        except ValueError:
            raise forms.ValidationError(
                "Please enter a valid domain name using only letters, "
                "numbers, and hyphens",
                code="invalid",
            )
        return validated


class BaseAlternativeDomainFormSet(RegistrarFormSet):
    JOIN = "alternative_domains"

    def should_delete(self, cleaned):
        domain = cleaned.get("alternative_domain", "")
        return domain.strip() == ""

    def pre_update(self, db_obj, cleaned):
        domain = cleaned.get("alternative_domain", None)
        if domain is not None:
            db_obj.website = f"{domain}.gov"

    def pre_create(self, db_obj, cleaned):
        domain = cleaned.get("alternative_domain", None)
        if domain is not None:
            return {"website": f"{domain}.gov"}
        else:
            return {}

    def to_database(self, obj: DomainApplication):
        self._to_database(
            obj, self.JOIN, self.should_delete, self.pre_update, self.pre_create
        )

    @classmethod
    def on_fetch(cls, query):
        return [{"alternative_domain": domain.sld} for domain in query]

    @classmethod
    def from_database(cls, obj):
        return super().from_database(obj, cls.JOIN, cls.on_fetch)


AlternativeDomainFormSet = forms.formset_factory(
    AlternativeDomainForm,
    extra=1,
    absolute_max=1500,  # django default; use `max_num` to limit entries
    formset=BaseAlternativeDomainFormSet,
)


class DotGovDomainForm(RegistrarForm):
    def to_database(self, obj):
        if not self.is_valid():
            return
        domain = self.cleaned_data.get("requested_domain", None)
        if domain:
            requested_domain = getattr(obj, "requested_domain", None)
            if requested_domain is not None:
                requested_domain.name = f"{domain}.gov"
                requested_domain.save()
            else:
                requested_domain = Domain.objects.create(name=f"{domain}.gov")
                obj.requested_domain = requested_domain
                obj.save()

        obj.save()

    @classmethod
    def from_database(cls, obj):
        values = {}
        requested_domain = getattr(obj, "requested_domain", None)
        if requested_domain is not None:
            values["requested_domain"] = requested_domain.sld
        return values

    def clean_requested_domain(self):
        """Validation code for domain names."""
        try:
            requested = self.cleaned_data.get("requested_domain", None)
            validated = Domain.validate(requested)
        except errors.BlankValueError:
            # none or empty string
            raise forms.ValidationError(
                "Enter the .gov domain you want. Don’t include “www” or “.gov.” For"
                " example, if you want www.city.gov, you would enter “city” (without"
                " the quotes).",
                code="invalid",
            )
        except errors.ExtraDotsError:
            raise forms.ValidationError(
                "Enter the .gov domain you want without any periods.",
                code="invalid",
            )
        except errors.DomainUnavailableError:
            raise forms.ValidationError(
                "ERROR MESSAGE GOES HERE",
                code="invalid",
            )
        except ValueError:
            raise forms.ValidationError(
                "Enter a domain using only letters, "
                "numbers, or hyphens (though we don't recommend using hyphens).",
                code="invalid",
            )
        return validated

    requested_domain = forms.CharField(label="What .gov domain do you want?")


class PurposeForm(RegistrarForm):
    purpose = forms.CharField(
        label="Purpose",
        widget=forms.Textarea(),
        error_messages={
            "required": "Describe how you'll use the .gov domain you’re requesting."
        },
    )


class YourContactForm(RegistrarForm):
    def to_database(self, obj):
        if not self.is_valid():
            return
        contact = getattr(obj, "submitter", None)
        if contact is not None:
            super().to_database(contact)
        else:
            contact = Contact()
            super().to_database(contact)
            obj.submitter = contact
            obj.save()

    @classmethod
    def from_database(cls, obj):
        contact = getattr(obj, "submitter", None)
        return super().from_database(contact)

    first_name = forms.CharField(
        label="First name / given name",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={"required": "Enter your first name / given name."},
    )
    middle_name = forms.CharField(
        required=False,
        label="Middle name",
    )
    last_name = forms.CharField(
        label="Last name / family name",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={"required": "Enter your last name / family name."},
    )
    title = forms.CharField(
        label="Title or role in your organization",
        required=True,
        label_suffix=REQUIRED_SUFFIX,
        error_messages={
            "required": (
                "Enter your title or role in your organization (e.g., Chief Information"
                " Officer)."
            )
        },
    )
    email = forms.EmailField(
        label="Email",
        required=True,
        label_suffix=REQUIRED_SUFFIX,
        error_messages={
            "invalid": (
                "Enter your email address in the required format, like"
                " name@example.com."
            )
        },
    )
    phone = PhoneNumberField(
        label="Phone",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={"required": "Enter your phone number."},
    )


class OtherContactsForm(RegistrarForm):
    first_name = forms.CharField(
        label="First name / given name",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={
            "required": "Enter the first name / given name of this contact."
        },
    )
    middle_name = forms.CharField(
        required=False,
        label="Middle name",
    )
    last_name = forms.CharField(
        label="Last name / family name",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={
            "required": "Enter the last name / family name of this contact."
        },
    )
    title = forms.CharField(
        label="Title or role in your organization",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={
            "required": (
                "Enter the title or role in your organization of this contact (e.g.,"
                " Chief Information Officer)."
            )
        },
    )
    email = forms.EmailField(
        label="Email",
        label_suffix=REQUIRED_SUFFIX,
        error_messages={
            "invalid": (
                "Enter an email address in the required format, like name@example.com."
            )
        },
    )
    phone = PhoneNumberField(
        label="Phone",
        label_suffix=REQUIRED_SUFFIX,
        required=True,
        error_messages={"required": "Enter a phone number for this contact."},
    )


class BaseOtherContactsFormSet(RegistrarFormSet):
    JOIN = "other_contacts"

    def should_delete(self, cleaned):
        empty = (isinstance(v, str) and not v.strip() for v in cleaned.values())
        return all(empty)

    def to_database(self, obj: DomainApplication):
        self._to_database(
            obj, self.JOIN, self.should_delete, self.pre_update, self.pre_create
        )

    @classmethod
    def from_database(cls, obj):
        return super().from_database(obj, cls.JOIN, cls.on_fetch)


OtherContactsFormSet = forms.formset_factory(
    OtherContactsForm,
    extra=1,
    absolute_max=1500,  # django default; use `max_num` to limit entries
    formset=BaseOtherContactsFormSet,
)


class SecurityEmailForm(RegistrarForm):
    security_email = forms.EmailField(
        required=False,
        label="Security email for public use",
        error_messages={
            "invalid": (
                "Enter an email address in the required format, like name@example.com."
            )
        },
    )


class AnythingElseForm(RegistrarForm):
    anything_else = forms.CharField(
        required=False,
        label="Anything else we should know?",
        widget=forms.Textarea(),
    )


class RequirementsForm(RegistrarForm):
    is_policy_acknowledged = forms.BooleanField(
        label=(
            "I read and agree to the requirements for registering "
            "and operating .gov domains."
        ),
        required=False,  # use field validation to enforce this
    )

    def clean_is_policy_acknowledged(self):
        """This box must be checked to proceed but offer a clear error."""
        # already converted to a boolean
        is_acknowledged = self.cleaned_data["is_policy_acknowledged"]
        if not is_acknowledged:
            raise forms.ValidationError(
                "Check the box if you read and agree to the requirements for"
                " registering and operating .gov domains.",
                code="invalid",
            )
        return is_acknowledged
