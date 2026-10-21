"""bank — имитация АБС, БКИ и антифрода (E02-03.7)

Revision ID: bank_0001
Revises:
"""

from alembic import op

revision = "bank_0001"
down_revision = None
branch_labels = None
depends_on = None

UP = """
CREATE TABLE account (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inn text NOT NULL CHECK (inn ~ '^([0-9]{10}|[0-9]{12})$'),
    number text NOT NULL UNIQUE,
    opened_at date NOT NULL,
    balance numeric(18, 2) NOT NULL,
    demo boolean
);
CREATE INDEX account_inn_idx ON account (inn);

CREATE TABLE transaction (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id uuid NOT NULL REFERENCES account (id),
    inn text NOT NULL CHECK (inn ~ '^([0-9]{10}|[0-9]{12})$'),
    date date NOT NULL,
    amount numeric(18, 2) NOT NULL CHECK (amount >= 0),
    direction text NOT NULL CHECK (direction IN ('IN', 'OUT')),
    counterparty text NOT NULL,
    counterparty_inn text,
    purpose text NOT NULL,
    balance_after numeric(18, 2) NOT NULL
);
CREATE INDEX transaction_inn_date_idx ON transaction (inn, date);
CREATE INDEX transaction_account_date_idx ON transaction (account_id, date);

CREATE TABLE credit_record (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inn text NOT NULL CHECK (inn ~ '^([0-9]{10}|[0-9]{12})$'),
    lender text NOT NULL,
    amount numeric(18, 2) NOT NULL CHECK (amount >= 0),
    monthly_payment numeric(18, 2) NOT NULL CHECK (monthly_payment >= 0),
    opened_at date NOT NULL,
    closed_at date,
    max_overdue_days integer NOT NULL DEFAULT 0 CHECK (max_overdue_days >= 0),
    active boolean NOT NULL
);
CREATE INDEX credit_record_inn_idx ON credit_record (inn, opened_at);

CREATE TABLE fraud_flag (
    inn text PRIMARY KEY CHECK (inn ~ '^([0-9]{10}|[0-9]{12})$'),
    flag boolean NOT NULL
);

-- Истинные категории операций для оценки категоризации (не читаются сервисами ml).
CREATE TABLE ground_truth (
    transaction_id uuid PRIMARY KEY REFERENCES transaction (id),
    inn text NOT NULL,
    category text NOT NULL
);
CREATE INDEX ground_truth_inn_idx ON ground_truth (inn);
"""

DOWN = """
DROP TABLE ground_truth, fraud_flag, credit_record, transaction, account;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
