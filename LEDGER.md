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
