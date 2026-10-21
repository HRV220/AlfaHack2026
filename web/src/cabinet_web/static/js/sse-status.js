// Индикатор состояния SSE: расширение htmx-ext-sse само переподключается
// с экспоненциальной задержкой, мы только показываем состояние.
(function () {
  function setStatus(kind, text) {
    var el = document.getElementById("sse-status");
    if (!el) return;
    el.textContent = text;
    el.className = "badge badge--" + kind;
  }
  document.addEventListener("htmx:sseOpen", function () {
    setStatus("ok", "подключено");
  });
  document.addEventListener("htmx:sseError", function () {
    setStatus("error", "связь потеряна, переподключаемся…");
  });
  document.addEventListener("htmx:sseBeforeMessage", function (event) {
    var name = event.detail && event.detail.type;
    if (name === "ping") setStatus("ok", "подключено");
  });
})();
