from django.core.signing import Signer, BadSignature
from django.urls import reverse
from django.conf import settings

import phonenumbers

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
    try:
        signature = Signature.objects.get(user=user)
    except Signature.DoesNotExist:
        return None
    if not signature.signature:
        return None
    return signature.signature.path


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
