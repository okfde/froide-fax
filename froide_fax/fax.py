import logging

import requests
from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from froide.foirequest.message_handlers import MessageHandler
from froide.foirequest.models import DeliveryStatus, FoiAttachment, FoiMessage
from froide.foirequest.models.message import MessageKind
from froide.helper.widgets import BootstrapCheckboxInput

from .forms import SignatureField, save_signature_for_user
from .pdf_generator import FaxMessagePDFGenerator
from .utils import create_fax_message, ensure_fax_number, get_media_url, get_signature

logger = logging.getLogger(__name__)


class FaxFailedException(Exception):
    msg: str

    def __init__(self, msg, *args, **kwargs):
        self.msg = msg
        super().__init__(*args, **kwargs)


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

    response = requests.post(
        "https://api.telnyx.com/v2/faxes", headers=headers, data=data
    )

    try:
        response.raise_for_status()
    except Exception:
        error_data = response.json()
        logger.error("Fax sending failed %s", error_data)
        raise FaxFailedException(response.text)
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
        try:
            fax_response = send_fax(fax_number, media_url)
        except FaxFailedException as e:
            ds.status = DeliveryStatus.Delivery.STATUS_FAILED
            ds.log = e.msg
            ds.save()
            return

        fax_data = fax_response.json().get("data")
        if fax_data:
            fax_id = fax_data.get("id", "")

        sent = fax_response.status_code == 202
        # store fax.sid in message 'email_message_id' (misnomer)
        FoiMessage.objects.filter(pk=fax_message.pk).update(
            email_message_id=fax_id, sent=sent
        )

    @classmethod
    def initialize_send_message_form(cls, form):
        if not ensure_fax_number(form.foirequest.public_body):
            return
        form.fields["send_fax"] = forms.BooleanField(
            required=False,
            label=_("Send message as fax"),
            widget=BootstrapCheckboxInput,
        )
        additional_render_fields = [form["send_fax"]]
        signature = get_signature(form.foirequest.user)
        # Only if no signature is present, we show the field
        if not signature:
            form.fields["signature"] = SignatureField(required=False)
            additional_render_fields.append(form["signature"])
        form.additional_render_fields = additional_render_fields

    @classmethod
    def clean_send_message_form(cls, form, cleaned_data):
        if not ensure_fax_number(form.foirequest.public_body):
            return

        if not cleaned_data["send_fax"]:
            return cleaned_data

        signature = get_signature(form.foirequest.user)
        if not signature and not cleaned_data["signature"]:
            form.add_error(
                "signature",
                _("You need to provide a signature to send a fax message."),
            )
        return cleaned_data

    @classmethod
    def save_send_message_form(cls, form, message, user):
        if not ensure_fax_number(form.foirequest.public_body):
            return

        if message.request.user != user:
            # Can't set signature for different user!
            return
        if form.cleaned_data["send_fax"]:
            if "signature" in form.cleaned_data:
                save_signature_for_user(user, form.cleaned_data["signature"])
            create_fax_message(message)
