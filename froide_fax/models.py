import base64
import os

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings

from froide.helper.storage import HashedFilenameStorage

DATA_URL_PNG = 'data:image/png;base64,'


def signature_path(instance=None, filename=None):
    path = ['signatures', filename]
    return os.path.join(*path)


class Signature(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User")
    )
    signature = models.ImageField(
        null=True, blank=True,
        upload_to=signature_path,
        storage=HashedFilenameStorage()
    )
    timestamp = models.DateTimeField(
        default=timezone.now
    )

    class Meta:
        verbose_name = _('Signature')
        verbose_name_plural = _('Signatures')

    def __str__(self):
        return str(self.user)

    def remove_signature_file(self):
        if self.signature and os.path.exists(self.signature.path):
            os.remove(self.signature.path)

    def get_signature_dataurl(self):
        if not self.signature:
            return None
        signature_bytes = self.get_signature_bytes()
        if not signature_bytes:
            return None
        b64_string = base64.b64encode(signature_bytes).decode('utf-8')
        return DATA_URL_PNG + b64_string

    def get_signature_bytes(self):
        if not self.signature:
            return None
        try:
            self.signature.open()
        except IOError:
            # File was deleted, set field to None
            self.signature = None
            self.save()
            return None
        try:
            return self.signature.read()
        finally:
            self.signature.close()
