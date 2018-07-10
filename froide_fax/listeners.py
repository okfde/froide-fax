from .tasks import send_message_as_fax_task
from .utils import ensure_fax_number, get_signature


def connect_message_send(sender, message=None, **kwargs):
    if message is None:
        return
    if message.kind != 'email':
        return
    if message.is_response:
        return

    request = message.request
    if not request.law.requires_signature:
        return

    fax_number = ensure_fax_number(message.recipient_public_body)
    if fax_number is None:
        return

    # TODO: remove feature flag
    if not message.sender_user.pk == 1:
        return

    sig = get_signature(message.sender_user)
    if not sig:
        return

    send_message_as_fax_task.delay(message.pk)
