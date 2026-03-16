import base64
from io import BytesIO

from django import forms
from django.utils import timezone
from froide.foirequest.models import FoiRequest

from .models import DATA_URL_PNG, Signature
from .utils import get_signature, send_messages_of_request
from .widgets import SignatureWidget


class SignatureField(forms.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", SignatureWidget)
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value == "":
            return None
        if not value.startswith(DATA_URL_PNG):
            raise forms.ValidationError("Bad format")
        try:
            image = value.split(",", 1)[1]
            image = base64.b64decode(image)
        except ValueError:
            raise forms.ValidationError("Bad format")
        return BytesIO(image)


class SignatureForm(forms.Form):
    signature = SignatureField(required=False)
    foirequest = forms.ModelChoiceField(
        queryset=None, required=False, widget=forms.HiddenInput
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        signature_required = kwargs.pop("signature_required", False)
        super(SignatureForm, self).__init__(*args, **kwargs)
        foirequests = FoiRequest.objects.filter(user=self.user)
        self.fields["foirequest"].queryset = foirequests
        signature = get_signature(self.user)
        if signature:
            signature_dataurl = signature.get_signature_dataurl()
            if signature_dataurl:
                self.fields["signature"].initial = signature_dataurl
        if signature_required:
            self.fields["signature"].widget.attrs.update({"required": True})

    def save(self):
        sig = save_signature_for_user(self.user, self.cleaned_data["signature"])
        if sig is not None and self.cleaned_data["foirequest"]:
            foirequest = self.cleaned_data["foirequest"]
            send_messages_of_request(foirequest)
        return sig


def save_signature_for_user(user, signature_bytes):
    try:
        sig = Signature.objects.get(user=user)
    except Signature.DoesNotExist:
        sig = Signature(user=user)

    sig.remove_signature_file()

    if signature_bytes is None and sig.pk:
        sig.delete()
        sig = None
    elif signature_bytes is not None:
        sig.signature.save("signature.png", signature_bytes)
        sig.timestamp = timezone.now()
        sig.save()
    else:
        sig = None
    return sig
