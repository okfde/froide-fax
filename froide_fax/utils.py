from datetime import timedelta

from django.core.signing import Signer, BadSignature
from django.urls import reverse
from django.conf import settings
from django.utils import timezone

import phonenumbers

from froide.foirequest.models import FoiMessage

from .models import Signature


def ensure_fax_number(publicbody):
    if not publicbody.fax:
        return None
    try:
        number = phonenumbers.parse(publicbody.fax, 'DE')
    except phonenumbers.phonenumberutil.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(number):
        publicbody.fax = ''
        publicbody.save()
        return None
    if not phonenumbers.is_valid_number(number):
        return None
    fax_number = phonenumbers.format_number(
        number, phonenumbers.PhoneNumberFormat.E164
    )
    if fax_number != publicbody.fax:
        publicbody.fax = fax_number
        publicbody.save()
    return fax_number


def get_signature(user):
    if user is None:
        return None
    if hasattr(user, '_signature'):
        return user._signature
    try:
        signature = Signature.objects.get(user=user)
    except Signature.DoesNotExist:
        user._signature = None
        return None
    user._signature = signature
    return signature


FAX_MEDIA_SALT = 'fax_media_url'
FAX_CALLBACK_SALT = 'fax_callback_url'


def get_media_url(att):
    attachment_signature = sign_obj_id(att.pk, salt=FAX_MEDIA_SALT)
    return settings.SITE_URL + reverse('froide_fax-media_url', kwargs={
        'signed': attachment_signature
    })


def get_status_callback_url(message):
    attachment_signature = sign_obj_id(message.pk, salt=FAX_CALLBACK_SALT)
    return settings.SITE_URL + reverse('froide_fax-status_callback', kwargs={
        'signed': attachment_signature
    })


def sign_obj_id(obj_id, salt=None):
    signer = Signer(salt=salt)
    value = signer.sign('%s@%s' % (
        obj_id, settings.TWILIO_ACCOUNT_SID)
    )
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
    parts = original.split('@', 1)
    if len(parts) != 2:
        return None
    if parts[1] != settings.TWILIO_ACCOUNT_SID:
        return None
    return int(parts[0])


def message_can_be_faxed(message, ignore_time=False, ignore_signature=False,
                         ignore_law=False):
    if message is None:
        return False
    if message.kind != 'email':
        return False
    if message.is_response:
        return False

    request = message.request
    if not ignore_law and not request.law.requires_signature:
        return False

    fax_number = ensure_fax_number(message.recipient_public_body)
    if fax_number is None:
        return False

    sig = get_signature(request.user)
    if not ignore_signature and not sig:
        return False

    not_too_long_ago = timezone.now() - timedelta(hours=36)
    if not ignore_time and message.timestamp < not_too_long_ago:
        return False

    already_faxed = set([m.original_id for m in request.messages
                         if not m.is_response and m.kind == 'fax'])
    if message.id in already_faxed:
        return False

    return True


def get_faxable_messages_from_foirequest(foirequest, **kwargs):
    return [m for m in foirequest.messages
            if message_can_be_faxed(m, **kwargs)]


def send_messages_of_request(foirequest):
    if not foirequest.law.requires_signature:
        return

    messages = get_faxable_messages_from_foirequest(foirequest)
    for message in messages:
        create_fax_message(message)


def create_fax_message(message, ignore_time=False, ignore_law=False):
    from .tasks import send_fax_message_task

    if not message_can_be_faxed(message, ignore_time=ignore_time,
                                ignore_law=ignore_law):
        return

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
    send_fax_message_task.delay(fax_message.pk)
    return fax_message
