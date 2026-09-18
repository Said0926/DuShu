/*
 * tooltip.js — подсказка по слову при наведении и по тапу.
 *
 * Данные приходят из локальной базы (/reader/lookup/), внешние API не
 * участвуют, поэтому подсказка появляется мгновенно и ничего не стоит.
 */

const reader = document.getElementById("reader");

if (reader) {
  const language = reader.dataset.lang;

  // Ответы кэшируем: пользователь возвращается к одним и тем же словам,
  // и повторно дёргать сервер незачем.
  const cache = new Map();

  // На десктопе подсказка по наведению, на телефоне — по тапу.
  // Проверяем именно возможность наведения, а не наличие тача: у ноутбука
  // с сенсорным экраном есть и то и другое.
  const canHover = window.matchMedia("(hover: hover)").matches;

  let activeWord = null;

  /**
   * Убирает открытую подсказку.
   */
  function closeTooltip() {
    if (!activeWord) {
      return;
    }
    const tooltip = activeWord.querySelector(".tooltip");
    if (tooltip) {
      tooltip.remove();
    }
    activeWord.classList.remove("is-active");
    activeWord = null;
  }

  /**
   * Собирает разметку подсказки из ответа сервера.
   *
   * @param {HTMLElement} word — элемент слова
   * @param {Object} data — поле data из ответа /reader/lookup/
   * @returns {HTMLElement}
   */
  function buildTooltip(word, data) {
    const tooltip = document.createElement("div");
    tooltip.className = "tooltip";

    const head = document.createElement("div");
    head.className = "tooltip__head";

    const hanzi = document.createElement("span");
    hanzi.className = "tooltip__word";
    hanzi.textContent = data.word;
    head.appendChild(hanzi);

    const pinyin = document.createElement("span");
    pinyin.className = "tooltip__pinyin";
    // Чтение из словаря точнее того, что мы посчитали для текста: словарь знает
    // про омографы. Если записи нет, показываем посчитанное.
    pinyin.textContent = data.found && data.entries.length
      ? data.entries[0].pinyin
      : word.dataset.pinyin;
    head.appendChild(pinyin);

    tooltip.appendChild(head);

    if (data.found) {
      for (const entry of data.entries) {
        const line = document.createElement("p");
        line.className = "tooltip__definition";
        line.textContent = entry.definitions.slice(0, 3).join("; ");
        tooltip.appendChild(line);
      }
    } else if (data.characters.length) {
      const note = document.createElement("p");
      note.className = "tooltip__note";
      note.textContent = "Слова нет в словаре — значения по иероглифам:";
      tooltip.appendChild(note);

      for (const character of data.characters) {
        const row = document.createElement("p");
        row.className = "tooltip__character";

        const glyph = document.createElement("span");
        glyph.className = "tooltip__character-hanzi";
        glyph.textContent = character.character;
        row.appendChild(glyph);

        const meaning = document.createElement("span");
        meaning.textContent = character.entries.length
          ? character.entries[0].definitions.slice(0, 2).join("; ")
          : "—";
        row.appendChild(meaning);

        tooltip.appendChild(row);
      }
    } else {
      const line = document.createElement("p");
      line.className = "tooltip__definition";
      line.textContent = "Ничего не нашлось.";
      tooltip.appendChild(line);
    }

    return tooltip;
  }

  /**
   * Запрашивает данные по слову, отдавая их из кэша при повторе.
   *
   * @param {string} word
   * @returns {Promise<Object|null>}
   */
  async function fetchWord(word) {
    if (cache.has(word)) {
      return cache.get(word);
    }

    const url = `/reader/lookup/?word=${encodeURIComponent(word)}&lang=${encodeURIComponent(language)}`;

    try {
      const response = await fetch(url);
      if (!response.ok) {
        return null;
      }
      const payload = await response.json();
      cache.set(word, payload.data);
      return payload.data;
    } catch (error) {
      // Сеть отвалилась — подсказки не будет, но чтение продолжается.
      console.warn("Не удалось получить подсказку:", error);
      return null;
    }
  }

  /**
   * Показывает подсказку для слова.
   *
   * @param {HTMLElement} word
   */
  async function openTooltip(word) {
    if (reader.classList.contains("hints-off")) {
      return;
    }

    closeTooltip();
    activeWord = word;
    word.classList.add("is-active");

    const data = await fetchWord(word.dataset.word);

    // Пока шёл запрос, курсор мог уехать на другое слово. Тогда этот ответ
    // уже неактуален и рисовать его нельзя.
    if (activeWord !== word || !data) {
      return;
    }

    word.appendChild(buildTooltip(word, data));
  }

  if (canHover) {
    // mouseover всплывает, в отличие от mouseenter, поэтому один обработчик
    // на контейнере заменяет обработчик на каждом слове.
    reader.addEventListener("mouseover", (event) => {
      const word = event.target.closest(".word");
      if (word && word !== activeWord) {
        openTooltip(word);
      }
    });

    reader.addEventListener("mouseout", (event) => {
      const word = event.target.closest(".word");
      // relatedTarget — куда курсор уходит. Если он остался внутри того же
      // слова (например, перешёл на саму подсказку), закрывать не нужно.
      if (word && !word.contains(event.relatedTarget)) {
        closeTooltip();
      }
    });
  } else {
    reader.addEventListener("click", (event) => {
      const word = event.target.closest(".word");
      if (!word) {
        return;
      }
      if (word === activeWord) {
        closeTooltip();
      } else {
        openTooltip(word);
      }
    });

    // Тап мимо текста закрывает подсказку.
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".word")) {
        closeTooltip();
      }
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeTooltip();
    }
  });

  // Слово — это кнопка, поэтому до него можно дойти табом.
  reader.addEventListener("focusin", (event) => {
    const word = event.target.closest(".word");
    if (word) {
      openTooltip(word);
    }
  });
}
