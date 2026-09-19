# Dúshū — read chinese

[Русский](README.md)

A web app for reading chinese texts. Paste a text and get it back in two modes:

- **Reading** — pinyin above every character, tone colours, a translation under each sentence
  and a dictionary entry when you hover a word;
- **Shadowing** — speech with the spoken word highlighted as it sounds, and a pause after every
  sentence for repeating it out loud.

It works without an account. Signing in only buys you saved texts and a higher hourly limit.

![Landing page](docs/screenshots/home.png)

---

## Contents

- [What is in it](#what-is-in-it)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [Dictionaries](#dictionaries)
- [How it is built](#how-it-is-built)
- [Extending it](#extending-it)
- [Commands](#commands)
- [Limitations and what production would need](#limitations-and-what-production-would-need)
- [Dictionary licences](#dictionary-licences)

---

## What is in it

**Reading.** The text is split into sentences and the sentences into words (jieba), and every
character gets the reading its context calls for: 行 is `háng` in 银行 and `xíng` in 不行. Pinyin
is rendered as real `<ruby>` markup and the tone is shown by colour. Sentences are translated by
DeepL; word hints come from a local database, so they appear instantly and cost nothing.

![Reading](docs/screenshots/reader.png)

**Shadowing.** Each sentence is synthesized on its own, a word lights up exactly while it sounds,
and the sentence is followed by the pause you are meant to repeat it in. Pause length, number of
repeats and speed from 0.5× to 1.5× are all adjustable.

![Shadowing](docs/screenshots/shadowing.png)

**The rest.** A library of saved texts with collections and reading statuses, five shared HSK
levels, sign-in by email and through Google, rate limiting, and display settings that follow the
reader between devices.

Stack: Python 3.12, Django 5.2, PostgreSQL 16, Django templates and vanilla JS with no frontend
framework, Docker, pytest, ruff, GitHub Actions. 461 tests.

---

## Quick start

Docker is the only requirement. No local Python is used — the container has 3.12.

```bash
git clone git@github.com:Said0926/DuShu.git
cd DuShu

cp .env.example .env
# Generate a SECRET_KEY and put it in .env:
docker compose run --rm web python -c \
  "from django.core.management.utils import get_random_secret_key as k; print(k())"

docker compose up -d
docker compose exec web python manage.py migrate
```

That is it — http://localhost:8000.

**The project runs without a single API key**, with one caveat about translation. Speech works
straight away: `edge-tts` is free and needs no account. Word hints appear once the dictionaries
are imported.

Translation, though, needs the DeepL key. Without it the page still opens and stays useful — the
text, pinyin, tones, dictionary and speech are all there — but a note appears under the
sentences saying the translation is unavailable. That is deliberate: a dying external service
must not take the page down with it. To see the source text in place of a translation and
exercise the whole interface, switch to the stub:

```bash
# .env
TRANSLATION_PROVIDER=apps.translation.providers.dummy.DummyProvider
```

Optionally:

```bash
# Admin site: this is where catalogue texts for the HSK levels are added.
docker compose exec web python manage.py createsuperuser

# In development, mail (address confirmation, password reset) is printed to the log:
docker compose logs -f web
```

---

## Environment variables

All of them live in `.env`; a commented template is in `.env.example`.

| Variable | Required | What happens without it |
|---|---|---|
| `DJANGO_SECRET_KEY` | yes | Django refuses to start |
| `POSTGRES_*`, `DATABASE_URL` | yes | no database; the defaults in the template work as they are |
| `DEEPL_API_KEY` | no | no translation; the page works and says so |
| `TRANSLATION_PROVIDER` | no | DeepL by default; the stub is only enabled by hand |
| `TTS_PROVIDER` | no | `edge-tts` by default, no key needed |
| `TTS_VOICE` | no | `zh-CN-XiaoxiaoNeural` |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | no | the Google button is not rendered at all; email sign-in still works |

A DeepL Free key is issued in your account under Account → API Keys. It looks like 36 characters
with an `:fx` suffix. The free quota is 500,000 characters a month, and every translation is
cached in the database, so reopening a text costs nothing.

The redirect URI for the Google console is
`http://localhost:8000/accounts/google/login/callback/`. Google's credentials live in `.env`
rather than in a `SocialApp` row, to keep secrets out of the database.

---

## Dictionaries

Word hints come from a local database — two dictionaries, russian and english. The dumps are
downloaded by hand and are not part of the repository.

```bash
mkdir -p data

# CC-CEDICT (english), ~124,000 entries
curl -L -o data/cedict.txt.gz \
  https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz

# BKRS (russian), ~3,460,000 entries
curl -L -o data/dabkrs.gz https://bkrs.info/downloads/daily/dabkrs_<YYMMDD>.gz

docker compose exec web python manage.py import_cedict data/cedict.txt.gz
docker compose exec web python manage.py import_bkrs data/dabkrs.gz
```

Both commands read `.gz` without unpacking it first and are safe to run twice. Updating a dump
needs `--replace`: without it changed entries are skipped as duplicates and stale ones survive.

Importing BKRS takes a few minutes — there are millions of entries.

---

## How it is built

The architecture is built for extension — personal spaced-repetition vocabulary and statistics
are next — so four rules have applied from day one.

**A feature is a Django app.** They all live in the `apps/` package.

| App | Responsibility |
|---|---|
| `core` | landing page, `base.html`, context processors, limit configuration |
| `accounts` | the user (email sign-in), settings, profile |
| `chinese` | sentences, segmentation, pinyin, tones. No models and no URLs |
| `dictionary` | dictionary entries, dump import, lookup |
| `translation` | translation providers, translation cache |
| `tts` | speech providers, timing alignment, audio cache |
| `reader` | the reading page |
| `shadowing` | the shadowing page |
| `library` | saved texts, collections, reading progress |

**Dependencies point one way.** Features (`reader`, `shadowing`, `library`) depend on
infrastructure (`chinese`, `dictionary`, `translation`, `tts`, `accounts`, `core`) and never on
each other. That is why the reader can open a saved text while knowing nothing about the library:
the title and the status arrive as hidden form fields.

**Logic lives in `services.py` and views stay thin.** A view parses the request, calls a service
and renders. Access rules are in services too, not in templates.

**External APIs are reached only through providers.** An abstract base class, concrete
implementations, and a dotted path in the settings to pick one. No `requests` calls from views.

Two more decisions worth knowing about:

**Everything that costs money is cached in the database.** Translations by sentence hash and
language, audio and timings by sentence hash and voice. A sentence shared by two texts is
therefore translated and spoken once for the whole site, and reopening is free.

**Speech timings are stored as character positions, not word indices.** Words exist only because
jieba segmented them, so a future jieba dictionary would silently move every cached timing onto
the wrong word. Characters do not move, so the mapping onto words is recomputed on every render.

---

## Extending it

### Add a translation language

One line in `config/settings/base.py`:

```python
TRANSLATION_LANGUAGES = {
    "ru": "Русский",
    "en": "English",
    "de": "Deutsch",   # that is all
}
```

No migration: the `language` field is a plain `CharField` **without `choices`** for exactly this
reason. Valid values are checked in forms and services.

### Add a provider

Say Azure instead of `edge-tts`:

```python
# apps/tts/providers/azure.py
class AzureTTSProvider(TTSProvider):
    def synthesize(self, sentences: list[str], voice: str) -> list[Synthesis]:
        ...
```

```bash
# .env
TTS_PROVIDER=apps.tts.providers.azure.AzureTTSProvider
```

No view, service or template changes. Translation works the same way.

### Add a feature

```
apps/your_feature/
├── models.py      # if it needs data of its own
├── services.py    # all the logic
├── views.py       # thin
├── urls.py
└── forms.py
templates/your_feature/
static/css/your_feature.css
tests/your_feature/
```

Then add the app to `LOCAL_APPS` and `include()` it in `config/urls.py`. Take chinese text
processing from `apps.chinese.services` rather than writing it again, so every feature sees the
same analysis.

---

## Commands

Everything runs inside the container.

```bash
docker compose up -d                                  # start
docker compose logs -f web                            # logs and mail
docker compose exec web pytest                        # tests
docker compose exec web pytest tests/chinese -v       # one app's tests
docker compose exec web ruff check .                  # linter
docker compose exec web ruff format .                 # formatter
docker compose down                                   # stop
```

Clearing a cache is what you do when it holds results you no longer trust. A cache hit never
reaches the provider, so they will not refresh themselves:

```bash
# Stubs accumulated while working without a DeepL key.
docker compose exec web python manage.py clear_translation_cache --provider DummyProvider

# Speech: everything, or by provider, or by voice. Files are deleted along with the rows.
docker compose exec web python manage.py clear_audio_cache
docker compose exec web python manage.py clear_audio_cache --voice zh-CN-XiaoxiaoNeural
```

If you run into your own hourly limit while testing — the counters live in process memory:

```bash
docker compose restart web
```

---

## Limitations and what production would need

This is a learning and portfolio project. Its local environment is honest; a production one does
not exist. What a real deployment would take:

**There is no mail.** `EMAIL_BACKEND` prints messages to the container log, while address
confirmation is mandatory — without it the higher limit would be handed out for an invented
address. An SMTP server or a mail service is needed.

**Limit counters live in process memory.** `LocMemCache` means a restart resets every limit and
each worker counts its own. A shared cache is needed — Redis or Memcached.

**Hourly limits do not guard a monthly budget.** DeepL Free allows 500,000 characters a month
while the limits count requests per hour. A global character counter is needed.

**`media/` is not a named volume.** The speech cache lives there, and recreating the container
wipes it. A volume or S3 is needed.

**`edge-tts` is unofficial.** It speaks to the endpoint Edge uses to read pages aloud: the voices
and the timings are the ones Azure sells, but nobody promised them to us, and it answers 503 from
time to time. That is acceptable here because everything is cached, so an outage costs one text's
first open. A real service would move to Azure, which is one new provider class.

**Google sign-in and other people's addresses.** `SOCIALACCOUNT_EMAIL_AUTHENTICATION` is on, so
somebody who registered with a password can later sign in through Google with the same address.
That is safe exactly as long as there is one provider and it is Google, which does not lie about
whether an address is verified. A second provider means revisiting the decision.

**Production settings.** `config/settings/prod.py` exists but has never been run in anger: it
needs `DEBUG=False`, real `ALLOWED_HOSTS`, HTTPS, static files served by nginx, and rate limiting
at the proxy — the hourly limit guards the translation budget, not the load.

---

## Dictionary licences

**CC-CEDICT** — CC BY-SA 4.0. Attribution is required and is in the site footer.

**BKRS** — the owners state: "The databases may be used freely for any purpose. You may cite this
site as the source" ([bkrs.info/p47](https://bkrs.info/p47)). That is an explicit permission
rather than a formal OSI licence; the attribution sits in the footer as well. Commercial use is
worth an email to them.
