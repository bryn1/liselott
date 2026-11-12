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
  cover_path TEXT, cover_source TEXT CHECK (cover_source IN ('libris','googlebooks','openlibrary','manual')),
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
  year INTEGER, cover_path TEXT, cover_source TEXT CHECK (cover_source IN ('libris','googlebooks','openlibrary','manual')),
  fetched_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dismissed (key TEXT PRIMARY KEY, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts (id INTEGER PRIMARY KEY, ip TEXT NOT NULL, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_book_title ON book(title);
CREATE INDEX IF NOT EXISTS idx_book_date ON book(date_read);
CREATE INDEX IF NOT EXISTS idx_book_year ON book(read_year);
