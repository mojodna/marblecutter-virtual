# coding=utf-8
from __future__ import division

import logging
import signal
import sys

import awsgi

sys.path.append("/var/task/.pypath")

from virtual.web import app

# reset the Lambda logger
root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)

logging.basicConfig(level=logging.INFO)

LOG = logging.getLogger(__name__)


def handler(signum, frame):
    LOG.warning("Request timed out; crashing in place of cleanup.")
    exit(1)


# Register the signal function handler
signal.signal(signal.SIGALRM, handler)


def handle(event, context):
    # Cloudfront isn't configured to pass Host headers, so the provided Host
    # header is the API Gateway hostname
    # event['headers']['Host'] = os.environ['SERVER_NAME']
    event["headers"]["X-Stage"] = event["requestContext"]["stage"]

    signal.setitimer(
        signal.ITIMER_REAL, (context.get_remaining_time_in_millis() - 250) / 1000
    )
    try:
        return awsgi.response(app, event, context)
    finally:
        # clear the interval timer
        signal.setitimer(signal.ITIMER_REAL, 0)
