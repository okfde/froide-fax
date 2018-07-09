from django.conf.urls import url

from .views import (
    fax_media_url, fax_status_callback,
    UpdateSignatureView
)

urlpatterns = [
    url(r"^signature/$", UpdateSignatureView.as_view(),
        name="froide_fax-update_signature"),
    url(r"^fax-callback/(?P<signed>[^/]+)/$", fax_status_callback,
        name="froide_fax-status_callback"),
    url(r"^fax-media/(?P<signed>[^/]+)/$", fax_media_url,
        name="froide_fax-media_url"),
]
