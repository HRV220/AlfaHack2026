"""core, часть 3 — ассистент, лента, события (E02-03.5)

Revision ID: core_0003
Revises: core_0002
"""

from alembic import op
from cabinet_common.db.sql import OUTBOX_DOWN, OUTBOX_UP

revision = "core_0003"
down_revision = "core_0002"
branch_labels = None
depends_on = None

UP = """
CREATE TABLE insight (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES company (id),
    gap jsonb NOT NULL,
    days_until integer NOT NULL,
    recommendation_id uuid REFERENCES recommendation (id),
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX insight_company_idx ON insight (company_id, created_at DESC);

CREATE TABLE chat_session (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES company (id),
    stage text NOT NULL,
    need_id uuid REFERENCES need (id),
    recommendation_id uuid REFERENCES recommendation (id),
    application_id uuid REFERENCES application (id),
    insight_id uuid REFERENCES insight (id),
    assistant_enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX chat_session_company_idx ON chat_session (company_id, created_at DESC);
CREATE INDEX chat_session_application_idx ON chat_session (application_id);

CREATE TABLE message (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES chat_session (id),
    company_id uuid NOT NULL REFERENCES company (id),
    role text NOT NULL,
    text text NOT NULL,
    need_id uuid REFERENCES need (id),
    recommendation_id uuid REFERENCES recommendation (id),
    question_id text,
    action_ids uuid[] NOT NULL DEFAULT '{}',
    blocked_by_guard boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX message_session_idx ON message (session_id, created_at);
CREATE INDEX message_company_idx ON message (company_id);

CREATE TABLE pending_action (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES chat_session (id),
    company_id uuid NOT NULL REFERENCES company (id),
    type text NOT NULL,
    label text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE INDEX pending_action_session_idx ON pending_action (session_id);
CREATE INDEX pending_action_company_idx ON pending_action (company_id);

CREATE TABLE escalation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES company (id),
    reason text NOT NULL,
    session_id uuid REFERENCES chat_session (id),
    application_id uuid REFERENCES application (id),
    summary text NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    closed_comment text
);
CREATE INDEX escalation_company_idx ON escalation (company_id);
CREATE INDEX escalation_application_idx ON escalation (application_id);

CREATE TABLE feed_item (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type text NOT NULL,
    title text NOT NULL,
    text text NOT NULL,
    published_at date NOT NULL,
    demo boolean,
    tags text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE feed_impression (
    id bigserial PRIMARY KEY,
    company_id uuid NOT NULL REFERENCES company (id),
    feed_item_id uuid NOT NULL REFERENCES feed_item (id),
    reasons jsonb NOT NULL DEFAULT '[]',
    shown_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX feed_impression_company_idx ON feed_impression (company_id, shown_at DESC);
CREATE INDEX feed_impression_item_idx ON feed_impression (feed_item_id);
"""

DOWN = """
DROP TABLE feed_impression, feed_item, escalation, pending_action, message, chat_session,
    insight;
"""


def upgrade() -> None:
    op.execute(UP)
    op.execute(OUTBOX_UP)


def downgrade() -> None:
    op.execute(OUTBOX_DOWN)
    op.execute(DOWN)
