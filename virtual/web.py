# coding=utf-8
from __future__ import absolute_import

import logging

from cachetools.func import lru_cache
from flask import Markup, jsonify, render_template, request, url_for
from marblecutter import NoCatalogAvailable, tiling
from marblecutter.formats.optimal import Optimal
from marblecutter.transformations import Image
from marblecutter.web import app
from . import marblecutter_overload_nd as marblecutter_nd
from mercantile import Tile
import urllib
from .nd_formats import Optimalnd

from .catalogs import VirtualCatalog







LOG = logging.getLogger(__name__)

IMAGE_TRANSFORMATION = Image()
IMAGE_FORMAT = Optimal()
IMAGE_FORMAT_ND = Optimal()


@lru_cache()
def make_catalog(args):
    source = args["url"]
    rgb = args.get("rgb")
    nodata = args.get("nodata")
    linear_stretch = args.get("linearStretch")
    band1 = args.get('band1')
    band2 = args.get('band2')

    try:
        return VirtualCatalog(
            source, rgb=rgb, nodata=nodata, linear_stretch=linear_stretch, band1=band1, band2=band2
        )
    except Exception as e:
        LOG.warn(e.message)
        raise NoCatalogAvailable()


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
            "{}{{z}}/{{x}}/{{y}}?{}".format(
                url_for("meta", prefix=make_prefix(), _external=True, _scheme=""),
                urllib.urlencode(request.args),
            )
        ]

    return jsonify(meta)


@app.route("/bounds/")
@app.route("/<prefix>/bounds/")
def bounds(prefix=None):
    catalog = make_catalog(request.args)

    return jsonify({"url": catalog.uri, "bounds": catalog.bounds})


@app.route("/preview")
@app.route("/<prefix>/preview")
def preview(prefix=None):
    # initialize the catalog so this route will fail if the source doesn't exist
    make_catalog(request.args)

    with app.app_context():
        return render_template(
            "preview.html",
            tilejson_url=Markup(
                url_for(
                    "meta",
                    prefix=make_prefix(),
                    _external=True,
                    _scheme="",
                    **request.args
                )
            ),
        ), 200, {
            "Content-Type": "text/html"
        }


@app.route("/tiles/<int:z>/<int:x>/<int:y>")
@app.route("/tiles/<int:z>/<int:x>/<int:y>@<int:scale>x")
@app.route("/<prefix>/tiles/<image_id>/<int:z>/<int:x>/<int:y>")
@app.route("/<prefix>/tiles/<int:z>/<int:x>/<int:y>")
def render_png(z, x, y, scale=1, prefix=None):
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


@app.route("/ndtiles/<int:z>/<int:x>/<int:y>")
@app.route("/ndtiles/<int:z>/<int:x>/<int:y>@<int:scale>x")
@app.route("/<prefix>/ndtiles/<image_id>/<int:z>/<int:x>/<int:y>")
@app.route("/<prefix>/ndtiles/<int:z>/<int:x>/<int:y>")
def render_nd_png(z, x, y, scale=1, prefix=None):
    catalog = make_catalog(request.args)
    tile = Tile(x, y, z)
    headers, data = marblecutter_nd.render_nd_tile(
        tile,
        catalog,
        format=IMAGE_FORMAT_ND,
        transformation=IMAGE_TRANSFORMATION,
        scale=scale,
    )

    headers.update(catalog.headers)

    return data, 200, headers
