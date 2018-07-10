import shutil
import os

try:
    from pylatex import NoEscape

    PDF_EXPORT_AVAILABLE = True

except ImportError:
    PDF_EXPORT_AVAILABLE = False

from froide.foirequest.pdf_generator import LetterPDFGenerator

from .utils import get_signature_path


class FaxMessagePDFGenerator(LetterPDFGenerator):
    def append_closing(self, doc):
        message = self.obj
        user = message.sender_user
        signature_filename = get_signature_path(user)
        if signature_filename is not None:
            shutil.copyfile(
                signature_filename,
                os.path.join(
                    self.path, 'signature.png'
                )
            )

            doc.append(NoEscape('''\\closing{Mit freundlichen Grüßen\\\\
\\includegraphics[height=5em]{signature}
}'''))
        else:
            super(FaxMessagePDFGenerator, self).append_closing(doc)
