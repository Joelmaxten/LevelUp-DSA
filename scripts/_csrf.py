"""
Makes app.test_client() behave like a browser with respect to CSRF: before the
first POST/PUT/PATCH/DELETE it loads a normal page, reads the token out of
<meta name="csrf-token"> (the way ui.js does), and sends it as X-CSRF-Token.

Usage, right after create_app():
    from scripts._csrf import enable_csrf_client
    enable_csrf_client(app)
"""
import re

from flask.testing import FlaskClient

_META = re.compile(r'<meta name="csrf-token" content="([^"]+)"')


class CsrfClient(FlaskClient):
    def csrf_token(self):
        # "/" renders layout.html for everyone (logged in or not) and never redirects.
        html = super().open("/").get_data(as_text=True)
        match = _META.search(html)
        return match.group(1) if match else ""

    def open(self, *args, **kwargs):
        method = (kwargs.get("method") or "GET").upper()
        if method not in ("GET", "HEAD", "OPTIONS"):
            headers = dict(kwargs.get("headers") or {})
            if not any(k.lower() == "x-csrf-token" for k in headers):
                headers["X-CSRF-Token"] = self.csrf_token()
            kwargs["headers"] = headers
        return super().open(*args, **kwargs)


def enable_csrf_client(app):
    app.test_client_class = CsrfClient
    return app
