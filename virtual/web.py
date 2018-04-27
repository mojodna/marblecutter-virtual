# coding=utf-8
from __future__ import absolute_import

import logging
import os

from cachetools.func import lru_cache
from flask import jsonify, render_template, request, url_for
from marblecutter import NoDataAvailable, tiling
from marblecutter.formats.png import PNG
from marblecutter.transformations import Image
from marblecutter.web import app
from mercantile import Tile
import urllib

from .catalogs import VirtualCatalog

LOG = logging.getLogger(__name__)

IMAGE_TRANSFORMATION = Image()
PNG_FORMAT = PNG()

REMOTE_CATALOG_BASE_URL = os.getenv(
    "REMOTE_CATALOG_BASE_URL", "https://api.openaerialmap.org"
)


@lru_cache()
def make_catalog(args):
    source = args["url"]
    rgb = args.get("rgb")
    nodata = args.get("nodata")
    linear_stretch = args.get("linearStretch")

    try:
        return VirtualCatalog(
            source, rgb=rgb, nodata=nodata, linear_stretch=linear_stretch
        )
    except Exception:
        raise NoDataAvailable()


def make_prefix():
    host = request.headers.get("X-Forwarded-Host", request.headers.get("Host", ""))

    # sniff for API Gateway
    if ".execute-api." in host and ".amazonaws.com" in host:
        return request.headers.get("X-Stage")


@app.route("/tiles/")
@app.route("/<prefix>/tiles/")
def meta(prefix=None):
    catalog = make_catalog(request.args)

    meta = {
        "bounds": catalog.bounds,
        "center": catalog.center,
        "maxzoom": catalog.maxzoom,
        "minzoom": catalog.minzoom,
        "name": catalog.name,
        "tilejson": "2.1.0",
    }

    with app.app_context():
        meta["tiles"] = [
            "{}{{z}}/{{x}}/{{y}}.png?url={}".format(
                url_for("meta", prefix=make_prefix(), _external=True, _scheme=""),
                urllib.quote_plus(catalog.uri),
            )
        ]

    return jsonify(meta)


@app.route("/bounds/")
@app.route("/<prefix>/bounds/")
def bounds(prefix=None):
    catalog = make_catalog(request.args)

    return jsonify({"url": catalog.uri, "bounds": catalog.bounds})


@app.route("/tiles/preview")
@app.route("/<prefix>/tiles/preview")
def preview(prefix=None):
    catalog = make_catalog(request.args)

    with app.app_context():
        return render_template(
            "preview.html",
            tilejson_url=url_for(
                "meta",
                prefix=make_prefix(),
                _external=True,
                _scheme="",
                url=catalog.uri,
            ),
        ), 200, {
            "Content-Type": "text/html"
        }


@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
@app.route("/tiles/<int:z>/<int:x>/<int:y>@<int:scale>x.png")
@app.route("/<prefix>/tiles/<image_id>/<int:z>/<int:x>/<int:y>.png")
@app.route("/<prefix>/tiles/<int:z>/<int:x>/<int:y>.png")
def render_png(z, x, y, scale=1, prefix=None):
    catalog = make_catalog(request.args)
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        catalog,
        format=PNG_FORMAT,
        transformation=IMAGE_TRANSFORMATION,
        scale=scale,
    )

    headers.update(catalog.headers)

    return data, 200, headers
