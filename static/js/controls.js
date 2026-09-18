/*
 * controls.js — общие интерактивные контролы: сегментированные переключатели и switch'и.
 *
 * Скрипт не знает, что именно переключает пользователь. Он меняет только классы
 * и ARIA-атрибуты, а затем сообщает об изменении событием. Конкретная страница
 * подписывается на это событие и решает, что делать дальше.
 *
 * Так контролы остаются переиспользуемыми: те же самые segmented и switch работают
 * на главной, в «Чтении» и в «Shadowing», и ни один из них не знает про другие.
 */

/**
 * Сегментированный контрол: несколько кнопок, активна ровно одна.
 *
 * @param {HTMLElement} group — контейнер с классом .segmented
 */
function initSegmented(group) {
  // Один обработчик на всю группу вместо обработчика на каждой кнопке.
  // Это называется делегированием: клик по кнопке "всплывает" до контейнера,
  // и там мы определяем, на что именно нажали.
  group.addEventListener("click", (event) => {
    // closest ищет ближайшего предка (включая сам элемент), подходящего под селектор.
    // Нужен потому, что клик может прийтись на текст внутри кнопки, а не на саму кнопку.
    const item = event.target.closest(".segmented__item");
    if (!item || !group.contains(item)) {
      return;
    }

    for (const button of group.querySelectorAll(".segmented__item")) {
      const isActive = button === item;
      button.classList.toggle("is-active", isActive);
      // aria-pressed сообщает скринридеру, какой сегмент выбран.
      // String(), потому что в атрибуте может лежать только строка, не boolean.
      button.setAttribute("aria-pressed", String(isActive));
    }

    // CustomEvent — собственное событие с произвольными данными в поле detail.
    // bubbles: true означает, что событие всплывает вверх по DOM, поэтому
    // слушать его можно и на самой группе, и на document.
    group.dispatchEvent(
      new CustomEvent("segmented:change", {
        detail: { value: item.dataset.value },
        bubbles: true,
      }),
    );
  });
}

/**
 * Переключатель (вкл/выкл). Состояние хранится в aria-checked — это один
 * источник правды сразу и для CSS, и для скринридера.
 *
 * @param {HTMLElement} button — кнопка с role="switch"
 */
function initSwitch(button) {
  button.addEventListener("click", () => {
    const checked = button.getAttribute("aria-checked") !== "true";
    button.setAttribute("aria-checked", String(checked));

    button.dispatchEvent(
      new CustomEvent("switch:change", {
        detail: { name: button.dataset.setting, checked },
        bubbles: true,
      }),
    );
  });
}

// Скрипт подключён с defer, поэтому на момент выполнения DOM уже разобран
// и ждать DOMContentLoaded не нужно.
document.querySelectorAll(".segmented").forEach(initSegmented);
document.querySelectorAll(".switch").forEach(initSwitch);
