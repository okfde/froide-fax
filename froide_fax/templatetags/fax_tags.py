from django import template

from ..forms import SignatureForm
from ..utils import get_signature

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

    sig = get_signature(foirequest.user)
    if sig is None:
        return True

    return False
