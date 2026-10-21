// CSRF: токен из <meta name="csrf-token"> (его выдаёт core-api в GET /auth/me)
// добавляется ко всем изменяющим HTMX-запросам в заголовок X-CSRF-Token.
document.addEventListener("htmx:configRequest", function (event) {
  var meta = document.querySelector('meta[name="csrf-token"]');
  var token = meta ? meta.getAttribute("content") : "";
  var verb = (event.detail.verb || "get").toLowerCase();
  if (token && verb !== "get") {
    event.detail.headers["X-CSRF-Token"] = token;
  }
});
