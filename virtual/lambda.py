# coding=utf-8
import logging
import os
import signal

from virtual.web import app
import serverless_wsgi

logging.getLogger("rasterio._base").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def handler(signum, frame):
    logger.error("Request timed out; shutting down to clean up.")
    os._exit(0)


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


def handle(event, context):
    context.get_remaining_time_in_millis()

    # transfer stage from event["requestContext"] to an X-Stage header
    event["headers"]["X-Stage"] = event.get("requestContext", {}).pop("stage", None)
    event["headers"]["Host"] = event["headers"].get(
        "X-Forwarded-Host", event["headers"].get("Host")
    )

    app.wsgi_app = TimeoutMiddleware(
        app.wsgi_app, context.get_remaining_time_in_millis() - 50
    )

    return serverless_wsgi.handle_request(app, event, context)
