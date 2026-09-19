"""Forms for the shadowing page."""

from apps.core.forms import TextSubmissionForm


class ShadowingForm(TextSubmissionForm):
    """The text a user submits for shadowing.

    Nothing is added to the shared form: this page needs exactly what the reader
    needs. The class stays so that a field only shadowing needs has an obvious
    place to go.
    """
