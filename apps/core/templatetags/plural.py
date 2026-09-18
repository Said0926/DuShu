"""Template filters for russian plural forms."""

from django import template

register = template.Library()


@register.filter
def plural_ru(number: int, forms: str) -> str:
    """Pick the russian plural form for a number.

    Django's built-in ``pluralize`` only knows two forms, which is enough for
    english but not for russian: 1 предложение, 2 предложения, 5 предложений.

    Args:
        number: The count.
        forms: Three comma-separated forms, for 1, for 2-4 and for 5-20.

    Returns:
        The matching form.

    Examples:
        >>> plural_ru(3, "предложение,предложения,предложений")
        'предложения'
    """
    one, few, many = (form.strip() for form in forms.split(","))

    count = abs(int(number))

    # 11-14 — исключение: они склоняются как «много», хотя оканчиваются на 1-4.
    if 11 <= count % 100 <= 14:
        return many

    last_digit = count % 10
    if last_digit == 1:
        return one
    if 2 <= last_digit <= 4:
        return few
    return many
