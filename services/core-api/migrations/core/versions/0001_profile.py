"""core, часть 1 — вход и профиль (E02-03.3)

Revision ID: core_0001
Revises:
"""

from alembic import op

revision = "core_0001"
down_revision = None
branch_labels = None
depends_on = None

UP = """
CREATE TABLE registry_snapshot (
    inn text PRIMARY KEY CHECK (inn ~ '^([0-9]{10}|[0-9]{12})$'),
    kpp text,
    ogrn text NOT NULL,
    name text NOT NULL,
    opf text NOT NULL,
    manager_name text NOT NULL,
    address text NOT NULL,
    okved text NOT NULL,
    industry_group text NOT NULL,
    registry_status text NOT NULL,
    registered_at date NOT NULL,
    liquidated_at date,
    origin text NOT NULL,
    fetched_at timestamptz NOT NULL
);

CREATE TABLE company (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inn text NOT NULL UNIQUE CHECK (inn ~ '^([0-9]{10}|[0-9]{12})$'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE applicant_role (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES company (id),
    role text NOT NULL,
    authority_confirmed boolean,
    selected_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX applicant_role_company_idx ON applicant_role (company_id);

CREATE TABLE need (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES company (id),
    version integer NOT NULL CHECK (version >= 1),
    origin text NOT NULL,
    text text,
    fields jsonb NOT NULL,
    non_target boolean NOT NULL DEFAULT false,
    questions_asked integer NOT NULL DEFAULT 0 CHECK (questions_asked >= 0),
    proposed_amount numeric(18, 2) CHECK (proposed_amount >= 0),
    insight_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX need_company_idx ON need (company_id, created_at DESC);

CREATE TABLE recommendation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES company (id),
    need_id uuid NOT NULL REFERENCES need (id),
    previous_id uuid REFERENCES recommendation (id),
    trigger text NOT NULL,
    need_snapshot jsonb NOT NULL,
    profile_version text NOT NULL,
    weights_profile text NOT NULL,
    evaluations jsonb NOT NULL,
    best_product_code text,
    alternative_product_codes text[] NOT NULL DEFAULT '{}',
    proposed_amount numeric(18, 2) CHECK (proposed_amount >= 0),
    versions jsonb NOT NULL,
    latency_ms integer NOT NULL CHECK (latency_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX recommendation_company_idx ON recommendation (company_id, created_at DESC);
CREATE INDEX recommendation_need_idx ON recommendation (need_id);

-- Снимки неизменяемы (архитектура 11.1): UPDATE, DELETE и TRUNCATE запрещены любой роли.
CREATE FUNCTION prevent_modification() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is immutable: % is not allowed', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE TRIGGER recommendation_immutable
    BEFORE UPDATE OR DELETE ON recommendation
    FOR EACH ROW EXECUTE FUNCTION prevent_modification();
CREATE TRIGGER recommendation_immutable_truncate
    BEFORE TRUNCATE ON recommendation
    FOR EACH STATEMENT EXECUTE FUNCTION prevent_modification();
"""

DOWN = """
DROP TABLE recommendation, need, applicant_role, company, registry_snapshot;
DROP FUNCTION prevent_modification();
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
