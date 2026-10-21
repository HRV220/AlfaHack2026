"""core, Row-Level Security по company_id (E02-03.6)

Сервис перед запросами клиента выполняет `SET LOCAL app.company_id = '<uuid>'`.
Без значения политика не пропускает ни одной строки. Вход по ИНН до известного `company_id`:
`SET LOCAL app.login_inn = '<инн>'` открывает на чтение только компанию с этим ИНН. `FORCE` нужен, потому что
роль сервиса владеет таблицами, а владелец иначе обходит RLS.

Revision ID: core_0004
Revises: core_0003
"""

from alembic import op

revision = "core_0004"
down_revision = "core_0003"
branch_labels = None
depends_on = None

# Таблица -> колонка, по которой сверяется компания. Реестр, лента и таблицы событий —
# общие данные без компании, RLS на них нет.
TENANT_TABLES = {
    "company": "id",
    "applicant_role": "company_id",
    "need": "company_id",
    "recommendation": "company_id",
    "application": "company_id",
    "application_version": "company_id",
    "status_history": "company_id",
    "document": "company_id",
    "consent": "company_id",
    "decision": "company_id",
    "clarification_request": "company_id",
    "contract": "company_id",
    "insight": "company_id",
    "chat_session": "company_id",
    "message": "company_id",
    "pending_action": "company_id",
    "escalation": "company_id",
    "feed_impression": "company_id",
}


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION current_company_id() RETURNS uuid LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.company_id', true), '')::uuid
        $$
    """)
    for table, column in TENANT_TABLES.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({column} = current_company_id()) "
            f"WITH CHECK ({column} = current_company_id())"
        )
    op.execute(
        "CREATE POLICY company_login ON company FOR SELECT "
        "USING (inn = NULLIF(current_setting('app.login_inn', true), ''))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY company_login ON company")
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION current_company_id()")
