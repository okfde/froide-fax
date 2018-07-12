from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

from froide.foirequest.models import (
    FoiMessage, FoiAttachment, DeliveryStatus
)
from froide.foirequest.views.attachment import send_attachment_file
from froide.helper.utils import get_redirect_url

from .forms import SignatureForm
from .utils import unsign_attachment_id, unsign_message_id
from .tasks import retry_fax_delivery


def fax_media_url(request, signed):
    attachment_id = unsign_attachment_id(signed)
    if attachment_id is None:
        return HttpResponse(status=403)

    attachment = get_object_or_404(FoiAttachment, pk=attachment_id)
    return send_attachment_file(attachment)


@csrf_exempt
def fax_status_callback(request, signed):
    message_id = unsign_message_id(signed)
    if message_id is None:
        return HttpResponse(status=403)

    message = get_object_or_404(FoiMessage, pk=message_id)

    fax_status = request.POST.get('FaxStatus')

    ds = message.get_delivery_status()
    ds.last_update = timezone.now()

    # See https://www.twilio.com/docs/fax/api/faxes#fax-status-values
    if fax_status in ('queued', 'processing', 'sending'):
        ds.status = DeliveryStatus.STATUS_SENDING
    elif fax_status in ('delivered', 'received'):
        ds.status = DeliveryStatus.STATUS_RECEIVED
    elif fax_status in ('no-answer', 'busy'):
        ds.status = DeliveryStatus.STATUS_DEFERRED
    elif fax_status in ('failed', 'canceled'):
        ds.status = DeliveryStatus.STATUS_FAILED

    current_log = '%s\n' % ds.last_update.isoformat()
    current_log += '\n'.join([
        '%s: %s' % (k, v) for k, v in request.POST.items()
        if k not in ('AccountSid', 'MediaUrl', 'OriginalMediaUrl')
    ])
    if ds.status == DeliveryStatus.STATUS_RECEIVED:
        ds.log = current_log.strip()
    else:
        ds.log += '\n\n%s' % current_log.strip()
    ds.save()

    if ds.status == DeliveryStatus.STATUS_DEFERRED:
        # Retry fax delivery in 45 minutes
        retry_fax_delivery.apply_async(
            (message.pk,), {}, countdown=45 * 60
        )

    return HttpResponse(status=204)


class UpdateSignatureView(LoginRequiredMixin, FormView):
    form_class = SignatureForm
    template_name = 'froide_fax/form.html'

    def get_form_kwargs(self):
        kwargs = super(UpdateSignatureView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        sig = form.save()
        if sig:
            messages.add_message(self.request, messages.SUCCESS, _(
                'Signature has been saved.'
            ))
        else:
            messages.add_message(self.request, messages.SUCCESS, _(
                'Signature has been removed.'
            ))
        return super(UpdateSignatureView, self).form_valid(form)

    def get_success_url(self):
        return get_redirect_url(self.request)
