from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile

from twilio.rest import Client

from froide.foirequest.models import (
    FoiMessage, FoiAttachment, DeliveryStatus
)
from froide.foirequest.message_handlers import MessageHandler

from .pdf_generator import FaxMessagePDFGenerator
from .utils import (
    get_media_url, get_status_callback_url, ensure_fax_number
)


def create_fax_attachment(fax_message):
    pdf_generator = FaxMessagePDFGenerator(fax_message.original)

    att = FoiAttachment(
        belongs_to=fax_message,
        name='fax.pdf',
        is_redacted=False,
        filetype='application/pdf',
        approved=False,
        can_approve=False
    )

    pdf_file = ContentFile(pdf_generator.get_pdf_bytes())
    att.size = pdf_file.size
    att.file.save(att.name, pdf_file)
    att.save()
    fax_message._attachments = None
    return att


def send_fax_message(fax_message):
    if not fax_message.kind == 'fax':
        return

    create_fax_attachment(fax_message)

    fax_message.send(notify=False)
    return fax_message


class FaxMessageHandler(MessageHandler):
    def run_send(self, **kwargs):
        fax_message = self.message

        fax_number = ensure_fax_number(fax_message.recipient_public_body)
        if fax_number is None:
            return None

        att = fax_message.attachments[0]

        media_url = get_media_url(att)
        status_url = get_status_callback_url(fax_message)

        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        client = Client(account_sid, auth_token)

        ds, created = DeliveryStatus.objects.update_or_create(
            message=fax_message,
            defaults=dict(
                status=DeliveryStatus.Delivery.STATUS_SENDING,
                last_update=timezone.now(),
            )
        )

        fax = client.fax.faxes.create(
            to=fax_number,
            from_=settings.TWILIO_FROM_NUMBER,
            media_url=media_url,
            quality='standard',
            status_callback=status_url,
            store_media=False
        )

        # store fax.sid in message 'email_message_id' (misnomer)
        FoiMessage.objects.filter(pk=fax_message.pk).update(
            email_message_id=fax.sid, sent=True
        )
