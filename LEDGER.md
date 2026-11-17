# LEDGER — Liselotts bokhylla

One ledger, repo root (PLAN-c3 §14). One line per milestone; details live in
the evidence file each line cites (`.audits/20261112-phase2/.tmp/`, gitignored
— the product repo carries the ledger, the audit trail stays beside it).
A line is only as fresh as the commit that wrote it; three or more commits
postdating a line make that line STALE — de-stale before quoting it.

- **M0+M1 foundation** (schema, seed importer, factory, mount) — DONE.
  Evidence `s1-evidence.md` (VERIFY_EXIT=0).
- **M2 auth** (password door, session guard, CSRF, login throttle) — DONE.
  Evidence `s2-evidence.md` (VERIFY_EXIT=0).
- **M3 enrichment + covers** (Libris/OL/GB resolvers, the one cover
  normalizer, `scripts/enrich_backfill.py` + F-2 convergence loop) — DONE.
  Evidence `s3-evidence.md` (VERIFY_EXIT=0).
- **M4 browse + search** (shelf, book page, search, prefixes) — DONE.
  Evidence `s4-evidence.md` (VERIFY_EXIT=0).
- **M5 owner doors** (add-door, omslag upload, wishlist, POST /backfill
  pinned cursor) — DONE. Evidence `s5-evidence.md` (VERIFY_EXIT=0).
- **H1** split app/enrich.py (431 lines) into single-concern modules — DONE
  (pure refactor). Evidence `h1-evidence.md`.
- **H2** omslag-saknas.svg wording reconciliation — DONE. Evidence
  `h2-evidence.md`.
- **M6 recommendation engine** — DONE (stage s6, T6.1–T6.4):
  - T6.1 `recommend.py` scorer — DONE (commit a102d95).
  - T6.2 /rekommendationer + dismiss — DONE (commit a220f5c).
  - T6.3 candidate-pool builder over the T5.6 core + `--authors` CLI + LIVE
    build — DONE (this commit). Pool: `sqlite3 /home/claudecode/liselott-build/liselott.db
    "SELECT COUNT(*) FROM candidate"` → **284** (2026-11-13, live OpenLibrary;
    five consecutive full passes new_candidates=0, §8 cap-40 honoured — last
    pass line: `mode=candidates total=247 scanned=247 processed=247
    fetched=40 failures=0 new_candidates=0 candidate_total=284`).
  - T6.4 POST /seed + POST /bundle HTTP ingest — DONE (this commit; the
    upsert core + both doors in `app/bundle.py`, named deviation from the
    plan's File line per the file-hygiene law, as `app/backfill.py` in M5).
- **M7 calm design pass** — DONE (stage s7, T7.1–T7.4):
  - T7.1 `DESIGN.md` (§9 table + FORBIDDEN verbatim) + tokens test both
    directions — DONE (commit 1d0904b).
  - T7.2 `scripts/contrast_check.py` over DESIGN.md, WCAG AA, planted-red
    proven (#9A948C → 2.79:1 exit 1; clean tree exit 0) — DONE (commit
    2eebc11).
  - T7.3 self-hosted Lora 400/700 woff2 + served OFL, `@font-face` with
    `font-display: swap`, relative src rides the one mount mechanism — DONE
    (commit 98a27bd).
  - T7.4 1280+375 screenshots × 7 pages, 14 describe-image notes (no
    overlap/garble), one real 375px defect found+fixed (`input[type=file]`
    11px overflow on redigera) — DONE (this commit). Evidence
    `.audits/20261112-M7-design/` + `s7-evidence.md` in the phase2 `.tmp/`.
- **Cover waves S12 / S12b (MC 12466)** — S12 committed (d7f1ed3, bounded
  fleet-browser pass over the build DB). Build-DB state measured by this seat
  2026-11-13 12:22 UTC (live `sqlite3`, wave 2 still running — treat as a
  floor): covers 72/724 (72 files in `covers/`), re-measured 12:34 UTC:
  covers 74/724 (74 files), manual+manual-url 27,
  `enrich_fail=1` 47, isbn13 671/724, candidate pool 284. Wave 2 report
  `s12b-covers-pass-report.csv` lands in the phase2 `.tmp/` beside this ledger.
- **T3.5/T3.6 live artifacts** (measured by this seat 2026-11-13, build DB
  `LISELOTT_DATA_DIR=/home/claudecode/liselott-build`): book 724 = 706 read +
  18 wishlist, ratings 6, ljudbok 52 (plan §5.8 outcome, exact); seed file
  sha256 matches the plan pin `420259164605b1b9…55ec24dc` byte-for-byte.
  Bundle `/home/claudecode/liselott-bundle/`: 724 lines, 45 carrying a cover
  (the T3.6 export predates the S12 cover waves), 2 chunks (893 310 B +
  211 050 B, both ≤ 900 000). ⇒ Re-export + re-chunk immediately before the
  runbook's bundle loop so covers won after T3.6 travel — noted in README.
- **M8 publish** — DONE (2026-11-13, MC 12451). The pre-publish version of
  this row measured a clone that had no remote yet; the run then happened:
  `bryn1/liselott` PUBLIC on GitHub, `https://sibbamala.com/liselott` serving
  — fix wave c2 re-measured by GET 2026-11-13: `/` `/logga-in` `/healthz`
  200, `/satt-loesenord` 404 (owner password set, §6.1 forever),
  quarantined names 404. Production counts (724 books, 80 covers, 671 ISBN,
  candidate pool) are orchestrator rapport-measurements from the run — the
  rapport doors behind the login stay the authority, never this ledger.
  The publish chain it took, commit by commit, is the rows below this one:
  staging-gate public landing, window reopens, hotfix-2 quarantine 404s,
  hotfix-3 static-in-closed-state, hotfix-4 regression legs, and the
  live-500 hosting `mirror.cachebust=off` fix.
- **M9 docs (stage s9, MC 12448)** — T9.1 DONE (this commit): README.md
  written (Swedish usage section + English maintainer half, §4 env table, §13
  suite-location rule verbatim, CODE-ONLY statement, T8 runbook pointer,
  stale-seed-header warning, §11 backup story) + this LEDGER brought true.
  T9.1 DoD greps on this commit: the per-file placeholder count (plan T9.1's
  grep line, markers of the to-do family) is 0 for each file, and the two
  retired-mechanism greps that line names (the deleted seed token, the
  history-rewrite tool) are 0 on the README. Full suite on this tree: 403
  passed, exit 0 (measured 2026-11-13). Evidence `s9-evidence.md` in the
  phase2 `.tmp/`. Two stage findings, both outside the docs-only file
  ownership of this stage, filed for the orchestrator: (1) T9.2 NOT LANDED —
  `scripts/backup.sh`, `GET /backup` and `tests/test_backup.sh` are absent
  (grep-measured); it needs a code child; the README states the current truth
  meanwhile. CLOSED 2026-11-13 by the T9.2 row below. (2) T9.3's retired-string gate is RED in code files this docs
  stage may not edit: the shared 900 000-byte budget lives under a retired
  constant name with 15 measured hits (13 in `app/*.py`, 2 in
  `app/static/js/omslag-upp.js` comments — run T9.3's gate-2 grep for the
  exact list) and `scripts/enrich_backfill.py`'s header quotes a
  retired flag name (1 hit) — a rename pass (code profile) closes it, and it
  must keep LEDGER.md + README.md clean too (they are: measured 0 this
  session). CLOSED 2026-11-13 by the T9.3 gate-2 row below. The placeholder gate (plan's case-sensitive form) is GREEN
  (exit 1) on the whole tree; the only case-INsensitive substring hits are
  `todo` as a local variable name in `scripts/cover_pass.py` (lines
  241/250/259) and `tbd` inside opaque Libris record ids in a fixture —
  substring noise, not placeholders.
- **T9.3 gate-2 retired-name sweep (MC 12479)** — DONE (this commit): stage
  finding (2) closed. The ONE 900 000-byte budget is now named by each site's
  concern: `MAX_FETCH` (what the app reads back from an http response —
  providers + hitta-omslag), `MAX_UPLOAD` (uploads — the name §10 sanctions,
  unchanged), `MAX_BUNDLE_CHUNK` (`/bundle` — §10's other sanctioned name,
  unchanged). The invented skip-flag name is gone from
  `scripts/enrich_backfill.py`'s header and the two test docstrings that
  echoed it; the rule it recorded (P2-b) is unchanged. Gate-2 text hits on
  README.md + `app/` + `scripts/` went 16 → 0 (the `.pyc` echoes are stale
  gitignored caches and vanish on the next run); full suite on this tree: 403
  passed, exit 0. Stage finding (1) — T9.2 backup — lands in the same card.
- **T9.2 backup route + round-trip (MC 12479)** — DONE (this commit): stage
  finding (1) closed. `app/backup.py` is now the ONE mechanism (sqlite backup
  API + one `covers/` tar, dir 700 / files 600, keep-last-14);
  `scripts/backup.sh` (backup|list|restore [STEM]) and `GET /backup?kind=db|covers`
  both run it — the route streams a fresh snapshot from a temp dir it deletes
  as the response ends, the shell verb writes the pair it keeps. Plan DoD:
  `bash tests/test_backup.sh` exits 0 printing `BOOKS_RESTORED=724` — three
  consecutive green runs measured (corpus leg, §13). The gate went RED twice
  and both reds were real: the §11 file modes (planted: chmod removed → FAIL
  `db-filen ar inte 600`) and a genuine defect on the first draft — pruning by
  `stem*` glob ate the whole same-second `-NN` family, so retention kept 12
  pairs where it promised 14 (fixed to remove exactly each pair's two files).
  `tests/test_guard.py` adapted in the same commit: its logged-in sweep read
  `.text` on every protected path and `/backup` answers with a sqlite file —
  the gate-page claim now decodes leniently, the claim itself unchanged.
  README's backup story + the env table followed the implementation (the
  "NOT yet in this tree" claim is retired with this commit). Suite: 403
  passed, exit 0. Not covered here and unchanged: T9.3's `git log
  origin/main` leg lands with the M8 push, and the §11 weekly pull stays a
  named-actor runbook step, not a daemon.

- **M8 staging-gate fix — public root landing (MC 12451)** — DONE (this
  commit): the vm106 staging gate refused the product path (`GET /liselott/`
  → 302/235 B, floor 256 B; reconcile.log 2026-11-13T14:34:18Z) while the
  three live service apps answer 200 at their roots (fest40 1815 B, matapp
  12388 B, klartx 4056 B, measured 2026-11-13). §6.4's allow-list widened by
  EXACTLY one leg: the root, reads only (`_is_public_root` in `app/auth.py`)
  — `GET /` now answers 200 in every state: `templates/start.html` (fixed
  copy, zero book data, ONE state-legal door — window-open → "Välj ditt
  lösenord", configured → "Logga in") in the two open states, and the §6.1-
  pinned gate page in the closed one (already 200/>256 B — no second closed-
  state page added). Every data route keeps its guard. Sweep legs updated to
  assert `/` 200 + no-leak instead of 302 (`test_guard` three states,
  `test_no_leak` matrix with the >256 B floor pinned); the legs that proved
  a session by "/" answering 200 now prove it by the owner nav. Red-proven:
  the `/` assert planted to 302 → `assert 200 == 302` FAILED → reverted.
  Gate-equivalent curl on a seeded local server (configured state, both
  request shapes byte-identical): `200 577B`; six anonymous probes carry
  zero seed titles. Full suite on this tree: 403 passed, exit 0.

- **Gate fix wave c2 (MC 12451)** — DONE (this commit): both final gates
  returned verdicts on tree 7b1bc595 (HEAD 5429ce8): DA-verdict FIX
  (1×P1, 2×P2, 1×P3, seams), TEST-verdict FAIL (F-A P1; mutation 7/9, the
  two survivors the same shelf behaviour). Seven commits, one per fix,
  each test-first with its FAIL→PASS recorded in
  `.audits/20261112-phase2/.tmp/c2-fix-evidence.md`: FIX 0 the shelf
  groups keyed on read_year — one section per year, "Utan år" trailing,
  "Att läsa" last — and `tests/test_shelf_grouping.py` kills the corpus-
  shape blind spot (suite green over 583 headings before; RED on the
  one-section-per-book plant after); FIX 1 GET /byter-losenord + the nav
  door "Byt lösenord", happy path proven THROUGH the real server pages,
  not through a session shortcut (P1-1/F-C); FIX 2 this snapshot + the
  README brought true to the published reality (F-B/F-D/F-H; the venv
  line now names `virtualenv` — what actually runs on VM350); FIX 3 the
  ingest doors answer named 4xx — /seed 413 over 1 MiB, 400
  "otillräcklig kodning", 400 naming an unknown section, /bundle named-
  line 400s for domain errors with the WHOLE POST in one transaction
  (`store_cover commit=False`) and a rollback proof (P3-4); FIX 4 the
  dead duplicate `return rel` deleted (P4-5); FIX 5 the closed state 404s
  quarantined names AND /robots.txt — staging posture state-invariant
  (F-E/F-F); FIX 6 /.tmp/ ignored (F-J). Full suite on this tree:
  **436 passed, exit 0** (was 422 + 14 new legs). OUT of this wave,
  named: P2-3 golden corpus rows in the public tree await an OWNER ruling
  (untouched by dispatch); F-G mutmut layout is fleet-tooling; F-I file
  sizes stay debt — `app/seed.py` 342, `app/auth.py` 332, `app/bundle.py`
  ~310 after this wave, test files `test_seed_routes.py` ~530,
  `test_enrich_resolve.py` 536 — none past the 400/600 gates, all still
  split candidates per the clean-code doctrine.
- **Gate fix wave c3 (MC 12451)** — DONE (commits 07c2551..9d9d847, seven):
  both final gates came back GREEN on the c3 tree — TEST-verdict-c3 **PASS**
  (CONFIDENCE 0.88, suite 466 passed ×2) and DA-verdict-c3 **SHIP** (0.9),
  both pinning tree `# JUDGED: 6e7d5796e05395d5bf0adea4768f3a66e7d80f99a9ec6
  270cc101d65b451679a`. Six fixes + one hygiene note: F-A2 (P1) a non-int
  `read_year` 400s named at the door instead of killing the shelf on every
  read; F-B2 (P2) the /bundle rollback reaches the BYTES (a mid-loop cover
  write that fails now unlinks what it wrote); F-C2 (P2) `POST /seed` is
  atomic — one flagged row commits NOTHING; F-D2/F-G2 (P3) ONE value
  vocabulary pass, so no container reaches a bind and a bare string never
  becomes single-character garbage again; F-F2 (P3) `/VERSION` 404s
  anonymously like every other quarantined name; F-H2 (P3) the real-server UI
  leg stops flaking (per-run free port). The mutation pass scored **6/7
  killed** and named its survivor out loud: no test could reach the /bundle
  DB catch arm — which is exactly the finding c4 below was dispatched for.
- **Final fix wave c4 (MC 12451)** — DONE (this commit, four commits, one per
  fix, each test-first with its FAIL→PASS in
  `.audits/20261112-phase2/.tmp/c4-fix-evidence.md`): **FIX 1** F-L2 (P3) —
  the json-LEGAL lone surrogate. `"\ud800"` parsed, reached the strict-UTF-8
  TEXT bind and died there with a UnicodeEncodeError that is NOT a
  `sqlite3.Error`, so the door answered 500 past its own rollback AND past
  the cover unlink (verifier left `covers/1.jpg` on disk with zero rows). It
  was the M7 plant's live twin: the arm existed, nothing could reach it. Now
  refused in the vocabulary pass that already owns every other value shape,
  and the arm is `(sqlite3.Error, UnicodeEncodeError)` with three mid-loop
  plants (Integrity/Operational/UnicodeEncode) proving it unwinds to the
  named 400, the rolled-back count and the ZERO cover files. **FIX 2**
  F-L3/F-M (P3) — NUL and the C0/C1 bytes were STORED at both doors and rode
  into the markup of five served pages; one shared rule (`seed.unstoreable`)
  refuses them at /bundle's field pass and at /seed's row validator, naming
  line/field and printing the CODE POINT (a refusal that echoed the byte
  would serve what it refuses). §5.4's tab-form row is untouched — the flag
  path still routes it to `import_overrides.csv`. **FIX 3** F-L4 (P4) — the
  two numbers that lied: the header reason line said `FILE-SIZE 413` on a
  417-line file (number dropped, reason kept — a counted note stales the
  commit it is written in), and `POST /seed` answered the SHELF's row count
  as if it were the POST's (`parsed=1 stored=3`), now the rows that POST
  stored while the CLI keeps §5.9's audited whole-table meaning and says so
  on the run where they differ. **FIX 4** (this commit, the docs duty) — the
  README's two `436 passed` claims are true again, these two rows land, and
  every count in the older rows is read as what it is: a measurement of ITS
  OWN tree, never the current suite. Full suite on this tree: **494 passed,
  exit 0** (`466` at the c3 base + 28 legs this wave). File sizes this wave:
  `app/bundle.py` 449, `app/seed.py` 406 — both past the ceiling, both now
  carrying a numberless reason line that names the mechanism owning them, the
  split still the queued clean-code follow-up both dispatches named out of
  scope; `tests/test_seed_routes.py` 579, inside the 600 test gate. The
  reason lines sit in the gate's FIRST FIVE LINES (dod_hygiene rule (h1) reads
  `lines[:5]`, and the c3 note — line 47 of a 452-line file — was true prose
  but invisible to the instrument: `app/bundle.py` 452 and `app/seed.py` 407
  now open with the reason and point to the long note below. OUT of
  this wave, named: P2-3's golden corpus rows in the public tree still await
  an OWNER ruling, and the c3 verdict's F-L1 doc staleness is the class of
  finding this wave keeps having to sweep — a count in prose is a claim
  without an instrument behind it.
- **Test-suite wave c5 (MC 12451)** — DONE (this commit, two test-only commits
  + this docs duty; transcripts in
  `.audits/20261112-phase2/.tmp/c5-*-evidence`-set): knut's SEALED rerun died
  `7 failed, 462 passed, 25 errors` on a clean checkout because the corpus legs
  hard-required the personal export (§13: "a `pytest.skip` is FORBIDDEN"), so
  the suite ran ONLY on the host already holding her diary — path F made the
  clean-environment contract unmeetable and no commit-bound card here could
  ever PASS. `tests/conftest.py` is now the ONE locator (`LISELOTT_SEED_FILE` →
  the gitignored in-repo location → skip with a named reason) and the eight
  corpus files take the path from it, CLI legs included, so the suite and
  `import_seed.py`/`parse_digest.py` resolve the corpus through one mechanism.
  Both sides measured at this commit: **494 passed, exit 0** with the export
  (zero new skips — the pins still RUN here) and **462 passed, 32 skipped,
  exit 0** in a fresh clone without it (`tests/` and bare, same result). The
  gate's own red legs: a one-byte-mutated copy FAILS the pinned sha256
  (`1 failed`, the two digests printed side by side) and a
  `LISELOTT_SEED_FILE` naming no file ERRORS all five parse legs — absence
  skips, misconfiguration and drift do not. OUT of this wave, named: (a)
  `tests/test_backup.sh` still fails loudly on a missing export BY DESIGN (a
  hand-run round-trip runbook, not a collected leg); (b) `test_no_diary_in_git`
  legs 1+3 need a real `.git` — they fail in a git-ARCHIVE tree with no `.git`,
  VERIFIED pre-existing at base `1e65919` (`c5-archive-nogit-BASE-1e65919.txt`),
  so a rerun host that unpacks an archive instead of cloning needs an OWNER/
  verifier call: clone-based rerun, or a separate wave for that guard. (c)
  CORRECTION, measured 2026-11-14 (c7): the same no-`.git` `git archive` tree
  answered **3 failed + 1 skipped** across the two guard files together —
  (b)'s diary legs 1+3 plus the leg (b) never named, `test_static::
  test_app_version_is_the_current_head` (no `.git`: `APP_VERSION` answers the
  tree's VERSION file while the HEAD probe answers empty), the skip being leg
  2's corpus absence, not git; c6 (00a85e0) fixed the DIARY-guard class (the
  guard now walks the tree — measured green in the archive), while the
  version leg measures red in a 00a85e0 archive too (clone-only by
  construction) and rides the same clone-vs-archive rerun-host decision.

- **Docs fix wave c9 (MC 12451)** — DONE (four docs commits, one per concern,
  C-3+C-4 sharing one): the findings of the two S9 docs gates on MC 12448
  that the c6 test-only and c7 docs waves left standing — `DA-verdict.md` (FIX,
  CONFIDENCE 0.90, `# JUDGED: 1120d19e…`) and `DA-verdict-c2.md` (FIX,
  CONFIDENCE 0.86, `# JUDGED: 99417b7c…`), both under
  `~/.local/state/knut-dispatch/card-12448.out/` (c7's own corrections already
  ride inside the c5 row above; c6 and c8 were test-only). C-1: §CODE-ONLY now
  states the rule AND the exception that ships in the PUBLIC tree — the 18
  T1.3 goldens, `data-import/import_overrides.csv`, five title-named provider
  fixtures, three `app/` comments, 36 tracked files holding ≥1 whole diary
  title by the guard's own leg-2 parse (the 36th is README itself, via the
  word-shape class it documents) — with the guard's thresholds
  (K = 20 titles / 100 shape lines) and the OWNER RULING still PENDING (P2-3,
  MC 12440; recommendation synthetic-ize, no consent manufactured). C-2: the
  manual no longer sends her through a "Redigera" link `bok.html` emits only
  inside `{% if not bok.has_cover %}`; it says where editing/deleting actually
  runs, which link exists, that a covered book reaches the page by typed
  address, and the Known limits carry the gap plus MC 12493 (the card for the
  missing door — a PRODUCT finding, not a docs one). C-3: the lead line sells
  "real cover where one was found, calm fix-me placeholder where it was not"
  instead of 100 % covers. C-4: budgets are named by their owner — the export
  scripts' `LINE_BUDGET = 400_000` (refuses to write, pinned by
  `tests/test_bundle.py`) versus the doors' body caps 900 000 (/bundle) and
  1 048 576 (/seed); re-measured in-process: an 800 080-byte single line POSTs
  200 with `inserted=1`. README + LEDGER ONLY — no app, template, script or
  test touched, full suite on this tree **494 passed, exit 0**, byte-for-byte
  the base `5c6b420`'s count: ZERO test delta. Live site untouched (anonymous
  GETs were not even needed). Transcripts:
  `.audits/20261112-phase2/.tmp/c9-fix-evidence.md`.
- SUPERSEDED 2026-11-14 (MC 12501): the row below stands as the trail of
  the wave that built the public-read machinery and its write posture — its
  WHOLE-site read scope (the shelf unfiltered, search and recs public too)
  was narrowed the same day to the PUBLIC SET; see the public-scope row at
  the end of this ledger. The quoted ruling stands; the implemented scope
  it describes is DO NOT USE as the contract any more.
- **Public-read wave (MC 12497)** — DONE (four commits, one per concern:
  guard+templates / tests / robots / this docs row): OWNER RULING 2026-11-14
  (web chat, verbatim): "The website sibbamala.com/liselott should be public.
  All rate books should be public. Rating and whishing is blocked behind
  liselotts password". Reading is public on a CONFIGURED site (shelf, bok
  page, search, recs, covers, the data-free landing, healthz, robots,
  static — anonymous GET/HEAD only), writing is every POST refused non-2xx
  (the guard's 302, never a 2xx), the SETUP-STATE exception holds (no
  password set → the choose-password gate wraps the whole site, robots says
  Disallow then too), quarantines untouched in all states, and the owner's
  write UI (betyg form, fixa-link, "Visa inte igen") paints only in her
  session. Owner surfaces `/onska /lagg-till /redigera /rapa /backup
  /byter-losenord /logga-ut` and the machine doors stay behind the session.
  The auth-wall tests were REWRITTEN to the new per-route matrix
  (`tests/test_public_read.py` NEW; guard/no_leak/browse/search/prefix/
  login/change_pw re-cut), and the guard's 501-stub helper now decides via
  the url_map matcher (its old string compare shadowed converter routes the
  moment anonymous reads reached routing — the flip surfaced a latent test
  defect, fixed here). Suite: 494 → **504 passed, exit 0** (build clone,
  corpus legs green) and 462+32skipped → **471 passed, 33 skipped, exit 0**
  (clean clone, `git archive` check). TEN planted-REDs pasted with executed
  restores (P1 reads-off, P2 method-rule, P3 fresh-wrap, P4/P5 owner-UI-on-
  public-pages, P6/P9 robots both directions, P7 anon Set-Cookie, P8 owner
  write dead, P10 owner-surface leak into the read set) — the campaign's
  FIRST P1 attempt echoed its plant/restore instead of executing them, that
  self-catch is recorded in the transcript header. Password machinery,
  doors' authenticated behaviour, data-import/ and golden rows: untouched.
  LIVE site untouched — it still answers the pre-wave code until the
  orchestrator re-publishes (the README Status row states that, no live
  claim manufactured). Transcripts:
  `.audits/20261112-phase2/.tmp/public-read-evidence.md` + `planted-red.md`
  (host-local, MC-linked).
- **SEC-WAVE p2 — security fixes (MC 12497)** — DONE (six commits: one per
  finding F-1..F-5 + this docs row), curing the security gate
  `.audits/20261112-phase2/out/SEC-verdict-12497.md` (SHIP 0.86 with
  F-1 P2 + F-2/F-3/F-4 P3 + F-5 P4-cluster; every finding re-run red before
  the wave, green after). F-1: the three dual-method views (`/logga-in`,
  `/satt-loesenord`, `/byter-losenord`) branch on `method == POST` — the
  GET-renders/else-processes split let HEAD execute every state change (5
  wrong HEADs drained §6.2 and 429-locked her NEXT real login; a HEAD+body
  logged in and changed the password with both CSRF defences bypassed) — and
  `_csrf_gate` no longer skips HEAD: the ORIGIN rule checks it as it checks
  POST; the token rule deliberately stays a CSRF_METHODS rule (HEAD is
  READ_METHODS; token-checking it would 400 the anonymous public reads — the
  reading used, stated in the evidence). F-2: `/bok` and `/cover` bound-check
  the id against sqlite's signed-64-bit INTEGER domain before the bind — an
  id `>= 2**63` matches werkzeug's unbounded `\d+` and answered the anonymous
  500 + traceback measured LIVE through the edge; the route's own 404 answers
  instead. F-3: `_is_public_read` tolerates the ONE trailing slash and the
  five public views register their slash spelling as an explicit rule on the
  SAME endpoint — werkzeug 3.1.9 REMOVED the strict-slash redirect (probed: no
  RequestRedirect on this pin), so guard-tolerance alone would trade the login
  wall for the router's 404; writes keep the 302 refuse, all three states keep
  their wall shape, `url_for` unchanged. F-4: `client_ip` = CF-Connecting-IP
  (edge-overwritten on the proxied zone) else the SOCKET PEER, XFF never —
  AND `server.py` runs uvicorn with `proxy_headers=False`, because the
  default rewrote REMOTE_ADDR from the spoofer's own XFF BELOW the app (the
  app-half alone stayed green on test_client while the raw stack still
  answered 302 — the raw-suite leg pins both halves; residual documented:
  port-direct CF-header rotation, accepted by the wave's trust order). F-5:
  `QUARANTINED_NAMESPACES` answers the bare `.git`'s 404 for its
  extension-less children in every state (sweep legs ride the QUARANTINED
  matrix), and the factory pins `Cache-Control: no-store` on owner-session
  text/html beside its `Vary: Cookie` — anonymous public HTML unpinned, the
  static immutable pin asserted untouched. Carried P4s DOCUMENTED not fixed:
  the CSRF-400 fingerprint on anonymous PUT/DELETE/PATCH at allow-listed
  paths, and the app-level body cap behind the edge caps. auth.py grew to 444
  lines — header carries the one-line reason; the one-concern split is
  SCHEDULED for the next hygiene pass, not smuggled into security work.
  Suite 504 → **537 passed, exit 0** (build clone) / **504 passed, 33
  skipped, exit 0** (clean `git archive` clone — corpus legs skip by name; the
  33 new legs are corpus-free and every finding carries a red-before
  transcript, raw-socket ones included). LIVE site untouched — one anonymous
  read-only overflow GET (still 500: live runs the pre-wave code until the
  orchestrator re-publishes); ZERO POSTs off loopback; production state
  untouched (scratch `LISELOTT_DATA_DIR` only); nothing pushed. Transcripts:
  `.audits/20261112-phase2/.tmp/secwave-p2-evidence.md` (host-local,
  MC-linked).
- **Public-scope narrowing (MC 12501)** — DONE (four commits, one per
  concern: guard+filter / tests / landing copy / this docs row): OWNER
  RULING 2026-11-14 (web chat, verbatim): "Rated books and their ratings as
  well as whishlist shall be public. The rest behind password" — the NEWER
  ruling supersedes the same-day broader public-read scope above (both
  quotes stand on their cards; the newer binds). The PUBLIC SET is the
  books with `rating IS NOT NULL` plus the wishlist rows — ONE predicate,
  `app/books.py::PUBLIC_SET_SQL`, applied at the data layer by
  `load_books(public_only=…)` (shelf + bok) and composed into the cover
  probe: no second gate, no new route. `/sok` and `/rekommendationer`
  rejoin the guard's uniform 302; a private `/bok`/`/cover` id answers the
  SAME 302, SAME Location, as a nonexistent id (equal-answer legs —
  id-enumeration learns nothing); unrated titles are absent from every
  anonymous response BY NAME, corpus-scale (all 700 unrated rows grepped
  out of the anon shelf, zero title collisions verified); the owner sees
  everything unfiltered everywhere — her view changed NOTHING; fresh-state
  wrap, write refusals, quarantines, robots state-dependence and the
  password machinery untouched. Tests: matrix flipped + planted-REDs per
  new leg (transcripts in the evidence file). Retired-claim sweep:
  landing copy rewritten, README exposure section + status bullets
  rewritten truthfully, the MC 12497 LEDGER row carries a SUPERSEDED
  marker line beside this one (replace, not erase). Suite: 537 → **546
  passed, exit 0** (build clone, corpus legs green) and **512 passed,
  34 skipped, exit 0** (clean clone, `git archive` check, exit 0). LIVE
  site untouched — one anonymous read-only GET of the live shelf, ZERO
  writes (scratch `LISELOTT_DATA_DIR` only); live still answers the
  pre-wave posture until the orchestrator re-publishes. Transcripts:
  `.audits/20261112-phase2/.tmp/public-scope-evidence.md` (host-local,
  MC-linked). F-1 CURE (same card, same concern, 2026-11-14): the scope
  gate (SEC-verdict-12501, VERDICT SHIP) found `book.notes` rendered
  UNGATED on public `/bok` pages (books.py SELECT + bok.html render) —
  latent, 0 of 53 live public pages carried note text; by the ruling's
  "rest" clause notes are owner-only. The cure is ONE place at the data
  layer: `load_books(public_only=…)` now projects `NULL AS notes` — no
  second gate in any template (bok.html untouched), the "Läst" date stays
  public (it rides the rated-book card by design), the owner's view is
  unchanged (she keeps her notes everywhere she sees the book). Tests:
  the stale "the note ships with the page" leg flipped to the new
  contract; one new leg plants a note on a rated AND on a wishlist public
  book and asserts the exact strings absent from anon `/bok` + anon shelf,
  present on the owner's; planted-RED both pre-cure and with the cure gate
  forced off (transcripts). Suite: base 546 re-measured at 0b8d801 →
  **547 passed, exit 0** (build clone, corpus legs green, 103.7s). LIVE
  untouched (scratch `LISELOTT_DATA_DIR` only); nothing pushed.
  Transcripts: `.audits/20261112-phase2/.tmp/notes-gate-evidence.md`
  (host-local, MC-linked).
- **MC 12522 public entrance at `/` — DONE (this commit):** OWNER REPORT
  2026-11-14 (web chat, verbatim): "I want you to do a browser test of the
  live website sibbamala.com/liselott. I only get to thr logga in page."
  Measured cause (orchestrator, real chromium 17:52Z, re-read here against
  HEAD): an anonymous `GET /` rendered `templates/start.html`'s intro copy and
  ONE "Logga in" link — no entrance to the public shelf — while `/bibliotek`
  anonymously served every public card. The public promise had no path from
  the door the owner actually opens. THE CURE IS REUSE, NOT A MECHANISM:
  `routes.rot()`'s anonymous configured branch hands the landing
  `_hyllgrupper()` — the ONE shelf read `/bibliotek` already ran (extracted
  out of `_hylla()`, which now calls it: the shelf page's read is unchanged,
  one caller gained) — and the shelf's section loop MOVED OUT of
  `bibliotek.html` into `templates/_hyllan.html`, which BOTH `/bibliotek` and
  the landing include (used twice → extracted, the `_bokkort.html` rule: one
  card markup, never a copy). Zero new query path, zero new filter
  (`books.PUBLIC_SET_SQL` stays the ONE gate, applied at the fetch by
  `load_books(public_only=…)`), zero new template mechanism, zero auth code
  touched. `app/auth.py` is BYTE-IDENTICAL (proven by this commit's
  `git diff HEAD~1 --name-only` — it does not appear; the root leg is MC
  12451's `_is_public_root`/`PUBLIC_READ_PATHS`) — the guard did not widen one
  path, one method or one id. The logged-in landing is MEASURED byte-identical,
  not merely asserted: HEAD~1's tree (git-archive'd) and this one rendered
  through ONE script on identical scratch DBs, with only the `?v=` cache key and
  the CSRF token normalised — the owner's `/`, `/bibliotek`, `/bok/2`,
  `/onska`, `/sok` and the anonymous shelf/book pages answer byte for byte the
  same in the seeded AND the empty state (`.audits/20261114-mc12522/`,
  host-local); only the anonymous `/` changed. The extraction is
  whitespace-neutral ON PURPOSE — `-%}` on the partial's import, the pages'
  `{% include … -%}` and one trailing-newline note in the partial: a stray
  newline is enough to change a served page — and one new leg pins her `/`
  equal to `/bibliotek` byte for byte, so drift in the shared include goes red.
  The WRAPPED setup state keeps its data-free landing and
  the "Välj ditt lösenord" door (no password → no public, the setup-state
  exception); the closed state still never reaches the view. The door stays:
  "Logga in" is now the landing's small footer line (`.landnings-dorr`, two
  rules in app.css, DESIGN.md's existing tokens only — the token gate and
  `scripts/contrast_check.py` stay green).
  TESTS: `tests/test_public_landing.py`, 8 legs — the entrance renders cards +
  the "Att läsa" section under the intro; its card links are EXACTLY the set
  `/bibliotek` emits (equality, not a sample); zero private rows, using TWO
  synthetic unrated wishlist-less fixtures seeded in the test's OWN temp DB
  (never real titles from `data-import/`), absent by title, author, year
  heading and id link; the door stays; the owner's landing is still her own
  full shelf; the wrapped setup landing shows no shelf; the CONFIGURED-but-
  empty public shelf still renders (the empty-page-import seam
  `test_empty_owner_surface` guards, now on the landing too); plus the
  corpus-scale private absence over the real export (path F). `tests/test_no_leak.py`
  strengthened, not weakened: its corpus absence sweep now runs over the
  landing too, and the landing's byte-silence leg gained the
  `class="bok-lank"` non-vacuity leg (the four golden corpus rows are all
  PRIVATE, so the silence claim still bites). Planted-REDs, one per contract
  half — entrance removed / landing reading the UNFILTERED shelf / door
  removed — each went red on its own legs
  (`.audits/20261114-mc12522/planted-red.md`, host-local, MC-linked).
  Retired-claim sweep: "the fixed-copy landing", "data-free landing", "zero
  app data" and "the landing is still ZERO data" rewritten in README (intro,
  status bullet, exposure section) + `routes.py` + `start.html` + the
  `test_no_leak`/`test_guard` comments — grep-to-zero over the tree, the
  M8/MC 12451 and MC 12497 LEDGER rows left standing as history (this row
  supersedes their landing SHAPE only: the root leg, the >256 B floor and the
  one-door rule all still hold). ONE stale line knowingly left: `app/auth.py`
  still describes the landing as "fixed copy with zero app data" — this card
  was bound to leave auth.py byte-identical, so that comment is a one-line
  doc follow-up for the next card, not a licence to touch the guard here.
  Suite: base 547 → **555 passed, exit 0** (VM350 build clone, corpus legs
  green, 97.9 s — the venv named on the card,
  `/var/lib/vm106-venvs/liselott/bin/python3`, does not exist on this host;
  the repo's own `.venv` ran it) and **520 passed, 35 skipped, exit 0** from
  a clean `git archive` clone (the corpus legs skip by name). LIVE untouched
  — no request left this session, ZERO writes, scratch `LISELOTT_DATA_DIR`
  only; live still answers the pre-wave posture until the orchestrator
  re-publishes. Nothing pushed.
- **MC 12523 P2-3 RESOLVED — public repo synthetic-ized — DONE (two commits,
  one per concern: fixtures/cases, then the CSV move + gate):** OWNER RULING
  2026-11-14 (web chat, verbatim, recing the P2-3 recommendation): "Do rec for
  p2-p3". SUPERSEDES the P2-3-PENDING notes carried in the MC 12440-era rows
  (rows above, left standing as history): the public repo's tracked test
  material carried real diary content — 40+ files, 35 unique real ISBN-13s,
  real titles/authors in goldens, fixtures and `app/` comments — measured at
  `97911ce` with the guard's leg-2 parse (36 tracked files ≥1 whole title;
  a substring instrument, its artifact class named generically in README per
  this card). **c1 (fixtures + suite):** every tracked title/author/publisher/
  ISBN/provider-fixture rewritten to Swedish-shaped SYNTHETIC data preserving
  each parse property (åäö folds, dupe-variants, multi-author splitters, the
  X-check-digit and ISBN-10 vectors, one intentionally-bad checksum kept bad;
  check-valid synthetic block `978-91-7371-…`); eight title-named fixture
  files renamed; new committed synthetic corpus `tests/fixtures/synthetic_seed.md`
  (43 entries, sha + digest + count pins computed at landing) and the corpus
  legs cut into TWO CASES (conftest `pytest_generate_tests`): `synthetic` runs
  everywhere (a clean clone runs the behaviour legs, it skips nothing),
  `personal` is ADDED wherever path F resolves the export — every personal pin
  (sha256 `420259…`, 725/724/1/6/52, digest `79ec15…`, dedupe tie-break,
  leak-matrix floors) stands unpinned-weak; legs that had to NAME rows (Evelyn
  override, Falska toner tie-break, search-e2e attach, no-leak probe) pin the
  mechanism on synthetic rows / DB-read probe titles instead, and the personal
  aliases CSV keeps a NAME-FREE pin (row count 15, every row resolving) where
  the file resolves. Suite: base 555 -> **577 passed, 0 skipped** (VM350).
  **c2 (this commit — CSVs off-repo + the gate):** `git rm
  data-import/author_aliases.csv data-import/import_overrides.csv` after
  byte-identical copies landed 0600 under `/home/claudecode/liselott-data/`;
  ONE resolver per CSV (`app/seed.py::aliases_file()/overrides_file()`, env
  `LISELOTT_ALIASES_FILE`/`LISELOTT_OVERRIDE_FILE` first, default off-repo
  home; no fallback pair) wired through the importer CLI, the /bundle door,
  `app_aliases()` and the tests; absent file = clean no-op, pinned by tests
  BOTH ways (tmp synthetic CSV applies; a fresh import with neither file
  stores every row, no alias rows, fel-år date stands). New committed
  `scripts/exposure_check.py`: reads the personal title/ISBN lists from
  OFF-REPO paths, `git grep -F -w` over the tracked universe, prints ONE
  number (tracked files with ≥1 hit), exit 0 only at 0 — measured **0** here;
  red-proofed by a planted real-title file in a throwaway `git archive` export
  (red, then green after removal — real tree never touched), transcript
  `.audits/20261114-mc12523/planted-red.md` (host-local, MC-linked). The
  whole-word instrument also retires the substring artifact class (one
  four-letter diary title hides inside robots.txt "Disallow" — class named,
  word not). CAVEATS, honestly: **git HISTORY keeps the old blobs** — this is
  a public repo and a history rewrite is a separate OWNER decision, NOT taken
  here; new clones and the current tree measure 0. `LISELOTT_REAL_TITLES`
  lists 734 titles (724 seed-parsed + 10 fixture-extracted extras, disclosed).
  Suite c2: **579 passed, 0 skipped, exit 0** on VM350; clean `git archive`
  clone **557 passed, 1 skipped, exit 0** — the single skip is the diary-in-git
  guard's leg 2, whose subject IS the personal export (loud reason; the 33 old
  corpus skips are gone, their shape-work now runs synthetic in every clone).
  The gate's own first RED run caught this card's committed script carrying
  the four-letter artifact word in its docstring — fixed, amended pre-push,
  transcript kept. Live untouched. Nothing pushed.
- **MC 12526 stale landing comment retired — DONE (this commit):** closes
  the ONE follow-up the MC 12522 row knowingly left open: `app/auth.py` §6.4
  still called the anonymous landing "fixed copy with zero app data" —
  CONTRADICTED since MC 12522 made the configured-state `/` render the
  PUBLIC shelf (rated + wishlist, `books.PUBLIC_SET_SQL` at the data layer)
  through the `PUBLIC_READ_*` rules in this file. COMMENT-ONLY fix: the
  sentence now states today's truth (public shelf via `PUBLIC_READ_*`; the
  setup-state landing stays data-free; everything else behind the password).
  Proof the guard is untouched: `git diff -w -- app/auth.py` — every changed
  line starts with `#`, zero logic lines, zero test files, `tests/conftest.py`
  untouched. Suite: **579 passed, exit 0** (base unchanged, VM350 `.venv`,
  `-p no:cacheprovider`, 110.45 s). Live untouched; nothing pushed.
- **MC 12532 sealed-env absence posture + suite CSV pins — DONE (this
  commit):** knut's sealed rerun died `48 failed, 18 errors` where the host
  run is green (verdict `.audits/20261114-sealedflake/`). Two causes, both
  runner-posture, no product behaviour change: (1) `app/seed.py` read CSV
  ABSENCE with `Path.is_file()`, which under a sealed runner (ProtectHome
  masks /home mode-000) RAISES OSError(EACCES) instead of answering False —
  `load_aliases` and the `read_overrides` twin now treat OSError as the
  absence their docstrings always promised (no-op `{}`); readable files
  behave identically. (2) `tests/conftest.py` pinned only `LISELOTT_DATA_DIR`
  — `LISELOTT_ALIASES_FILE`/`LISELOTT_OVERRIDE_FILE` rode UNPINNED, so on
  this host the REAL personal CSVs silently backed legs labelled synthetic;
  a session autouse fixture now pins BOTH to non-existent paths in pytest's
  tmp space (the synthetic posture), legs that build their own CSV keep
  setting their env per-test, and the personal-CSV pin leg lifts the suite
  pin to fall back to DATA_HOME — the pin doctrine still runs the real CSVs
  wherever they resolve (the 21 `[personal]` corpus legs unchanged, the
  15-row CSV leg still PASSES here). The `test_seed_aliases.py` skip-guard
  took the same unsafe `is_file()` (the sealed RED showed 1 skip where
  GREEN shows 2 — the guard itself raised); it answers skip, never error.
  Two new legs: the mode-000 EACCES-absence pin (real producer, uid-1000
  traversal, no mock — loaders answer `{}` AND /bundle still 200) and the
  synthetic-purity path-shape pin (both envs outside the personal home,
  name-free). Planted red proven: reverting the seed.py hunks makes the
  EACCES leg FAIL `PermissionError [Errno 13]` — both transcripts in
  `.audits/20261114-sealedflake/fix-red.md` (host-local). Suite: **581
  passed, exit 0** (579 base + the two new legs, 0 skipped both ways on
  this host; VM350 `.venv`, `-p no:cacheprovider`, 111.66 s). Live
  untouched; nothing pushed.
- **MC 12533 sealed-shape pre-push smoke — DONE (this commit):**
  `scripts/sealed_smoke.sh [SHA]` runs knut's vm100 verify seal over this
  repo's suite FROM THE BUILD HOST before any push — git-archive of the SHA
  into `vm100:/var/tmp/sealed-smoke/<sha8>`, non-sealed pip fetch unit, then
  `systemd-run --wait --collect --pipe` with the flag pairs copied VERBATIM
  from `sandbox.py` `verify_argv` (source + date named in the script; flags
  literal, nothing parsed off vm100 at run time). The sealed pytest exit is
  the script's exit. Measured at landing, both legs clean single attempts:
  HEAD **558 passed, 2 skipped, exit 0** (107 s on vm100); bug commit
  2dbeed7 **48 failed, 491 passed, 1 skipped, 18 errors**, exit 1 — the
  gate's red case IS the historical bug (1 skip vs GREEN's 2 reproduces the
  raising skip-guard of MC 12532 above). When to run + honest limit (the
  flag list is a MIRROR of vm100's seal; knut stays the authority): README
  §Sealed-shape pre-push smoke.
- **MC 12542 M9a-1 — the price door, the FLOOR/badge engine and the public
  wishlist price line — DONE (this commit):** `POST /pris`
  (`app/pris.py`, DESIGN-prisbevakning-v2 §6e) takes a JSON array of
  `{isbn, retailer, price, currency, checked_at}` and owns everything else —
  body ≤ `MAX_PRIS_BODY` 65 536 B (named 413) and ≤ `MAX_PRIS_ROWS` 500 rows
  (named 400) both judged before a row is parsed, a POST whose envelope carries
  no `Content-Length` is the 411 the other machine doors already answer, `isbn`
  exactly 13 ASCII digits resolving to a WISHLIST row, `bokus`/`SEK`/integer
  1..20000, `checked_at` inside the CLAMPED window [now − 2 d, now + 5 min]
  (§4 rule 5), a same-day re-ask UPSERTs into ONE history point via the §1 day
  index `ux_price_isbn_day` (schema.sql carries that DDL verbatim — it was the
  one thing M8 could not add without this card), a single-step drop past 60 % is
  STORED FLAGGED (`suspect=1`, G1 computed before the upsert against the latest
  observation strictly before that row's DAY and made payload-aware so restating
  a day inside one POST cannot smuggle the drop past it), one 730-day prune per
  accepted POST, and the response is seven counters that echo no book data.
  AUTHZ EXPOSURE, NAMED: `/pris` joins `auth.TOKENLESS_POSTS` — tokenless (no
  CSRF token, foreign Origin 400), NEVER guardless: an anonymous POST meets the
  guard's uniform 302, the route joins no read allow-list, and it was added to
  all three exhaustive sweeps (`test_guard.OWNER_ONLY`,
  `test_public_read.WRITE_ROUTES`, `test_ingest_vocab`'s 411 door loop). Its
  credential is the owner's own site password until M9a-2 hands it to a unit's
  0600 env file. `app/priskort.py` is the ONE price read plus the §4 FLOOR-EVENT
  walk — FRESH (current row = today's UTC date), DEPTH ≥ 8 distinct days inside
  90, FLOOR = min over ACCEPTED rows strictly earlier, STRICTLY-BELOW, and the
  badge identity is the EVENT's fixed floor: opens on a new low, persists under
  it, closes at or above it, re-arms only from the confirmed low — so 100→30→105
  →30 is ONE badge and not two, and a suspect ghost price enters no floor.
  §8's two legs are `tests/test_pris_badge.py` as the lit-string walks
  `".........BBB."` and `"..........BB..B"`. The DISPLAY (§5 + the owner's
  public-scope ruling of 2026-11-15, quoted verbatim in README) rides the ONE
  `bokkort` macro: `/bibliotek`'s wishlist cards and the owner's `/onska` rows
  show `99 kr · Bokus` + `REA` + the worded check date, a price not seen today
  shows its date and "kan ha ändrats" and NEVER a badge, and no observation
  renders NO element at all; the deep-link is derived by the server from the
  stored isbn (no stored URL column, no query param), and read-year cards are
  never handed price data — measured byte-identical to the pre-M9a page
  (`/bibliotek` and `/` anonymous and logged in, 2 621 / 2 911 / 3 518 B).
  Suite **647 passed, exit 0** (VM350 `.venv`, `-p no:cacheprovider`, 138 s):
  41 door legs, 13 badge legs, 12 display legs, 66 new in all. PLANTED RED, one
  per gate this card added — the date clamp, the price bounds, the wishlist
  resolve, the byte budget, the row budget, the Content-Length rule, the
  TOKENLESS membership itself (red as the CSRF 400), the G1 flag, the
  floor-skips-suspect rule, the badge CLOSE (`lit = True`: day 13 of leg 2
  stayed lit, `..........BBB.B` where the contract says `..........BB..B`), the
  template's badge/stale/no-observation gates, both read-scope filters and the
  `/onska` duplicate branch — every one red on its own leg first; transcripts on
  the card. Two of those reds are the reason to plant: the first ghost-price leg
  stayed GREEN under the mutation (the ghost's own event kept the simpler series
  lit) and was rewritten with a closing 200 in it; and the full-suite run caught
  a fourth `/onska` render that had no price map at all.
  A THIRD red came from OUTSIDE the suite and is the one worth carrying: the
  card's own `scripts/exposure_check.py` run printed 0 and looked green, because
  the gate greps the TRACKED universe (`git grep`) and the new test files were
  still untracked — after the commit it went red on ONE literal, a plausible
  978-91 isbn in `tests/test_pris_door.py`'s unknown-isbn leg that was in fact a
  REAL wishlist ISBN off `liselott-data/real-isbns.txt` (read by instrument only,
  never echoed). Cured here: that isbn is now an instrument-chosen 979-prefixed
  synthetic (a prefix this diary never carries), the leg re-proved red-capable
  against a build that lands any isbn, and the rule is in the leg's docstring —
  "synthetic-looking" is not synthetic, the list is the oracle, and the exposure
  gate must be run STAGED, never on an untracked tree.
  HONEST LIMITS: no fetcher ships with this card, so `price` is empty on a fresh
  site and production cards render exactly the price-less page until M9a-2
  installs the daily pass (README §Known limits); a holder of the credential can
  still backdate by ≤ 2 days — §6e's window is the mitigation, the residual is
  named, not fixed here; §6e's response envelope names no key for an isbn that
  matches several rows, so the door resolves MIN(id) of the wishlist rows and
  counts it accepted (the ambiguity has no home in the pinned shape, inventing a
  counter would be inventing contract); the display legs are anchored to today's
  UTC date and a run straddling midnight needs a re-run (stated in the file); and
  the design-pinned subtitle shipped verbatim under a named open question —
  the owner ruled the wording the next day (MC 12546 below: the pinned
  string carried a typo; the fix and its marker are there).
  Nothing pushed; the live DB and `liselott-data` untouched.
- **MC 12546 M9a-1b — the dedicated price-door token + the badge wording —
  DONE (this commit):** two owner rulings of 2026-11-15. (a) The `/pris`
  door's credential is no longer the owner's site session: `POST /pris`
  reaches its route WITHOUT a session (the guard's door allow is
  method-exact, `auth._is_pris_door` — every other method keeps the uniform
  302 and no other route joins any allow-list), and THE DOOR does its own
  credential check FIRST, before the envelope rules and before any body
  parse: header `X-Pris-Token` vs env `PRIS_DOOR_TOKEN` (read per request,
  the app's env idiom) under `hmac.compare_digest` over UTF-8 bytes —
  constant-time, byte-exact; env unset or empty ⇒ 503 fail-closed for EVERY
  POST, the owner's session included (unset never means open — the shipped
  default until M9a-2 wires the runner env); wrong or absent ⇒ 401, ONE
  uniform copy, no absent-vs-wrong oracle. A valid owner session still
  posts WITHOUT the token (her own tools ride the session she already
  holds). Her password is copied nowhere and rotating the door key is set
  new env + restart. Foreign Origin still 400s AT THE GUARD with a valid
  token; CSRF-tokenless posture, budgets, windows, UPSERT, suspect flag and
  counters unchanged (docs §6e re-ruled for the credential leg only, marker
  inline). The three exhaustive sweeps keep sweeping `/pris` under the NEW
  posture: `test_guard` (GET 302 in OWNER_ONLY + the disarmed POST answered
  503 in the configured sweep), `test_public_read.WRITE_ROUTES` (`/pris`
  now 503 disarmed), `test_ingest_vocab` (the 411 door loop, reached through
  an armed door + owner session). (b) The REA badge subtitle is "Lägsta
  pris på 90 dagar" (the v2.4 design pin carried a typo; owner string quoted
  in README) — `_bokkort.html`, the two display legs and both docs lines
  updated, the docs PINNED notes kept with dated owner-ruling markers,
  repo grep for the retired string = 0. Suite **653 passed** exit 0 (VM350
  `.venv`, `-p no:cacheprovider`, 149 s): 47 door legs — the 40 kept from
  M9a-1 all MIGRATED to the runner posture (token stamped, no session)
  beside 7 new credential legs (the retired anonymous-POST-302 leg became
  the GET-uniform-302 leg; 651 was the DoD floor). PLANTED RED, one per new gate (`.tmp/m9a1b-planted-red.md`):
  the 503 fail-closed, the 401 refusal, the byte-exact compare
  (`startswith` mutant), the session carve, the POST-only guard allow and
  the disarmed-owner leg. `scripts/exposure_check.py` run STAGED: 0, exit 0
  (tracked universe; the instrument-checked 979-prefix rule held — no new
  13-digit fixture value entered the tree). Nothing pushed; live DB and
  `liselott-data` untouched.

- **MC 12547 M9a-2a — the daily pris-vakt RUNNER (Bokus-only, the tick's
  mechanics) — DONE (this commit):** `scripts/pris_vakt.py` (stdlib +
  playwright only) drives the tick exactly as the MC 12540 sweep MEASURED it:
  scope from the app's OWN public `/bibliotek` "Att läsa" section (§2, ALARM
  + non-zero on `section_missing`/`empty_section`/`isbn_shape`/`fetch_failed`
  — a failed scope read is never a silent green), per-id ISBN GETs at the
  0.5 s own-origin courtesy (302/404 = the benign `gone`, no dt = the legit
  `no_isbn`), ≤ 250 asks with the excess FIFO-CARRIED by wish age (§3 v2.4),
  then per book one reused browser: goto ≤ 15 000 ms, the SELECTOR WAIT
  `text=Lägg i varukorg` ≤ 15 s (never a sleep), the serialized hydrated DOM
  through the PURE parser, ≥ 5 s + jitter before EVERY Bokus visit, and the
  door POST flushes every `PRIS_FLUSH_EVERY = 25` rows AND once at tick end
  (§6e's 500 cap never approached; door 503/401/unreachable = ONE try then
  loud, no retry loop). `PRIS_DOOR_TOKEN` + `LISELOTT_URL` are the ONLY env
  names (values never here — MC 12546: her password is copied nowhere), the
  pin boots `~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome` by
  explicit `executable_path` and a launched version not starting `153.` is
  ALARM + non-zero with ZERO asks, and the elapsed-budget stop exits
  non-zero at 6 600 s — 10 min BEFORE §6a's TimeoutStartSec=7200, whose
  printed math (250 × (5 s + 15 s) ≈ 5 100 s) rides in the header.
  `scripts/pris_parse.py` is the pure five-class parser (bytes in, class +
  price out, no I/O): PRICE = identity-OK + cart leaf + EXACTLY one token
  1..20000 in the FIRST token-bearing ancestor (measured `div.mt-5.flex.
  flex-col.gap-5`; NBSP normalized BEFORE tokenizing; script/style text
  never visible), TWO+ tokens = AMBIGUOUS (the named campaign expected-miss,
  never a posted price), no leaf + identity OK = FORMAT (e-bok/ljudbok — no
  fallback-to-another-number path), identity fails = NOT-CARRIED (the title
  tail `| Bokus` + `/bok/` URL are the ONLY gates — measured: not-found
  answers HTTP 200, a status branch is dead code), and NO-PRICE is the one
  unexpected-parse class. THE READING THIS CARD FIXED (from the sweep's 0/6):
  the N=3 consecutive stop AND the 7-day chronic escalator key on NO-PRICE
  ONLY — the measured shelf answers NOT-CARRIED/FORMAT for 5 of its 6 books
  PERMANENTLY, and any wider key cools the watch down every single day.
  `scripts/pris_state.py` owns the four StateDirectory files: `watch_state`
  (N=3 auto-stop reason self-clears when its cooldown passes; §6c's
  owner-stop stands until she resumes), `cooldown_until` = now + 24 h
  (a resting tick asks NOTHING, exits 0, `vilar=` in the summary), the
  FIFO `carry_over`, and `parse_fails.json` (3 distinct NO-PRICE days in 7
  ⇒ ESCALATE naming the isbn); `tree_rss_kib` is the runner's own-tree peak
  line — §6a's first-tick CGROUP row stays OWED by the real tick (M9a-2b).
  `tests/test_pris_vakt.py` adds 43 legs over synthetic fragments and faked
  seams (zero network — the first REAL Bokus visit is M9a-2b's): the five
  classes each named + NBSP + bounds (0 / 20001 reject, 20 000 accept with
  the thousands space) + title-tail-only gate catching a planted 200-page,
  and flush-at-25, budget stop (banks + carries), N=3 writes+honors+
  self-clears the cooldown, scope-empty ALARMs with ZERO boots, FIFO carry
  past 250 (carried 10 asked FIRST next tick), version-ALARM (fake 148 ⇒
  zero asks), pacing ≥ 5 s on the injected clock. PLANTED RED: 28/28 gates
  went red on their own named leg, one mutant at a time with sha-verified
  restore (`.tmp/m9a2a-planted-red.md`; one belt-not-a-gate annotated GREEN
  honestly). Suite **696 passed** exit 0 (VM350 `.venv`,
  `-p no:cacheprovider`, 146 s): 653 kept + 43 new. The real network leg
  is NOT this card — conftest.py untouched, no live DB, `liselott-data`
  untouched. `scripts/exposure_check.py` run STAGED: 0, exit 0 (tracked
  universe; every fixture isbn is 979-prefix synthetic). Nothing pushed;
  the sweep DOMs under `.audits/` never entered the repo or a fixture.


- **MC 12549 M9a-2a-fix — the healthy zero-price run is a SUMMARY fact, not
  an ALARM (owner ruling 2026-11-15, option 1 verbatim: "alarm only for
  real failures").** The shelf legitimately holds ~0 readable Bokus prices
  and a nightly alarm trains everyone to ignore real alarms, so
  `scripts/pris_vakt.py` drops the zero-store red clause and the
  `ALARM noll prisrad` line: a healthy complete tick exits 0 (journald
  INFO) and the summary carries the fact visibly — `stored 0 av N kollade`
  replaces the `stored=N` token. EVERY true-failure ALARM stays VERBATIM:
  scope errors (section_missing/empty/fetch_failed/isbn_shape), pin and
  version mismatch, door 503 + the rejected_* counters (a flush that
  delivered real rows without acceptance stays red — §6e counts every
  non-accepted row), the N=3 stop and the chronic escalator; an uncaught
  crash is still a traceback + non-zero exit. Tests: the zero-store leg
  re-written as `test_healthy_zero_price_run_is_summary_not_alarm`
  (summary shows `stored 0 av 2 kollade`, no ALARM line, exit 0), the
  chronic-blind-proof leg now asserts the whole tick green, the two
  `stored=` token pins re-aimed at the Swedish clause — every other alarm
  leg untouched. PLANTED REDS 3/3 (.tmp/m9a2a-fix-planted-red.md, one
  mutant at a time, sha-verified restore): muting the stored clause from
  the summary ⇒ healthy-zero RED; empty_section slipping the scope check ⇒
  its alarm leg RED; the rejected_* accumulation muted ⇒ door-rejected
  RED. Suite **696 passed** exit 0. `scripts/exposure_check.py` run
  STAGED: 0, exit 0; secret_scan --range clean. Nothing pushed; docs/ §3
  zero-price line + rule-4 pointer carry the dated ruling marker
  (host-local, untracked); conftest untouched, no real data, no network.
- **MC 12551 M10 — the public shelf's filter row + search (owner 2026-11-15,
  verbatim: "The public page needs filter by score, year, search by author,
  title and year").** `GET /bibliotek` gains `?betyg=1..5&ar=YYYY&q=<text>` for
  the ANONYMOUS reader — ONE calm GET-form row above the shelf
  (`app/templates/_publik-filtrering.html`: two selects + a search box + a
  submit, plain HTML, no JavaScript, no new design tokens, `contrast_check`
  PASS) — and `app/filtrering.py` owns the rules: the params combine with AND,
  an INVALID value is the ABSENT value (the calm public shelf, never a 500),
  and every narrowing is a SUBTRACTION from the rows the ONE public filter
  already returned (`books.load_books(public_only=True)` under
  `books.PUBLIC_SET_SQL`, MC 12501) — the module runs NO query of its own, not
  even for the year list the form offers, so a filtered page can never be
  wider than the public set. `ar` is the shelf's own year (the `read_year` the
  section heading shows — `books.shelf_year`, F-A2's guarded int, extracted from
  `group_for_shelf` so grouping and filter read the SAME year); `q` is TITLE OR
  AUTHOR with §7's `text.fold` on both sides (åäö- and case-safe), a substring
  test over rows in hand and NOT a SQL LIKE, so `%`, `_`, `*`, `?`, a quote and
  the word ESCAPE are literal characters by construction; the wishlist is
  narrowed by `q` ONLY (it carries no rating and no read year — the ruling made
  it public as it is, so no `betyg`/`ar` speaks for it and none can leak it).
  The OWNER is never filtered: `_publik_filtrering()` returns None for a
  session, her params are inert, so MC 12501's "her view changed NOTHING" and
  MC 12522's landing==shelf byte equality both still hold.
  BYTE IDENTITY, measured on `6d4d576` BEFORE the first edit and pinned (the
  MC 12522 idiom): anonymous `/` unchanged (raw 2911 B, normalized 2874 B /
  sha 56780752…), owner `/` and `/bibliotek` unchanged (raw 4313 B, normalized
  4276 B / sha fedfe610…), and anonymous `/bibliotek` is the pinned base page
  (normalized 2584 B / sha fb5269d1…) plus EXACTLY one 822-byte form row —
  deleting that `<form>` reproduces the base bytes byte for byte. The
  stylesheet's `?v=<APP_VERSION>` cache key IS the commit (T4.4), so the pins
  normalize that one token and pin everything else literally; the pins are
  whitespace-exact by construction (`bibliotek.html` gained one include line,
  its prose folded into the pre-existing comment, and the partial's TRUE render
  ends at `</form>` so the strip-leg is clean).
  Tests: 18 new legs in `tests/test_public_filter.py` — the three byte pins
  (landing, shelf-plus-form-row, owner-inert), the params one at a time, the
  AND-combination, the calm "Inga träffar" state without the owner's empty-diary
  chrome, the wishlist rule, the year-`<option>` list read off the public rows
  only, no-private-name-under-any-param (typed/folded/cased, non-vacuity
  pinned), the betyg×year×q FUZZ asserting every rendered card is a public id
  (≥20 cards painted, so the loop cannot pass vacuously), the wildcard/quote
  literals over BOTH metacharacter dialects + the escaped q-echo, the
  invalid-param calm legs, HEAD/write sweeps with params on, and the owner's
  `/sok` untouched. PLANTED REDS 7/7 (.tmp/mc12551-planted-red.md, one mutant
  at a time, sha-verified restore, green pair after each): matcher turned
  fnmatch wildcard ⇒ wildcards leg RED (the first attempt at that leg named only
  SQL-LIKE metacharacters, which fnmatch treats as literals — it stayed GREEN,
  so the leg was strengthened before it counted); `public_only` dropped on the
  q path ⇒ leak legs RED; `public_only` dropped on the ar path ⇒ year legs RED;
  wishlist-q dropped ⇒ wishlist/empty-state legs RED; year list from a
  table-wide query ⇒ year-option leg RED; the landing's shelf include removed ⇒
  landing pin + MC 12522 legs RED; betyg clamp widened to `\d+` ⇒ invalid-param
  leg RED. Suite **714 passed** exit 0 (696 before + 18 new).
  `scripts/exposure_check.py` run STAGED: 0 findings, exit 0;
  `secret_scan.sh --range origin/main..main` clean. Nothing pushed.
  conftest untouched, `liselott-data` untouched (synthetic fixtures only, the
  979-isbn rule), no network, routes.py back to 400 lines.
- **MC 12570 pris-vakt transport — curl-subprocess, urllib RETIRED (measured
  live, first manual tick 2026-11-16 06:19: scope GET "bibliotek 403" —
  Cloudflare refuses python-urllib, curl's default UA passes the edge; the
  fleet's known CF fact).** The two plain legs (scope GET §2 + door POST §6e)
  now ride the new `scripts/pris_vakt.py::_curl`: argv list, never
  `shell=True`, curl's DEFAULT UA, `--max-time` 15 (GET) / 30 (POST) with a
  hard subprocess watchdog at ceiling + 5 s, POST body `--data-binary @-` on
  stdin, status off `--write-out`, body to a temp file. Return shape and
  exception mapping byte-for-byte unchanged (non-2xx rides an empty body /
  `{}` like the old HTTPError, transport failure is status 0), so the alarm
  path PROVED by that 06:19 tick (`scope_error=fetch_failed ... (bibliotek
  403)`, exit=1) stands — a new leg pins the exact line. urllib is deleted
  whole (no caller would remain — the unit's transport surface is the
  `run_tick` get/post seams, untouched); the browser leg is unaffected. The
  docstring line that named the urllib era now names the measured CF fact +
  date; a header comment carries the >400-line reason (the card's diff scope
  pinned the transport beside its two mapping legs). New legs
  `test_default_transports_ride_curl_argv` (argv shape: curl first, url
  last, no shell, max-time 15/30, watchdog, body on stdin) and
  `test_curl_403_keeps_the_fetch_failed_alarm`; PLANTED REDS 3/3
  (.tmp/mc12570-planted-red.md, sha-verified restore): max-time pinned 30 =>
  argv leg RED, `@-` broken => argv leg RED, status flattened to 200 => 403
  leg RED. Seam-leg rewrites ZERO — all 24 runner legs flow through the
  seams unchanged. Reading stated: the card pins the GET ceiling at 15 s
  (urllib ran 30) — GET tightens per the card's explicit ceiling. Suite
  **715 passed, 1 failed** (716 collected, 714 before + 2 new): the one RED
  is the PRE-EXISTING clock-window leg
  `test_pris_door::test_g1_compares_the_day_before_never_the_same_day` —
  module-level `NU - timedelta(hours=8)` is only "today" when the wall clock
  is ≥ 08:00 UTC, so it goes RED 00:00–08:00 UTC; measured RED at 06:3x UTC
  on the UNTOUCHED base (07fb9c4) and GREEN in the afternoon — out of this
  card's diff scope, reported not silently fixed. `scripts/exposure_check.py`
  run STAGED: 0 findings, exit 0; `secret_scan.sh --range origin/main..main`
  clean. Nothing pushed. conftest untouched, `liselott-data` untouched,
  no real data, no network in any leg.
- **MC 12571 de-time-bomb — the G1 day-pair leg, green at every hour.**
  The clock-window leg MC 12570 reported is FIXED: its earlier half was
  stamped eight hours off the module `NU`, which the door read as YESTERDAY
  every 00:00–08:00 UTC, turning the same-day re-ask into a real G1
  comparison (inserted+flagged where updated+clean is the contract). The
  leg's day pair now comes from ONE clock read at leg start, the earlier
  half anchored by the new `tidigare_samma_dag` helper — same UTC date at
  its earliest second, `replace` cannot cross the date boundary. The same
  bomb class sat in `test_door_upserts_a_same_day_re_ask_into_one_point`
  (`NU − 6 h`, red before 06:00 UTC) — same file, same anchor, fixed in
  this commit. `app/pris.py` UNTOUCHED: the freeze seam `ingest(now=…)`
  already exists, but these legs ride the HTTP door, which never passes
  `now`, and the card's first reading (single clock read) wins — zero
  production change, no new seam, so no default-unchanged leg is owed.
  Measured RED at 06:5x UTC on the untouched tree, GREEN at the SAME wall
  clock after. Door file 47/47 green under TZ=UTC AND TZ=Europe/Stockholm;
  suite **716 passed** exit 0. `scripts/exposure_check.py` run STAGED:
  0 findings, exit 0; `secret_scan.sh --range origin/main..main` clean.
  Nothing pushed. conftest untouched, synthetic 979-isbn data only,
  `scripts/pris_vakt.py` untouched (the live tick's file).
- **MC 12597 M11-N4 — the app side of "AI rekommenderar" (design MC 12590
  PLAN).** DONE (this commit): `ai_rek` table (idempotent CREATE, the price
  idiom, rec_key UNIQUE = isbn13-else-seed.book_key, state new/accept/
  decline CHECK + declined_at); `app/ai_rek.py` = the fifth machine door
  POST /ai-rek (the /pris posture verbatim + AI_REC_DOOR_TOKEN 64-hex
  ENFORCED — a malformed armed env is the DISARMED door 503; one uniform
  401; owner session rides tokenless; GET keeps the uniform 302; auth joins
  TOKENLESS_POSTS + `_is_ai_rek_door` POST-only) + accept/decline owner
  POSTs (guard+CSRF, the /djem pattern) + `onska.skapa_onska` — ONE wish
  writer, two callers, the lagg-till POST contract byte-identical; the
  upsert NEVER touches accept/decline rows (kept_* counters — declines
  never resurface, door-side); the page gains the "AI rekommenderar"
  section (fit DESC, empty-state line). MOVED OUT of routes.py: the rec
  page + /djem (pure move, endpoint names stand) — routes.py 376 lines
  (<=400), and the F-3 slash rule for /rekommendationer MOVED with the
  view because url_for builds the FIRST rule of an endpoint: registered
  beside the old loop it flipped every rendered nav URL to the slash
  spelling and the MC 12551 byte pins went red (measured +1 byte on the
  owner pages); with the rule under the view the owner landing re-dumped
  BYTE-IDENTICAL against a HEAD worktree. PLAN deviations, each named:
  schema columns per the card (isbn13/author_name/fit REAL [0,1] enforced
  door-side + declined_at, not PLAN's isbn/author/rank); fit DESC not rank;
  one test file (tests/test_ai_rek.py, 20 legs) not PLAN's two, and
  test_no_leak.py untouched (the leak legs ride the new file: zero
  "AI rekommenderar" bytes in every anonymous answer, positive owner-page
  leg, both lists, fit DESC); the §d full-replacement sweep NOT built (the
  card's ingest DoD names upsert-only — a DELETE no caller of this card
  issues is a mechanism waiting for a spec); no app.css lines (existing
  classes cover the section); accept COMMITS the state flip BEFORE the
  writer (the writer owns its commit/rollback — flipping inside its txn
  would let the UNIQUE rollback undo the flip); runner scripts (§e) are
  another card, app side only here. PLANTED-RED: the kept_* branch, the
  accept state-guard, the writer's "redan" collision, the 64-hex arming and
  the guard's door term each went RED on its named leg and green after
  restore (map in the test file's docstring). Suite baseline BEFORE the
  work: **716 passed** (`pytest -q`, the repo .venv; system python3
  carries 4 pre-existing raw-socket failures — not this card's tree
  state); after: **736 passed** exit 0 (716 + 20 new, zero regressions),
  incl. the MC 12551 byte pins. `scripts/exposure_check.py` run STAGED:
  0 findings exit 0. Nothing pushed. docs/ left untracked (untouched).

- **MC 12597 fix-wave — the MC 12602 DA-gate verdict FIX, repaired in one
  commit (2026-11-16).** All six shipped-side findings, each with new legs
  (tests/test_ai_rek.py 20→29, tests/test_no_leak.py +1 × 2 corpus cases)
  and a planted-red run per new gate (map in the test file's docstring):
  F-P1-1 (decline-permanence was keyed on the INGEST identity) — the upsert
  now matches the whole BOOK identity via `_bok_rad`: the UNIQUE rec_key,
  the isbn lane, and the §5.3 title+author key through the new
  `onska.wish_key` (split_authors + app_aliases + seed.book_key — the
  normalization seed.py §5.3 names, cited; ONE identity implementation, two
  callers, the door's "same book" IS the wish's); a decided row wins the
  match on any lane and stays untouched, later `new` twins merge.
  F-P2-2 — `skapa_onska` runs THE §7 mechanism `search.normalize_isbn` on
  the accept path's isbn (check-digit failure = NO isbn = NULL, never the
  machine's token into book identity); /lagg-till byte-identical (it never
  passed an isbn to the writer). F-P2-3 — accept runs the writer FIRST, a
  raise is a named 400 with state 'new' and the retry works, the flip (own
  `state='new'` guard) lands only after the writer succeeded. F-P3-6 — the
  disarmed-door copy is generic; the leak leg asserts zero `ai[- ]?rek`
  bytes in the anonymous 503. F-P3-7 — the INSERT rides
  `ON CONFLICT(rec_key) DO NOTHING` + re-ask (the /pris race posture); the
  leg forces the check-then-act interleave with a barrier and pins one row,
  two 200s, zero exceptions. F-P4-1 — schema bakes
  `fit REAL CHECK (fit BETWEEN 0 AND 1)` + `kategori TEXT CHECK IN
  (nyhet,klassiker,blandad)` (the table has never been live → baked fresh,
  no migrate.py entry owed), kategori rides the ingest door-gated by
  KATEGORIER; README gained the AI_REC_DOOR_TOKEN env row, the machine-door
  bullet and the guard-paragraph pair; the `.ai-rek` classes KEPT and given
  three calm palette-var rules (decision stated, VERSION 2026.11-4).
  Interpretation: for a DECIDED matched row "update" reads as count kept_*
  and leave untouched — the card's own DoD line "NEVER overwrites an
  accept/decline row"; only `new` matches refresh. Runner-side findings
  F-P2-4/F-P2-5 are MC 12601's, untouched here. Suite: before **736**,
  after **747 passed** exit 0, zero regressions (incl. the MC 12551 byte
  pins). `scripts/exposure_check.py` run STAGED: exit 0. Nothing pushed.
  docs/ left untouched.

- **M11-N5R generation runner** (MC 12601, 2026-11-17) —
  `scripts/ai_rek_pass.py` + the shared `scripts/curl_transport.py`:
  MC 12570's `_curl` moved VERBATIM (AST-slice byte-diff vs HEAD: identical)
  into the ONE transport both door runners now ride; `pris_vakt` rebinds to
  import it (382 lines — the >400 header reason retired with it; its test
  patch-surface moved with the function, all pris legs green). The runner:
  `--corpus` loads the 13-column N1 corpus.tsv (header/isbn/year/category
  shape pinned; duplicate-isbn ACROSS books refused at load — the N3 merge
  lane can never run on its input; C0/C1 control chars kill the corpus at
  load — carry N5), `--library` GETs the PUBLIC shelf through the shared
  transport and grades it with the NEW `pris_parse.read_graded` (221 graded
  cards measured off the served page = the owner-scope count exactly), joins
  via the app's ONE identity (`onska.wish_key` = the §5.3 seed.book_key
  chain; the shelf's cards carry no isbn, the wish_key lane is what bites),
  asks Lane E ONE cover_pass-shaped call (one model id, temp 0, reasoning
  low both layers; max_tokens 12000 after the measured 6000 reasoning-death:
  empty content, gate refused, zero POST), strict-parses (prose / fence /
  dict / truncated = refused, exit 3, ZERO door calls), and gates IN CODE:
  returned isbn outside the loaded corpus => row REJECTED (carry N3 cited),
  fit bool/non-finite/outside [0,1] => REJECTED, never clamped (`_obs`
  parity), best-row-wins dedupe by isbn ∪ wish_key BEFORE POST (carry N1 —
  fired on a real corpus twin in the demo), control-char belt on the
  payload (N5), kategori (nyhet|klassiker|blandad, mapped from the corpus'
  classic/new_release/mix) on EVERY row, <20 accepted => refuse loud (a
  thin generation is a failed generation), ZERO graded rows => refuse
  BEFORE the lane (MC 12602 scope row 2). Delivery POST {base}/ai-rek on
  the shared transport, `X-Ai-Rek-Token` from AI_REC_DOOR_TOKEN asserted
  against the DOOR's own `TOKEN_SHAPE` (64-hex; the value never echoed —
  pinned by its leg); `--dry-run` prints and POSTS NOTHING (socket-guarded
  leg). DOCUMENTED, NOT BUILT: MC 12602 scope row 1's full-replacement
  sweep — the door has NO delete verb (`ingest` is upsert-only, no route
  retires a state='new' row), so rows absent from this generation survive
  on the page; DELETE-by-absence needs a door route that does not exist,
  and this card forbids app code (gap named to the orchestrator). Carries:
  N2 decline-flip is app-side P3, unreachable from the single-writer
  runner; known limit MEASURED live — the corpus' subtitle-tailed titles do
  not unify with the shelf's plain titles through wish_key (the alias table
  is the app's ONLY spelling mechanism; NO second normalizer added). LIVE
  dry-run demo 2026-11-16 (printed in the card result): real corpus.tsv vs
  REAL public shelf + REAL Lane E — 26 rows, 1 owned book dropped by
  wish_key, 25 candidates ranked to 24 (one twin deduped), fits descending
  in [0,1], all three kategorier riding, INGET POSTAT (dry-run guard +
  token env absent, belt on top of braces). Tests:
  `tests/test_ai_rek_pass.py` 16 offline legs (join-drop / hallucination /
  hostile-JSON×5 / fit-domain / dry-run-socket-guard / taste-empty /
  twin-dedupe / control-chars×2 / isbn-dup / floor / door-argv-shape /
  token-echo) + ONE live-optional skipped by default;
  `tests/test_pris_parse.py` +2 `read_graded` legs. Planted-red: 9 mutants
  (one gate condition forced off at a time) each went RED on its named leg,
  green on sha-verified restore. Suite: before **747**, after **765 passed
  + 1 skipped** exit 0, zero regressions (pris legs included).
  `scripts/exposure_check.py`: **0 findings exit 0** — it CAUGHT a real-
  book collision in the first synthetic isbn lane; the lane now rides the
  invalid ISBN group 9999 (the gate's red-proof, in passing). Nothing
  pushed. docs/ left untouched.

- **MC 12601 c3 FIX-WAVE (DA-verdict-c3) — EVIDENCE CORRECTION + mix gate +
  belt (2026-11-17).** CORRECTION (DA F-P2-1, re-verified by this seat's
  own run before writing it): the M11-N5R line above claims the live demo's
  25->24 was `one twin deduped by identity` / `fired on a real corpus twin`
  — **CONTRADICTED, retired by this line**: the pinned corpus.tsv carries
  ZERO identity twins (26 distinct wish_keys AND 26 distinct isbns; dedupe
  over all 26 rows drops 0 — DA probe6 reproduced here), so the `REK
  DUBLETT bort` the demo printed was the MODEL ECHOING one candidate row
  twice inside its own answer, caught by the OUTPUT dedupe — the N1 guard
  works (fixture legs green), the ATTRIBUTION was false; the c3 re-run of
  the live demo echoed the same row again (same REK DUBLETT line), fitting
  the correction exactly. SUPERSEDED with it: the `alias table is the app's
  ONLY spelling mechanism` repair sentence (DA F-P2-2c) — seed.book_key
  alias-resolves AUTHOR names only, titel is never looked up (probe3), so
  it can never repair a title misspelling, and the table is NOT empty (15
  off-repo entries); the working repair is data-side (MC 12617 shelf-exact
  corpus rebase). The old line is kept as versioned truth, never rewritten.
  ADDED by this wave (same commit): (2) the MIX GATE — output without >=1
  nyhet AND >=1 klassiker REFUSES the generation, exit 6, ZERO POSTs (owner
  scope, the owner's own words: `newly released books as well as classics`);
  legs nyhet-only-refuses / klassiker-only-refuses / mixed-rides; live demo
  re-run: real output 10 nyhet + 9 klassiker + 5 blandad rides, exit 0,
  INGET POSTAT. (3) belt F-C3-1 (tester's L11): `by_isbn` is now the
  OFFERED set — an isbn naming a corpus row the join DROPPED as owned is
  refused post-parse even when the model names it back (leg
  test_owned_book_named_back_is_refused; planted-red: gate forced off =>
  2/2 mix legs + the belt leg go RED, sha-verified restores). (4) hygiene:
  ai_rek_pass.py carries the proper header size reason (468 > 400, one-
  gate-chain rationale) — stated call: REASON, not split (splitting would
  scatter the one-path guarantee; tests file 443 lines <= 600). The
  token/`--config` argv finding is NOT this wave's (moved to MC 12616,
  both callers). Suite: before 765+1skip, after **769 passed + 1 skipped**
  exit 0, zero regressions. exposure_check 0 findings exit 0. Nothing
  pushed. docs/ left untouched.
- **MC 12616 M11-N8a — the /ai-rek door full-swap + the token out of
  argv (2026-11-17)** — `POST /ai-rek` gains the OPTIONAL full-swap
  envelope `{"generation": [ …rows… ]}` (PLAN §d completion): the POSTed
  list IS the complete new generation and `_sweepa` deletes the
  state='new' rows whose identity is ABSENT from it — identity is THE
  SAME union the fix-wave matcher `_bok_rad` matches on, extracted
  verbatim as `_samma_bock` (ONE mechanism, two callers — no second
  "same book" rule was written). accept/decline rows are NEVER deleted:
  two belts, the sweep SELECT scopes to `state='new'` AND the DELETE
  re-guards it (each single removal stayed GREEN — the red mutant had to
  take BOTH out, `test_full_swap_never_deletes_accept_or_decline_incl_identity_variants`
  then goes red). An EMPTY generation is REFUSED fail-loud (400
  `EMPTY_GENERATION`, rows kept) and the belt stands inside ingest too:
  zero VALID identities sweep nothing (500 shape-garbage rows retire
  nothing, `rejected_shape` answers loudly). The answer gains `deleted_n`
  ONLY in full mode; mode-off is byte-identical (all 29 existing door
  legs green UNTOUCHED). Runner: `--full` (DEFAULT off) sends the
  envelope; the door posture is unchanged behind the envelope (disarmed
  503 / uniform 401 / uniform 302 legs ride both payload shapes).
  TOKEN OUT OF ARGV (DA c3 P2, the reproduced /proc/<curl>/cmdline
  leak): `curl_transport._curl_config` writes the secret headers to a
  per-call `mkstemp` 0600 file, curl reads them via `--config @<path>`,
  the file is unlinked in the finally and the content is never echoed;
  the AI-rec door post rides it — ZERO token bytes (not even the header
  NAME) reach the child's argv, leg-proved against the LIVE
  /proc/<curl-pid>/cmdline of the execed child (the leg first
  reproduced the leak verbatim RED on the old shape, then gated it
  GREEN). pris_vakt keeps its header-as-argv path byte-identical —
  `_curl`'s signature is unchanged (stated reading: the card pins that
  caller's behaviour; the shared mechanism is the transport MODULE, one
  transport with two call shapes, its legs green). BONUS (DA c4 P3):
  lane ask budget default 300 → 600 s + `--lane-timeout` flag. RETIRED
  CLAIM rewritten the same commit: the runner's "the door supports NO
  delete verb" KNOWN-LIMITS paragraph (grep-to-zero). Docs: README door
  section carries envelope + deleted_n + `--full` + `--lane-timeout` +
  transport lines. Suite: before 769+1skip, after **782 passed +
  1 skipped** exit 0 (+13 net legs: 8 `tests/test_ai_rek_sweep.py`,
  3 `tests/test_door_transport.py` — split out at the 600-line test
  ceiling, fixtures imported — 3 `tests/test_ai_rek_pass.py`);
  planted-red map in the commit body. exposure_check 0 findings.
  Nothing pushed. docs/ left untouched.
- **MC 12616 c5 FIX WAVE (DA-verdict-c5, 2026-11-17, commit on top of
  `b7b5a86` — not amended, the verdicts pin that hash)** — CORRECTION,
  versioned truth (the row above stands, unrewritten): its
  "STATED READING: … the card pins that caller's [pris_vakt] behaviour"
  is VOID — DA c5 F-P2-1 read the board and the LEDGER: the card's 01:23
  append says "owns token-argv fix (DA c3 P2)" and LEDGER:1079 moved the
  finding to MC 12616 "both callers"; no ruling ever pinned pris, and
  fleet law is a shared fix reaches EVERY caller. FIXED in this commit:
  `pris_vakt.door_post` now rides `_curl_config` too — byte-identical ON
  THE WIRE (same header name, same value), ZERO token bytes on the
  nightly tick's /proc/<curl>/cmdline; its weld leg was UPDATED RED-FIRST
  (`test_default_transports_ride_curl_argv`, the old `X-Pris-Token: <cred>`
  in-argv assert replaced by the config-file assertions) and the PRIS
  door got its own live-curl-cmdline leg
  (`test_pris_door_post_token_absent_from_the_live_curl_cmdline`, RED
  first with the token VERBATIM on the old shape). Minimal by design:
  N4b (MC 12606) retires pris_vakt wholesale per owner ruling — this
  closes the interval. F-P3-1: `_curl_config` now validates EVERY pair
  BEFORE any file exists — header name `[A-Za-z0-9:-]+`, value free of
  `"`, BACKSLASH (real curl expands `\`-escapes in quoted config values —
  DA measured a genuine wire-newline injection from a literal `\n`) and
  any non-printable; legs parametrized ×6 values + ×5 names with the
  mkstemp-boomer (a created file fails the leg). F-P4-2 (P4): the
  unlink is best-effort TWICE, a transient first failure neither raises
  nor strands the 0600 file (leg `test_config_unlink_is_best_effort_twice`);
  README names the config-file mechanism for BOTH doors (receipt hygiene,
  no paths with secrets). Retired reading grep-to-zero in LIVE prose
  (module docstrings rewritten; LEDGER/commit text keeps the history per
  the append-only convention). Mutants red→green sha-verified: pris back
  to argv-header → pris weld + pris /proc RED; guard backslash dropped →
  the two backslash legs RED; second unlink removed → residue leg RED
  (propagates); ai-rec door reverted → its /proc leg RED. Suite: before
  782+1skip, after **795 passed + 1 skipped** exit 0 (+13 net c5 legs:
  1 pris weld UPDATE + 12 new). exposure_check 0 findings. Nothing
  pushed. docs/ left untouched.
- **MC 12616 FIX-WAVE 2 (DA-verdict-c6 F-P1-1 P1, 2026-11-17, commit on
  top of `13a50b2` — not amended, the verdicts pin that hash)** —
  CORRECTION, versioned truth (the c5 rows above stand, unrewritten):
  their "byte-identical ON THE WIRE" — and the module docstring, both
  runner docstrings and the two test docstrings that repeated it — was
  asserted on FABRICATED curl results and was FALSE (DA c6 F-P1-1,
  measured): curl 7.81 silently IGNORES `--config @<path>` (the `@` form
  is include-syntax for INSIDE config files only), WARNs once and posts
  WITHOUT the header — 297 → 217 wire bytes on pris, ZERO header
  occurrences live on both doors; the /ai-rek door had been broken since
  b7b5a86, pris since 13a50b2. Doors failed CLOSED (uniform 401, exit
  5/1 loud, no leak, no data loss) — P1, not P0. THE FIX: the ONE site
  `build_args("@" + path)` → PLAIN `build_args(path)`; DA's own A/B
  proved the plain-form capture byte-identical (port-normalized) to the
  header-as-argv parent — the claim is TRUE of the fix and now held by
  the class the suite LACKED: REAL-WIRE delivery legs (local listener,
  raw capture, no fabricated curl): 
  `test_pris_door_delivers_the_token_header_on_the_wire`,
  `test_ai_rek_door_delivers_the_token_header_on_the_wire`,
  `test_config_delivery_is_wire_identical_to_the_argv_header_form`.
  RED-FIRST against the broken tree (raw capture printed tokenless),
  GREEN on the plain form; re-planted `@` after the fix turns both wire
  legs RED again. All five false claims REWRITTEN truthfully in live
  prose (curl_transport module+function docstrings, pris_vakt.door_post,
  ai_rek_pass delivery paragraph, both test-file docstrings + the weld
  comments — in-process legs now say SHAPE, wire legs carry ARRIVAL).
  F-P4-6: value guard gains `isascii()` BEFORE mkstemp (printable
  non-ASCII passed isprintable, created the file and wrote header #1's
  secret bytes before UnicodeEncodeError); parametrized legs `café` +
  the emoji refuse with mkstemp boomed (ZERO bytes). F-P4-7 honesty:
  the docstring now NAMED the crash class the double unlink cannot
  cover (SIGKILL between mkstemp and finally strands the 0600 file —
  HOUSEKEEPING: 5 pre-fix 0600 token tmpfiles sit in /tmp, stat-only
  observed by the DA and by me; the ORCHESTRATOR clears them separately,
  NOT this commit; signal-safe cleanup is a future runner card).
  F-P4-8a LANDED (carried twice): README names that `deleted_n` counts
  SWEEP deletions only, duppar-merge rows not counted. The THREE wire
  legs run the REAL production curl binary against a local listener —
  host evidence, not a fixture (the two guard params prove the zero-byte
  refuse with a boomed mkstemp). Mutants: `@` re-inserted → ALL THREE wire
  legs RED (sha-verified restore); suite: before 795+1skip, after
  **800 passed + 1 skipped** exit 0 (+5: 3 wire legs + 2 guard params).
  EXPOSURE CATCH PRE-COMMIT: the gate went RED on the test file — the
  DA probe3 template's dummy ISBN (prefix 978 + ten zeros — described by
  shape, never quoted, the value itself is a real line in the private
  real-ISBN list and stays out of tracked text) was carried into the two
  copied wire fixtures; swapped to `9781234567890` (gate-verified NOT on
  the list — no list content ever echoed), the legs re-green, exposure
  back to 0 findings. Then THIS row's own first draft quoted the value
  and the gate caught the LEDGER too — the gate caught exposures INSIDE
  MC 12616's own wave twice, pre-commit; that is the instrument working.
  Nothing pushed. docs/ left untouched.
