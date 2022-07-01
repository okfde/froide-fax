import base64
from io import BytesIO

from django import forms
from django.utils import timezone

from froide.foirequest.models import FoiRequest

from .models import DATA_URL_PNG, Signature
from .utils import get_signature, send_messages_of_request
from .widgets import SignatureWidget


class SignatureForm(forms.Form):
    signature = forms.CharField(required=False, widget=SignatureWidget)
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

    def clean_signature(self):
        data_uri = self.cleaned_data["signature"]
        if data_uri == "":
            return None
        if not data_uri.startswith(DATA_URL_PNG):
            raise forms.ValidationError("Bad format")
        try:
            image = data_uri.split(",", 1)[1]
            image = base64.b64decode(image)
        except ValueError:
            raise forms.ValidationError("Bad format")
        return BytesIO(image)

    def save(self):
        try:
            sig = Signature.objects.get(user=self.user)
        except Signature.DoesNotExist:
            sig = Signature(user=self.user)

        sig.remove_signature_file()

        signature = self.cleaned_data["signature"]
        if signature is None and sig.pk:
            sig.delete()
            sig = None
        elif signature is not None:
            sig.signature.save("signature.png", signature)
            sig.timestamp = timezone.now()
            sig.save()
        else:
            sig = None
        if sig is not None and self.cleaned_data["foirequest"]:
            foirequest = self.cleaned_data["foirequest"]
            send_messages_of_request(foirequest)
        return sig
