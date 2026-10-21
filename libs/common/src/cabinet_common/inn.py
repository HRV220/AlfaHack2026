"""Проверка ИНН по контрольной сумме (10 цифр — юрлицо, 12 — ИП)."""

_WEIGHTS_10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_WEIGHTS_12_FIRST = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_WEIGHTS_12_SECOND = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _check_digit(digits: str, weights: tuple[int, ...]) -> int:
    return sum(w * int(d) for w, d in zip(weights, digits, strict=False)) % 11 % 10


def is_valid_inn(value: str) -> bool:
    """Верна ли длина (10 или 12 цифр) и контрольные цифры."""
    if not (value.isascii() and value.isdigit()):
        return False
    if len(value) == 10:
        return int(value[9]) == _check_digit(value, _WEIGHTS_10)
    if len(value) == 12:
        return int(value[10]) == _check_digit(value, _WEIGHTS_12_FIRST) and int(
            value[11]
        ) == _check_digit(value, _WEIGHTS_12_SECOND)
    return False
