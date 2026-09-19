/*
 * library.js — кнопка «Сохранить в библиотеку» на странице «Чтение».
 *
 * Сохраняем запросом, а не отправкой формы: обычная форма перезагрузила бы
 * страницу, «Чтение» прогнало бы текст заново — то есть сохранение стоило бы
 * единицы часового лимита — и потерялось бы место, до которого дочитали.
 */

const saveButton = document.getElementById("save-text");
const sourceInput = document.getElementById("source-text");

if (saveButton && sourceInput) {
  /**
   * Переводит кнопку в конечное состояние: текст сохранён, нажимать больше нечего.
   *
   * @param {string} label — надпись
   */
  function markDone(label) {
    saveButton.textContent = label;
    saveButton.disabled = true;
  }

  saveButton.addEventListener("click", async () => {
    // Блокируем сразу: два быстрых клика иначе ушли бы двумя запросами.
    saveButton.disabled = true;

    try {
      const response = await fetch(saveButton.dataset.url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": window.DushuCsrf.getCsrfToken(),
        },
        body: JSON.stringify({ content: sourceInput.value }),
      });

      const answer = await response.json();

      if (!response.ok) {
        // Возвращаем кнопку в рабочее состояние: причина могла быть временной.
        saveButton.disabled = false;
        saveButton.textContent = answer.message || "Не удалось сохранить";
        return;
      }

      // created === false означает, что этот текст уже был в библиотеке.
      markDone(answer.data.created ? "В библиотеке" : "Уже в библиотеке");
    } catch (error) {
      console.warn("Не удалось сохранить текст:", error);
      saveButton.disabled = false;
      saveButton.textContent = "Не удалось сохранить";
    }
  });
}
