from django.contrib import admin

from .models import Signature


class SignatureAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'timestamp', 'user')
    date_hierarchy = 'timestamp'
    raw_id_fields = ('user',)


admin.site.register(Signature, SignatureAdmin)
