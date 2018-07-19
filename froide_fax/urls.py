from django.conf.urls import url

from .views import (
    fax_media_url, fax_status_callback,
    UpdateSignatureView, send_as_fax
)

urlpatterns = [
    url(r"^signature/$", UpdateSignatureView.as_view(),
        name="froide_fax-update_signature"),
    url(r"^send-fax/(?P<message_id>\d+)/$", send_as_fax,
        name="froide_fax-send_as_fax"),
    url(r"^fax-callback/(?P<signed>[^/]+)/$", fax_status_callback,
        name="froide_fax-status_callback"),
    url(r"^fax-media/(?P<signed>[^/]+)/$", fax_media_url,
        name="froide_fax-media_url"),
]
