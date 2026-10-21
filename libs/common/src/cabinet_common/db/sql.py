"""Общий DDL для таблиц событий (архитектура 9): outbox и processed_events в схемах сервисов."""

OUTBOX_UP = """
CREATE TABLE outbox (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    topic text NOT NULL,
    key text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    attempts integer NOT NULL DEFAULT 0
);
CREATE INDEX outbox_unpublished_idx ON outbox (created_at) WHERE published_at IS NULL;

CREATE TABLE processed_events (
    event_id uuid PRIMARY KEY,
    topic text NOT NULL,
    processed_at timestamptz NOT NULL DEFAULT now()
);
"""

OUTBOX_DOWN = """
DROP TABLE IF EXISTS processed_events;
DROP TABLE IF EXISTS outbox;
"""
