from .tasks import send_message_as_fax_task
from .utils import message_can_be_faxed


def connect_message_send(sender, message=None, **kwargs):
    if len(sender.messages) > 1:
        # Only send first message automatically
        return

    if not message_can_be_faxed(message):
        return

    send_message_as_fax_task.delay(message.pk)
