/*
 * csrf.js — один помощник на весь проект.
 *
 * Обычные формы получают токен тегом {% csrf_token %}, а запросам через fetch
 * приходится читать его из cookie самим. Это задокументированный способ из
 * документации Django, и нужен он уже двум модулям — настройкам и библиотеке,
 * поэтому лежит отдельно, а не копируется.
 */

/**
 * Достаёт CSRF-токен из cookie.
 *
 * @returns {string} токен, либо пустая строка, если cookie ещё нет
 */
function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

window.DushuCsrf = { getCsrfToken };
