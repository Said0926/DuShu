"""Views for the accounts app."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class ProfileView(LoginRequiredMixin, TemplateView):
    """The signed-in user's own account page.

    ``LoginRequiredMixin`` sends anonymous visitors to ``settings.LOGIN_URL`` and
    brings them back here afterwards, so the check is not repeated by hand. The
    template reads everything it needs from ``user``, which the auth context
    processor already provides.
    """

    template_name = "accounts/profile.html"
