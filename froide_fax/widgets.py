from django import forms


class SignatureWidget(forms.HiddenInput):
    template_name = 'froide_fax/widgets/signature.html'

    @property
    def media(self):
        return forms.Media(css={'all': ('froide_fax/signature.css',)},
                           js=('froide_fax/signature_pad.min.js',
                               'froide_fax/signature.js'))
