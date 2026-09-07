(function () {
  function getCookie(name) {
    const prefix = `${name}=`;
    return document.cookie
      .split(";")
      .map((value) => value.trim())
      .find((value) => value.startsWith(prefix))
      ?.slice(prefix.length) || "";
  }

  function isUnsafeMethod(method) {
    return !["GET", "HEAD", "OPTIONS", "TRACE"].includes(String(method || "GET").toUpperCase());
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = function secureFetch(input, init) {
    const options = init ? { ...init } : {};
    const method = options.method || (input && input.method) || "GET";
    const targetUrl = new URL(typeof input === "string" || input instanceof URL ? input : input.url, window.location.href);

    if (targetUrl.origin === window.location.origin && isUnsafeMethod(method)) {
      const csrfToken = decodeURIComponent(getCookie("csrf_access_token"));
      if (csrfToken) {
        const headers = new Headers(options.headers || (input && input.headers) || {});
        if (!headers.has("X-CSRF-TOKEN")) {
          headers.set("X-CSRF-TOKEN", csrfToken);
        }
        options.headers = headers;
      }
    }

    return originalFetch(input, options);
  };
})();
