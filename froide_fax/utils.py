import json
import re
from datetime import datetime, timedelta
from typing import List

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.core.signing import BadSignature, Signer
from django.urls import reverse
from django.utils import timezone

import phonenumbers

from froide.foirequest.models import DeliveryStatus, FoiMessage, FoiRequest
from froide.foirequest.models.message import MessageKind

from .models import Signature


def ensure_fax_number(publicbody):
    if not publicbody.fax:
        return None
    try:
        number = phonenumbers.parse(publicbody.fax, "DE")
    except phonenumbers.phonenumberutil.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(number):
        publicbody.fax = ""
        publicbody.save()
        return None
    if not phonenumbers.is_valid_number(number):
        return None
    fax_number = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    if fax_number != publicbody.fax:
        publicbody.fax = fax_number
        publicbody.save()
    return fax_number


def get_signature(user):
    if user is None:
        return None
    if hasattr(user, "_signature"):
        return user._signature
    try:
        signature = Signature.objects.get(user=user)
    except Signature.DoesNotExist:
        user._signature = None
        return None
    user._signature = signature
    return signature


FAX_MEDIA_SALT = "fax_media_url"
FAX_CALLBACK_SALT = "fax_callback_url"


def get_media_url(att):
    return get_signed_media_url(att)


def get_signed_media_url(att):
    attachment_signature = sign_obj_id(att.pk, salt=FAX_MEDIA_SALT)
    return settings.SITE_URL + reverse(
        "froide_fax-media_url", kwargs={"signed": attachment_signature}
    )


def get_status_callback_url(message):
    attachment_signature = sign_obj_id(message.pk, salt=FAX_CALLBACK_SALT)
    return settings.SITE_URL + reverse(
        "froide_fax-status_callback", kwargs={"signed": attachment_signature}
    )


def sign_obj_id(obj_id, salt=None):
    signer = Signer(salt=salt)
    value = signer.sign("%s@%s" % (obj_id, settings.TELNYX_APP_ID))
    return value


def unsign_attachment_id(signature):
    return unsign_obj_id(signature, salt=FAX_MEDIA_SALT)


def unsign_message_id(signature):
    return unsign_obj_id(signature, salt=FAX_CALLBACK_SALT)


def unsign_obj_id(signature, salt=None):
    signer = Signer(salt=salt)
    try:
        original = signer.unsign(signature)
    except BadSignature:
        return None
    parts = original.split("@", 1)
    if len(parts) != 2:
        return None
    if parts[1] != settings.TELNYX_APP_ID:
        return None
    return int(parts[0])


def message_can_be_faxed(
    message: FoiMessage,
    ignore_time: bool = False,
    ignore_signature: bool = False,
    ignore_law: bool = False,
) -> bool:
    if message is None:
        return False
    if not message.is_email:
        return False
    if message.is_response:
        return False

    foirequest = message.request
    if not foirequest.law or (not ignore_law and not foirequest.law.requires_signature):
        return False

    if not message.recipient_public_body:
        return False

    fax_number = ensure_fax_number(message.recipient_public_body)
    if fax_number is None:
        return False

    sig = get_signature(foirequest.user)
    if not ignore_signature and not sig:
        return False

    not_too_long_ago = timezone.now() - timedelta(hours=36)
    if not ignore_time and message.timestamp < not_too_long_ago:
        return False

    already_faxed = set(
        [
            m.original_id
            for m in foirequest.messages
            if not m.is_response and m.kind == MessageKind.FAX
        ]
    )
    if message.id in already_faxed:
        return False

    return True


def get_faxable_messages_from_foirequest(
    foirequest: FoiRequest, **kwargs
) -> List[FoiMessage]:
    return [m for m in foirequest.messages if message_can_be_faxed(m, **kwargs)]


def send_messages_of_request(foirequest: FoiRequest) -> None:
    if not foirequest.law.requires_signature:
        return

    messages = get_faxable_messages_from_foirequest(foirequest)
    for message in messages:
        create_fax_message(message)


def create_fax_message(
    message: FoiMessage, ignore_time: bool = False, ignore_law: bool = False
) -> FoiMessage:
    from .tasks import send_fax_message_task

    if not message_can_be_faxed(
        message, ignore_time=ignore_time, ignore_law=ignore_law
    ):
        return

    fax_message = FoiMessage.objects.create(
        kind=MessageKind.FAX,
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
        plaintext="",
        original=message,
    )
    send_fax_message_task.delay(fax_message.pk)
    return fax_message


def message_can_get_fax_report(message: FoiMessage) -> bool:
    if message.kind != MessageKind.FAX:
        return False

    try:
        deliverystatus = message.deliverystatus
    except DeliveryStatus.DoesNotExist:
        return False

    return deliverystatus.status in (
        DeliveryStatus.Delivery.STATUS_SENT,
        DeliveryStatus.Delivery.STATUS_RECEIVED,
    )


def create_fax_log(previous_log, data):
    return json.dumps(data, cls=DjangoJSONEncoder)


def parse_fax_log(deliverystatus):
    log = deliverystatus.log
    try:
        data = json.loads(log)
        date_fields = ("date_created", "date_updated")
        for key in date_fields:
            try:
                data[key] = datetime.fromisoformat(data[key].replace("Z", ""))
            except (ValueError, KeyError):
                data[key] = None
        return data
    except ValueError:
        pass
    if "FaxSid: " in log:
        data = parse_twilio_fax_log(log)
        if data is None:
            return
        json_data = json.dumps(data, cls=DjangoJSONEncoder)
        deliverystatus.log = json_data
        deliverystatus.save(update_fields=["log"])
        return data


def parse_twilio_fax_log(log):
    sid_re = re.compile(r"FaxSid: (FX\w+)")
    csid_re = re.compile(r"RemoteStationId: ?(.*)")
    bitrate_re = re.compile(r"BitRate: (\d+)")
    match = sid_re.search(log)
    if match is None:
        return
    csid = csid_re.search(log).group(1)
    bit_rate = bitrate_re.search(log)
    if bit_rate:
        bit_rate = bit_rate.group(1)
    fax_sid = match.group(1)
    try:
        date_created = datetime.fromisoformat(log.splitlines()[0])
    except ValueError:
        date_created = None
    fax_data = {
        "num_pages": re.search(r"NumPages: (.*)", log).group(1),
        "from_": re.search(r"From: (.*)", log).group(1),
        "to": re.search(r"To: (.*)", log).group(1),
        "sid": fax_sid,
        "date_created": date_created,
    }
    fax_data["csid"] = csid
    fax_data["bit_rate"] = bit_rate
    fields = (
        "from_",
        "to",
        "quality",
        "num_pages",
        "duration",
        "status",
        "date_created",
        "date_updated",
        "sid",
        "csid",
        "bit_rate",
    )
    return {k: v for k, v in fax_data.items() if k in fields}
