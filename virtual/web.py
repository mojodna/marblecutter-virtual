# coding=utf-8
from __future__ import absolute_import

import logging

from cachetools.func import lru_cache
from flask import Flask, Markup, jsonify, redirect, render_template, request
from flask_cors import CORS
from marblecutter import NoCatalogAvailable, tiling
from marblecutter.formats.optimal import Optimal
from marblecutter.transformations import Image
from marblecutter.web import bp, url_for
from mercantile import Tile

try:
    from urllib.parse import urlparse, urlencode
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
except ImportError:
    from urlparse import urlparse
    from urllib import urlencode
    from urllib2 import urlopen, Request, HTTPError

from .catalogs import VirtualCatalog

logging.basicConfig()
LOG = logging.getLogger(__name__)

IMAGE_TRANSFORMATION = Image()
IMAGE_FORMAT = Optimal()

app = Flask("marblecutter-virtual")
app.register_blueprint(bp)
app.url_map.strict_slashes = False
CORS(app, send_wildcard=True)


@lru_cache()
def make_catalog(args):
    if args.get("url", "") == "":
        raise NoCatalogAvailable()

    try:
        return VirtualCatalog(
            args["url"],
            rgb=args.get("rgb"),
            nodata=args.get("nodata"),
            linear_stretch=args.get("linearStretch"),
            resample=args.get("resample"),
            expr=args.get("expr", None)
        )
    except Exception as e:
        LOG.exception(e)
        raise NoCatalogAvailable()


@app.route("/")
def index():
    return (render_template("index.html"), 200, {"Content-Type": "text/html"})


@app.route("/tiles/")
def meta():
    catalog = make_catalog(request.args)

    meta = {
        "bounds": catalog.bounds,
        "center": catalog.center,
        "maxzoom": catalog.maxzoom,
        "minzoom": catalog.minzoom,
        "name": catalog.name,
        "tilejson": "2.1.0",
        "tiles": [
            "{}{{z}}/{{x}}/{{y}}?{}".format(
                url_for("meta", _external=True, _scheme=""), urlencode(request.args)
            )
        ],
    }

    return jsonify(meta)


@app.route("/bounds/")
def bounds():
    catalog = make_catalog(request.args)

    return jsonify({"url": catalog.uri, "bounds": catalog.bounds})


@app.route("/preview")
def preview():
    try:
        # initialize the catalog so this route will fail if the source doesn't exist
        make_catalog(request.args)
    except Exception:
        return redirect(url_for("index"), code=303)

    return (
        render_template(
            "preview.html",
            tilejson_url=Markup(
                url_for("meta", _external=True, _scheme="", **request.args)
            ),
            source_url=request.args["url"],
        ),
        200,
        {"Content-Type": "text/html"},
    )


@app.route("/tiles/<int:z>/<int:x>/<int:y>")
@app.route("/tiles/<int:z>/<int:x>/<int:y>@<int:scale>x")
def render_png(z, x, y, scale=1):
    catalog = make_catalog(request.args)
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        catalog,
        format=IMAGE_FORMAT,
        transformation=IMAGE_TRANSFORMATION,
        scale=scale,
    )

    headers.update(catalog.headers)

    return data, 200, headers
