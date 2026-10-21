from datetime import UTC, datetime

import pytest
from cabinet_common.auth import SESSION_TTL_HOURS, TokenClaims, TokenRole
from cabinet_common.outbox import OutboxRecord
from pydantic import ValidationError


def test_token_claims_fields() -> None:
    now = datetime.now(UTC)
    claims = TokenClaims(sub="u1", company_id="c1", role=TokenRole.APPLICANT, iat=now, exp=now)
    assert claims.role == "applicant"
    assert SESSION_TTL_HOURS == 8


def test_token_claims_immutable_and_role_validated() -> None:
    now = datetime.now(UTC)
    claims = TokenClaims(sub="u1", company_id="c1", role=TokenRole.UNDERWRITER, iat=now, exp=now)
    with pytest.raises(ValidationError):
        claims.company_id = "other"
    with pytest.raises(ValidationError):
        TokenClaims(sub="u1", company_id="c1", role="admin", iat=now, exp=now)  # type: ignore[arg-type]


def test_outbox_record_defaults() -> None:
    rec = OutboxRecord(id="1", topic="t", key="k", payload={}, created_at=datetime.now(UTC))
    assert rec.published_at is None
    assert rec.attempts == 0
