from froide.foirequest.pdf_generator import LetterPDFGenerator

from .utils import get_signature


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
