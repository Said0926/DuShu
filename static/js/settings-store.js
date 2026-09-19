/*
 * settings-store.js — настройки пользователя.
 *
 * У модуля два режима, и снаружи они неразличимы: и reader.js, и home.js
 * просто зовут readSetting и writeSetting, не зная, куда всё уходит.
 *
 *   гость         — localStorage этого браузера;
 *   авторизован   — база на сервере.
 *
 * Режим определяется по разметке: сервер отдаёт настройки авторизованного
 * блоком <script id="user-settings"> и кладёт адрес сохранения в data-атрибут
 * <body>. Нет блока — значит гость. Отдельного запроса «а кто я?» не нужно.
 *
 * Всё хранится одним объектом, а не россыпью ключей: добавить новую настройку
 * можно, ничего здесь не переписывая.
 */

const STORAGE_KEY = "dushu.settings";

const serverElement = document.getElementById("user-settings");
const settingsUrl = document.body.dataset.settingsUrl || "";

// Копия серверных настроек в памяти. Её же правит writeSetting, чтобы страница
// сразу видела новое значение, не дожидаясь ответа сервера.
const serverSettings = serverElement ? JSON.parse(serverElement.textContent) : null;
const isAuthenticated = serverSettings !== null && settingsUrl !== "";

/**
 * Отправляет одну настройку на сервер.
 *
 * Ответа никто не ждёт: значение уже применено к странице и к копии в памяти,
 * поэтому интерфейс не должен подвисать на время запроса. Если сохранить не
 * удалось, пользователь увидит изменение, но после перезагрузки его не станет —
 * поэтому пишем предупреждение в консоль, а не молчим.
 *
 * @param {string} name — имя настройки
 * @param {*} value — значение
 */
async function saveToServer(name, value) {
  try {
    const response = await fetch(settingsUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": window.DushuCsrf.getCsrfToken(),
      },
      body: JSON.stringify({ name, value }),
    });

    if (!response.ok) {
      console.warn("Настройку не удалось сохранить, статус:", response.status);
    }
  } catch (error) {
    console.warn("Настройку не удалось сохранить:", error);
  }
}

/**
 * Читает все настройки.
 *
 * @returns {Object} сохранённые значения, либо пустой объект
 */
function readSettings() {
  if (isAuthenticated) {
    return { ...serverSettings };
  }

  try {
    // localStorage может быть недоступен: приватный режим в Safari, запрет
    // сторонних данных, переполнение. Настройки — не та вещь, из-за которой
    // страница имеет право не работать.
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (error) {
    console.warn("Не удалось прочитать настройки:", error);
    return {};
  }
}

/**
 * Сохраняет одну настройку, не затирая остальные.
 *
 * @param {string} name — имя настройки
 * @param {*} value — значение
 */
function writeSetting(name, value) {
  if (isAuthenticated) {
    serverSettings[name] = value;
    saveToServer(name, value);
    return;
  }

  try {
    const settings = readSettings();
    settings[name] = value;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch (error) {
    console.warn("Не удалось сохранить настройку:", error);
  }
}

/**
 * Читает одну настройку.
 *
 * @param {string} name — имя настройки
 * @param {*} fallback — что вернуть, если настройка не сохранена
 * @returns {*}
 */
function readSetting(name, fallback) {
  const settings = readSettings();
  return name in settings ? settings[name] : fallback;
}

// Скрипты подключаются обычными тегами, без модулей, поэтому обмен идёт через
// один объект в window. Имя выбрано с префиксом проекта, чтобы не столкнуться
// с чем-то посторонним.
window.DushuSettings = { readSettings, readSetting, writeSetting };
