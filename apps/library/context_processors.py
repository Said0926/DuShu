"""Context processors of the library app."""

from .models import ReadingProgress


def reading_statuses(request) -> dict[str, list[tuple[str, str]]]:
    """Put the list of reading statuses into every template.

    The same three-segment control appears on a library card and in the reader's
    header. Handing the labels to every template through settings, rather than
    importing them into the reader's views, is what keeps the two features from
    depending on each other in Python — the rule the app map sets out.

    Costs nothing: the value is a constant on the model, not a query.
    """
    return {"reading_statuses": ReadingProgress.Status.choices}
