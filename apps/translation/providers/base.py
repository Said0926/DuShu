"""The provider interface every translation backend implements."""

from abc import ABC, abstractmethod


class TranslationProvider(ABC):
    """Translates sentences into a target language.

    Everything that talks to a translation service goes through this class, so
    swapping DeepL for something else means writing one new subclass and
    changing one setting — no view, service or template is affected.

    Implementations must honour two rules:

    - the result has exactly as many items as the input;
    - the order is preserved.

    Without them a sentence would end up showing another sentence's translation,
    which is worse than showing none at all.
    """

    @abstractmethod
    def translate(self, sentences: list[str], target_lang: str) -> list[str]:
        """Translate a batch of sentences.

        Args:
            sentences: Sentences to translate, already deduplicated by the caller.
            target_lang: Language code as used in ``settings.TRANSLATION_LANGUAGES``.

        Returns:
            Translations, one per input sentence, in the same order.

        Raises:
            TranslationError: If the service is unreachable or rejects the request.
        """
