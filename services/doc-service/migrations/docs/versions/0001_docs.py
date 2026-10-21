"""docs — распознавание документов (E02-03.9)

Revision ID: docs_0001
Revises:
"""

from alembic import op
from cabinet_common.db.sql import OUTBOX_DOWN, OUTBOX_UP

revision = "docs_0001"
down_revision = None
branch_labels = None
depends_on = None

UP = """
CREATE TABLE parse_job (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL,
    application_id uuid NOT NULL,
    inn text NOT NULL CHECK (inn ~ '^([0-9]{10}|[0-9]{12})$'),
    type text NOT NULL,
    storage_key text NOT NULL,
    status text NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED')),
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz
);
CREATE INDEX parse_job_document_idx ON parse_job (document_id);
CREATE INDEX parse_job_application_idx ON parse_job (application_id);
CREATE INDEX parse_job_status_idx ON parse_job (status) WHERE status IN ('QUEUED', 'RUNNING');

CREATE TABLE extracted_field (
    id bigserial PRIMARY KEY,
    parse_job_id uuid NOT NULL REFERENCES parse_job (id),
    name text NOT NULL,
    value jsonb,
    confidence numeric(5, 4) CHECK (confidence BETWEEN 0 AND 1),
    page integer CHECK (page >= 1)
);
CREATE INDEX extracted_field_job_idx ON extracted_field (parse_job_id);

CREATE TABLE validation_result (
    id bigserial PRIMARY KEY,
    parse_job_id uuid NOT NULL REFERENCES parse_job (id),
    check_name text NOT NULL,
    passed boolean NOT NULL,
    details jsonb
);
CREATE INDEX validation_result_job_idx ON validation_result (parse_job_id);
"""

DOWN = """
DROP TABLE validation_result, extracted_field, parse_job;
"""


def upgrade() -> None:
    op.execute(UP)
    op.execute(OUTBOX_UP)


def downgrade() -> None:
    op.execute(OUTBOX_DOWN)
    op.execute(DOWN)
