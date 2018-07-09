import base64
from io import BytesIO

from django import forms
from django.utils import timezone

from .models import Signature
from .widgets import SignatureWidget
from .utils import get_signature

DATA_URL_PNG = 'data:image/png;base64,'


class SignatureForm(forms.Form):
    signature = forms.CharField(
        required=False,
        widget=SignatureWidget
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super(SignatureForm, self).__init__(*args, **kwargs)
        signature = get_signature(self.user)
        if signature:
            with open(signature, 'rb') as f:
                b64_string = base64.b64encode(f.read()).decode('utf-8')
            self.fields['signature'].initial = DATA_URL_PNG + b64_string

    def clean_signature(self):
        data_uri = self.cleaned_data['signature']
        if data_uri == '':
            return None
        if not data_uri.startswith(DATA_URL_PNG):
            raise forms.ValidationError('Bad format')
        try:
            image = data_uri.split(',', 1)[1]
            image = base64.b64decode(image)
        except ValueError:
            raise forms.ValidationError('Bad format')
        return BytesIO(image)

    def save(self):
        try:
            sig = Signature.objects.get(user=self.user)
        except Signature.DoesNotExist:
            sig = Signature(user=self.user)

        signature = self.cleaned_data['signature']
        if signature is None:
            sig.delete()
        else:
            sig.signature.save('signature.png', signature)
            sig.timestamp = timezone.now()
            sig.save()
