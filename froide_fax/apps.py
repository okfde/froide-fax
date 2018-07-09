# -*- encoding: utf-8 -*-
from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class FroideFaxConfig(AppConfig):
    name = 'froide_fax'
    verbose_name = _("Froide Fax App")

    def ready(self):
        from .listeners import connect_message_send
        from froide.foirequest.models import FoiRequest

        FoiRequest.message_sent.connect(connect_message_send)
