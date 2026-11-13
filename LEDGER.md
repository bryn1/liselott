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
