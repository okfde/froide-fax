from django import template

from ..forms import SignatureForm

register = template.Library()


@register.filter
def get_signature_form(user):
    return SignatureForm(user=user)
