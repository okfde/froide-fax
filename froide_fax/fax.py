from django.conf import settings
from django.utils import timezone
from django.core.files import File
from django.db import transaction

from twilio.rest import Client

from froide.foirequest.models import (
    FoiMessage, FoiAttachment, DeliveryStatus
)
from froide.foirequest.message_handlers import MessageHandler

from .pdf_generator import FaxMessagePDFGenerator
from .utils import (
    get_media_url, get_status_callback_url, ensure_fax_number
)


def create_fax_message_with_attachment(message):
    pdf_generator = FaxMessagePDFGenerator(message)

    with pdf_generator.get_pdf_filename() as filename:
        with transaction.atomic():
            fax_message = FoiMessage.objects.create(
                kind='fax',
                request=message.request,
                subject=message.subject,
                subject_redacted=message.subject_redacted,
                is_response=False,
                sender_user=message.sender_user,
                sender_name=message.sender_name,
                sender_email=message.sender_email,
                recipient_email=message.recipient_public_body.fax,
                recipient_public_body=message.recipient_public_body,
                recipient=message.recipient,
                timestamp=timezone.now(),
                plaintext='',
                original=message
            )

            att = FoiAttachment(
                belongs_to=fax_message,
                name='fax.pdf',
                is_redacted=False,
                filetype='application/pdf',
                approved=False,
                can_approve=False
            )

            with open(filename, 'rb') as f:
                pdf_file = File(f)
                att.file = pdf_file
                att.size = pdf_file.size
                att.save()
    return fax_message, att


def send_message_as_fax(message):
    if message.message_copies.filter(kind='fax').exists():
        # Already exists
        return

    fax_number = ensure_fax_number(message.recipient_public_body)
    if fax_number is None:
        return None

    fax_message, att = create_fax_message_with_attachment(message)

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

        DeliveryStatus.objects.create(
            message=fax_message,
            status=DeliveryStatus.STATUS_UNKNOWN,
            last_update=timezone.now(),
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
        FoiMessage.objects.filter(
            pk=fax_message.pk).update(
                email_message_id=fax.sid, sent=True
        )
