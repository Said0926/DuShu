/*
 * player.js — плеер страницы «Shadowing».
 *
 * Весь звук и все тайминги уже в разметке: у каждого предложения есть
 * data-audio и data-duration, у каждого слова — data-start и data-end
 * в миллисекундах. Поэтому плеер получился полностью синхронным: он не ждёт
 * ответов сервера, и состояний «грузится / упало / не успело» у него нет.
 *
 * Важная тонкость про скорость. audio.currentTime измеряется во времени самой
 * записи, а не по настенным часам: на 0,5× он растёт вдвое медленнее реального
 * времени. Значит тайминги, записанные для нормальной скорости, сравниваются
 * с currentTime напрямую — пересчитывать их под playbackRate не нужно.
 *
 * JS здесь, как и везде в проекте, меняет только классы, data-атрибуты и
 * текст. Ни одного inline-стиля: заливку дорожки рисует <progress>.
 */

const root = document.getElementById("shadowing");
const audio = document.getElementById("player");
const store = window.DushuSettings;

if (root && audio && store) {
  // --- разметка, из которой плеер читает данные ---

  const sentences = Array.from(root.querySelectorAll(".stage__sentence"));
  const rows = Array.from(root.querySelectorAll(".sentence-row"));
  const progress = document.getElementById("progress");
  const timeCurrent = document.getElementById("time-current");
  const timeTotal = document.getElementById("time-total");
  const currentNumber = document.getElementById("current-number");
  const currentRepeat = document.getElementById("current-repeat");
  const totalRepeats = document.getElementById("total-repeats");
  const repeatsValue = document.getElementById("repeats-value");

  // Фиксированная пауза и множитель для автоматической — из DESIGN.md §7.
  const FIXED_PAUSE_MS = 2000;
  const AUTO_PAUSE_FACTOR = 1.5;

  // Границы степпера повторов. Те же числа проверяет сервер
  // (MIN_REPEATS / MAX_REPEATS в apps/accounts/models.py).
  const MIN_REPEATS = 1;
  const MAX_REPEATS = 5;

  // --- состояние ---

  let index = 0; // какое предложение открыто
  let repeat = 1; // какой это повтор
  let repeats = clampRepeats(Number(root.dataset.repeats) || MIN_REPEATS);
  let pauseMode = root.dataset.pauseMode === "fixed" ? "fixed" : "auto";
  let speed = 1;

  // Идентификатор таймера паузы между предложениями. Нужен, чтобы отменить
  // отложенный переход, если в это время нажали play, next или строку списка:
  // иначе пауза «выстрелит» поверх нового предложения и уведёт с него.
  let pauseTimer = null;

  /**
   * Приводит число повторов в допустимые границы.
   *
   * @param {number} value
   * @returns {number}
   */
  function clampRepeats(value) {
    return Math.min(MAX_REPEATS, Math.max(MIN_REPEATS, value));
  }

  /**
   * Форматирует миллисекунды как 0:04.
   *
   * padStart дополняет строку слева до нужной длины, поэтому секунды всегда
   * двузначные и таймер не дёргается по ширине.
   *
   * @param {number} ms
   * @returns {string}
   */
  function formatTime(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${Math.floor(totalSeconds / 60)}:${seconds}`;
  }

  /** Отменяет отложенный переход к следующему предложению. */
  function cancelPause() {
    if (pauseTimer !== null) {
      clearTimeout(pauseTimer);
      pauseTimer = null;
    }
  }

  /** Снимает караоке-подсветку со всех слов. */
  function clearHighlight() {
    for (const word of root.querySelectorAll(".word.is-speaking")) {
      word.classList.remove("is-speaking");
    }
  }

  /**
   * Открывает предложение: показывает его, подставляет аудио, обнуляет прогресс.
   *
   * @param {number} next — номер предложения с нуля
   */
  function show(next) {
    index = Math.min(sentences.length - 1, Math.max(0, next));
    repeat = 1;

    const sentence = sentences[index];
    const duration = Number(sentence.dataset.duration);

    // Текущее предложение выбирается классом, а не перерисовкой разметки.
    sentences.forEach((element, position) => {
      element.classList.toggle("is-current", position === index);
    });

    // В списке три состояния: текущее, пройденное и впереди (DESIGN.md §7).
    rows.forEach((row, position) => {
      row.classList.toggle("is-current", position === index);
      row.classList.toggle("is-done", position < index);
    });

    clearHighlight();

    audio.src = sentence.dataset.audio;
    audio.playbackRate = speed;

    progress.value = 0;
    progress.max = duration;
    timeCurrent.textContent = formatTime(0);
    timeTotal.textContent = formatTime(duration);
    currentNumber.textContent = String(index + 1);
    currentRepeat.textContent = "1";

    // scrollIntoView прокручивает список к текущей строке. block: "nearest" —
    // чтобы страница не прыгала, когда строка и так видна.
    rows[index]?.scrollIntoView({ block: "nearest" });
  }

  /** Запускает воспроизведение текущего предложения с начала. */
  function play() {
    cancelPause();
    audio.playbackRate = speed;
    // Обещание от play() может отклониться — например, если браузер запретил
    // автовоспроизведение. Молча игнорируем: пользователь нажмёт ещё раз,
    // а необработанное отклонение засоряло бы консоль.
    audio.play().catch(() => {});
  }

  /** Ставит на паузу, оставляя позицию на месте. */
  function pause() {
    cancelPause();
    audio.pause();
  }

  /**
   * Сколько молчать после предложения, прежде чем идти дальше.
   *
   * Автоматический режим даёт полторы длительности фразы: повторить её вслух
   * занимает чуть больше времени, чем прослушать.
   *
   * @returns {number} миллисекунды
   */
  function pauseLength() {
    if (pauseMode === "fixed") {
      return FIXED_PAUSE_MS;
    }
    return Number(sentences[index].dataset.duration) * AUTO_PAUSE_FACTOR;
  }

  /**
   * Что делать, когда предложение доиграло.
   *
   * Сначала добираем повторы, потом уходим на следующее предложение. И то и
   * другое — после паузы, которая и есть смысл упражнения: в этой тишине
   * фраза повторяется вслух.
   */
  function onEnded() {
    clearHighlight();
    progress.value = progress.max;

    const isLastRepeat = repeat >= repeats;
    const isLastSentence = index >= sentences.length - 1;

    if (isLastRepeat && isLastSentence) {
      root.classList.remove("is-playing");
      return;
    }

    pauseTimer = setTimeout(() => {
      pauseTimer = null;

      if (isLastRepeat) {
        show(index + 1);
      } else {
        repeat += 1;
        currentRepeat.textContent = String(repeat);
        clearHighlight();
      }

      play();
    }, pauseLength());
  }

  /**
   * Подсвечивает слово, которое звучит прямо сейчас, и двигает прогресс.
   *
   * Слова перебираются целиком на каждом кадре: их в предложении десятки,
   * так что это дешевле и несравнимо понятнее, чем поддерживать указатель
   * на текущее слово и следить за его сдвигами при перемотке.
   */
  function render() {
    const position = audio.currentTime * 1000;

    progress.value = Math.min(position, progress.max);
    timeCurrent.textContent = formatTime(position);

    for (const word of sentences[index].querySelectorAll(".word")) {
      const start = Number(word.dataset.start);
      const end = Number(word.dataset.end);
      // Слово без таймингов (пунктуация, латиница) не подсвечивается никогда:
      // dataset.start у него нет, и Number(undefined) даёт NaN, а любое
      // сравнение с NaN ложно.
      word.classList.toggle("is-speaking", position >= start && position < end);
    }
  }

  // --- восстановление сохранённых настроек ---

  // Пиньинь, цвета тонов и перевод — те же настройки, что в «Чтении», поэтому
  // читаются из того же стора и теми же именами: выключил перевод там —
  // выключен и здесь.
  const SWITCH_CLASSES = {
    pinyin: "pinyin-off",
    tones: "tones-off",
    translation: "translation-off",
  };

  for (const [name, className] of Object.entries(SWITCH_CLASSES)) {
    const enabled = store.readSetting(name, true);
    root.classList.toggle(className, !enabled);

    const button = root.querySelector(`.switch[data-setting="${name}"]`);
    if (button) {
      button.setAttribute("aria-checked", String(enabled));
    }
  }

  repeats = clampRepeats(store.readSetting("repeats", repeats));
  pauseMode = store.readSetting("pauseMode", pauseMode) === "fixed" ? "fixed" : "auto";
  repeatsValue.textContent = String(repeats);
  totalRepeats.textContent = String(repeats);

  for (const button of document.querySelectorAll("#pause-mode .segmented__item")) {
    const isActive = button.dataset.value === pauseMode;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  }

  // --- органы управления ---

  document.getElementById("play").addEventListener("click", () => {
    if (audio.paused) {
      root.classList.add("is-playing");
      play();
    } else {
      root.classList.remove("is-playing");
      pause();
    }
  });

  document.getElementById("repeat").addEventListener("click", () => {
    audio.currentTime = 0;
    root.classList.add("is-playing");
    play();
  });

  document.getElementById("prev").addEventListener("click", () => {
    show(index - 1);
    if (root.classList.contains("is-playing")) {
      play();
    }
  });

  document.getElementById("next").addEventListener("click", () => {
    show(index + 1);
    if (root.classList.contains("is-playing")) {
      play();
    }
  });

  // Переход по списку предложений — тоже делегированием: строк много,
  // а обработчик один.
  document.getElementById("sentence-list").addEventListener("click", (event) => {
    const row = event.target.closest(".sentence-row");
    if (!row) {
      return;
    }
    show(Number(row.dataset.index));
    if (root.classList.contains("is-playing")) {
      play();
    }
  });

  // Скорость применяется к уже играющему звуку сразу: playbackRate можно
  // менять на ходу, перезапускать воспроизведение не нужно.
  document.getElementById("speed").addEventListener("segmented:change", (event) => {
    speed = Number(event.detail.value);
    audio.playbackRate = speed;
  });

  document.getElementById("pause-mode").addEventListener("segmented:change", (event) => {
    pauseMode = event.detail.value;
    store.writeSetting("pauseMode", pauseMode);
  });

  document.getElementById("repeats").addEventListener("click", (event) => {
    const button = event.target.closest(".stepper__btn");
    if (!button) {
      return;
    }

    const updated = clampRepeats(repeats + Number(button.dataset.step));
    if (updated === repeats) {
      return;
    }

    repeats = updated;
    repeatsValue.textContent = String(repeats);
    totalRepeats.textContent = String(repeats);
    store.writeSetting("repeats", repeats);
  });

  root.addEventListener("switch:change", (event) => {
    const { name, checked } = event.detail;
    const className = SWITCH_CLASSES[name];
    if (className) {
      root.classList.toggle(className, !checked);
      store.writeSetting(name, checked);
    }
  });

  // --- кадры анимации ---

  /*
   * Подсветка обновляется по кадрам, а не по событию timeupdate.
   *
   * Это не украшательство: timeupdate приходит примерно четыре раза в секунду,
   * то есть раз в 250 мс, а односложное слово звучит около 120 мс. По
   * настоящим замерам 我 (125 мс) и 去 (113 мс) не подсвечивались вообще ни
   * разу — событие просто перепрыгивало через них. В китайском односложные
   * слова самые частые, так что пострадала бы ровно та функция, ради которой
   * страница и сделана.
   *
   * requestAnimationFrame вызывается примерно 60 раз в секунду и сам
   * останавливается в фоновой вкладке, где рисовать всё равно нечего.
   */
  let frameId = null;

  function onFrame() {
    frameId = null;
    render();

    // Цикл живёт ровно столько, сколько идёт звук: на паузе кадры не нужны.
    if (!audio.paused) {
      frameId = requestAnimationFrame(onFrame);
    }
  }

  function startFrames() {
    if (frameId === null) {
      frameId = requestAnimationFrame(onFrame);
    }
  }

  // --- события самого аудио ---

  audio.addEventListener("playing", startFrames);
  audio.addEventListener("ended", onEnded);

  // Страница открывается на первом предложении, но не играет: звук начинается
  // только по нажатию, иначе браузер всё равно его заблокирует.
  show(0);
}
