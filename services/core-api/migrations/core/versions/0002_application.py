"""core, часть 2 — заявка (E02-03.4)

Revision ID: core_0002
Revises: core_0001
"""

from alembic import op

revision = "core_0002"
down_revision = "core_0001"
branch_labels = None
depends_on = None

UP = """
CREATE TABLE application (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES company (id),
    recommendation_id uuid NOT NULL REFERENCES recommendation (id),
    current_version integer NOT NULL DEFAULT 1 CHECK (current_version >= 1),
    status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
        'DRAFT', 'SUBMITTED', 'DOCUMENTS_PARSING', 'CHECKING', 'MANUAL_REVIEW', 'NEEDS_INFO',
        'APPROVED', 'APPROVED_REDUCED', 'DECLINED', 'ACCEPTED', 'SIGNED')),
    phone text,
    email text,
    status_text text NOT NULL DEFAULT '',
    next_step_text text NOT NULL DEFAULT '',
    decision_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz
);
CREATE INDEX application_company_idx ON application (company_id, created_at DESC);
CREATE INDEX application_status_idx ON application (status);
CREATE INDEX application_recommendation_idx ON application (recommendation_id);

CREATE TABLE application_version (
    application_id uuid NOT NULL REFERENCES application (id),
    version integer NOT NULL CHECK (version >= 1),
    company_id uuid NOT NULL REFERENCES company (id),
    params jsonb NOT NULL,
    company jsonb NOT NULL,
    applicant_role jsonb,
    clarification jsonb,
    prefilled_fields text[] NOT NULL DEFAULT '{}',
    checklist jsonb NOT NULL DEFAULT '[]',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (application_id, version)
);
CREATE INDEX application_version_company_idx ON application_version (company_id);

CREATE TABLE status_history (
    id bigserial PRIMARY KEY,
    application_id uuid NOT NULL REFERENCES application (id),
    company_id uuid NOT NULL REFERENCES company (id),
    from_status text,
    to_status text NOT NULL,
    actor text NOT NULL,
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX status_history_application_idx ON status_history (application_id, created_at);
CREATE INDEX status_history_company_idx ON status_history (company_id);

CREATE TABLE document (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id uuid NOT NULL REFERENCES application (id),
    company_id uuid NOT NULL REFERENCES company (id),
    type text NOT NULL,
    filename text NOT NULL,
    mime text NOT NULL,
    size_bytes integer NOT NULL CHECK (size_bytes >= 0),
    storage_key text NOT NULL,
    status text NOT NULL DEFAULT 'UPLOADED' CHECK (status IN (
        'UPLOADED', 'CHECKING', 'ACCEPTED', 'PARSED', 'REPLACE_REQUIRED')),
    reject_reason text,
    parse_result jsonb,
    edits jsonb NOT NULL DEFAULT '[]',
    uploaded_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX document_application_idx ON document (application_id);
CREATE INDEX document_company_idx ON document (company_id);

CREATE TABLE consent (
    application_id uuid PRIMARY KEY REFERENCES application (id),
    company_id uuid NOT NULL REFERENCES company (id),
    given boolean NOT NULL DEFAULT false,
    given_at timestamptz
);
CREATE INDEX consent_company_idx ON consent (company_id);

CREATE TABLE decision (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id uuid NOT NULL REFERENCES application (id),
    application_version integer NOT NULL CHECK (application_version >= 1),
    company_id uuid NOT NULL REFERENCES company (id),
    outcome text NOT NULL,
    stop_reason text,
    pd_raw numeric(9, 8),
    pd numeric(9, 8),
    grade text,
    amount_requested numeric(18, 2) NOT NULL CHECK (amount_requested >= 0),
    amount_approved numeric(18, 2) CHECK (amount_approved >= 0),
    rate numeric(7, 6),
    term_months integer NOT NULL,
    payment numeric(18, 2) CHECK (payment >= 0),
    reason_codes jsonb NOT NULL DEFAULT '[]',
    shap_top10 jsonb NOT NULL DEFAULT '[]',
    features jsonb NOT NULL DEFAULT '[]',
    review_triggers text[] NOT NULL DEFAULT '{}',
    recommendation_id uuid NOT NULL REFERENCES recommendation (id),
    versions jsonb NOT NULL,
    decided_at timestamptz NOT NULL,
    final_outcome text,
    underwriter jsonb,
    clarifications jsonb NOT NULL DEFAULT '[]',
    UNIQUE (application_id, application_version)
);
CREATE INDEX decision_company_idx ON decision (company_id);
CREATE INDEX decision_recommendation_idx ON decision (recommendation_id);

-- Снимок решения неизменяем; после решения андеррайтера дописываются только итог,
-- сведения о сотруднике и запросы уточнения (контракт: Decision).
CREATE FUNCTION decision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'decision is immutable: DELETE is not allowed'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF (to_jsonb(NEW) - 'final_outcome' - 'underwriter' - 'clarifications')
       IS DISTINCT FROM
       (to_jsonb(OLD) - 'final_outcome' - 'underwriter' - 'clarifications') THEN
        RAISE EXCEPTION 'decision is immutable: only final_outcome, underwriter and clarifications may change'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER decision_immutable
    BEFORE UPDATE OR DELETE ON decision
    FOR EACH ROW EXECUTE FUNCTION decision_guard();
CREATE TRIGGER decision_immutable_truncate
    BEFORE TRUNCATE ON decision
    FOR EACH STATEMENT EXECUTE FUNCTION prevent_modification();

CREATE TABLE clarification_request (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id uuid NOT NULL REFERENCES application (id),
    company_id uuid NOT NULL REFERENCES company (id),
    type text NOT NULL,
    document_type text,
    text text NOT NULL,
    status text NOT NULL DEFAULT 'OPEN',
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    reply jsonb
);
CREATE INDEX clarification_request_application_idx ON clarification_request (application_id);
CREATE INDEX clarification_request_company_idx ON clarification_request (company_id);

CREATE TABLE contract (
    application_id uuid PRIMARY KEY REFERENCES application (id),
    company_id uuid NOT NULL REFERENCES company (id),
    product_code text NOT NULL,
    amount numeric(18, 2) NOT NULL CHECK (amount >= 0),
    term_months integer NOT NULL,
    rate numeric(7, 6) NOT NULL,
    payment numeric(18, 2) NOT NULL CHECK (payment >= 0),
    overpayment numeric(18, 2) NOT NULL CHECK (overpayment >= 0),
    schedule jsonb NOT NULL,
    disclaimer text,
    signed boolean NOT NULL DEFAULT false,
    signed_at timestamptz,
    generated_at timestamptz NOT NULL
);
CREATE INDEX contract_company_idx ON contract (company_id);
"""

DOWN = """
DROP TABLE contract, clarification_request, decision, consent, document, status_history,
    application_version, application;
DROP FUNCTION decision_guard();
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
