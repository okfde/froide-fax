from django.contrib import admin

from .models import Signature


class SignatureAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'timestamp',)
    date_hierarchy = 'timestamp'
    raw_id_fields = ('user',)
    search_fields = ('user__email',)


admin.site.register(Signature, SignatureAdmin)
