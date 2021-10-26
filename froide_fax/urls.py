from django.conf.urls import path, re_path

from .views import (
    fax_media_url,
    fax_status_callback,
    UpdateSignatureView,
    send_as_fax,
    pdf_report,
)

urlpatterns = [
    path(
        "signature/", UpdateSignatureView.as_view(), name="froide_fax-update_signature"
    ),
    path("send-fax/<int:message_id>/", send_as_fax, name="froide_fax-send_as_fax"),
    path("report/<int:message_id>/", pdf_report, name="froide_fax-report"),
    path("fax-callback/", fax_status_callback, name="froide_fax-status_callback"),
    re_path(
        r"^fax-callback/(?P<signed>[^/]+)/$",
        fax_status_callback,
        name="froide_fax-status_callback",
    ),
    re_path(
        r"^fax-media/(?P<signed>[^/]+)/$", fax_media_url, name="froide_fax-media_url"
    ),
]
