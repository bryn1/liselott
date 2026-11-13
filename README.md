# Liselotts bokhylla

A Swedish-language, login-gated personal book diary for exactly one reader
(Liselott): she adds the books she reads, grades them 1–5, searches her own
library, and gets recommendations derived only from her own books and grades —
with a real cover on every shelf card. It is built to be served at
`https://sibbamala.com/liselott` on the fleet's auto lane. The build contract
is `PLAN-c3` (the pinned plan); this README states what the tree actually is.

## Status snapshot — every number here measured 2026-11-13 (this session)

- Build milestones M0–M7 are done and committed; the full offline test suite
  passes: **403 passed, exit 0** (`.venv/bin/pytest -q`, VM350 build clone).
- The build database holds **724 books** (706 read + 18 wishlist), **671** with
  an ISBN, **6** rated, **52** ljudbok, and a recommendation candidate pool of
  **284** authors' works (`sqlite3 /home/claudecode/liselott-build/liselott.db`).
- Covers: **74 of 724** books have a cover file (74 files in the build `covers/`
  dir; 27 of them owner-chosen via upload/URL; 47 books are marked
  `enrich_fail=1` — no provider had one). Measured twice while this README was
  written — 72 at 12:22 UTC, 74 at 12:34 UTC — because a second bounded cover
  wave was running, so this count moves; the authority for production is
  `GET /rapa/omslag-rapport`, once published.
- **Publish (plan milestone M8) has NOT run yet**: this clone has no git remote,
  `bryn1/liselott` does not exist on GitHub, and `https://sibbamala.com/liselott/logga-in`
  answers 404 (all three measured 2026-11-13). The ordered publish runbook —
  leak checklist, public flip, owner sets the password in a 20-minute window,
  seed + bundle + candidate + cover loops over HTTP — is PLAN-c3 §10 with tasks
  T8.1–T8.8. Nothing in this README claims otherwise.

## För Liselott — så här använder du boken

**Logga in.** Öppna sidan (länken får du av orchestratorn,
`sibbamala.com/liselott`) och skriv ditt lösenord. Inget annat än lösenordet
behövs — det finns inget användarnamn.

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

**Önskelistan.** Böcker du vill läsa ligger under "Önska". När du läser en
önskbok markerar du den som läst, då hamnar den i hyllan.

**Rekommendationer.** "Rekommendationer" visar de 12 bästa förslagen utifrån
dina egna betyg — varje kort förklarar varför ("För att du gav …").
"Visa inte igen" tar bort ett förslag för alltid.

**Byt lösenord.** Under "Byt lösenord" (kräver nuvarande lösenord). OBS: alla
inloggningar, även din egen, loggas ut vid bytet — logga in med det nya.

**Radera en bok.** "Ta bort" på boksidan frågar en gång till innan den försvinner.

## For maintainers

### Run it (dev)

```bash
cd /home/claudecode/liselott
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
LISELOTT_ENV=dev PORT=8166 .venv/bin/python server.py   # bind $PORT, no fallback
```

Then `http://127.0.0.1:8166/liselott/` — first boot within 20 min shows the
set-password page; both request shapes (bare `/…` and `/liselott/…`) route.
Tests: `cd /home/claudecode/liselott && .venv/bin/pytest -q` (offline, no
provider network; 403 tests green 2026-11-13).

### Suite-location rule (PLAN-c3 §13, verbatim in force)

The corpus-dependent tests (T1.2/T1.5/T1.6/T1.7/T1.8-leg2/T2.6) read
`/home/claudecode/liselott/data-import/seed-books-raw.md` (present, sha-pinned,
in the VM350 build clone; NEVER in git). Missing file → those tests FAIL (assert
loudly) — a `pytest.skip` is FORBIDDEN. "Full suite green" is legitimately run
ONLY on the VM350 build clone. Every other test is corpus-independent and runs
in any fresh clone.

### Environment (exhaustive)

| variable | meaning |
|---|---|
| `PORT` | the port `server.py` binds (set by the lane unit; no fallback) |
| `HOME` | set by the lane unit to the app's StateDirectory (production) |
| `LISELOTT_PREFIX` | mount prefix for emitted URLs; default `/liselott` — correct in production with nothing set |
| `LISELOTT_DATA_DIR` | data-dir override — dev/test/build use only |
| `LISELOTT_ENV=dev` | local/test only — turns the session cookie's `Secure` flag off; UNSET means production (Secure ON, debug OFF) |

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

### CODE-ONLY repo (the P0-1 rule)

Per the fleet convention this repo copies from `bryn1/fest40`: *CODE ONLY —
site content enters via POST /seed into the host state dir, never git.* The raw
seed file (`data-import/seed-books-raw.md`, sha256
`420259164605b1b9e221e4e9fc8b6f5f98676f0c4bc9e4f6c02e6e5555ec24dc`, re-measured
2026-11-13 and matching the plan pin) and every whole-corpus artifact are
gitignored and have never been committed — `tests/test_no_diary_in_git.py`
guards that permanently. The transfer bundle lives outside git at
`/home/claudecode/liselott-bundle/`.

**Stale seed header:** the raw seed file's header prose (lines 1–7) is parsed
nowhere and carries two false claims (it says no grades exist — 6 rating rows
do; it advertises a date-suffix form — no row uses it; the real form is a
LEADING `YYMMDD` token, 45 rows). Trust the plan's §5 rules, never the header.

### Machine routes (all behind the owner session)

- `POST /seed` — the raw markdown in, `parsed=725 stored=724 duplicates=1` out
  (asserted by the suite). Idempotent.
- `POST /bundle` — newline-JSON lines ≤ 400 KB, request bodies ≤ 900 000 bytes
  (the one byte budget for every transfer into the app, ≈14 % margin under the
  lane's measured ≈1 MiB edge). Matches rows by `book_key` (the shared hash in
  `app/seed.py`), fills ONLY empty ISBN/year/genre holes and absent covers,
  never changes status/dates/notes, never overwrites a manual or URL-chosen
  cover. Re-POST is a no-op. `scripts/export_bundle.py` +
  `scripts/chunk_bundle.py --max-bytes 900000` make the chunks; the chunks on
  disk today are the T3.6 export (724 lines, 45 carrying a cover, 2 chunks,
  893 310 B and 211 050 B) — re-export right before publishing so the bundle
  carries every cover won since.
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
opportunistic, with a 6 h cooldown after a 429; Libris does not resolve from
VM350 at all and is exercised by fixtures). One normalizer, `store_cover`,
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
15 min per client IP (CF-Connecting-IP, else the LAST `X-Forwarded-For` hop) →
429. Cookie `liselott_session`, HttpOnly, SameSite=Lax, Path=`/liselott`,
Secure unless `LISELOTT_ENV=dev`. `POST /byter-losenord` rotates the hash and
regenerates `secret.key`, killing every session. `scripts/reset_password.py`
works on VM350/dev only — the production jail has no shell, so a forgotten
production password means a redeploy-restart (reopens the window) or a
vm106-ROOT DB action. That gap is plan §12, accepted at fest40 parity.

### Backup story (plan §11)

What exists **today** (measured 2026-11-13): `GET /backup` and
`scripts/backup.sh` are NOT yet in this tree — the deliverable is plan T9.2
with the round-trip test `BOOKS_RESTORED=724`. A backup that works right now is
a plain copy of the data dir (`liselott.db` + `covers/`) — the DB answers to
sqlite's own backup API (that is what the T9.2 script will use), plus
`backups/` (keep-last-14, dir 700, files 600) as designed. **Ownership:** the
auto lane gives no cron on vm106 (no login), so the named actor is the
orchestrator: pull weekly via the route, store under
`/home/claudecode/liselott-backups/` on VM350, cadence logged on the MC card.
An on-host cron remains a vm106-ROOT action — owner decision, never assumed.

### Known limits (all measured or plan-stated, 2026-11-13)

- Cover coverage in the build DB: 74/724 at commit time (12:34 UTC; it moved
  72→74 during the writing of this file while a second cover wave ran; 47
  books are provider-exhausted, `enrich_fail=1`). Publish
  requires the owner's residual acceptance for the remaining misses (plan §12
  OQ-2 / task T8.7) — never a silent placeholder majority.
- Not published (see Status); production DB is empty until the runbook seeds it.
- Production candidate pool starts empty; runbook step 6 builds it (build pool
  reference: 284).
- Libris is unreachable from VM350 (fixture-tested; may work from the lane —
  upside only). Google Books without a key 429s under load.
- The recommendation engine and every provider run inside the app's own jail;
  it needs no VM350 for future books.
