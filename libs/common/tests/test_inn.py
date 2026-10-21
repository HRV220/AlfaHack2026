import pytest
from cabinet_common.inn import is_valid_inn


@pytest.mark.parametrize("inn", ["7707083893", "500100732259", "7812345675"])
def test_valid_inn(inn: str) -> None:
    assert is_valid_inn(inn)


@pytest.mark.parametrize(
    "inn",
    [
        "7707083892",
        "500100732258",
        "500100732250",
        "",
        "123",
        "77070838931",
        "77070838ab",
        "٧٧٠٧٠٨٣٨٩٣",
    ],
)
def test_invalid_inn(inn: str) -> None:
    assert not is_valid_inn(inn)
