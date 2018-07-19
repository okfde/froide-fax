from .tasks import send_message_as_fax_task
from .utils import ensure_fax_number, get_signature


def connect_message_send(sender, message=None, **kwargs):
    if message is None:
        return
    if message.kind != 'email':
        return
    if message.is_response:
        return

    if len(sender.messages) > 1:
        # Only send first message automatically
        return

    request = message.request
    if not request.law.requires_signature:
        return

    fax_number = ensure_fax_number(message.recipient_public_body)
    if fax_number is None:
        return

    sig = get_signature(message.sender_user)
    if not sig:
        return

    send_message_as_fax_task.delay(message.pk)
