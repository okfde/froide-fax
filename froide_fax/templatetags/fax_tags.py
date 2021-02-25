from django import template

from ..forms import SignatureForm
from ..utils import (
    get_faxable_messages_from_foirequest, message_can_be_faxed,
    get_signature
)

register = template.Library()


@register.filter
def get_signature_form(user, signature_required=False):
    return SignatureForm(user=user, signature_required=signature_required)


@register.filter
def foirequest_needs_signature(foirequest):
    if not foirequest.law.requires_signature:
        return False

    fax_number = foirequest.public_body.fax
    if not fax_number:
        return False

    messages = get_faxable_messages_from_foirequest(
        foirequest, ignore_signature=True
    )
    if not messages:
        return False

    if get_signature(foirequest.user):
        # Already has signature
        return False

    return True


@register.filter
def can_fax_message(message, request):
    return message_can_be_faxed(
        message,
        ignore_time=True,
        ignore_law=request.user.is_staff
    )
