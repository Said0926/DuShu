"""Forms for the reader page."""

from apps.core.forms import TextSubmissionForm


class ReaderForm(TextSubmissionForm):
    """The text a user submits for reading.

    Nothing is added to the shared form any more: the translation language moved
    there when shadowing started showing translations too. The class stays so
    that a field only the reader needs has an obvious place to go.
    """
