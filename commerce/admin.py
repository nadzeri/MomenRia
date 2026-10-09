from django.contrib import admin
from django import forms
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from momenria.admin import AuditReasonForm, ReadOnlyAdmin
from momenria.http import ApiError

from .models import Entitlement, Order, PaymentEvent, Refund
from .services import record_refund_outcome


class RefundOutcomeForm(AuditReasonForm):
    outcome = forms.ChoiceField(choices=[(value, label) for value, label in Refund.State.choices if value != Refund.State.REQUESTED])
    amount_idr = forms.IntegerField(min_value=1, label="This refund request amount (IDR)")
    reference = forms.CharField(min_length=5, max_length=180, label="External refund or tracking reference")
    evidence = forms.CharField(min_length=10, max_length=1000, widget=forms.Textarea, label="Verified dashboard/report or approved transfer evidence")

    class Meta:
        model = Refund
        fields = ("amount_idr",)


@admin.register(Refund)
class RefundAdmin(ReadOnlyAdmin):
    def get_urls(self):
        return [path("<uuid:refund_id>/record/", self.admin_site.admin_view(self.record), name="commerce_refund_record")] + super().get_urls()

    def get_readonly_fields(self, request, obj=None):
        return super().get_readonly_fields(request, obj) + ("record_outcome",)

    @admin.display(description="Audited refund outcome")
    def record_outcome(self, obj):
        return format_html('<a href="{}">Record external refund outcome</a>', reverse("admin:commerce_refund_record", args=(obj.id,)))

    def record(self, request, refund_id):
        if not request.user.has_perm("commerce.change_refund"):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        from django.shortcuts import get_object_or_404
        refund = get_object_or_404(Refund, pk=refund_id)
        form = RefundOutcomeForm(request.POST or None, instance=refund)
        if request.method == "POST" and form.is_valid():
            values = dict(form.cleaned_data)
            values["reason"] = values.pop("audit_reason")
            try:
                record_refund_outcome(request.user, refund.id, **values)
            except ApiError as error:
                form.add_error(None, error.message)
            else:
                self.message_user(request, "External refund outcome recorded. This form does not transfer money.")
                return HttpResponseRedirect(reverse("admin:commerce_refund_change", args=(refund.id,)))
        return TemplateResponse(request, "admin/refund_outcome.html", {**self.admin_site.each_context(request), "title": "Record external refund outcome", "form": form, "refund": refund})


for model in (Order, PaymentEvent, Entitlement):
    admin.site.register(model, ReadOnlyAdmin)
