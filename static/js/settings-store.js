/*
 * settings-store.js — настройки пользователя в браузере.
 *
 * Гость должен иметь возможность пользоваться сайтом без регистрации, поэтому
 * его настройки живут в localStorage. На шестом этапе появится вход, и для
 * авторизованных те же самые значения будут приходить с сервера — интерфейс
 * этого модуля тогда не изменится, поменяется только источник данных.
 *
 * Всё хранится одним объектом под одним ключом, а не россыпью ключей:
 * добавить новую настройку тогда можно, ничего не переписывая.
 */

const STORAGE_KEY = "dushu.settings";

/**
 * Читает все настройки.
 *
 * @returns {Object} сохранённые значения, либо пустой объект
 */
function readSettings() {
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
