"""Speech backends.

Concrete providers are not imported here: settings names one by path and it is
loaded on demand. Importing them all would drag aiohttp into every test run.
"""

from .base import CharTiming, Synthesis, TTSProvider

__all__ = ["CharTiming", "Synthesis", "TTSProvider"]
