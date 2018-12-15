# coding=utf-8
import logging
import os

from virtual.web import app
import serverless_wsgi

logging.getLogger("rasterio._base").setLevel(logging.WARNING)


def handle(event, context):
    # transfer stage from event["requestContext"] to an X-Stage header
    event["headers"]["X-Stage"] = event.get("requestContext", {}).pop("stage", None)
    event["headers"]["Host"] = event["headers"].get(
        "X-Forwarded-Host", event["headers"].get("Host")
    )
    return serverless_wsgi.handle_request(app, event, context)
