# coding=utf-8
from __future__ import division, print_function

import logging
import os
import signal

from openaerialmap.web import app

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


def handler(signum, frame):
    LOG.warning("Request timed out; crashing in place of cleanup.")
    exit(1)


# Register the signal function handler
signal.signal(signal.SIGALRM, handler)


class TimeoutMiddleware:

    def __init__(self, app, timeout):
        self.timeout = timeout
        self.wrapped_app = app

    def __call__(self, environ, start_response):
        # set an interval timer in float seconds
        signal.setitimer(signal.ITIMER_REAL, self.timeout / 1000)
        try:
            return self.wrapped_app(environ, start_response)
        finally:
            # clear the interval timer
            signal.setitimer(signal.ITIMER_REAL, 0)


class HostMiddleware:

    def __init__(self, app):
        self.wrapped_app = app

    def __call__(self, environ, start_response):
        # treat X-Forwarded-Host as Host
        environ["HTTP_HOST"] = environ.get(
            "HTTP_X_FORWARDED_HOST", environ.get("HTTP_HOST")
        )

        return self.wrapped_app(environ, start_response)


# TODO make this configurable (or base it on an X-header containing the amount of time remaining)
app.wsgi_app = HostMiddleware(TimeoutMiddleware(app.wsgi_app, 14000))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
