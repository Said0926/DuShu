from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Project user.

    Currently identical to Django's built-in user. It exists from day one because
    swapping ``AUTH_USER_MODEL`` after the first migration effectively requires
    recreating the database.

    Later stages add: email-based login via allauth (stage 6) and a one-to-one
    ``UserSettings`` record holding the reader and shadowing preferences.
    """

    def __str__(self) -> str:
        return self.username
