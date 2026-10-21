import httpx


def test_home_for_signed_in_client(make_client) -> None:  # type: ignore[no-untyped-def]
    _, client = make_client()
    client.cookies.set("session", "s1")
    response = client.get("/")
    assert response.status_code == 200
    assert "Опишите задачу" in response.text
    assert "ООО Ромашка" in response.text
    assert '<meta name="csrf-token" content="tok-123">' in response.text
    assert response.headers["cache-control"] == "no-store"


def test_home_for_anonymous_has_no_token(make_client) -> None:  # type: ignore[no-untyped-def]
    _, client = make_client()
    response = client.get("/")
    assert response.status_code == 200
    assert '<meta name="csrf-token" content="">' in response.text


def test_home_renders_error_screen_when_core_api_is_down(make_client) -> None:  # type: ignore[no-untyped-def]
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    _, client = make_client(down)
    client.cookies.set("session", "s1")
    response = client.get("/")
    assert response.status_code == 503
    assert "Кабинет временно недоступен" in response.text
    assert 'role="alert"' in response.text


def test_home_renders_error_screen_on_core_api_5xx(make_client) -> None:  # type: ignore[no-untyped-def]
    _, client = make_client(lambda request: httpx.Response(502))
    client.cookies.set("session", "s1")
    assert client.get("/").status_code == 503


def test_not_found_page(make_client) -> None:  # type: ignore[no-untyped-def]
    _, client = make_client()
    response = client.get("/nope")
    assert response.status_code == 404
    assert "Страница не найдена" in response.text


def test_server_error_page(make_client) -> None:  # type: ignore[no-untyped-def]
    app, client = make_client()

    async def boom() -> None:
        raise RuntimeError("boom")

    app.add_api_route("/boom", boom)

    response = client.get("/boom")
    assert response.status_code == 500
    assert "Что-то пошло не так" in response.text
    assert "boom" not in response.text


def test_health_does_not_need_core_api(make_client) -> None:  # type: ignore[no-untyped-def]
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    _, client = make_client(down)
    assert client.get("/health").json() == {"status": "ok", "service": "web"}


def test_correlation_id_is_returned_and_forwarded(make_client) -> None:  # type: ignore[no-untyped-def]
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("x-correlation-id"))
        return httpx.Response(200, json={"csrf_token": "t", "company": None})

    _, client = make_client(handler)
    client.cookies.set("session", "s1")
    response = client.get("/", headers={"X-Correlation-Id": "abc-1"})
    assert response.headers["x-correlation-id"] == "abc-1"
    assert seen == ["abc-1"]
    assert client.get("/").headers["x-correlation-id"]


def test_stream_check_page_points_to_contract_endpoint(make_client) -> None:  # type: ignore[no-untyped-def]
    _, client = make_client()
    response = client.get("/stream-check")
    assert response.status_code == 200
    assert 'sse-connect="/api/v1/events/stream"' in response.text
    assert 'sse-swap="ping"' in response.text


def test_static_is_served(make_client) -> None:  # type: ignore[no-untyped-def]
    _, client = make_client()
    assert client.get("/static/vendor/htmx.min.js").status_code == 200
    assert client.get("/static/css/app.css").status_code == 200
