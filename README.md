# Liselotts bokhylla

A Swedish-language personal book diary for exactly one writer (Liselott):
she adds the books she reads, grades them 1–5, searches her own
library, and gets recommendations derived only from her own books and grades —
a real cover on a shelf card wherever one has been found, a calm fix-me
placeholder wherever it has not, with the cover waves still running (the
measured share lives in the Status snapshot and Known limits below, never in
this line). **Reading the diary is public** (owner ruling 2026-11-14, MC
12497: "The website sibbamala.com/liselott should be public. All rate books
should be public. Rating and whishing is blocked behind liselotts
password"): the shelf, bok pages, search, recommendation pages, covers and
rating stars answer any anonymous visitor on a configured site; every write
— grading, wishing, adding, editing, deleting, the machine doors, backups,
rapporter — stays behind her one password. It is built to be served at
`https://sibbamala.com/liselott` on the fleet's auto lane. The build contract
is `PLAN-c3` (the pinned plan); this README states what the tree actually is.

## Status snapshot — re-measured 2026-11-14 against HEAD 93f08f7 (public-read wave, MC 12497)

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
- **MC 12497 public-read wave (2026-11-14):** the tree implements the
  public-read contract — `app/auth.py::_is_public_read` answers the read set
  (`/`, `/bibliotek`, `/bok/<id>`, `/sok`, `/rekommendationer`, `/cover/<id>`,
  plus `/healthz`, `/robots.txt`, static) to anonymous GET/HEAD on a
  CONFIGURED site, every write keeps the guard's non-2xx refuse, the
  setup-state exception holds (no password set → the choose-password gate
  wraps the whole site as before), and `robots.txt` now answers `Allow: /`
  on the public site (`Disallow: /` while it is still wrapped). Owner write
  UI (betyg form, "Omslag saknas — fixa", "Visa inte igen") paints only in
  her session. **The live site still runs the pre-wave code until the
  orchestrator re-publishes; flipping live behaviour is that act, not this
  tree's.**
- The full offline test suite passes: **504 passed, exit 0**
  (`.venv/bin/pytest -q`, VM350 build clone, re-run 2026-11-14 at this wave —
  the public-read matrix `tests/test_public_read.py` and the re-cut auth-wall
  legs are the delta from the old 494) and **471 passed,
  33 skipped, exit 0** in a clean clone without her personal export — the 33
  are the corpus legs, skipping by name, never silently (MC 12451 c5; the
  +1 skip since the old count is the new corpus write-refusal leg).
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
Bara du kan skriva: betygsätta, önska, lägga till, redigera och ta bort
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
`Sarenbrant` hittar `Sarenbrant` oavsett bockar.

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
provider network; 504 tests green at this commit with the personal corpus
resolvable, 471 passed + 33 corpus legs skipped in a clean clone — see
Suite-location rule).

### Suite-location rule (corpus legs, path F — MC 12451 c5)

The corpus-dependent tests (T1.2/T1.5/T1.6/T1.7/T1.8-leg2/T2.6/T4.3) need the
raw personal export `data-import/seed-books-raw.md` (sha-pinned, gitignored —
path F keeps it OUT of git). `tests/conftest.py` holds the ONE locator:
`LISELOTT_SEED_FILE` wins, else that in-repo location, else the leg **SKIPS**
with the reason `personal corpus absent — path F keeps it out of git; run on a
host holding the export or set LISELOTT_SEED_FILE` (`pytest -rs` prints one
line per skipped leg — 33 of them). Where the export resolves, those legs RUN
and every pin holds unchanged: file sha256, 725/724/1, the dedupe tie-break,
the drift digest, the leak matrix. Absence skips loudly; it never greens an
assertion. A `LISELOTT_SEED_FILE` naming no file ERRORS (misconfiguration is
not absence), and a corpus with the wrong sha FAILS the pinned-sha leg.

Measured at this commit, both sides: **504 passed, exit 0** on the VM350 build
clone (export present), **471 passed, 33 skipped, exit 0** in a fresh clone
without it. Every other test is corpus-independent and runs in any clone.

`tests/test_backup.sh` keeps its fail-loudly posture on purpose: it is the §11
round-trip runbook a human runs by hand, not a collected pytest leg, and a
silent skip there would be the vacuous-green defect class §13 named.

> **SUPERSEDED (2026-11-14, MC 12451 c5) — the old PLAN-c3 §13 rule, verbatim,
> DO NOT USE:** "Missing file → those tests FAIL (assert loudly) — a
> `pytest.skip` is FORBIDDEN. 'Full suite green' is legitimately run ONLY on the
> VM350 build clone." It made the suite runnable only on the one host already
> holding her personal data, which fails the clean-environment contract and
> blocked any verifier (knut) from ever PASSing a commit-bound card on this repo.

### Environment (exhaustive)

| variable | meaning |
|---|---|
| `PORT` | the port `server.py` binds (set by the lane unit; no fallback) |
| `HOME` | set by the lane unit to the app's StateDirectory (production) |
| `LISELOTT_PREFIX` | mount prefix for emitted URLs; default `/liselott` — correct in production with nothing set |
| `LISELOTT_DATA_DIR` | data-dir override — dev/test/build use only |
| `LISELOTT_BACKUP_DIR` | where `scripts/backup.sh` writes its pairs; default `$HOME/liselott-backups` (§11). `GET /backup` never writes here — it streams from a temp dir |
| `LISELOTT_ENV=dev` | local/test only — turns the session cookie's `Secure` flag off; UNSET means production (Secure ON, debug OFF) |
| `LISELOTT_SEED_FILE` | test suite ONLY (MC 12451 c5) — points at the personal seed export so the corpus legs RUN; unset, the locator falls back to `data-import/seed-books-raw.md` and the legs skip where neither exists. The app never reads it |
| `FIRECRAWL_SEARCH_URL` | the S12 cover pass ONLY (`scripts/cover_pass.py`, MC 12466) — the search endpoint it asks for candidate pages; default `http://192.168.5.20:3002/v1/search` (firecrawl on noa). The app never reads it |
| `DESCRIBE_IMAGE_ENDPOINT` | the S12 cover pass ONLY — the chat-completions endpoint its vision gate (verbatim transcription check) calls; default `http://192.168.5.223:8888/v1/chat/completions`. The app never reads it |
| `DESCRIBE_IMAGE_MODEL` | the S12 cover pass ONLY — the model the vision gate asks to report the cover's printed words; default `qwen3.8-flash-next`. The app never reads it |

**Production needs zero custom env.** The lane unit sets only `HOME` and `PORT`;
everything else falls out of the defaults above.

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

### Reading is public, writing is private (MC 12497, owner ruling 2026-11-14)

The guard (`app/auth.py::_auth_gate`) answers in three states, measured in
`tests/test_guard.py`, `tests/test_public_read.py` and (over the corpus)
`tests/test_no_leak.py`:

- **Configured site, anonymous reads:** the §6.4 allow-list plus the
  public-read set — `/` (the fixed-copy landing: still zero app data, one
  door), `/bibliotek`, `/bok/<id>`, `/sok`, `/rekommendationer`,
  `/cover/<id>`, `/healthz`, `/robots.txt`, `/static/*` — answer with the
  real route (200, or the route's own 404 when no row stands behind it).
  A public page carries no owner door (no edit link, no byt lösenord, no
  logga-ut, no betyg widget, no "Visa inte igen") and never sets a session
  cookie. `robots.txt` says `Allow: /` here — the site is public to read.
- **Configured site, anonymous writes:** every POST stays the guard's 302 to
  `/logga-in` (the `/satt-loesenord` door answers its §6.1 404) — including
  POSTs aimed at the READ paths: the method rule in `_is_public_read` is what
  makes "public to read" not mean "public to write". Owner surfaces —
  `/onska`, `/lagg-till`, `/redigera/<id>`, `/rapa/*`, `/backup`,
  `/byter-losenord`, `/logga-ut` and the machine doors `/seed`, `/bundle`,
  `/backfill` — stay behind her session.
- **No password set (the setup-state exception):** everything above reverts
  to the §6.1 wrap — every data route redirects to `/satt-loesenord`,
  `robots.txt` says `Disallow: /` (an inviting one would point crawlers at a
  setup door), the landing keeps its single setup door. Public-read is a
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

**The exception that ships, named because the repo is PUBLIC.** Some real diary
rows are tracked as test fixtures: the 18 T1.3 parse goldens in
`tests/test_seed_rows.py` carry real titles and authors (two of them a read
date, one a grade); `data-import/import_overrides.csv` carries one real row with
its read date; five recorded provider fixtures name five more real titles in
their filenames (`tests/fixtures/libris_xsearch_god-jul-agnes.json`,
`_den-sarade-pianisten`, `_helenas-resa`, `_dar-vinden-dansar`, `_stold`); and
three `app/` comments name one title, two of them its ISBN as well. Measured
2026-11-14 on the build clone with the guard's own leg-2 parse — a whole-title
*substring* instrument, so a hit can be a word-shape artifact (`Disa` inside
"Disallow"): **36 tracked files hold ≥1 whole diary title** (18 in
`test_seed_rows.py`, every other file 1–6; the count's own universe includes
this README — its single hit is the artifact class it names, one word shape
inside its own explanatory sentence, counted 2026-11-14 at `97911ce`).

`tests/test_no_diary_in_git.py` is green beside those rows by calibration, not
by cleanliness: leg 2 fails a file at ≥20 whole corpus titles (`MAX_TITLES = 20`,
whose own comment reads "T1.3 goldens = 18") and leg 1 at ≥100 seed-shape lines
(`MAX_SHAPE_LINES = 100`). What the guard does hold, in every checkout form, is
the bulk: the raw export, `golden_parse.json` and any `seed-bundle*` appear in
no commit, and the first two remain gitignored.

Whether the tracked fixture rows belong in a public repo is an OPEN question,
not a shipped decision: they await an **OWNER RULING** (P2-3, MC 12440 — the
LEDGER's c2 and c4 rows carry it). The recommendation on the table is to
synthetic-ize the goldens and the override row; ratifying them as shipped is the
alternative. No ruling has landed. Until one does, this section states the
exposure — it does not approve it.

**Stale seed header:** the raw seed file's header prose (lines 1–7) is parsed
nowhere and carries two false claims (it says no grades exist — 6 rating rows
do; it advertises a date-suffix form — no row uses it; the real form is a
LEADING `YYMMDD` token, 45 rows). Trust the plan's §5 rules, never the header.

### Machine routes (all behind the owner session)

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
