import json

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class FroideFaxConfig(AppConfig):
    name = 'froide_fax'
    verbose_name = _("Froide Fax App")

    def ready(self):
        from froide.account import account_canceled
        from froide.account.export import registry
        from froide.foirequest.models import FoiRequest

        from .listeners import connect_message_send

        FoiRequest.message_sent.connect(connect_message_send)

        account_canceled.connect(cancel_user)
        registry.register(export_user_data)


def cancel_user(sender, user=None, **kwargs):
    from .models import Signature

    if user is None:
        return

    try:
        sig = Signature.objects.get(user=user)
    except Signature.DoesNotExist:
        return
    sig.remove_signature_file()
    sig.delete()


def export_user_data(user):
    from .models import Signature
    try:
        signature = Signature.objects.get(user=user)
    except Signature.DoesNotExist:
        return

    yield ('signature.json', json.dumps({
            'timestamp': signature.timestamp.isoformat(),
        }).encode('utf-8')
    )
    signature_bytes = signature.get_signature_bytes()
    if signature_bytes is not None:
        yield ('signature.png', signature_bytes)
