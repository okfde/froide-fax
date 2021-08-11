import base64
from froide.foirequest.pdf_generator import LetterPDFGenerator

from filingcabinet.utils import get_local_file
from filingcabinet.pdf_utils import PDFProcessor

from .utils import get_signature, parse_fax_log


class FaxMessagePDFGenerator(LetterPDFGenerator):
    template_name = 'froide_fax/message_letter.html'

    def get_context_data(self, obj):
        ctx = super().get_context_data(obj)
        user = obj.sender_user
        signature = get_signature(user)
        if signature:
            ctx.update({
                'signature': signature.get_signature_dataurl()
            })

        return ctx


class FaxReportPDFGenerator(LetterPDFGenerator):
    template_name = 'froide_fax/report.html'

    def get_context_data(self, obj):
        ctx = super().get_context_data(obj)

        att = obj.attachments[0]
        assert att.name == 'fax.pdf'

        with get_local_file(att.file.path) as path:
            pdf = PDFProcessor(path)
            for _, image in pdf.get_images([1], resolution=150):
                image_bytes = image.make_blob('png')
                break

        ctx['page_image'] = base64.b64encode(image_bytes).decode('ascii')
        data = parse_fax_log(obj.deliverystatus)
        ctx['fax'] = data

        return ctx
