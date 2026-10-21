"""kb — база знаний ассистента: статьи и фрагменты с вектором и tsvector (E02-03.9)

Размерность вектора 1024 — модель эмбеддингов bge-m3 (E02-07.2).

Revision ID: kb_0001
Revises:
"""

from alembic import op

revision = "kb_0001"
down_revision = None
branch_labels = None
depends_on = None

UP = """
CREATE TABLE article (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    title text NOT NULL,
    body text NOT NULL,
    source text,
    tags text[] NOT NULL DEFAULT '{}',
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chunk (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id uuid NOT NULL REFERENCES article (id),
    ord integer NOT NULL CHECK (ord >= 0),
    text text NOT NULL,
    embedding vector(1024),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('russian', text)) STORED,
    UNIQUE (article_id, ord)
);
CREATE INDEX chunk_tsv_idx ON chunk USING gin (tsv);
CREATE INDEX chunk_embedding_idx ON chunk USING hnsw (embedding vector_cosine_ops);
"""

DOWN = """
DROP TABLE chunk, article;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
