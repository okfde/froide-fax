import contextlib
import logging
import socket

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

import requests
import requests.packages.urllib3.util.connection as urllib3_cn

from froide.foirequest.message_handlers import MessageHandler
from froide.foirequest.models import DeliveryStatus, FoiAttachment, FoiMessage
from froide.foirequest.models.message import MessageKind

from .pdf_generator import FaxMessagePDFGenerator
from .utils import ensure_fax_number, get_media_url

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def patch_requests_only_ipv4():
    """
    Patch requests to force use of IPv4
    """

    original_func = urllib3_cn.allowed_gai_family
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
    yield
    urllib3_cn.allowed_gai_family = original_func


def convert_to_fax_bytes(original_message: FoiMessage) -> bytes:
    pdf_generator = FaxMessagePDFGenerator(original_message)
    return pdf_generator.get_pdf_bytes()


def create_fax_attachment(fax_message):
    att = FoiAttachment(
        belongs_to=fax_message,
        name="fax.pdf",
        is_redacted=False,
        filetype="application/pdf",
        approved=False,
        can_approve=False,
    )
    pdf_bytes = convert_to_fax_bytes(fax_message.original)
    pdf_file = ContentFile(pdf_bytes)
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


def send_fax_telnyx(
    to,
    from_,
    media_url,
    connection_id,
    authorization="",
    quality="high",
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
    with patch_requests_only_ipv4():
        response = requests.post(
            "https://api.telnyx.com/v2/faxes", headers=headers, data=data
        )
    try:
        response.raise_for_status()
    except Exception:
        error_data = response.json()
        logger.error("Fax sending failed %s", error_data)
        raise
    return response


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

        fax_response = send_fax(fax_number, media_url)

        fax_data = fax_response.json().get("data")
        if fax_data:
            fax_id = fax_data.get("id", "")

        sent = fax_response.status_code == 202
        # store fax.sid in message 'email_message_id' (misnomer)
        FoiMessage.objects.filter(pk=fax_message.pk).update(
            email_message_id=fax_id, sent=sent
        )
