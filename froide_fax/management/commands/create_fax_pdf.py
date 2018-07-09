from django.core.management.base import BaseCommand
from django.utils import translation
from django.conf import settings

from froide.foirequest.models import FoiMessage

from ...pdf_generator import FaxMessagePDFGenerator


class Command(BaseCommand):
    help = "Create PDF"

    def add_arguments(self, parser):
        parser.add_argument('message_id', type=int)
        parser.add_argument('filename', type=str)

    def handle(self, *args, **options):
        translation.activate(settings.LANGUAGE_CODE)

        message = FoiMessage.objects.get(pk=options['message_id'])
        pdf_generator = FaxMessagePDFGenerator(message)

        result = pdf_generator.get_pdf_bytes()

        with open(options['filename'], 'wb') as f:
            f.write(result)

        print('Done')
