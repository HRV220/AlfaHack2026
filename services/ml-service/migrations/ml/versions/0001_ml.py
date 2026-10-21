"""ml — профиль, прогноз, журналы расчётов (E02-03.8)

Revision ID: ml_0001
Revises:
"""

from alembic import op
from cabinet_common.db.sql import OUTBOX_DOWN, OUTBOX_UP

revision = "ml_0001"
down_revision = None
branch_labels = None
depends_on = None

UP = """
CREATE TABLE profile_snapshot (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inn text NOT NULL,
    version text NOT NULL,
    as_of timestamptz NOT NULL,
    profile jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (inn, version)
);

CREATE TABLE enriched_transaction (
    transaction_id uuid PRIMARY KEY,
    inn text NOT NULL,
    date date NOT NULL,
    amount numeric(18, 2) NOT NULL CHECK (amount >= 0),
    direction text NOT NULL CHECK (direction IN ('IN', 'OUT')),
    category text NOT NULL,
    category_confidence numeric(5, 4) CHECK (category_confidence BETWEEN 0 AND 1),
    model_version text NOT NULL
);
CREATE INDEX enriched_transaction_inn_date_idx ON enriched_transaction (inn, date);

CREATE TABLE recurring_payment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inn text NOT NULL,
    counterparty text NOT NULL,
    category text NOT NULL,
    period_days integer NOT NULL,
    amount numeric(18, 2) NOT NULL CHECK (amount >= 0),
    next_date date NOT NULL
);
CREATE INDEX recurring_payment_inn_idx ON recurring_payment (inn);

CREATE TABLE forecast (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inn text NOT NULL,
    horizon_days integer NOT NULL,
    cushion numeric(18, 2) NOT NULL CHECK (cushion >= 0),
    daily jsonb NOT NULL,
    model_version text NOT NULL,
    generated_at timestamptz NOT NULL
);
CREATE INDEX forecast_inn_idx ON forecast (inn, generated_at DESC);

CREATE TABLE cash_gap (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_id uuid NOT NULL REFERENCES forecast (id),
    inn text NOT NULL,
    date date NOT NULL,
    probability numeric(5, 4) NOT NULL CHECK (probability BETWEEN 0 AND 1),
    deficit numeric(18, 2) NOT NULL CHECK (deficit >= 0),
    cushion numeric(18, 2) NOT NULL CHECK (cushion >= 0),
    return_date_p50 date,
    reasons jsonb NOT NULL DEFAULT '[]',
    recurring_last_year boolean NOT NULL DEFAULT false
);
CREATE INDEX cash_gap_inn_date_idx ON cash_gap (inn, date);
CREATE INDEX cash_gap_forecast_idx ON cash_gap (forecast_id);

CREATE TABLE scoring_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inn text NOT NULL,
    application_id uuid,
    application_version integer,
    pd_raw numeric(9, 8),
    pd numeric(9, 8),
    grade text,
    features jsonb NOT NULL,
    shap_top10 jsonb NOT NULL DEFAULT '[]',
    model_version text NOT NULL,
    latency_ms integer NOT NULL CHECK (latency_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX scoring_log_inn_idx ON scoring_log (inn, created_at DESC);
CREATE INDEX scoring_log_application_idx ON scoring_log (application_id);

CREATE TABLE recommendation_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inn text NOT NULL,
    recommendation_id uuid,
    need jsonb NOT NULL,
    result jsonb NOT NULL,
    versions jsonb NOT NULL,
    latency_ms integer NOT NULL CHECK (latency_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX recommendation_log_inn_idx ON recommendation_log (inn, created_at DESC);
CREATE INDEX recommendation_log_recommendation_idx ON recommendation_log (recommendation_id);

CREATE TABLE whatif_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inn text NOT NULL,
    recommendation_id uuid,
    changes jsonb NOT NULL,
    result jsonb NOT NULL,
    latency_ms integer CHECK (latency_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX whatif_log_inn_idx ON whatif_log (inn, created_at DESC);
"""

DOWN = """
DROP TABLE whatif_log, recommendation_log, scoring_log, cash_gap, forecast, recurring_payment,
    enriched_transaction, profile_snapshot;
"""


def upgrade() -> None:
    op.execute(UP)
    op.execute(OUTBOX_UP)


def downgrade() -> None:
    op.execute(OUTBOX_DOWN)
    op.execute(DOWN)
