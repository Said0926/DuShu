"""Translation backends.

Concrete providers are not imported here: settings names one by path and it is
loaded on demand. Importing them all would drag requests into every test run.
"""

from .base import TranslationProvider

__all__ = ["TranslationProvider"]
