from cabinet_common.init.runner import Step, StepWarning, run_steps


def recording(calls: list[str], name: str) -> Step:
    def run() -> str:
        calls.append(name)
        return name

    return Step(name, run)


def failing(name: str, *, required: bool = True) -> Step:
    def run() -> str:
        raise RuntimeError("сбой шага")

    return Step(name, run, required=required)


def test_all_steps_run_in_order_and_return_zero() -> None:
    calls: list[str] = []
    steps = [recording(calls, name) for name in ("a", "b", "c")]
    assert run_steps(steps) == 0
    assert calls == ["a", "b", "c"]


def test_required_step_failure_stops_init() -> None:
    calls: list[str] = []
    steps = [recording(calls, "a"), failing("b"), recording(calls, "c")]
    assert run_steps(steps) == 1
    assert calls == ["a"]


def test_optional_step_failure_does_not_stop_init() -> None:
    calls: list[str] = []
    steps = [failing("a", required=False), recording(calls, "b")]
    assert run_steps(steps) == 0
    assert calls == ["b"]


def test_empty_plan_succeeds() -> None:
    assert run_steps([]) == 0


def test_warning_from_required_step_fails_init() -> None:
    calls: list[str] = []

    def warn() -> str:
        raise StepWarning("миграции применены не полностью")

    steps = [Step("migrations", warn), recording(calls, "seed")]
    assert run_steps(steps) == 1
    assert calls == []
