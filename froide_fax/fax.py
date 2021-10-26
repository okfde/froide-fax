from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile

from twilio.rest import Client

from froide.foirequest.models import FoiMessage, FoiAttachment, DeliveryStatus
from froide.foirequest.message_handlers import MessageHandler
from froide.foirequest.models.message import MessageKind

from .pdf_generator import FaxMessagePDFGenerator
from .utils import get_media_url, get_status_callback_url, ensure_fax_number

import requests


def create_fax_attachment(fax_message):
    pdf_generator = FaxMessagePDFGenerator(fax_message.original)

    att = FoiAttachment(
        belongs_to=fax_message,
        name="fax.pdf",
        is_redacted=False,
        filetype="application/pdf",
        approved=False,
        can_approve=False,
    )

    pdf_file = ContentFile(pdf_generator.get_pdf_bytes())
    att.size = pdf_file.size
    att.file.save(att.name, pdf_file)
    att.save()
    fax_message._attachments = None
    return att


def send_fax_message(fax_message):
    if not fax_message.kind == MessageKind.FAX:
        return

    create_fax_attachment(fax_message)

    fax_message.send(notify=False)
    return fax_message


def get_twilio_client():
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    return Client(account_sid, auth_token)


def get_twilio_fax_data(fax_sid):
    client = get_twilio_client()
    fax_data = client.fax.faxes(fax_sid).fetch()
    return fax_data._properties


def send_fax_telnyx(
    to,
    from_,
    media_url,
    connection_id,
    authorization="",
    quality="normal",
):
    """this sends a single message through the telnyx fax gateway
    results / error to be handled by calling instance"""
    data = {
        "to": to,
        "from": from_,
        "media_url": media_url,
        "connection_id": connection_id,  # this is a misnomer, app_id goes here
        "quality": quality,  # choice of normal, high, very_high
    }

    headers = {
        "Authorization": authorization,
    }

    r = requests.post("https://api.telnyx.com/v2/faxes", headers=headers, data=data)
    return r


def send_fax(fax_number, media_url):
    return send_fax_telnyx(
        to=fax_number,
        from_=settings.TELNYX_FROM_NUMBER,
        media_url=media_url,
        connection_id=settings.TELNYX_APP_ID,
        authorization=f"Bearer {settings.TELNYX_API_KEY}",
    )


class FaxMessageHandler(MessageHandler):
    def run_send(self, **kwargs):
        fax_message = self.message

        fax_number = ensure_fax_number(fax_message.recipient_public_body)
        if fax_number is None:
            return None

        att = fax_message.attachments[0]

        media_url = get_media_url(att)

        ds, created = DeliveryStatus.objects.update_or_create(
            message=fax_message,
            defaults=dict(
                status=DeliveryStatus.Delivery.STATUS_SENDING,
                last_update=timezone.now(),
            ),
        )

        fax_send = send_fax(fax_number, media_url)

        fax_id = fax_send.json().get("data")
        if fax_id:
            fax_id = fax_id.get("id")

        sent = fax_send.status_code == 202
        # store fax.sid in message 'email_message_id' (misnomer)
        FoiMessage.objects.filter(pk=fax_message.pk).update(
            email_message_id=fax_id, sent=sent
        )
