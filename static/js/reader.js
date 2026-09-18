/*
 * reader.js — настройки страницы «Чтение».
 *
 * Все переключатели, кроме языка перевода, работают без обращения к серверу:
 * они снимают и вешают классы на контейнере, а как это выглядит, решает CSS.
 * Текст при этом не перерисовывается.
 */

const readerElement = document.getElementById("reader");
const store = window.DushuSettings;

if (readerElement && store) {
  // Имя настройки -> класс, который её выключает. Классы именно «выключающие»,
  // потому что по умолчанию всё включено, и разметка остаётся чистой.
  const SWITCH_CLASSES = {
    pinyin: "pinyin-off",
    translation: "translation-off",
    tones: "tones-off",
    hints: "hints-off",
  };

  const FONT_SIZES = {
    sm: "var(--reader-sm)",
    md: "var(--reader-md)",
    lg: "var(--reader-lg)",
  };

  /**
   * Применяет состояние переключателя к тексту.
   *
   * @param {string} name — имя настройки
   * @param {boolean} enabled — включена ли она
   */
  function applySwitch(name, enabled) {
    const className = SWITCH_CLASSES[name];
    if (className) {
      readerElement.classList.toggle(className, !enabled);
    }
  }

  /**
   * Применяет размер шрифта.
   *
   * Это единственное место, где JS трогает style напрямую. Альтернатива —
   * три класса-модификатора, но размеры уже заданы переменными в tokens.css,
   * и дублировать их в CSS ради этого не хочется.
   *
   * @param {string} size — sm, md или lg
   */
  function applyFontSize(size) {
    readerElement.style.fontSize = FONT_SIZES[size] || FONT_SIZES.md;
  }

  // --- восстановление сохранённых настроек ---

  for (const [name, className] of Object.entries(SWITCH_CLASSES)) {
    const enabled = store.readSetting(name, true);
    applySwitch(name, enabled);

    const button = document.querySelector(`.switch[data-setting="${name}"]`);
    if (button) {
      button.setAttribute("aria-checked", String(enabled));
    }
    // className не используется здесь напрямую, но оставлен в цикле,
    // чтобы список настроек был в одном месте.
    void className;
  }

  const savedSize = store.readSetting("fontSize", "md");
  applyFontSize(savedSize);
  for (const button of document.querySelectorAll("#font-size .segmented__item")) {
    const isActive = button.dataset.value === savedSize;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  }

  // --- реакция на переключение ---

  // События приходят от controls.js: он меняет классы и ARIA, а что это значит
  // для страницы, решаем здесь.
  document.addEventListener("switch:change", (event) => {
    const { name, checked } = event.detail;
    applySwitch(name, checked);
    store.writeSetting(name, checked);
  });

  const fontSizeGroup = document.getElementById("font-size");
  if (fontSizeGroup) {
    fontSizeGroup.addEventListener("segmented:change", (event) => {
      applyFontSize(event.detail.value);
      store.writeSetting("fontSize", event.detail.value);
    });
  }

  // Язык перевода — единственная настройка, которой нужен сервер: меняется
  // и перевод предложений, и язык подсказок. Отправляем форму с тем же текстом.
  const languageForm = document.getElementById("language-form");
  const languageValue = document.getElementById("language-value");
  if (languageForm && languageValue) {
    languageForm.addEventListener("segmented:change", (event) => {
      if (event.detail.value === languageValue.value) {
        return;
      }
      languageValue.value = event.detail.value;
      store.writeSetting("language", event.detail.value);
      languageForm.submit();
    });
  }
}
