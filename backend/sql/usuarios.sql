-- Execute no SQL Editor do Supabase antes do deploy no Render
-- Database → SQL Editor → New query → cole isso → Run

CREATE TABLE IF NOT EXISTS usuarios (
    id          TEXT PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    nome        TEXT NOT NULL,
    senha_hash  TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'operador',
    ativo       BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE usuarios DISABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
