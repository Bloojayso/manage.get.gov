from __future__ import annotations  # allows forward references in annotations
from itertools import zip_longest
import logging
from phonenumber_field.formfields import PhoneNumberField  # type: ignore

from django import forms
from django.core.validators import RegexValidator
from django.utils.safestring import mark_safe

from registrar.models import Contact, DomainApplication, Domain

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
    def to_database(self, obj):
        if not self.is_valid():
            return
        obj.save()
        normalized = Domain.normalize(self.cleaned_data["current_site"], blank=True)
        if normalized:
            # TODO: ability to update existing records
            obj.current_websites.create(website=normalized)

    @classmethod
    def from_database(cls, obj):
        current_website = obj.current_websites.first()
        if current_website is not None:
            return {"current_site": current_website.website}
        else:
            return {}

    current_site = forms.CharField(
        required=False,
        label=(
            "Enter your organization’s website in the required format, like"
            " www.city.com."
        ),
    )

    def clean_current_site(self):
        """This field should be a legal domain name."""
        inputted_site = self.cleaned_data["current_site"]
        if not inputted_site:
            # empty string is fine
            return inputted_site

        # something has been inputted

        if inputted_site.startswith("http://") or inputted_site.startswith("https://"):
            # strip of the protocol that the pasted from their web browser
            inputted_site = inputted_site.split("//", 1)[1]

        if Domain.string_could_be_domain(inputted_site):
            return inputted_site
        else:
            # string could not be a domain
            raise forms.ValidationError(
                "Enter your organization’s website in the required format, like"
                " www.city.com.",
                code="invalid",
            )


class AlternativeDomainForm(RegistrarForm):
    alternative_domain = forms.CharField(
        required=False,
        label="Alternative domain",
    )


class BaseAlternativeDomainFormSet(RegistrarFormSet):
    def to_database(self, obj: DomainApplication):
        if not self.is_valid():
            return

        obj.save()
        query = obj.alternative_domains.order_by("created_at").all()  # order matters

        # the use of `zip` pairs the forms in the formset with the
        # related objects gotten from the database -- there should always be
        # at least as many forms as database entries: extra forms means new
        # entries, but fewer forms is _not_ the correct way to delete items
        # (likely a client-side error or an attempt at data tampering)

        for db_obj, post_data in zip_longest(query, self.forms, fillvalue=None):

            cleaned = post_data.cleaned_data if post_data is not None else {}
            domain = cleaned.get("alternative_domain", None)

            # matching database object exists, update or delete it
            if db_obj is not None and isinstance(domain, str):
                entry_was_erased = domain.strip() == ""
                if entry_was_erased:
                    db_obj.delete()
                    continue
                try:
                    normalized = Domain.normalize(domain, "gov", blank=True)
                except ValueError as e:
                    logger.debug(e)
                    continue
                db_obj.website = normalized
                db_obj.save()

            # no matching database object, create it
            elif db_obj is None and domain is not None:
                try:
                    normalized = Domain.normalize(domain, "gov", blank=True)
                except ValueError as e:
                    logger.debug(e)
                    continue
                obj.alternative_domains.create(website=normalized)

    @classmethod
    def from_database(cls, obj):
        query = obj.alternative_domains.order_by("created_at").all()  # order matters
        return [{"alternative_domain": domain.sld} for domain in query]


AlternativeDomainFormSet = forms.formset_factory(
    AlternativeDomainForm,
    extra=1,
    absolute_max=1500,
    formset=BaseAlternativeDomainFormSet,
)


class DotGovDomainForm(RegistrarForm):
    def to_database(self, obj):
        if not self.is_valid():
            return
        normalized = Domain.normalize(
            self.cleaned_data["requested_domain"], "gov", blank=True
        )
        if normalized:
            requested_domain = getattr(obj, "requested_domain", None)
            if requested_domain is not None:
                requested_domain.name = normalized
                requested_domain.save()
            else:
                requested_domain = Domain.objects.create(name=normalized)
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

    requested_domain = forms.CharField(label="What .gov domain do you want?")

    def clean_requested_domain(self):
        """Requested domains need to be legal top-level domains, not subdomains.

        If they end with `.gov`, then we can reasonably take that off. If they have
        any other dots in them, raise an error.
        """
        requested = self.cleaned_data["requested_domain"]
        if not requested:
            # none or empty string
            raise forms.ValidationError(
                "Enter the .gov domain you want. Don’t include “www” or “.gov.” For"
                " example, if you want www.city.gov, you would enter “city” (without"
                " the quotes).",
                code="invalid",
            )
        if requested.endswith(".gov"):
            requested = requested[:-4]
        if "." in requested:
            raise forms.ValidationError(
                "Enter the .gov domain you want without any periods.",
                code="invalid",
            )
        if not Domain.string_could_be_domain(requested + ".gov"):
            raise forms.ValidationError(
                "Enter a domain using only letters, "
                "numbers, or hyphens (though we don't recommend using hyphens).",
                code="invalid",
            )
        return requested


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
    def to_database(self, obj):
        if not self.is_valid():
            return
        obj.save()

        query = obj.other_contacts.order_by("created_at").all()

        # the use of `zip` pairs the forms in the formset with the
        # related objects gotten from the database -- there should always be
        # at least as many forms as database entries: extra forms means new
        # entries, but fewer forms is _not_ the correct way to delete items
        # (likely a client-side error or an attempt at data tampering)

        for db_obj, post_data in zip_longest(query, self.forms, fillvalue=None):

            cleaned = post_data.cleaned_data if post_data is not None else {}

            # matching database object exists, update it
            if db_obj is not None and cleaned:
                empty = (isinstance(v, str) and not v.strip() for v in cleaned.values())
                erased = all(empty)
                if erased:
                    db_obj.delete()
                    continue
                for key, value in cleaned.items():
                    setattr(db_obj, key, value)
                db_obj.save()

            # no matching database object, create it
            elif db_obj is None and cleaned:
                obj.other_contacts.create(**cleaned)

    @classmethod
    def from_database(cls, obj):
        return obj.other_contacts.order_by("created_at").values()  # order matters


OtherContactsFormSet = forms.formset_factory(
    OtherContactsForm,
    extra=1,
    absolute_max=1500,
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
