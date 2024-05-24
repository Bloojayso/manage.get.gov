"""Utilities for sending emails."""

import boto3
import logging
from datetime import datetime
from django.conf import settings
from django.template.loader import get_template
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from waffle import switch_is_active


logger = logging.getLogger(__name__)


class EmailSendingError(RuntimeError):
    """Local error for handling all failures when sending email."""

    pass


def send_templated_email(
    template_name: str,
    subject_template_name: str,
    to_address: str,
    bcc_address="",
    context={},
    attachment_file: str = None,
):
    """Send an email built from a template to one email address.

    template_name and subject_template_name are relative to the same template
    context as Django's HTML templates. context gives additional information
    that the template may use.

    Raises EmailSendingError if SES client could not be accessed
    """
    if switch_is_active("disable_email_sending") and not settings.IS_PRODUCTION:
        message = "Could not send email. Email sending is disabled due to switch 'disable_email_sending'."
        raise EmailSendingError(message)

    template = get_template(template_name)
    email_body = template.render(context=context)

    subject_template = get_template(subject_template_name)
    subject = subject_template.render(context=context)

    try:
        ses_client = boto3.client(
            "sesv2",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=settings.BOTO_CONFIG,
        )
        logger.info(f"An email was sent! Template name: {template_name} to {to_address}")
    except Exception as exc:
        logger.debug("E-mail unable to send! Could not access the SES client.")
        raise EmailSendingError("Could not access the SES client.") from exc

    destination = {"ToAddresses": [to_address]}
    if bcc_address:
        destination["BccAddresses"] = [bcc_address]

    try:
        if attachment_file is None:
            ses_client.send_email(
                FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
                Destination=destination,
                Content={
                    "Simple": {
                        "Subject": {"Data": subject},
                        "Body": {"Text": {"Data": email_body}},
                    },
                },
            )
        else:
            ses_client = boto3.client(
                "ses",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=settings.BOTO_CONFIG,
            )
            send_email_with_attachment(
                settings.DEFAULT_FROM_EMAIL, to_address, subject, email_body, attachment_file, ses_client
            )
    except Exception as exc:
        raise EmailSendingError("Could not send SES email.") from exc


def send_email_with_attachment(sender, recipient, subject, body, attachment_file, ses_client):
    # Create a multipart/mixed parent container
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    # Add the text part
    text_part = MIMEText(body, "plain")
    msg.attach(text_part)

    # Add the attachment part
    attachment_part = MIMEApplication(attachment_file)
    # Adding attachment header + filename that the attachment will be called
    current_date = datetime.now().strftime("%m%d%Y")
    current_filename = f"domain-metadata-{current_date}.zip"
    attachment_part.add_header("Content-Disposition", f'attachment; filename="{current_filename}"')
    msg.attach(attachment_part)

    response = ses_client.send_raw_email(Source=sender, Destinations=[recipient], RawMessage={"Data": msg.as_string()})
    return response
