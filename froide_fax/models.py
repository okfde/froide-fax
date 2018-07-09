import os

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.conf import settings

from froide.helper.storage import HashedFilenameStorage


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

    def __str__(self):
        return _('Signature %s') % self.pk
