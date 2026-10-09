import time
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID

from allauth.account import app_settings
from allauth.account.forms import UserTokenForm
from allauth.account.internal.stagekit import unstash_login
from allauth.account.models import EmailAddress, get_emailconfirmation_model
from allauth.account.utils import get_next_redirect_url
from allauth.account.views import INTERNAL_RESET_SESSION_KEY
from django import forms
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from catalog.models import TemplateVersion


def authentication_return(request):
    if not request.path.startswith("/accounts/"):
        return {}
    view = request.resolver_match.url_name
    recovery_views = {"account_reset_password", "account_reset_password_done", "account_reset_password_from_key", "account_reset_password_from_key_done"}
    explicit = "next" in request.GET or "next" in request.POST
    recovery = request.session.get("account_recovery_return")
    target = get_next_redirect_url(request)
    completion = {"account_reset_password": "account_reset_password_done", "account_reset_password_from_key": "account_reset_password_from_key_done"}.get(view)
    if target and request.method == "POST" and completion:
        wrapper = urlsplit(target)
        if wrapper.path == reverse(completion) and not wrapper.scheme and not wrapper.netloc and not wrapper.fragment:
            target = parse_qs(wrapper.query).get("next", [None])[0]
    if (explicit and not target) or (request.method == "GET" and (view in {"account_login", "account_signup"} or not explicit and view == "account_reset_password")):
        request.session.pop("account_recovery_return", None)
        recovery = None
    if recovery and not 0 <= time.time() - recovery["started_at"] <= app_settings.LOGIN_TIMEOUT:
        request.session.pop("account_recovery_return", None)
        recovery = None
    if not target and not explicit:
        if view in recovery_views and recovery:
            target = recovery["next"]
        if view in {"account_email_verification_sent", "account_confirm_email", "mfa_authenticate"} and not request.user.is_authenticated:
            pending = unstash_login(request, peek=True)
            if pending and view == "account_confirm_email":
                confirmation = get_emailconfirmation_model().from_key(request.resolver_match.kwargs["key"])
                if not confirmation or not pending.user or confirmation.email_address.user_id != pending.user.pk:
                    pending = None
            target = pending.redirect_url if pending else None
    if not target or not target.startswith("/#/") or not url_has_allowed_host_and_scheme(target, allowed_hosts=set()):
        request.session.pop("account_recovery_return", None)
        return {}
    parsed = urlsplit(target)
    if parsed.path != "/" or parsed.query or parsed.scheme or parsed.netloc or "\\" in target:
        request.session.pop("account_recovery_return", None)
        return {}
    if view == "account_reset_password_from_key" and recovery:
        uid = request.resolver_match.kwargs["uidb36"]
        if request.method == "GET":
            key = request.resolver_match.kwargs["key"]
            token = UserTokenForm(data={"uidb36": uid, "key": request.session.get(INTERNAL_RESET_SESSION_KEY, "") if key == "set-password" else key})
            if not token.is_valid() or not recovery.get("email") or not (token.reset_user.email.lower() == recovery["email"] or EmailAddress.objects.filter(user=token.reset_user, email=recovery["email"]).exists()):
                request.session.pop("account_recovery_return", None)
                return {}
            recovery = {**recovery, "uid": uid}
            request.session["account_recovery_return"] = recovery
        elif recovery.get("uid") != uid:
            request.session.pop("account_recovery_return", None)
            return {}
    if view == "account_reset_password_from_key_done" and recovery and not recovery.get("uid"):
        return {}
    label = {"/": "Beranda", "/projects": "Foto saya", "/templates": "Pilihan template", "/support": "Bantuan"}.get(parsed.fragment)
    parts = parsed.fragment.split("/")
    if len(parts) in {3, 4} and parts[1] == "studio":
        try:
            template_id = UUID(parts[2])
            if len(parts) == 4:
                UUID(parts[3])
        except ValueError:
            request.session.pop("account_recovery_return", None)
            return {}
        name = TemplateVersion.objects.filter(pk=template_id, status=TemplateVersion.Status.PUBLISHED, evidence_approved=True).values_list("name", flat=True).first()
        if name:
            label = f"Studio · {name}"
    if not label:
        request.session.pop("account_recovery_return", None)
        return {}
    if view == "account_reset_password":
        recovery = {"next": target, "started_at": time.time()}
        if request.method == "POST":
            # Allauth renders reset and unknown-account mail with the request before redirecting.
            try:
                recovery["email"] = forms.EmailField(max_length=254).clean(request.POST.get("email", "")).lower()
            except forms.ValidationError:
                pass
        request.session["account_recovery_return"] = recovery
    query = urlencode({"next": target})
    return {
        "account_return_label": label,
        "account_return_next": target,
        "account_return_login_url": f"{reverse('account_login')}?{query}",
        "account_return_signup_url": f"{reverse('account_signup')}?{query}",
        "account_return_reset_url": f"{reverse('account_reset_password')}?{query}",
        "account_return_reset_receipt": f"{reverse('account_reset_password_done')}?{query}",
        "account_return_reset_completion": f"{reverse('account_reset_password_from_key_done')}?{query}",
    }
