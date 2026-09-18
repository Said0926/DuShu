/*
 * home.js — поведение главной страницы: счётчик символов и выбор языка перевода.
 */

const textarea = document.getElementById("id_text");
const counter = document.getElementById("char-counter");
const languageInput = document.getElementById("id_lang");
const languageGroup = document.querySelector(".input-card .segmented");

/**
 * Обновляет счётчик под полем ввода.
 *
 * Числа форматируются через toLocaleString("ru-RU") — он сам расставит
 * разделители разрядов: 5000 превращается в «5 000».
 */
function updateCounter() {
  const used = textarea.value.length.toLocaleString("ru-RU");
  const max = Number(textarea.dataset.maxLength).toLocaleString("ru-RU");
  counter.textContent = `${used} / ${max} символов`;
}

if (textarea && counter) {
  textarea.addEventListener("input", updateCounter);
  // Вызываем сразу, чтобы счётчик не был пустым до первого ввода.
  // Заодно это покрывает случай, когда браузер восстановил текст после перезагрузки.
  updateCounter();
}

// Сегментированный контрол сам по себе только подсвечивает выбор. Чтобы значение
// уехало на сервер вместе с формой, кладём его в скрытое поле.
if (languageGroup && languageInput) {
  const store = window.DushuSettings;

  // Восстанавливаем язык, выбранный в прошлый раз. Без этого настройка
  // сохранялась, но никогда не читалась: пользователь переключался на English,
  // возвращался и снова видел русский.
  if (store) {
    const savedLanguage = store.readSetting("language", null);
    const savedButton =
      savedLanguage &&
      languageGroup.querySelector(`.segmented__item[data-value="${savedLanguage}"]`);

    if (savedButton) {
      languageInput.value = savedLanguage;
      for (const button of languageGroup.querySelectorAll(".segmented__item")) {
        const isActive = button === savedButton;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", String(isActive));
      }
    }
  }

  languageGroup.addEventListener("segmented:change", (event) => {
    languageInput.value = event.detail.value;
    if (store) {
      store.writeSetting("language", event.detail.value);
    }
  });
}
