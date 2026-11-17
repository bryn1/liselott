# Liselotts bokhylla

A Swedish-language personal book diary for exactly one writer (Liselott):
she adds the books she reads, grades them 1–5, searches her own
library, and gets recommendations derived only from her own books and grades —
a real cover on a shelf card wherever one has been found, a calm fix-me
placeholder wherever it has not, with the cover waves still running (the
measured share lives in the Status snapshot and Known limits below, never in
this line). **The PUBLIC SET is public** (owner ruling 2026-11-14, web chat,
verbatim: "Rated books and their ratings as well as whishlist shall be
public. The rest behind password" — narrowing the same-day earlier claim of
MC 12497, the newer ruling binding): the shelf filtered to it (rated books
with their stars, plus the wishlist) — narrowable by the public reader's own
filter row (MC 12551: score, read year, and a title/author search, always over
those SAME public rows and never beyond them), the bok pages and covers of
public-set ids, and the landing — which since MC 12522 OPENS that public shelf
instead of only pointing at a login door — answer any anonymous visitor on a
configured site; everything else — the unfiltered shelf, search, recommendations, and
every write (grading, wishing, adding, editing, deleting, the machine doors,
backups, rapporter) — stays behind her one password. It is built to be
served at `https://sibbamala.com/liselott` on the fleet's auto lane. The
build contract is `PLAN-c3` (the pinned plan); this README states what the
tree actually is.

## Status snapshot — re-measured 2026-11-14 against HEAD (sec-wave p2, MC 12497)

- Build milestones M0–M7 are done and committed, and **the publish (plan
  milestone M8) HAS RUN**: `bryn1/liselott` exists on GitHub with visibility
  **PUBLIC** (`gh repo view`, re-measured 2026-11-14) and the app **serves at
  `https://sibbamala.com/liselott`** — `/` 200 (re-checked by curl GET
  2026-11-14); `/logga-in` 200, `/healthz` 200 `ok`, `/satt-loesenord` 404
  (the owner's password is set, as designed), quarantined names 404 (the
  full GET matrix measured at the publish, 2026-11-13 — the site is in use,
  so a later wave re-fetches `/` only). What the
  publish took — staging-gate landing, static in the closed state,
  quarantine 404s, the live-500 cachebust fix, the setup-window reopens —
  is LEDGER rows, not this snapshot's fine print.
- **MC 12497 public-read wave (2026-11-14; its WHOLE-site read scope is
  SUPERSEDED the same day by MC 12501 below — this bullet stands as the
  trail of what that wave fixed beside the scope):** the write posture it
  pinned stands unchanged — every write keeps the guard's non-2xx refuse,
  the setup-state exception holds (no password set → the choose-password
  gate wraps the whole site as before), the owner write UI (betyg form,
  "Omslag saknas — fixa", "Visa inte igen") paints only in her session.
  **The live site still runs the pre-wave code until the orchestrator
  re-publishes; flipping live behaviour is that act, not this tree's.**
- **MC 12501 public-scope narrowing (2026-11-14, re-measured against HEAD
  the same day):** OWNER RULING (web chat, verbatim): "Rated books and
  their ratings as well as whishlist shall be public. The rest behind
  password". The anonymous read surface is the PUBLIC SET — rated books
  with their stars, exactly as the owner sees them, plus the wishlist
  (`app/auth.py::PUBLIC_READ_PATHS` carries `/` and `/bibliotek` only;
  `app/books.py::PUBLIC_SET_SQL` is the ONE filter the shelf/bok/cover
  fetches apply). `/sok` and `/rekommendationer` answer the guard's 302 to
  `/logga-in` again; a private `/bok/<id>` or `/cover/<id>` answers the
  SAME 302 a nonexistent id does (id-enumeration learns nothing, VERIFIED
  by equal-status-and-Location legs); the owner's own view is unfiltered
  everywhere, zero visible change when she is logged in. `robots.txt`
  stays state-dependent (`Allow: /` on the configured site, `Disallow: /`
  while it is still wrapped). **The live site still answers the pre-wave
  code until the orchestrator re-publishes.**
- **MC 12522 public entrance (2026-11-14, re-measured against HEAD the same
  day):** OWNER REPORT (web chat, verbatim): "I want you to do a browser test
  of the live website sibbamala.com/liselott. I only get to thr logga in page."
  Measured cause: the anonymous landing rendered its intro copy and one
  "Logga in" link and nothing else — the public shelf `/bibliotek` serves had
  NO path from the landing, so the public promise was unreachable from the door
  the owner actually opens. The cure is reuse, not a mechanism: the anonymous
  branch of `rot()` hands the landing `_hyllgrupper()` — the SAME read
  `/bibliotek` serves (`books.load_books(public_only=True)` under the ONE
  filter `PUBLIC_SET_SQL`) — and `templates/start.html` includes
  `templates/_hyllan.html`, the SAME shelf markup `/bibliotek` includes
  (extracted, never copied: one card, one meaning). `app/auth.py` is
  byte-identical (the root leg is MC 12451's, untouched); the logged-in landing
  is byte-identical MEASURED (HEAD~1's tree and this one rendered through one
  script on identical scratch DBs — every page this card did not change answers
  byte for byte the same, seeded and empty states alike); the door stays as the
  landing's small
  footer line; the WRAPPED setup state still shows no shelf (no password → no
  public). Tests: 8 new legs in `tests/test_public_landing.py` (entrance, card
  links identical to `/bibliotek`'s, synthetic private rows absent by
  title/author/year/id, the owner's landing unchanged, the door, the setup
  state, the empty public shelf, corpus-scale private absence) and the
  corpus-scale absence sweep in
  `tests/test_no_leak.py` now runs over the landing too; three planted-RED
  transcripts (entrance removed / unfiltered read / door removed). Suite:
  547 → **555 passed, exit 0** (the counts live in the Status snapshot below).
  **The live site still answers the pre-wave code until the orchestrator
  re-publishes.**
- **SEC-WAVE p2 — security fixes (MC 12497, 2026-11-14):** the five findings of
  the security gate `.audits/20261112-phase2/out/SEC-verdict-12497.md` are
  cured in this tree — one commit each: HEAD never executes a state change
  (POST is the only processing method on the three lifecycle views, and the
  CSRF gate's same-origin rule now checks HEAD — F-1); ids beyond sqlite's
  signed-64-bit domain answer the route's own 404 on /bok and /cover, never
  the bind's 500 (F-2); a trailing slash on a public read is the same page in
  place — guard match extended and one explicit rule per spelling, no redirect
  mechanism (werkzeug 3.1 has no slash-redirect; F-3); the §6.2 bucket keys on
  CF-Connecting-IP else the socket peer, `X-Forwarded-For` never trusted at
  the origin, and the uvicorn entry runs `proxy_headers=False` (F-4); the
  extension-less `.git` namespace answers the bare `.git`'s 404 and
  owner-painted HTML carries `Cache-Control: no-store` beside its
  `Vary: Cookie` (F-5). Carried P4s, documented NOT fixed: the CSRF-400
  fingerprint on anonymous state-method attempts at allow-listed paths, and
  the app-level body cap behind the edge caps. Live STILL answers the
  pre-wave code (re-measured this session: the overflow GET answers 500
  live, one read-only request) — flipping live behaviour is the re-publish,
  not this tree.
- The full offline test suite passes: **555 passed, exit 0**
  (`.venv/bin/pytest -q`, VM350 build clone, re-run 2026-11-14 at MC 12522 —
  the +8 legs over the prior 547 are `tests/test_public_landing.py`: the
  public entrance, its card-link equality with `/bibliotek`, the synthetic
  private-row absence, the owner's unchanged landing, the door, the wrapped
  setup state, the empty public shelf and one corpus-scale absence leg) and
  **520 passed, 35 skipped, exit 0** in a clean clone without her personal export (`git archive`
  of the tree; the corpus legs skip
  by name, never silently (MC 12451 c5; MC 12522 added one corpus leg and
  seven that run in any clone)).
- The build database holds **724 books** (706 read + 18 wishlist), **671** with
  an ISBN (parse: `isbn13` non-empty), **6** rated, **52** ljudbok, and a
  recommendation candidate pool of **284** authors' works
  (`sqlite3 /home/claudecode/liselott-build/liselott.db`, re-measured
  2026-11-14 — unchanged from 2026-11-13).
- Covers: the build DB held **74 of 724** at T9.1 time (27 owner-chosen via
  upload/URL; 47 marked `enrich_fail=1` — no provider had one; the count
  moved 72→74 while that snapshot was written, a second bounded cover wave
  running). Production serves **80 covers of 724** — orchestrator-measured
  through the rapport door during the M8 run. The authority for any live
  count is `GET /rapa/omslag-rapport`, owner-session behind the login.

## För Liselott — så här använder du boken

**Logga in.** Öppna sidan (länken får du av orchestratorn,
`sibbamala.com/liselott`) och skriv ditt lösenord. Inget annat än lösenordet
behövs — det finns inget användarnamn.

**Alla kan läsa.** Sedan den 14 november 2026 är sajten publik: hyllan,
boksidorna, sök, rekommendationer, omslag och stjärnor syns för alla utan
lösenord — och det som står som anteckning på en bok sida visas då för alla.
Endast du kan skriva: betygsätta, önska, lägga till, redigera och ta bort
kräver ditt lösenord.

**Första lösenordet.** När appen startas för första gången är ett fönster öppet
i 20 minuter: då sätter du ditt lösenord (minst 10 tecken). Fönstret stängs för
gott när lösenordet är sparat — och när du kommer in är du redan inloggad.
Missar du fönstret är det inte farligt: en omstart av appen öppnar det igen
(orchestratorn gör det på några minuter).

**Betygsätt.** Öppna en bok och sätt 1–5 stjärnor (heltal, inga halva). Med
fem stjärnor föreslår boken mer av samma författare — därför lönar det sig att
betygsätta sina favoriter.

**Sök.** Sökfältet hittar böcker på fem vägar: ISBN (10 eller 13 siffror,
bindestreck är ok), titel, författare, årtal (t.ex. `2024`) och genre
(t.ex. `kriminalitet`). Bokstäverna å, ä, ö räknas som a och o i sökningen, så
`Ahrstedt` hittar `Åhrstedt` oavsett bockar.

**Lägg till en bok.** "Lägg till" räcker med titel (författare valfritt). Appen
får boken att direkt försöka hitta omslag och ISBN från Libris, Open Library
och Google Books.

**Fixa ett omslag.** Saknar en bok omslag syns "Omslag saknas — fixa" på
boksidan. Där kan du (1) prova "Hämta omslag" igen, (2) **ladda upp** en egen
bild — den förminskas på din egen dator innan den skickas, så stora bilder är
helt okej, eller (3) **klistra in en webbadress**: "hitta omslag" hämtar
omslagsbilden från vilken sida som helst (t.ex. ett förlags bokpresentation).
Alla böcker utan omslag samlas i en lista under "Saknade omslag" där du kan
fixa dem ett åt gången. (Eget uppladdat eller inskickat omslag skrivs aldrig
över av systemet.)

**Önskelistan.** Böcker du vill läsa ligger under "Önskelista". När du läser en
önskbok markerar du den som läst, då hamnar den i hyllan.

**Rekommendationer.** "Rekommendationer" visar de 12 bästa förslagen utifrån
dina egna betyg — varje kort förklarar varför ("För att du gav …").
"Visa inte igen" tar bort ett förslag för alltid.

**Byt lösenord.** Under "Byt lösenord" (kräver nuvarande lösenord). OBS: alla
inloggningar, även din egen, loggas ut vid bytet — logga in med det nya.

**Redigera eller radera en bok.** Det som ändrar en bok — titel, författare,
utgivningsår, format, läst-datum, ISBN, anteckningar, omslag och själva
borttagningen — finns på redigeringssidan, `…/redigera/<bok-id>`. Boksidan har
idag bara en länk dit, och den syns bara när omslag saknas: "**Omslag saknas —
fixa**". (I listan "Saknade omslag", under Rapporter, heter länken "Ladda upp
bild" och går till samma ställe.) Har boken ett omslag finns **ingen** synlig
länk dit alls — då når du dit genom att skriva adressen. Det är en känd brist,
inte meningen, och den gäller alla böcker som redan har ett omslag. Själva
betygsättningen går alltid direkt på boksidan: stjärnorna och "Spara betyg",
även på en bok med omslag. Längst ner på redigeringssidan står "Ta bort boken" —
knappen är sin egen bekräftelse, ett klick tar bort boken direkt.

## For maintainers

### Run it (dev)

```bash
cd /home/claudecode/liselott
virtualenv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
LISELOTT_ENV=dev PORT=8166 .venv/bin/python server.py   # bind $PORT, no fallback
```

`virtualenv` (21.7.1) is the VM350-proven path — measured this session:
`python3 -m venv` FAILS there ("ensurepip is not available", python3.10
without the python3.10-venv package) and `virtualenv` creates the working
3.10.12 venv verbatim; it is also what built the repo's own `.venv`. On a
Debian box with `python3.10-venv` installed, `python3 -m venv` works too.

Then `http://127.0.0.1:8166/liselott/` — first boot within 20 min shows the
set-password page; both request shapes (bare `/…` and `/liselott/…`) route.
Tests: `cd /home/claudecode/liselott && .venv/bin/pytest -q` (offline, no
provider network; **577 passed, exit 0** at this commit on the VM350 build
clone — see Suite-location rule).

### Suite-location rule (corpus cases, path F — MC 12451 c5; two-case cut MC 12523)

The corpus-dependent tests (T1.2/T1.5/T1.6/T1.7/T2.6/T4.3) are **case-
parametrized, not skipped**: the `synthetic` case runs EVERYWHERE on the
committed `tests/fixtures/synthetic_seed.md` (invented Swedish-shaped rows
carrying the same parse shapes, sha/digest/count-pinned at landing), and the
`personal` case is ADDED wherever path F resolves the personal export — the
ONE locator lives in `tests/conftest.py` (`LISELOTT_SEED_FILE` wins, else
`data-import/seed-books-raw.md`, gitignored). Where the export resolves every
personal pin holds unchanged (file sha256, 725/724/1, dedupe tie-break, drift
digest, leak-matrix scale floors); a corpus with the wrong sha FAILS the
pinned-sha leg and a `LISELOTT_SEED_FILE` naming no file ERRORS (misconfig is
not absence). A clean clone runs the synthetic half for real — zero skips on
the behaviour legs; the only skip left is `test_no_diary_in_git` leg 2, whose
subject IS the personal export (a guard grepping the real corpus's titles
proves nothing without it, and it skips with a loud reason). Measured at this
commit: **577 passed, 0 skipped, exit 0** on the VM350 build clone; from a
clean `git archive` clone **557 passed, 1 skipped, exit 0** — the single skip
is `test_no_diary_in_git` leg 2 (its subject IS the export). The 33 old corpus
skips are gone: their shape-work now runs synthetic in every clone.

`tests/test_backup.sh` keeps its fail-loudly posture on purpose: it is the §11
round-trip runbook a human runs by hand, not a collected pytest leg, and a
silent skip there would be the vacuous-green defect class §13 named.

> **SUPERSEDED (2026-11-14, MC 12451 c5) — the old PLAN-c3 §13 rule, verbatim,
> DO NOT USE:** "Missing file → those tests FAIL (assert loudly) — a
> `pytest.skip` is FORBIDDEN. 'Full suite green' is legitimately run ONLY on the
> VM350 build clone." It made the suite runnable only on the one host already
> holding her personal data, which fails the clean-environment contract and
> blocked any verifier (knut) from ever PASSing a commit-bound card on this repo.

### Sealed-shape pre-push smoke (MC 12533)

```bash
scripts/sealed_smoke.sh [SHA]   # default HEAD; KEEP=1 keeps the remote tree
```

Run it for ANY commit touching `tests/conftest.py` or the file-posture of
`app/seed.py` (the MC 12526/12532 class: `is_file()` vs a mode-000 masked
`/home` = EACCES passed five manual green runs on two hosts and was caught
ONLY by knut's sealed lane), and before any session's first push. The smoke
applies THAT seal from the build host in ~2 min: `git archive` of the SHA
into `vm100:/var/tmp/sealed-smoke/<sha8>` (never `/tmp` — the sealed unit is
`PrivateTmp=yes`), a non-sealed pip fetch unit (the seal denies the network
the fetch needs), then `systemd-run --wait --collect --pipe` with the flag
list copied VERBATIM from `vm100:/opt/knut/bin/sandbox.py` `verify_argv`
(source + date named in the script's comment; flags are literals, nothing is
parsed off vm100 at run time). The sealed pytest exit is the script's exit
and the run-log tail is the answer. Measured at landing: HEAD **558 passed,
2 skipped, exit 0** (107 s on vm100); the bug commit 2dbeed7 **48 failed,
491 passed, 1 skipped, 18 errors**, exit 1 — the gate's red case IS the
historical bug, not a planted one.

Honest limit: the flag list is a MIRROR of vm100's seal — if the seal
changes, the mirror goes stale; refresh the literals from `sandbox.py`.
It is a smoke, not the verifier: knut's sealed lane stays the authority
that gates every push.

### Environment (exhaustive)

| variable | meaning |
|---|---|
| `PORT` | the port `server.py` binds (set by the lane unit; no fallback) |
| `HOME` | set by the lane unit to the app's StateDirectory (production) |
| `LISELOTT_PREFIX` | mount prefix for emitted URLs; default `/liselott` — correct in production with nothing set |
| `LISELOTT_DATA_DIR` | data-dir override — dev/test/build use only |
| `LISELOTT_BACKUP_DIR` | where `scripts/backup.sh` writes its pairs; default `$HOME/liselott-backups` (§11). `GET /backup` never writes here — it streams from a temp dir |
| `LISELOTT_ENV=dev` | local/test only — turns the session cookie's `Secure` flag off; UNSET means production (Secure ON, debug OFF) |
| `AI_REC_DOOR_TOKEN` | MC 12597 — the dedicated credential of the `/ai-rek` AI-recommendation door — the `POST /ai-rek` ingest and its `GET /ai-rek/library-keys` read face (MC 12643) alike (header `X-Ai-Rek-Token`, constant-time compare), and the **64-hex requirement ON THE VALUE**: unset, empty or malformed = the door is DISARMED — 503 for every POST, fail-closed, the owner's session included (a malformed env is never a weaker door; `openssl rand -hex 32` is the shape). Rotation = set the new value + restart the door. Liselott's site password is never involved. Read per request by `app/ai_rek.py`, never by any other route |
| `LISELOTT_SEED_FILE` | test suite ONLY (MC 12451 c5) — points at the personal seed export so the `personal` corpus CASE runs; unset, the locator falls back to `data-import/seed-books-raw.md`; with neither, only the synthetic cases run. The app never reads it |
| `LISELOTT_ALIASES_FILE` | MC 12523 — the personal author-alias CSV (off-repo state data, `canonical,alias` rows); default `/home/claudecode/liselott-data/author_aliases.csv`; ABSENT = no aliases (clean no-op, tested). Read by the importer CLI, the /bundle door and the add/edit doors through `app/seed.py` |
| `LISELOTT_OVERRIDE_FILE` | MC 12523 — the personal date-override CSV (`exact title,ISO-date` rows); default `/home/claudecode/liselott-data/import_overrides.csv`; ABSENT = no date fixes (clean no-op, tested). Same readers |
| `LISELOTT_REAL_TITLES` / `LISELOTT_REAL_ISBNS` | `scripts/exposure_check.py` ONLY (MC 12523) — the off-repo personal lists the public-repo gate greps for; defaults `/home/claudecode/liselott-data/real-titles.txt` / `real-isbns.txt`. The app never reads them |
| `FIRECRAWL_SEARCH_URL` | the S12 cover pass ONLY (`scripts/cover_pass.py`, MC 12466) — the search endpoint it asks for candidate pages; default `http://192.168.5.20:3002/v1/search` (firecrawl on noa). The app never reads it |
| `DESCRIBE_IMAGE_ENDPOINT` | the S12 cover pass ONLY — the chat-completions endpoint its vision gate (verbatim transcription check) calls; default `http://192.168.5.223:8888/v1/chat/completions`. The app never reads it |
| `DESCRIBE_IMAGE_MODEL` | the S12 cover pass ONLY — the model the vision gate asks to report the cover's printed words; default `qwen3.8-flash-next`. The app never reads it |

**Production needs zero custom env.** The lane unit sets only `HOME` and `PORT`;
everything else falls out of the defaults above.

**`PRIS_DOOR_TOKEN` is RETIRED (MC 12606, M11-N4b)** and belongs to no row of
that table any more: the owner ruled the price feature away — "Books on sale
can be removed. No interest in buying books." — so `POST /pris`, its door
credential and its `X-Pris-Token` header are gone from the code, and
`/pris` is now an ordinary unknown path (anonymous 302 to the login page,
owner 404). Nothing in this tree reads that env name; a host unit or env file
that still exports it is INERT, and the teardown of the vm106 side (the
pris-vakt unit/timer and its 0600 token file) is the orchestrator's follow-up
row, named in the LEDGER.

### Where the data lives

`app/db.py::state_base()` picks the first writable of: `$LISELOTT_DATA_DIR`
(dev/test/build), then `$HOME/liselott-state` (production:
`/var/lib/vm106-app-liselott/liselott-state`, the lane StateDirectory — the
only writable path under its `ProtectSystem=strict`), then `./data`. None
writable → the process exits "refusing to start" rather than half-start.
Inside the data dir: `liselott.db` (SQLite, WAL), `covers/<book_id>.jpg`,
`secret.key` (0600, first boot), `enrich_report.json`. The build run uses
`LISELOTT_DATA_DIR=/home/claudecode/liselott-build`. The whole diary is thus
two things: one SQLite file and one directory of JPEGs.

### The public set is public, the rest behind the password (MC 12501, owner ruling 2026-11-14 — narrowing MC 12497 the same day)

The guard (`app/auth.py::_auth_gate`) answers in three states, measured in
`tests/test_guard.py`, `tests/test_public_read.py` and (over the corpus)
`tests/test_no_leak.py`:

- **Configured site, anonymous reads:** the guard opens `/` (since MC 12522 the
  landing IS the entrance: intro copy + the public shelf under it, one small
  "Logga in" door as the footer — the private half stays out of the body by the
  same ONE filter), `/bibliotek`, `/bok/<id>`,
  `/cover/<id>`, `/healthz`, `/robots.txt`, `/static/*` — and the data
  layer (the ONE filter, `app/books.py::PUBLIC_SET_SQL`:
  `rating IS NOT NULL OR status <> 'read'`) decides WHAT those pages may
  paint: the shelf shows the public set only — rated books with their
  stars and the wishlist section — and an unrated book appears NOWHERE in
  an anonymous response (no title, no private-only author, no year-section
  only they populated, no id link: the corpus-scale absence legs grep all
  700 unrated corpus titles out of the shelf body). The free-text note
  field is NOT public — owner-only by the ruling's "The rest behind
  password" clause (F-1 cure, 2026-11-14): `load_books(public_only=…)`
  projects `notes` as NULL in the ONE public projection, so no public page
  paints a note and no template can (the "Läst" date stays public — it
  rides the rated-book card by design). `/bok/<id>` and
  `/cover/<id>` answer 200 for public-set ids; any other id — private or
  nonexistent alike, overflow ids included — meets the guard's uniform 302
  to `/logga-in`, identical in status AND Location, so id-enumeration
  learns nothing. `/sok` and `/rekommendationer` are NOT public: same
  uniform 302. A public page carries no owner door (no edit link, no byt
  lösenord, no logga-ut, no betyg widget, no "Visa inte igen") and never
  sets a session cookie. `robots.txt` says `Allow: /` here — the site
  publishes its public set (the private half is unreachable to a crawler
  regardless of what the file says).
- **RETIRED — the wishlist's price line** (M9a, MC 12542/12546; retired by
  MC 12606, M11-N4b, owner rulings 2026-11-16 verbatim: "Books on sale can be
  removed. No interest in buying books." and the older "rea, om inte nu så
  sen"). The price line and the `REA` badge are OFF the cards: the "Att läsa"
  rows and the owner's `/onska` rows carry title, author, format and stars —
  no price, no "Lägsta pris på 90 dagar", no "pris kollat" date, no Bokus
  link. The ruling kept the wishlist ITSELF whole (every wish still renders,
  public and owner alike) and kept the stored history: the `price` table and
  its columns stay in `app/schema.sql` behind a RETIRED comment, with NO
  destructive migration and no `DROP`. What the card below this one used to
  describe is now a claim with no implementation; `tests/test_pris_retired.py`
  pins the opposite — the wishlist page carries ZERO bytes matching
  `streckpris|rea|lägga|pris|90 dagar` (case-insensitive) for the owner AND
  the anonymous reader, even with a price row planted in the kept table.
- **Configured site, the public reader's filters** (MC 12551, owner
  2026-11-15, verbatim: "The public page needs filter by score, year, search by
  author, title and year"): above `/bibliotek` the anonymous reader gets ONE
  calm GET-form row — a `betyg` select (1–5), an `ar` select carrying the years
  the PUBLIC shelf actually populated, and a `q` box that searches TITLE OR
  AUTHOR (`app/templates/_publik-filtrering.html`, plain HTML, no JavaScript,
  the existing design tokens). `app/filtrering.py` owns the rules: the params
  combine with AND, a bad value is the ABSENT value (the calm public shelf,
  never a 500), and every narrowing is a SUBTRACTION from the rows the ONE
  public filter already returned — the module runs no query of its own, not
  even for the year list the form offers, so a filtered page can never be
  wider than the public set. `ar` is the shelf's own year (the `read_year` the
  section heading shows, `books.shelf_year`); `q` folds case and diacritics
  (§7's `app/text.py::fold`) over rows already in hand and is NOT a SQL LIKE —
  `%`, `_`, `*`, `?`, a quote and the word ESCAPE are ordinary characters,
  which is exactly why a wildcard needle answers "Inga träffar". The wishlist
  is narrowed by `q` ONLY: it carries neither rating nor read year, so no
  `betyg`/`ar` param speaks for it. The OWNER is never filtered (her params are
  inert) and the landing carries no form row — both render the bytes they had
  before the filters existed, pinned by `tests/test_public_filter.py`. Public
  stays exactly the ruling's list — rated books, the wishlist (without the
  price line MC 12606 retired) and PUBLIC FILTERING over those
  rows; NOTHING else becomes public.
- **Configured site, anonymous writes:** every POST stays the guard's 302 to
  `/logga-in` (the `/satt-loesenord` door answers its §6.1 404) — including
  POSTs aimed at the READ paths: the method rule in `_is_public_read` is what
  makes "public to read" not mean "public to write". The ONE named exception
  is `POST /ai-rek` (M11, MC 12597):
  the guard lets that POST method reach its door, which then answers
  with its OWN dedicated door credential
  (503 disarmed / 401 wrong key, see *Machine routes*) — never a session,
  never the site password; every other method on `/ai-rek` keeps
  the uniform 302. MC 12643 (owner ruling "A") adds the door's READ face,
  GET `/ai-rek/library-keys`: the guard lets THAT path through only with the
  `X-Ai-Rek-Token` header RIDING (presence opens the way, correctness is
  answered in the door), so its no-header face is the same uniform 302 —
  nothing joins the public read surface. (MC 12606 retired the second exception this paragraph
  named, `POST /pris`; `/pris` is not a door any more and keeps the uniform
  302 like every other path.) Owner surfaces —
  `/onska`, `/lagg-till`, `/redigera/<id>`, `/rapa/*`, `/backup`,
  `/byter-losenord`, `/logga-ut` and the machine doors `/seed`, `/bundle`,
  `/backfill` — stay behind her session, as do search and
  recommendations.
- **Configured site, the owner:** she sees EVERYTHING unfiltered,
  everywhere — the full shelf including every unrated row, search, recs,
  her pages in every slash spelling. The narrowing changed nothing in her
  view.
- **No password set (the setup-state exception):** everything above reverts
  to the §6.1 wrap — every data route redirects to `/satt-loesenord`,
  `robots.txt` says `Disallow: /` (an inviting one would point crawlers at a
  setup door), the landing keeps its single setup door. The public set is a
  property of the CONFIGURED site only. The closed window 404s `robots.txt`
  and serves the pinned gate page everywhere else, as before.

Quarantines are untouched in every state: `/liselott.db`, `/VERSION`, state
paths and other mirror-dropped names answer the guard's 404; extension-less
unknowns keep the uniform 302 (T2.6). `tests/test_backup.sh`'s
`GET /backup` door is still session-gated.

### CODE-ONLY repo (the P0-1 rule)

Per the fleet convention this repo copies from `bryn1/fest40`: *CODE ONLY —
site content enters via POST /seed into the host state dir, never git.* The raw
seed file (`data-import/seed-books-raw.md`, sha256
`420259164605b1b9e221e4e9fc8b6f5f98676f0c4bc9e4f6c02e6e5555ec24dc`, re-measured
2026-11-13 and matching the plan pin) and every whole-corpus artifact are
gitignored and have never been committed; the transfer bundle lives outside git
at `/home/claudecode/liselott-bundle/`.

**The tracked fixtures are synthetic (MC 12523).** They used to carry real
diary content — the 18 T1.3 parse goldens in `tests/test_seed_rows.py`, five
recorded provider fixtures (real titles in their filenames too), a few
`app/` comment lines and one CSV row — a state the LEDGER's c2/c4 rows and
the P2-3 history in MC 12440 describe, measured 2026-11-14 at `97911ce` with
the guard's own leg-2 parse: **36 tracked files then held ≥1 whole diary
title** (18 in `test_seed_rows.py`, every other file 1–6). MC 12523 replaced
all of it with Swedish-shaped synthetic titles, authors and check-valid
synthetic ISBNs (e.g. the `978-91-7371-…` block): fixtures, goldens and the
committed synthetic corpus `tests/fixtures/synthetic_seed.md` name nothing
real, and every earlier row that quoted a real title now reads generically —
"raden omnämner verliga titlar — borttagna ur publisert material av MC 12523;
spåret på MC 12440" — the row's claim stands, only its quoted strings left.
The two personal CSVs that used to sit in `data-import/`
(`author_aliases.csv`, `import_overrides.csv`) are OFF-REPO state data now —
removed from git by this card, read through ONE resolver each
(`app/seed.py::aliases_file()/overrides_file()`; `LISELOTT_ALIASES_FILE` /
`LISELOTT_OVERRIDE_FILE` win, else `/home/claudecode/liselott-data/<name>.csv`
on the app host). An absent file is a clean no-op: no aliases, no date fixes,
every row still imports (both halves pinned by tests). Two honest caveats:
**git history keeps the old blobs** — this repo is public, and a history
rewrite is a separate OWNER decision, not taken here; new clones and the
current tree are clean. And a whole-title *substring* instrument has a
word-shape artifact class (one four-letter diary title is a substring of the
robots.txt directive "Disallow" — named here only as a class, not as the
word) — `scripts/exposure_check.py` is the standing measurement: it reads the
personal title/ISBN lists from OUTSIDE the repo (never committed), runs
`git grep -F -w` over the tracked universe, prints ONE number — the count of
tracked files holding ≥1 real diary string — and exits 0 only at zero. It
measured **0 (exit 0)** at this commit; its red-proof (a planted real-title
file in a throwaway archive-export repo, red then green, real tree untouched)
is in the landing transcript `.audits/20261114-mc12523/planted-red.md`
(host-local, MC-linked). P2-3 is **RESOLVED** by the owner's ruling MC 12523,
verbatim: "Do rec for p2-p3".

`tests/test_no_diary_in_git.py` guards this posture in every checkout form:
leg 2 fails a tracked file at ≥20 whole PERSONAL-corpus titles, leg 1 at ≥100
seed-entry shape lines, and leg 3 keeps the raw export, `golden_parse.json`
and any `seed-bundle*` out of every entry of the tree — the bulk claim (the
raw export never in git) has held since T1.8 and holds now.

**Stale seed header:** the raw seed file's header prose (lines 1–7) is parsed
nowhere and carries two false claims (it says no grades exist — 6 rating rows
do; it advertises a date-suffix form — no row uses it; the real form is a
LEADING `YYMMDD` token, 45 rows). Trust the plan's §5 rules, never the header.

## Machine routes (behind the owner session — `/ai-rek` behind its own door token, MC 12597; `/pris` retired by MC 12606)

- `POST /seed` — the raw markdown in, `parsed=725 stored=724 duplicates=1` out
  (the loader/CLI pins the `parsed`/`duplicates` triple; the door's own legs
  assert shape and the `stored=` delta, not this whole-table triple).
  Idempotent. `stored=` is the rows **that POST**
  stored, so a re-POST of the same file answers `stored=0` (nothing new landed —
  that is the idempotence proof, not a failure); the CLI's counts line keeps
  §5.9's audited meaning, the WHOLE table (724 on a fresh import, 724 again on
  a re-run, and it names which is which on stderr when the two differ).
- `POST /bundle` — request body ≤ 900 000 bytes (`MAX_BUNDLE_CHUNK`, ≈14 %
  margin under the lane's measured ≈1 MiB edge), answered with a named 400;
  `POST /seed` owns a SEPARATE budget, `MAX_SEED_BODY` = 1 048 576 B (1 MiB),
  answered with a named 413 (`app/bundle.py`). Two budgets ship, one per door —
  not one for every transfer. Both doors count the BODY's bytes, not the shape
  inside them: the `/bundle` door has no per-line limit — a single
  800 080-byte newline-JSON line POSTs and INSERTs (re-measured in-process
  2026-11-14; DA-verdict-c2 F-6a got 800 249 B through the same door). The
  ≤ 400 KB figure is the SHIPPERS' line budget, not a door rule; the two
  scripts below own it. Matches rows by `book_key` (the shared hash in
  `app/seed.py`), fills ONLY empty ISBN/year/genre holes and absent covers,
  never changes status/dates/notes, never overwrites a manual or URL-chosen
  cover. Re-POST is a no-op. The chunk set is regenerated, never quoted:
  `scripts/export_bundle.py` + `scripts/chunk_bundle.py --max-bytes 900000`
  split the export at line boundaries (byte-concat equals the bundle exactly
  and the sha256 is printed); both carry `LINE_BUDGET = 400_000` and write
  NOTHING when a row exceeds it, and `tests/test_bundle.py` pins every line of
  the exported bundle under it — that is who keeps lines ≤ 400 KB, never the
  door. §5.9's runbook re-exports + re-chunks immediately before publishing so
  every cover won since the last export travels. Dated snapshot 2026-11-14: a
  724-line export of 2 765 194 B in 4 chunks — 856 873 / 889 325 / 879 626 /
  139 370 B, each ≤ 900 000.
- **RETIRED — `POST /pris`, the price door** (M9a-1/M9a-1b, MC 12542/12546;
  deleted by MC 12606, M11-N4b, on the owner's ruling "Books on sale can be
  removed. No interest in buying books."). The route, `app/pris.py`, its read
  model `app/priskort.py`, the `PRIS_DOOR_TOKEN`/`X-Pris-Token` credential and
  the guard's POST-method door allow are ALL OUT of the tree: `/pris` is now
  answered by the guard before routing, exactly like any other unknown path
  (anonymous 302 to `/logga-in` in status AND Location, owner 404), and the
  env name is inert. Everything this bullet documented — the row contract, the
  day-dedup index, the counters, the 60% `suspect` flag, the 2-day backdate
  residual — is history, carried by the LEDGER rows of MC 12542/12546/12547/
  MC 12549 and by git, not by code. The `/ai-rek` door below (POST + its
  MC 12643 read face) is now the ONLY door-token machine route standing.
- `POST /ai-rek` (M11, MC 12597) — the AI-recommendation ingest door. A JSON
  array of `{title, author_name, isbn13, year, reason, source, fit, kategori}`
  in, the six counters (`accepted`, `inserted`, `updated`, `kept_accept`,
  `kept_decline`, `rejected_shape`) out, zero book data echoed. `fit` is a
  finite number in [0,1] (the table CHECKs it too) and `kategori` is `nyhet`,
  `klassiker` or `blandad`. The upsert matches the WHOLE book identity — the
  UNIQUE `rec_key`, the isbn, and the §5.3 normalized title+author key (the
  shared `app/onska.py::wish_key` chain) — and NEVER overwrites or resurrects
  a row in state `accept`/`decline` (a decided book stays decided however it
  is re-spelled); the INSERT is `ON CONFLICT DO NOTHING` + re-ask, so two
  concurrent POSTs land one row, never an error. Body ≤ `MAX_AI_REK_BODY` =
  262 144 B (named 413) and ≤ `MAX_AI_REK_ROWS` = 500 (named 400), judged
  before any row is parsed; no `Content-Length` is a 411. The credential is
  the dedicated door token: header `X-Ai-Rek-Token` constant-time compared to
  the env `AI_REC_DOOR_TOKEN`, which is 64-hex ENFORCED — unset, empty OR
  malformed means DISARMED (503, fail-closed, owner session included), wrong
  or absent token ⇒ 401 in one uniform copy; a valid owner session rides
  without the token; GET keeps the guard's uniform 302 (MC 12546's posture
  verbatim). The payload has one OPTIONAL envelope (MC 12616, PLAN §d):
  a JSON object `{"generation": [ …rows… ]}` declares the list the COMPLETE
  new generation — the door then deletes the `state='new'` rows whose
  identity is ABSENT from it (identity = the same `rec_key` ∪ isbn ∪
  `wish_key` union the upsert matches on, one mechanism) and the answer
  gains `deleted_n` — that counter names SWEEP deletions only: rows the
  upsert MERGED under an existing `duppar` id are not counted in it
  (MC 12616, DA c5 F-P4-5). `accept`/`decline` rows are NEVER deleted,
  and an EMPTY generation is refused fail-loud (400, rows kept). Without the key
  the payload is today's upsert, byte-identical. Fleet-side runner
  `scripts/ai_rek_pass.py`: `--full` sends the envelope (DEFAULT off —
  explicit opt-in); `--lane-timeout` sizes the Lane E ask budget (default
  600 s — the shipped 300 died mid-generation, DA c4 P3). The fleet-side
  door runner's token never crosses argv: the
  secret header rides a per-call 0600 `--config` tmpfile — the PLAIN path
  form, NOT `--config @<path>`: curl silently ignores the `@` form and
  posts WITHOUT the header (DA c6 F-P1-1; real-wire delivery legs pin
  arrival) — unlinked when the call returns, its content never echoed, no
  path on the command line carries a secret, so `/proc/<curl>/cmdline` is
  clean (MC 12616, DA c3 P2 + c5 F-P2-1; the weld was cut for TWO runners
  and MC 12606 retired the second, `X-Pris-Token` — the shared transport in
  `scripts/curl_transport.py` stays, `ai_rek_pass` is its one runner (its
  MC 12643 keys reader in `scripts/ai_rek_belt.py` rides the same halves)
  and `tests/test_door_transport.py` carries the byte-identity leg now).
- `GET /ai-rek/library-keys` (M11-N9a, MC 12643, owner ruling "A" — chat
  2026-11-17, accepting: the generator gets the COMPLETE read-title list via
  the existing machine door; public scope UNCHANGED) — the door's READ face
  for the recommendation runner: a JSON list of `{"titel", "forfattare",
  "status"}` for EVERY `bok` row, all statuses (read AND wishlist — books
  she has READ are never recommended again, and the runner drops matching
  candidates before the Lane E ask). THE SAME credential as the POST
  (`X-Ai-Rek-Token` vs the 64-hex `AI_REC_DOOR_TOKEN`): unset/malformed env
  ⇒ the generic 503, empty-or-wrong header ⇒ the one uniform 401, a valid
  owner session rides without the token. THE GUARD lets the GET through ONLY
  with the header riding — the no-header face is the guard's uniform 302,
  byte-identical to an anonymous GET `/ai-rek`: this route joins NO public
  allow-list, the public read surface stays graded + wishlist. Zero secret
  bytes in the body (no isbn, no dates, no keys), zero writes.
- `POST /backfill?n=5&after=<id>[&mode=candidates]` — the cover/ISBN retry and
  candidate-pool builder, resumable by `last_id` (cursor advances past
  permanent failures; wrap = fresh pass). Shares one pipeline with
  `scripts/enrich_backfill.py` (flags: `--dry-run --limit N --offline --authors
  --report PATH`; it already targets exactly the rows still missing data).
- `GET /rapa/omslag-rapport` (JSON inventory), `GET /rapa/omslag` (the Swedish
  fix-me list page), `GET /rapa/rekommendation-rapport` (pool gauge).
- CSRF posture: browser forms carry a session token; the machine routes allow
  a curl POST (no `Origin`) and reject a foreign one.

### Covers and "hitta omslag"

Provider order libris → openlibrary → google-books (GB is keyless →
opportunistic, with a 6 h cooldown after a 429; Libris IS reachable from
VM350 — `https://libris.kb.se/` answers 200 (measured 2026-11-14), exactly as
`app/enrich_libris.py`'s HOST-CORRECTION header (2026-11-13) records: the
plan's NO-DNS measurement pinned the wrong host, `librisxl.net` — and its
enrichment legs are still exercised by fixtures, because the suite is offline
by contract). One normalizer, `store_cover`,
re-encodes every image to ≤340×510 JPEG — upload, bundle-write and provider-
fetch all ride it. Browser uploads are downscaled client-side (`omslag-upp.js`,
canvas + quality ladder) before POST, so a large phone photo never trips the
server cap. `POST /omslag/<id>/hitta` ("hitta omslag", plan OQ-2): you paste
the URL of a page (publisher page, library record); the app fetches it
server-side, http/https ONLY (refused before a byte is requested), takes its
`og:image` — else its largest `<img>` — accepts the body only if its magic
bytes say image, caps it at the same 900 000 bytes, and stores it as
`manual-url` (never overwritten by a later bundle).

### Password rules and recovery

argon2id, min 10 chars; setup window 20 min from process start AND only while
no password is set; `/satt-loesenord` is 404 forever after. 5 failed logins per
15 min per client IP — CF-Connecting-IP when present, else the socket peer;
`X-Forwarded-For` is never trusted at the origin (MC 12497 sec-wave,
SEC-verdict-12497 F-4: one client-written header used to hop the bucket) →
429. Cookie `liselott_session`, HttpOnly, SameSite=Lax, Path=`/liselott`,
Secure unless `LISELOTT_ENV=dev`. `POST /byter-losenord` rotates the hash and
regenerates `secret.key`, killing every session. `scripts/reset_password.py`
works on VM350/dev only — the production jail has no shell, so a forgotten
production password means a redeploy-restart (reopens the window) or a
vm106-ROOT DB action. That gap is plan §12, accepted at fest40 parity.

### Backup story (plan §11)

What exists **today** (measured 2026-11-13): `scripts/backup.sh` and
`GET /backup?kind=db|covers` (session-gated), both running the ONE mechanism in
`app/backup.py`: the DB through sqlite's own backup API plus a `covers/` tar,
as a pair — backup dir 700, files 600, retention keep-last-14.
`bash tests/test_backup.sh` is the round-trip gate: it seeds the corpus into a
scratch state dir, makes the pair, prunes to 14, restores into an empty state
dir and prints `BOOKS_RESTORED=724`, then pulls both kinds through the route
and checks the guard's 302 and the unknown-kind 400. The route streams a
FRESH snapshot and deletes its temp file as the response ends; the shell verb
writes the pair it keeps (`scripts/backup.sh list`, then
`scripts/backup.sh restore [STEM]` into `$LISELOTT_DATA_DIR`). **Ownership:**
the auto lane gives no cron on vm106 (no login), so the named actor is the
orchestrator: pull weekly via the route (a logged-in `curl` with a cookie jar,
both kinds), store under `/home/claudecode/liselott-backups/` on VM350,
cadence logged on the MC card. Restoring INTO production and any on-host cron
remain vm106-ROOT actions — owner decision, never assumed.

### Known limits (all measured or plan-stated, 2026-11-13)

- **RETIRED (MC 12606): the price feature has no code left to fetch.** This
  bullet used to carry the M9a-2 promise — the door stood but no runner read
  Bokus, so `price` stayed empty on a fresh site. The owner's ruling
  ("Books on sale can be removed. No interest in buying books.") retired the
  feature instead: the door, the display and `scripts/pris_vakt.py` +
  `scripts/pris_state.py` (the nightly pass and its state file, which the
  LEDGER never pinned as installed — no unit or timer row for them exists in
  LEDGER or README, and the first REAL Bokus visit recorded by MC 12549 never
  ran) are deleted. The `price` table keeps whatever a live site already
  stored: no migration touches it. HOST-SIDE RESIDUAL, not this tree: any
  vm106 systemd unit/timer and the runner's 0600 token/env file still naming
  pris-vakt belong to the orchestrator's teardown row, named in the LEDGER.
- Cover coverage: build DB 74/724 at T9.1 time (47 books provider-exhausted,
  `enrich_fail=1`); production serves 80/724 (orchestrator rapport-measured
  in the M8 run). The residual misses ride the fix-me loop (`/rapa/omslag`),
  owner-driven — never a silent placeholder majority.
- **No edit door for a book that HAS a cover** (measured at this commit):
  `app/templates/bok.html` emits its only `/redigera/<id>` link inside
  `{% if not bok.has_cover %}` (and since MC 12497 inside her session too —
  the public bok page paints no write door at all), and the shelf cards link
  the book page only —
  so a covered book reaches editing/deleting solely by typing the address
  (the page itself answers 200). Grading is unaffected. Card MC 12493 is
  filed to add a calm "Redigera" link; until that ships the manual above
  states the typed-address path, never a link that is not there.
- Production IS published and seeded (M8 ran — see Status). Live counts
  belong to the rapport doors behind the login, not to this file.
- The production candidate pool was built by the runbook's candidate loop
  (build pool reference: 284).
- Libris is reachable from VM350 (`https://libris.kb.se/` answers 200,
  measured 2026-11-14; the Covers section carries the HOST-CORRECTION note) —
  its enrichment legs stay fixture-tested because the suite is offline.
  Google Books without a key 429s under load.
- The recommendation engine and every provider run inside the app's own jail;
  it needs no VM350 for future books.
