import logging
from faker import Faker
from django.db import transaction

from registrar.models import (
    User,
    UserGroup,
)
from registrar.models.allowed_email import AllowedEmail


fake = Faker()
logger = logging.getLogger(__name__)


class UserFixture:
    """
    Load users into the database.

    Make sure this class' `load` method is called from `handle`
    in management/commands/load.py, then use `./manage.py load`
    to run this code.
    """

    ADMINS = [
        {
            "username": "aad084c3-66cc-4632-80eb-41cdf5c5bcbf",
            "first_name": "Aditi",
            "last_name": "Green",
            "email": "aditidevelops+01@gmail.com",
            "title": "Positive vibes",
        },
        {
            "username": "be17c826-e200-4999-9389-2ded48c43691",
            "first_name": "Matthew",
            "last_name": "Spence",
            "title": "Hollywood hair",
        },
        {
            "username": "5f283494-31bd-49b5-b024-a7e7cae00848",
            "first_name": "Rachid",
            "last_name": "Mrad",
            "email": "rachid.mrad@associates.cisa.dhs.gov",
            "title": "Common pirate",
        },
        {
            "username": "eb2214cd-fc0c-48c0-9dbd-bc4cd6820c74",
            "first_name": "Alysia",
            "last_name": "Broddrick",
            "email": "abroddrick@truss.works",
            "title": "I drink coffee and know things",
        },
        {
            "username": "8f8e7293-17f7-4716-889b-1990241cbd39",
            "first_name": "Katherine",
            "last_name": "Osos",
            "email": "kosos@truss.works",
            "title": "Grove keeper",
        },
        {
            "username": "70488e0a-e937-4894-a28c-16f5949effd4",
            "first_name": "Gaby",
            "last_name": "DiSarli",
            "email": "gaby@truss.works",
            "title": "De Stijl",
        },
        {
            "username": "83c2b6dd-20a2-4cac-bb40-e22a72d2955c",
            "first_name": "Cameron",
            "last_name": "Dixon",
            "email": "cameron.dixon@cisa.dhs.gov",
            "title": "Product owner",
        },
        {
            "username": "30001ee7-0467-4df2-8db2-786e79606060",
            "first_name": "Zander",
            "last_name": "Adkinson",
            "title": "ACME specialist",
        },
        {
            "username": "2bf518c2-485a-4c42-ab1a-f5a8b0a08484",
            "first_name": "Paul",
            "last_name": "Kuykendall",
            "title": "Dr. Silvertongue",
        },
        {
            "username": "2a88a97b-be96-4aad-b99e-0b605b492c78",
            "first_name": "Rebecca",
            "last_name": "Hsieh",
            "email": "rebecca.hsieh@truss.works",
            "title": "Catlady",
        },
        {
            "username": "fa69c8e8-da83-4798-a4f2-263c9ce93f52",
            "first_name": "David",
            "last_name": "Kennedy",
            "email": "david.kennedy@ecstech.com",
            "title": "Mean lean coding machine",
        },
        {
            "username": "f14433d8-f0e9-41bf-9c72-b99b110e665d",
            "first_name": "Nicolle",
            "last_name": "LeClair",
            "email": "nicolle.leclair@ecstech.com",
            "title": "Nightowl",
        },
        {
            "username": "24840450-bf47-4d89-8aa9-c612fe68f9da",
            "first_name": "Erin",
            "last_name": "Song",
            "title": "Catlady 2",
        },
        {
            "username": "e0ea8b94-6e53-4430-814a-849a7ca45f21",
            "first_name": "Kristina",
            "last_name": "Yin",
            "title": "Hufflepuff prefect",
        },
        {
            "username": "ac49d7c1-368a-4e6b-8f1d-60250e20a16f",
            "first_name": "Vicky",
            "last_name": "Chin",
            "email": "szu.chin@associates.cisa.dhs.gov",
            "title": "Ze whip",
        },
        {
            "username": "66bb1a5a-a091-4d7f-a6cf-4d772b4711c7",
            "first_name": "Christina",
            "last_name": "Burnett",
            "email": "christina.burnett@cisa.dhs.gov",
            "title": "Groovy",
        },
        {
            "username": "76612d84-66b0-4ae9-9870-81e98b9858b6",
            "first_name": "Anna",
            "last_name": "Gingle",
            "email": "annagingle@truss.works",
            "title": "Sweetwater sailor",
        },
        {
            "username": "63688d43-82c6-480c-8e49-8a1bfdd33b9f",
            "first_name": "Elizabeth",
            "last_name": "Liao",
            "email": "elizabeth.liao@cisa.dhs.gov",
            "title": "Software Engineer",
        },
        {
            "username": "c9c64cd5-bc76-45ef-85cd-4f6eefa9e998",
            "first_name": "Samiyah",
            "last_name": "Key",
            "email": "skey@truss.works",
            "title": "Designer",
        },
        {
            "username": "f20b7a53-f40d-48f8-8c12-f42f35eede92",
            "first_name": "Kimberly",
            "last_name": "Aralar",
            "email": "kimberly.aralar@gsa.gov",
            "title": "Designer",
        },
        {
            "username": "4aa78480-6272-42f9-ac29-a034ebdd9231",
            "first_name": "Kaitlin",
            "last_name": "Abbitt",
            "email": "kaitlin.abbitt@cisa.dhs.gov",
            "title": "Product Manager",
        },
        {
            "username": "5e54fd98-6c11-4cb3-82b6-93ed8be50a61",
            "first_name": "Gina",
            "last_name": "Summers",
            "email": "gina.summers@ecstech.com",
            "title": "Scrum Master",
        },
    ]

    STAFF = [
        {
            "username": "ffec5987-aa84-411b-a05a-a7ee5cbcde54",
            "first_name": "Aditi-Analyst",
            "last_name": "Green-Analyst",
            "email": "aditidevelops+02@gmail.com",
        },
        {
            "username": "d6bf296b-fac5-47ff-9c12-f88ccc5c1b99",
            "first_name": "Matthew-Analyst",
            "last_name": "Spence-Analyst",
        },
        {
            "username": "319c490d-453b-43d9-bc4d-7d6cd8ff6844",
            "first_name": "Rachid-Analyst",
            "last_name": "Mrad-Analyst",
            "email": "rachid.mrad@gmail.com",
        },
        {
            "username": "b6a15987-5c88-4e26-8de2-ca71a0bdb2cd",
            "first_name": "Alysia-Analyst",
            "last_name": "Alysia-Analyst",
        },
        {
            "username": "91a9b97c-bd0a-458d-9823-babfde7ebf44",
            "first_name": "Katherine-Analyst",
            "last_name": "Osos-Analyst",
            "email": "kosos+1@truss.works",
        },
        {
            "username": "2cc0cde8-8313-4a50-99d8-5882e71443e8",
            "first_name": "Zander-Analyst",
            "last_name": "Adkinson-Analyst",
        },
        {
            "username": "57ab5847-7789-49fe-a2f9-21d38076d699",
            "first_name": "Paul-Analyst",
            "last_name": "Kuykendall-Analyst",
        },
        {
            "username": "e474e7a9-71ca-449d-833c-8a6e094dd117",
            "first_name": "Rebecca-Analyst",
            "last_name": "Hsieh-Analyst",
        },
        {
            "username": "5dc6c9a6-61d9-42b4-ba54-4beff28bac3c",
            "first_name": "David-Analyst",
            "last_name": "Kennedy-Analyst",
            "email": "david.kennedy@associates.cisa.dhs.gov",
        },
        {
            "username": "0eb6f326-a3d4-410f-a521-aa4c1fad4e47",
            "first_name": "Gaby-Analyst",
            "last_name": "DiSarli-Analyst",
            "email": "gaby+1@truss.works",
        },
        {
            "username": "cfe7c2fc-e24a-480e-8b78-28645a1459b3",
            "first_name": "Nicolle-Analyst",
            "last_name": "LeClair-Analyst",
            "email": "nicolle.leclair@gmail.com",
        },
        {
            "username": "378d0bc4-d5a7-461b-bd84-3ae6f6864af9",
            "first_name": "Erin-Analyst",
            "last_name": "Song-Analyst",
            "email": "erin.song+1@gsa.gov",
        },
        {
            "username": "9a98e4c9-9409-479d-964e-4aec7799107f",
            "first_name": "Kristina-Analyst",
            "last_name": "Yin-Analyst",
            "email": "kristina.yin+1@gsa.gov",
        },
        {
            "username": "8f42302e-b83a-4c9e-8764-fc19e2cea576",
            "first_name": "Vickster-Analyst",
            "last_name": "Chin-Analyst",
            "email": "szu.chin@ecstech.com",
        },
        {
            "username": "22f88aa5-3b54-4b1f-9c57-201fb02ddba7",
            "first_name": "Christina-Analyst",
            "last_name": "Burnett-Analyst",
            "email": "christina.burnett@gwe.cisa.dhs.gov",
        },
        {
            "username": "e1e350b1-cfc1-4753-a6cb-3ae6d912f99c",
            "first_name": "Anna-Analyst",
            "last_name": "Gingle-Analyst",
            "email": "annagingle+analyst@truss.works",
        },
        {
            "username": "0c27b05d-0aa3-45fa-91bd-83ee307708df",
            "first_name": "Elizabeth-Analyst",
            "last_name": "Liao-Analyst",
            "email": "elizabeth.liao@gwe.cisa.dhs.gov",
        },
        {
            "username": "ee1e68da-41a5-47f7-949b-d8a4e9e2b9d2",
            "first_name": "Samiyah-Analyst",
            "last_name": "Key-Analyst",
            "email": "skey+1@truss.works",
        },
        {
            "username": "cf2b32fe-280d-4bc0-96c2-99eec09ba4da",
            "first_name": "Kimberly-Analyst",
            "last_name": "Aralar-Analyst",
            "email": "kimberly.aralar+1@gsa.gov",
        },
        {
            "username": "80db923e-ac64-4128-9b6f-e54b2174a09b",
            "first_name": "Kaitlin-Analyst",
            "last_name": "Abbitt-Analyst",
            "email": "kaitlin.abbitt@gwe.cisa.dhs.gov",
        },
    ]

    # Additional emails to add to the AllowedEmail whitelist.
    ADDITIONAL_ALLOWED_EMAILS: list[str] = ["davekenn4242@gmail.com", "rachid_mrad@hotmail.com"]

    @classmethod
    def load_users(cls, users, group_name, are_superusers=False):
        """Loads the users into the database and assigns them to the specified group."""
        logger.info(f"Going to load {len(users)} users for group {group_name}")

        # Step 1: Fetch the group
        group = UserGroup.objects.get(name=group_name)

        # Step 2: Identify new and existing users
        existing_usernames, existing_user_ids = cls._get_existing_users(users)
        new_users = cls._prepare_new_users(users, existing_usernames, existing_user_ids, are_superusers)

        # Step 3: Create new users
        cls._create_new_users(new_users)

        # Step 4: Update existing users
        # Get all users to be updated (both new and existing)
        created_or_existing_users = User.objects.filter(username__in=[user.get("username") for user in users])
        users_to_update = cls._get_users_to_update(created_or_existing_users)
        cls._update_existing_users(users_to_update)

        # Step 5: Assign users to the group
        cls._assign_users_to_group(group, created_or_existing_users)

        logger.info(f"Users loaded for group {group_name}.")

    def load_allowed_emails(cls, users, additional_emails):
        """Populates a whitelist of allowed emails (as defined in this list)"""
        logger.info(f"Going to load allowed emails for {len(users)} users")
        if additional_emails:
            logger.info(f"Going to load {len(additional_emails)} additional allowed emails")

        existing_emails = set(AllowedEmail.objects.values_list("email", flat=True))
        new_allowed_emails = []

        for user_data in users:
            user_email = user_data.get("email")
            if user_email and user_email not in existing_emails:
                new_allowed_emails.append(AllowedEmail(email=user_email))

        # Load additional emails, only if they don't exist already
        for email in additional_emails:
            if email not in existing_emails:
                new_allowed_emails.append(AllowedEmail(email=email))

        if new_allowed_emails:
            try:
                AllowedEmail.objects.bulk_create(new_allowed_emails)
                logger.info(f"Loaded {len(new_allowed_emails)} allowed emails")
            except Exception as e:
                logger.error(f"Unexpected error during allowed emails bulk creation: {e}")
        else:
            logger.info("No allowed emails to load")

    @staticmethod
    def _get_existing_users(users):
        user_identifiers = [(user.get("username"), user.get("id")) for user in users]
        existing_users = User.objects.filter(
            username__in=[user[0] for user in user_identifiers] + [user[1] for user in user_identifiers]
        ).values_list("username", "id")
        existing_usernames = set(user[0] for user in existing_users)
        existing_user_ids = set(user[1] for user in existing_users)
        return existing_usernames, existing_user_ids

    @staticmethod
    def _prepare_new_users(users, existing_usernames, existing_user_ids, are_superusers):
        new_users = []
        for user_data in users:
            username = user_data.get("username")
            id = user_data.get("id")
            first_name = user_data.get("first_name")
            last_name = user_data.get("last_name")
            email = user_data.get("email", f"placeholder.{first_name}.{last_name}@igorville.gov")
            if username not in existing_usernames and id not in existing_user_ids:
                user = User(
                    id=id,
                    first_name=first_name,
                    last_name=last_name,
                    username=username,
                    email=email,
                    title=user_data.get("title", "Peon"),
                    phone=user_data.get("phone", "2022222222"),
                    is_active=user_data.get("is_active", True),
                    is_staff=True,
                    is_superuser=are_superusers,
                )
                new_users.append(user)
        return new_users

    @staticmethod
    def _create_new_users(new_users):
        if new_users:
            try:
                User.objects.bulk_create(new_users)
                logger.info(f"Created {len(new_users)} new users.")
            except Exception as e:
                logger.error(f"Unexpected error during user bulk creation: {e}")
        else:
            logger.info("No new users to create.")

    @staticmethod
    def _get_users_to_update(users):
        users_to_update = []
        for user in users:
            updated = False
            if not user.title:
                user.title = "Peon"
                updated = True
            if not user.phone:
                user.phone = "2022222222"
                updated = True
            if not user.is_staff:
                user.is_staff = True
                updated = True
            if updated:
                users_to_update.append(user)
        return users_to_update

    @staticmethod
    def _update_existing_users(users_to_update):
        if users_to_update:
            User.objects.bulk_update(users_to_update, ["is_staff", "title", "phone"])
            logger.info(f"Updated {len(users_to_update)} existing users.")

    @staticmethod
    def _assign_users_to_group(group, users):
        users_not_in_group = users.exclude(groups__id=group.id)
        if users_not_in_group.exists():
            group.user_set.add(*users_not_in_group)

    @classmethod
    def load(cls):
        with transaction.atomic():
            cls.load_users(cls.ADMINS, "full_access_group", are_superusers=True)
            cls.load_users(cls.STAFF, "cisa_analysts_group")

            # Combine ADMINS and STAFF lists
            all_users = cls.ADMINS + cls.STAFF
            cls.load_allowed_emails(cls, all_users, additional_emails=cls.ADDITIONAL_ALLOWED_EMAILS)
