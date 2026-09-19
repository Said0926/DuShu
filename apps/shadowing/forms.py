"""Forms for the shadowing page."""

from apps.core.forms import TextSubmissionForm


class ShadowingForm(TextSubmissionForm):
    """The text a user submits for shadowing.

    Nothing is added to the shared form: this page does not translate, so it has
    no use for a language. It exists as its own class anyway, so that a field
    only shadowing needs has an obvious place to go.
    """
