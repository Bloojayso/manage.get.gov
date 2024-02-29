import csv
import logging
from datetime import datetime
from registrar.models.domain import Domain
from registrar.models.domain_application import DomainApplication
from registrar.models.domain_information import DomainInformation
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat, Coalesce

from registrar.models.public_contact import PublicContact
from registrar.utility.enums import DefaultEmail

logger = logging.getLogger(__name__)


def write_header(writer, columns):
    """
    Receives params from the parent methods and outputs a CSV with a header row.
    Works with write_header as long as the same writer object is passed.
    """
    writer.writerow(columns)

def get_domain_infos(filter_condition, sort_fields):
    domain_infos = (
        DomainInformation.objects.select_related("domain", "authorizing_official")
        .filter(**filter_condition)
        .order_by(*sort_fields)
    )

    # Do a mass concat of the first and last name fields for authorizing_official.
    # The old operation was computationally heavy for some reason, so if we precompute
    # this here, it is vastly more efficient.
    domain_infos_cleaned = domain_infos.annotate(
        ao=Concat(
            Coalesce(F("authorizing_official__first_name"), Value("")),
            Value(" "),
            Coalesce(F("authorizing_official__last_name"), Value("")),
            output_field=CharField(),
        )
    )
    return domain_infos_cleaned

def parse_row(columns, domain_info: DomainInformation, security_emails_dict=None, get_domain_managers=False):
    """Given a set of columns, generate a new row from cleaned column data"""

    # Domain should never be none when parsing this information
    if domain_info.domain is None:
        raise ValueError("Domain is none")

    domain = domain_info.domain  # type: ignore

    # Grab the security email from a preset dictionary.
    # If nothing exists in the dictionary, grab from .contacts.
    if security_emails_dict is not None and domain.name in security_emails_dict:
        _email = security_emails_dict.get(domain.name)
        security_email = _email if _email is not None else " "
    else:
        # If the dictionary doesn't contain that data, lets filter for it manually.
        # This is a last resort as this is a more expensive operation.
        security_contacts = domain.contacts.filter(contact_type=PublicContact.ContactTypeChoices.SECURITY)
        _email = security_contacts[0].email if security_contacts else None
        security_email = _email if _email is not None else " "

    # These are default emails that should not be displayed in the csv report
    invalid_emails = {DefaultEmail.LEGACY_DEFAULT.value, DefaultEmail.PUBLIC_CONTACT_DEFAULT.value}
    if security_email.lower() in invalid_emails:
        security_email = "(blank)"

    if domain_info.federal_type:
        domain_type = f"{domain_info.get_organization_type_display()} - {domain_info.get_federal_type_display()}"
    else:
        domain_type = domain_info.get_organization_type_display()

    # create a dictionary of fields which can be included in output
    FIELDS = {
        "Domain name": domain.name,
        "Status": domain.get_state_display(),
        "Expiration date": domain.expiration_date,
        "Domain type": domain_type,
        "Agency": domain_info.federal_agency,
        "Organization name": domain_info.organization_name,
        "City": domain_info.city,
        "State": domain_info.state_territory,
        "AO": domain_info.ao,  # type: ignore
        "AO email": domain_info.authorizing_official.email if domain_info.authorizing_official else " ",
        "Security contact email": security_email,
        "Created at": domain.created_at,
        "First ready": domain.first_ready,
        "Deleted": domain.deleted,
    }

    if get_domain_managers:
        # Get each domain managers email and add to list
        dm_emails = [dm.user.email for dm in domain.permissions.all()]

        # Set up the "matching header" + row field data
        for i, dm_email in enumerate(dm_emails, start=1):
            FIELDS[f"Domain manager email {i}"] = dm_email

    row = [FIELDS.get(column, "") for column in columns]
    return row

def _get_security_emails(sec_contact_ids):
    """
    Retrieve security contact emails for the given security contact IDs.
    """
    security_emails_dict = {}
    public_contacts = (
        PublicContact.objects.only("email", "domain__name")
        .select_related("domain")
        .filter(registry_id__in=sec_contact_ids)
    )

    # Populate a dictionary of domain names and their security contacts
    for contact in public_contacts:
        domain: Domain = contact.domain
        if domain is not None and domain.name not in security_emails_dict:
            security_emails_dict[domain.name] = contact.email
        else:
            logger.warning("csv_export -> Domain was none for PublicContact")

    return security_emails_dict

def update_columns_with_domain_managers(columns, max_dm_count):
    """
    Update the columns list to include "Domain manager email {#}" headers
    based on the maximum domain manager count.
    """
    for i in range(1, max_dm_count + 1):
        columns.append(f"Domain manager email {i}")

def write_csv(
    writer,
    columns,
    sort_fields,
    filter_condition,
    get_domain_managers=False,
    should_write_header=True,
):
    """
    Receives params from the parent methods and outputs a CSV with fltered and sorted domains.
    Works with write_header as longas the same writer object is passed.
    get_domain_managers: Conditional bc we only use domain manager info for export_data_full_to_csv
    should_write_header: Conditional bc export_data_domain_growth_to_csv calls write_body twice
    """

    all_domain_infos = get_domain_infos(filter_condition, sort_fields)

    # Store all security emails to avoid epp calls or excessive filters
    sec_contact_ids = all_domain_infos.values_list("domain__security_contact_registry_id", flat=True)

    security_emails_dict = _get_security_emails(sec_contact_ids)

    if get_domain_managers and len(all_domain_infos) > 0:
        # We want to get the max amont of domain managers an
        # account has to set the column header dynamically
        max_dm_count = max(len(domain_info.domain.permissions.all()) for domain_info in all_domain_infos)
        update_columns_with_domain_managers(columns, max_dm_count)

    # Reduce the memory overhead when performing the write operation
    paginator = Paginator(all_domain_infos, 1000)

    for page_num in paginator.page_range:
        page = paginator.page(page_num)
        rows = []
        for domain_info in page.object_list:
            try:
                row = parse_row(columns, domain_info, security_emails_dict, get_domain_managers)
                rows.append(row)
            except ValueError:
                # This should not happen. If it does, just skip this row.
                # It indicates that DomainInformation.domain is None.
                logger.error("csv_export -> Error when parsing row, domain was None")
                continue

    if should_write_header:
        write_header(writer, columns)

    writer.writerows(rows)

def get_domain_requests(filter_condition, sort_fields):
    domain_requests = (
        DomainApplication.objects.all()
        .filter(**filter_condition)
        .order_by(*sort_fields)
    )

    return domain_requests

def parse_request_row(columns, request: DomainApplication):
    """Given a set of columns, generate a new row from cleaned column data"""

    requested_domain_name = 'No requested domain'

    # Domain should never be none when parsing this information
    if request.requested_domain is not None:
        domain = request.requested_domain
        requested_domain_name = domain.name

    domain = request.requested_domain  # type: ignore

    if request.federal_type:
        request_type = f"{request.get_organization_type_display()} - {request.get_federal_type_display()}"
    else:
        request_type = request.get_organization_type_display()

    # create a dictionary of fields which can be included in output
    FIELDS = {
        "Requested domain": requested_domain_name,
        "Status": request.get_status_display(),
        "Organization type": request_type,
        "Agency": request.federal_agency,
        "Organization name": request.organization_name,
        "City": request.city,
        "State": request.state_territory,
        "AO email": request.authorizing_official.email if request.authorizing_official else " ",
        "Security contact email": request,
        "Created at": request.created_at,
        "Submission date": request.submission_date,
    }

    row = [FIELDS.get(column, "") for column in columns]
    return row

def write_requests_csv(
    writer,
    columns,
    sort_fields,
    filter_condition,
    should_write_header=True,
):
    """
    """

    all_requetsts = get_domain_requests(filter_condition, sort_fields)

    # Reduce the memory overhead when performing the write operation
    paginator = Paginator(all_requetsts, 1000)

    for page_num in paginator.page_range:
        page = paginator.page(page_num)
        rows = []
        for request in page.object_list:
            try:
                row = parse_request_row(columns, request)
                rows.append(row)
            except ValueError:
                # This should not happen. If it does, just skip this row.
                # It indicates that DomainInformation.domain is None.
                logger.error("csv_export -> Error when parsing row, domain was None")
                continue

    if should_write_header:
        write_header(writer, columns)

    writer.writerows(rows)

def export_data_type_to_csv(csv_file):
    """All domains report with extra columns"""

    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Status",
        "Expiration date",
        "Domain type",
        "Agency",
        "Organization name",
        "City",
        "State",
        "AO",
        "AO email",
        "Security contact email",
        # For domain manager we are pass it in as a parameter below in write_body
    ]

    # Coalesce is used to replace federal_type of None with ZZZZZ
    sort_fields = [
        "organization_type",
        Coalesce("federal_type", Value("ZZZZZ")),
        "federal_agency",
        "domain__name",
    ]
    filter_condition = {
        "domain__state__in": [
            Domain.State.READY,
            Domain.State.DNS_NEEDED,
            Domain.State.ON_HOLD,
        ],
    }
    write_csv(writer, columns, sort_fields, filter_condition, get_domain_managers=True, should_write_header=True)

def export_data_full_to_csv(csv_file):
    """All domains report"""

    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Domain type",
        "Agency",
        "Organization name",
        "City",
        "State",
        "Security contact email",
    ]
    # Coalesce is used to replace federal_type of None with ZZZZZ
    sort_fields = [
        "organization_type",
        Coalesce("federal_type", Value("ZZZZZ")),
        "federal_agency",
        "domain__name",
    ]
    filter_condition = {
        "domain__state__in": [
            Domain.State.READY,
            Domain.State.DNS_NEEDED,
            Domain.State.ON_HOLD,
        ],
    }
    write_csv(writer, columns, sort_fields, filter_condition, get_domain_managers=False, should_write_header=True)

def export_data_federal_to_csv(csv_file):
    """Federal domains report"""

    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Domain type",
        "Agency",
        "Organization name",
        "City",
        "State",
        "Security contact email",
    ]
    # Coalesce is used to replace federal_type of None with ZZZZZ
    sort_fields = [
        "organization_type",
        Coalesce("federal_type", Value("ZZZZZ")),
        "federal_agency",
        "domain__name",
    ]
    filter_condition = {
        "organization_type__icontains": "federal",
        "domain__state__in": [
            Domain.State.READY,
            Domain.State.DNS_NEEDED,
            Domain.State.ON_HOLD,
        ],
    }
    write_csv(writer, columns, sort_fields, filter_condition, get_domain_managers=False, should_write_header=True)

def get_default_start_date():
    # Default to a date that's prior to our first deployment
    return timezone.make_aware(datetime(2023, 11, 1))

def get_default_end_date():
    # Default to now()
    return timezone.now()

def format_start_date(start_date):
    return timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%d")) if start_date else get_default_start_date()

def format_end_date(end_date):
    return timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%d")) if end_date else get_default_end_date()

def export_data_domain_growth_to_csv(csv_file, start_date, end_date):
    """
    Growth report:
    Receive start and end dates from the view, parse them.
    Request from write_body READY domains that are created between
    the start and end dates, as well as DELETED domains that are deleted between
    the start and end dates. Specify sort params for both lists.
    """

    start_date_formatted = format_start_date(start_date)
    end_date_formatted = format_end_date(end_date)
    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Domain type",
        "Agency",
        "Organization name",
        "City",
        "State",
        "Status",
        "Expiration date",
        "Created at",
        "First ready",
        "Deleted",
    ]
    sort_fields = [
        "domain__first_ready",
        "domain__name",
    ]
    filter_condition = {
        "domain__state__in": [Domain.State.READY],
        "domain__first_ready__lte": end_date_formatted,
        "domain__first_ready__gte": start_date_formatted,
    }

    # We also want domains deleted between sar and end dates, sorted
    sort_fields_for_deleted_domains = [
        "domain__deleted",
        "domain__name",
    ]
    filter_condition_for_deleted_domains = {
        "domain__state__in": [Domain.State.DELETED],
        "domain__deleted__lte": end_date_formatted,
        "domain__deleted__gte": start_date_formatted,
    }

    write_csv(writer, columns, sort_fields, filter_condition, get_domain_managers=False, should_write_header=True)
    write_csv(
        writer,
        columns,
        sort_fields_for_deleted_domains,
        filter_condition_for_deleted_domains,
        get_domain_managers=False,
        should_write_header=False,
    )

def get_sliced_domains(filter_condition):
    """
    """

    domains = DomainInformation.objects.all().filter(**filter_condition)
    federal = domains.filter(organization_type=DomainApplication.OrganizationChoices.FEDERAL).count()
    interstate = domains.filter(organization_type=DomainApplication.OrganizationChoices.INTERSTATE).count()
    state_or_territory = domains.filter(organization_type=DomainApplication.OrganizationChoices.STATE_OR_TERRITORY).count()
    tribal = domains.filter(organization_type=DomainApplication.OrganizationChoices.TRIBAL).count()
    county = domains.filter(organization_type=DomainApplication.OrganizationChoices.COUNTY).count()
    city = domains.filter(organization_type=DomainApplication.OrganizationChoices.CITY).count()
    special_district = domains.filter(organization_type=DomainApplication.OrganizationChoices.SPECIAL_DISTRICT).count()
    school_district = domains.filter(organization_type=DomainApplication.OrganizationChoices.SCHOOL_DISTRICT).count()
    election_board = domains.filter(is_election_board=True).count()

    return [federal,
         interstate,
         state_or_territory,
         tribal,
         county,
         city,
         special_district,
         school_district,
         election_board]

def export_data_managed_vs_unamanaged_domains(csv_file, start_date, end_date):
    """
    """

    start_date_formatted = format_start_date(start_date)
    end_date_formatted = format_end_date(end_date)
    writer = csv.writer(csv_file)
    columns = [
        "Domain name",
        "Domain type",
    ]
    sort_fields = [
        "domain__name",
    ]

    writer.writerow(["START DATE"])
    writer.writerow([])

    filter_managed_domains_start_date = {
        "domain__permissions__isnull": False,
        "domain__created_at__lte": start_date_formatted,
    }
    managed_domains_sliced_at_start_date = get_sliced_domains(filter_managed_domains_start_date)

    writer.writerow(["MANAGED DOMAINS COUNTS"])
    writer.writerow(["FEDERAL", "INTERSTATE", "STATE_OR_TERRITORY", "TRIBAL", "COUNTY", "CITY", "SPECIAL_DISTRICT", "SCHOOL_DISTRICT", "ELECTION OFFICE"])
    writer.writerow(managed_domains_sliced_at_start_date)
    writer.writerow([])

    write_csv(writer, columns, sort_fields, filter_managed_domains_start_date, get_domain_managers=True, should_write_header=True)
    writer.writerow([])
    
    filter_unmanaged_domains_start_date = {
        "domain__permissions__isnull": True,
        "domain__first_ready__lte": start_date_formatted,
    }
    unmanaged_domains_sliced_at_start_date = get_sliced_domains(filter_unmanaged_domains_start_date)

    writer.writerow(["UNMANAGED DOMAINS COUNTS"])
    writer.writerow(["FEDERAL", "INTERSTATE", "STATE_OR_TERRITORY", "TRIBAL", "COUNTY", "CITY", "SPECIAL_DISTRICT", "SCHOOL_DISTRICT", "ELECTION OFFICE"])
    writer.writerow(unmanaged_domains_sliced_at_start_date)
    writer.writerow([])
    write_csv(writer, columns, sort_fields, filter_unmanaged_domains_start_date, get_domain_managers=True, should_write_header=True)
    writer.writerow([])

    writer.writerow(["END DATE"])
    writer.writerow([])

    filter_managed_domains_end_date = {
        "domain__permissions__isnull": False,
        "domain__first_ready__lte": end_date_formatted,
    }
    managed_domains_sliced_at_end_date = get_sliced_domains(filter_managed_domains_end_date)

    writer.writerow(["MANAGED DOMAINS COUNTS"])
    writer.writerow(["FEDERAL", "INTERSTATE", "STATE_OR_TERRITORY", "TRIBAL", "COUNTY", "CITY", "SPECIAL_DISTRICT", "SCHOOL_DISTRICT", "ELECTION OFFICE"])
    writer.writerow(managed_domains_sliced_at_end_date)
    writer.writerow([])

    write_csv(writer, columns, sort_fields, filter_managed_domains_end_date, get_domain_managers=True, should_write_header=True)
    writer.writerow([])
    
    filter_unmanaged_domains_end_date = {
        "domain__permissions__isnull": True,
        "domain__first_ready__lte": end_date_formatted,
    }
    unmanaged_domains_sliced_at_end_date = get_sliced_domains(filter_unmanaged_domains_end_date)
    
    writer.writerow(["UNMANAGED DOMAINS COUNTS"])
    writer.writerow(["FEDERAL", "INTERSTATE", "STATE_OR_TERRITORY", "TRIBAL", "COUNTY", "CITY", "SPECIAL_DISTRICT", "SCHOOL_DISTRICT", "ELECTION OFFICE"])
    writer.writerow(unmanaged_domains_sliced_at_end_date)
    writer.writerow([])

    write_csv(writer, columns, sort_fields, filter_unmanaged_domains_end_date, get_domain_managers=True, should_write_header=True)

def export_data_requests_to_csv(csv_file, start_date, end_date):
    """
    """

    start_date_formatted = format_start_date(start_date)
    end_date_formatted = format_end_date(end_date)
    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Requested domain",
        "Organization type",
        "Submission date",
    ]
    sort_fields = [
        # "domain__name",
    ]
    filter_condition = {
        "status": DomainApplication.ApplicationStatus.SUBMITTED,
        "submission_date__lte": end_date_formatted,
        "submission_date__gte": start_date_formatted,
    }

    write_requests_csv(writer, columns, sort_fields, filter_condition, should_write_header=True)
