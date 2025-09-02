SET search_path TO public;

-- Extensión para búsquedas por similitud (trigram)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =========================================
--  Tablas
-- =========================================

-- Tabla de editoriales
CREATE TABLE IF NOT EXISTS editorials (
    id   SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

-- Tabla de conferencias
CREATE TABLE IF NOT EXISTS conferences (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    series       TEXT,
    location     TEXT,
    editorial_id INTEGER REFERENCES editorials(id)
);

-- Tabla de ediciones de conferencia (por año)
CREATE TABLE IF NOT EXISTS conference_editions (
    id            SERIAL PRIMARY KEY,
    conference_id INTEGER NOT NULL REFERENCES conferences(id),
    year          INTEGER NOT NULL,
    booktitle     TEXT
);

-- Tabla de autores (mejorada)
CREATE TABLE IF NOT EXISTS authors (
    id                       SERIAL PRIMARY KEY,
    full_name                TEXT NOT NULL,
    publication_count        INTEGER DEFAULT 0,
    first_publication_year   INTEGER,
    last_publication_year    INTEGER,
    most_common_conference   TEXT
);

-- Tabla de artículos/papers
CREATE TABLE IF NOT EXISTS papers (
    id         SERIAL PRIMARY KEY,
    authors    TEXT,
    edition_id INTEGER NOT NULL REFERENCES conference_editions(id),
    title      TEXT NOT NULL,
    pages      TEXT,
    publisher  TEXT,
    abstract   TEXT,
    doi        TEXT UNIQUE NOT NULL,
    url        TEXT,
    isbn       TEXT,
    keywords   TEXT
);

-- Tabla intermedia autores <-> papers (N:N)
CREATE TABLE IF NOT EXISTS paper_authors (
    paper_id  INTEGER REFERENCES papers(id)   ON DELETE CASCADE,
    author_id INTEGER REFERENCES authors(id)  ON DELETE CASCADE,
    PRIMARY KEY (paper_id, author_id)
);

-- Estado del sistema
CREATE TABLE IF NOT EXISTS sistema_estado (
    ultima_actualizacion DATE,
    min_year INT,
    max_year INT
);

-- =========================================
--  Índices
-- =========================================

-- Índices de filtrado
CREATE INDEX IF NOT EXISTS idx_ce_year   ON conference_editions (year);
CREATE INDEX IF NOT EXISTS idx_conf_name ON conferences (name);
CREATE INDEX IF NOT EXISTS idx_auth_name ON authors (full_name);

-- Búsqueda por similitud en keywords (trigram GIN)
CREATE INDEX IF NOT EXISTS idx_papers_kw_trgm
    ON papers USING gin (keywords gin_trgm_ops);

-- (Nota: no se crea el índice único parcial por DOI porque la columna ya es UNIQUE NOT NULL)
