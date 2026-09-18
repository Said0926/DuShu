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
   * Через data-атрибут, а не через style: инлайновый стиль сильнее любого
   * правила в CSS, поэтому он перебивал бы и медиазапрос, который на телефоне
   * уменьшает текст. Заодно это соблюдает общее правило — JS меняет только
   * классы и data-атрибуты.
   *
   * @param {string} size — sm, md или lg
   */
  function applyFontSize(size) {
    readerElement.dataset.size = size;
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

  // Если пользователь размер не выбирал, атрибут не ставим: тогда действует
  // значение из CSS, а на узком экране — уменьшенное из медиазапроса.
  const savedSize = store.readSetting("fontSize", null);
  if (savedSize) {
    applyFontSize(savedSize);
  }

  for (const button of document.querySelectorAll("#font-size .segmented__item")) {
    const isActive = button.dataset.value === (savedSize || "md");
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
