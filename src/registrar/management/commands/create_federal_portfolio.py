"""Loads files from /tmp into our sandboxes"""

import argparse
import logging
from django.core.management import BaseCommand, CommandError
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models import DomainInformation, DomainRequest, FederalAgency, Suborganization, Portfolio, User


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Creates a federal portfolio given a FederalAgency name"

    def add_arguments(self, parser):
        """Add three arguments:
        1. agency_name => the value of FederalAgency.agency
        2. --parse_requests => if true, adds the given portfolio to each related DomainRequest
        3. --parse_domains => if true, adds the given portfolio to each related DomainInformation
        """
        parser.add_argument(
            "agency_name",
            help="The name of the FederalAgency to add",
        )
        parser.add_argument(
            "--parse_requests",
            action=argparse.BooleanOptionalAction,
            help="Adds portfolio to DomainRequests",
        )
        parser.add_argument(
            "--parse_domains",
            action=argparse.BooleanOptionalAction,
            help="Adds portfolio to DomainInformation",
        )

    def handle(self, agency_name, **options):
        parse_requests = options.get("parse_requests")
        parse_domains = options.get("parse_domains")

        if not parse_requests and not parse_domains:
            raise CommandError("You must specify at least one of --parse_requests or --parse_domains.")

        federal_agency = FederalAgency.objects.filter(agency__iexact=agency_name).first()
        if not federal_agency:
            raise ValueError(
                f"Cannot find the federal agency '{agency_name}' in our database. "
                "The value you enter for `agency_name` must be "
                "prepopulated in the FederalAgency table before proceeding."
            )

        portfolio = self.create_or_modify_portfolio(federal_agency)
        self.create_suborganizations(portfolio, federal_agency)

        if parse_requests:
            self.handle_portfolio_requests(portfolio, federal_agency)

        if parse_domains:
            self.handle_portfolio_domains(portfolio, federal_agency)

    def create_or_modify_portfolio(self, federal_agency):
        """Creates or modifies a portfolio record based on a federal agency."""
        portfolio_args = {
            "federal_agency": federal_agency,
            "organization_name": federal_agency.agency,
            "organization_type": DomainRequest.OrganizationChoices.FEDERAL,
            "creator": User.get_default_user(),
            "notes": "Auto-generated record",
        }

        if federal_agency.so_federal_agency.exists():
            portfolio_args["senior_official"] = federal_agency.so_federal_agency.first()

        portfolio, created = Portfolio.objects.get_or_create(
            organization_name=portfolio_args.get("organization_name"),
            defaults=portfolio_args
        )

        if created:
            message = f"Created portfolio '{portfolio}'"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
        else:
            proceed = TerminalHelper.prompt_for_execution(
                system_exit_on_terminate=False,
                info_to_inspect=f"""The given portfolio '{federal_agency.agency}' already exists in our DB.
                If you cancel, the rest of the script will still execute but this record will not update.
                """,
                prompt_title="Do you wish to modify this record?",
            )
            if proceed:
                for key, value in portfolio_args.items():
                    setattr(portfolio, key, value)
                portfolio.save()
                message = f"Modified portfolio '{portfolio}'"
                TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

        return portfolio

    def create_suborganizations(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """Create Suborganizations tied to the given portfolio based on DomainInformation objects"""
        valid_agencies = DomainInformation.objects.filter(federal_agency=federal_agency, organization_name__isnull=False)
        org_names = set(valid_agencies.values_list("organization_name", flat=True))

        if not org_names:
            TerminalHelper.colorful_logger(logger.warning, TerminalColors.YELLOW, f"No suborganizations found for {federal_agency}")
            return

        # Check if we need to update any existing suborgs first. This step is optional.
        existing_suborgs = Suborganization.objects.filter(name__in=org_names)
        if existing_suborgs.exists():
            self._update_existing_suborganizations(portfolio, existing_suborgs)

        # Create new suborgs, as long as they don't exist in the db already
        new_suborgs = []
        for name in org_names - set(existing_suborgs.values_list("name", flat=True)):
            if name.lower() == portfolio.organization_name.lower():
                # If the suborg name is a portfolio name that currently exists, thats not a suborg - thats the portfolio itself!
                # In this case, we can use this as an opportunity to update address information.
                self._update_portfolio_location_details(portfolio, valid_agencies.filter(organization_name=name).first())
            else:
                new_suborgs.append(Suborganization(name=name, portfolio=portfolio))

        if new_suborgs:
            Suborganization.objects.bulk_create(new_suborgs)
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, f"Added {len(new_suborgs)} suborganizations")
        else:
            TerminalHelper.colorful_logger(logger.warning, TerminalColors.YELLOW, "No suborganizations added")

    def _update_existing_suborganizations(self, portfolio, orgs_to_update):
        """
        Update existing suborganizations with new portfolio.
        Prompts for user confirmation before proceeding.
        """
        proceed = TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=False,
            info_to_inspect=f"""Some suborganizations already exist in our DB.
            If you cancel, the rest of the script will still execute but these records will not update.

            ==Proposed Changes==
            The following suborgs will be updated: {[org.name for org in orgs_to_update]}
            """,
            prompt_title="Do you wish to modify existing suborganizations?",
        )
        if proceed:
            for org in orgs_to_update:
                org.portfolio = portfolio

            Suborganization.objects.bulk_update(orgs_to_update, ["portfolio"])
            message = f"Updated {len(orgs_to_update)} suborganizations"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.MAGENTA, message)

    def _update_portfolio_location_details(self, portfolio: Portfolio, domain_info: DomainInformation):
        """
        Update portfolio location details based on DomainInformation.
        Copies relevant fields and saves the portfolio.
        """
        location_props = [
            "address_line1",
            "address_line2",
            "city",
            "state_territory",
            "zipcode",
            "urbanization",
        ]

        for prop_name in location_props:
            # Copy the value from the domain info object to the portfolio object
            value = getattr(domain_info, prop_name)
            setattr(portfolio, prop_name, value)

        portfolio.save()
        message = f"Updated location details on portfolio '{portfolio}'"
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

    def handle_portfolio_requests(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """
        Associate portfolio with domain requests for a federal agency.
        Updates all relevant domain request records.
        """
        domain_requests = DomainInformation.objects.filter(federal_agency=federal_agency)
        if not domain_requests.exists():
            message = "Portfolios not added to domain requests: no valid records found"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
        else:
            for domain_request in domain_requests:
                domain_request.portfolio = portfolio

            DomainRequest.objects.bulk_update(domain_requests, ["portfolio"])
            message = f"Added portfolio '{portfolio}' to {len(domain_requests)} domain requests"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)

    def handle_portfolio_domains(self, portfolio: Portfolio, federal_agency: FederalAgency):
        """
        Associate portfolio with domains for a federal agency.
        Updates all relevant domain information records.
        """
        domain_infos = DomainInformation.objects.filter(federal_agency=federal_agency)
        if not domain_infos.exists():
            message = "Portfolios not added to domains: no valid records found"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.YELLOW, message)
        else:
            for domain_info in domain_infos:
                domain_info.portfolio = portfolio

            DomainInformation.objects.bulk_update(domain_infos, ["portfolio"])
            message = f"Added portfolio '{portfolio}' to {len(domain_infos)} domains"
            TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, message)
