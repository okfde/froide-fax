from django.conf import settings
from django.utils import translation

from froide.celery import app as celery_app
from froide.foirequest.models import FoiMessage

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
    from .fax import send_fax_message

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


@celery_app.task
def send_test_fax():
    from .fax import send_fax_telnyx

    """
    send test faxes regularly, possibly with a distinct APP_ID, to gather receipts and ensure fax sending works as intended
    """
    to = settings.faxtest_receive_number
    from_ = settings.TELNYX_FROM_NUMBER
    media_url = settings.faxtest_pdf_url
    connection_id = settings.faxtest_app_id or settings.TELNYX_APP_ID
    authorization = f"Bearer {settings.TELNYX_API_KEY}"

    api_answer = send_fax_telnyx(
        to=to,
        from_=from_,
        media_url=media_url,
        connection_id=connection_id,
        authorization=authorization,
    )

    assert api_answer.status_code == 202
    # further process results here
