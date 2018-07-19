from django.conf import settings
from django.utils import translation

from froide.celery import app as celery_app
from froide.foirequest.models import FoiMessage

from .fax import send_fax_message
from .utils import create_fax_message


@celery_app.task
def send_message_as_fax_task(message_id):
    translation.activate(settings.LANGUAGE_CODE)

    try:
        message = FoiMessage.objects.get(pk=message_id)
    except FoiMessage.DoesNotExist:
        return

    create_fax_message(message)


@celery_app.task
def send_fax_message_task(message_id):
    translation.activate(settings.LANGUAGE_CODE)

    try:
        message = FoiMessage.objects.get(pk=message_id)
    except FoiMessage.DoesNotExist:
        return

    send_fax_message(message)


@celery_app.task
def retry_fax_delivery(message_id):
    translation.activate(settings.LANGUAGE_CODE)

    try:
        message = FoiMessage.objects.get(pk=message_id)
    except FoiMessage.DoesNotExist:
        return

    message.resend()
