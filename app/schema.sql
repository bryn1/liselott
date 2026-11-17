-- Liselotts bokhylla schema — cycle-1 §5 DDL with the four PLAN-c3 §5 changes:
-- (1) dismissed keyed by TEXT key (P2-3), (2) book.tried_providers/enrich_fail
-- (F-2 evidence), (3) book.book_key NOT NULL UNIQUE (P1-3 upsert match key),
-- (4) candidate unchanged. Idempotent: every CREATE carries IF NOT EXISTS.
CREATE TABLE IF NOT EXISTS book (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, isbn13 TEXT, isbn10 TEXT,
  year INTEGER, format TEXT NOT NULL CHECK (format IN ('bok','ljudbok')),
  date_read TEXT,               -- ISO YYYY-MM-DD, nullable
  read_year INTEGER NOT NULL,   -- from seed section; wishlist rows use 0 sentinel
  rating INTEGER CHECK (rating BETWEEN 1 AND 5),   -- NULL = unrated
  notes TEXT,
  cover_path TEXT, cover_source TEXT CHECK (cover_source IN ('libris','googlebooks','openlibrary','manual','manual-url')),
  status TEXT NOT NULL DEFAULT 'read' CHECK (status IN ('read','wishlist')),
  book_key TEXT NOT NULL UNIQUE,   -- §5.3: sha256 key, the ONLY bundle-upsert match key
  tried_providers TEXT,            -- csv of provider names attempted, e.g. 'libris,ol,gb'
  enrich_fail INTEGER NOT NULL DEFAULT 0,
  created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS author (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS book_author (book_id INTEGER NOT NULL, author_id INTEGER NOT NULL, PRIMARY KEY (book_id, author_id));
CREATE TABLE IF NOT EXISTS author_alias (alias TEXT NOT NULL UNIQUE, author_id INTEGER NOT NULL REFERENCES author(id));
CREATE TABLE IF NOT EXISTS genre (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS book_genre (book_id INTEGER NOT NULL, genre_id INTEGER NOT NULL, PRIMARY KEY (book_id, genre_id));
CREATE TABLE IF NOT EXISTS candidate (id INTEGER PRIMARY KEY, title TEXT NOT NULL, author_name TEXT, isbn13 TEXT,
  year INTEGER, cover_path TEXT, cover_source TEXT CHECK (cover_source IN ('libris','googlebooks','openlibrary','manual','manual-url')),
  fetched_at TEXT NOT NULL);
-- RETIRED (MC 12606, M11-N4b; owner rulings 2026-11-16, verbatim: "Books on
-- sale can be removed. No interest in buying books." and "rea, om inte nu så
-- sen"): the price/sale feature is GONE — the /pris door, the card's price
-- line and the REA badge, and the nightly pris-vakt runner. This table is
-- KEPT VERBATIM, columns included: NO destructive migration, no DROP, no
-- rewrite of data she owns. Nothing in the app writes or reads it any more
-- (app/pris.py and app/priskort.py were deleted with this ruling), so the DDL
-- below is idempotent history for a re-opened question, not a live mechanism.
-- ── history (M9a-1, DESIGN-prisbevakning-v2 §1, verbatim DDL) ──────────────
-- The UNIQUE day index IS the dedup (no SELECT-then-INSERT anywhere), which
-- is what makes a same-day re-ask land in ONE history point; `book_id` was
-- ingest-resolved metadata and rides the one delete door (ON DELETE CASCADE).
-- `url` is GONE by design: the public deep-link was server-derived from
-- `isbn`, never client-supplied.
CREATE TABLE IF NOT EXISTS price (
  id INTEGER PRIMARY KEY,
  isbn TEXT NOT NULL,
  book_id INTEGER NOT NULL REFERENCES book(id) ON DELETE CASCADE,
  retailer TEXT NOT NULL CHECK (retailer IN ('bokus')),
  price INTEGER NOT NULL CHECK (price BETWEEN 1 AND 20000),
  currency TEXT NOT NULL DEFAULT 'SEK' CHECK (currency = 'SEK'),
  list_price INTEGER, campaign TEXT,
  checked_at TEXT NOT NULL,      -- ISO UTC (auth.utcnow_iso format)
  ok INTEGER NOT NULL DEFAULT 1 CHECK (ok = 1),
  suspect INTEGER NOT NULL DEFAULT 0 CHECK (suspect IN (0,1)));
CREATE UNIQUE INDEX IF NOT EXISTS ux_price_isbn_day
  ON price (isbn, retailer, substr(checked_at,1,10));
CREATE INDEX IF NOT EXISTS idx_price_checked ON price(checked_at);
-- M11 (MC 12597, design MC 12590): the AI-recommended category. One table,
-- the whole AI lifecycle; a rec is NOT a book until she accepts (then the
-- wish is its own row, §5.11). rec_key is the upsert match key, computed
-- DOOR-side: isbn13 when present, else seed.book_key(title,[author]) — so
-- "same book" means the same thing the bundle upsert means.
CREATE TABLE IF NOT EXISTS ai_rek (
  id INTEGER PRIMARY KEY,
  rec_key TEXT NOT NULL UNIQUE,
  isbn13 TEXT,
  title TEXT NOT NULL,
  author_name TEXT,
  year INTEGER,
  reason TEXT NOT NULL,
  source TEXT NOT NULL,
  -- MC 12602 F-P4-1: the fit domain baked into the table (the door already
  -- enforces it; this is the belt, and the cheapest form while the table
  -- has zero live rows — no live DB has ever baked the old shape, so no
  -- migrate.py re-create is owed) + the category the plan's §e output
  -- carries and the page must one day tell apart.
  fit REAL NOT NULL CHECK (fit BETWEEN 0 AND 1),
  kategori TEXT CHECK (kategori IN ('nyhet','klassiker','blandad')),
  state TEXT NOT NULL DEFAULT 'new' CHECK (state IN ('new','accept','decline')),
  ts TEXT NOT NULL,                      -- auth.utcnow_iso shape, SERVER clock
  declined_at TEXT);                     -- set by the ONE decline flip
CREATE TABLE IF NOT EXISTS dismissed (key TEXT PRIMARY KEY, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts (id INTEGER PRIMARY KEY, ip TEXT NOT NULL, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_book_title ON book(title);
CREATE INDEX IF NOT EXISTS idx_book_date ON book(date_read);
CREATE INDEX IF NOT EXISTS idx_book_year ON book(read_year);
