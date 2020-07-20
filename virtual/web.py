# coding=utf-8
from __future__ import absolute_import

import logging

from affine import Affine
from cachetools.func import lru_cache
from collections import defaultdict
from concurrent import futures
from datetime import datetime
from flask import Flask, Markup, jsonify, redirect, render_template, request
from flask_cors import CORS
from itertools import groupby
from marblecutter import WEB_MERCATOR_CRS, get_source, read_window
from marblecutter.tiling import TILE_SHAPE
from marblecutter.mosaic import MAX_WORKERS
from marblecutter import NoCatalogAvailable, tiling
from marblecutter.formats.optimal import Optimal
from marblecutter.transformations import Image
from marblecutter.web import bp, url_for
from marblecutter.utils import Bounds, Source, PixelCollection
import mercantile
import numpy as np
import jq
import re
import requests
from shapely.geometry import box

try:
    from urllib.parse import urlparse, urlencode
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
except ImportError:
    from urlparse import urlparse
    from urllib import urlencode
    from urllib2 import urlopen, Request, HTTPError

from .catalogs import VirtualCatalog

LOG = logging.getLogger(__name__)

IMAGE_TRANSFORMATION = Image()
IMAGE_FORMAT = Optimal()

app = Flask("marblecutter-virtual")
app.register_blueprint(bp)
app.url_map.strict_slashes = False
CORS(app, send_wildcard=True)

class Timer:
    def __init__(self, description):
        self.description = description
    def __enter__(self, *args):
        self.start = datetime.now()
    def __exit__(self, *args):
        duration = (datetime.now() - self.start).total_seconds()
        LOG.info(f'{self.description} took {duration} seconds')

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

@app.route("/test")
def test():
    return (
        render_template(
            "test.html",
            tilejson_url=Markup(
                url_for("meta", _external=True, _scheme="", **request.args)
            ),
        ),
        200,
        {"Content-Type": "text/html"},
    )


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

@app.route("/stac/<int:z>/<int:x>/<int:y>")
@app.route("/stac/<int:z>/<int:x>/<int:y>@<int:scale>x")
def render_png_from_stac_catalog(z, x, y, scale=1):
    with Timer("rendering png from stac catalog"):
        stac_url = request.args.get("url", None)
        jq_filter = request.args.get("jq", None)
        stac_expr = request.args.get("expr", None)
        stac_datetime = request.args.get("datetime", None)

        # size of the tile, usually (256, 256)
        shape = tuple(map(int, Affine.scale(scale) * TILE_SHAPE))

        if stac_expr:
            # captures asset-band combos
            # like B5[0] in (B5[0] - B4[0])/(B5[0] + B4[0])
            # or like NIR in (NIR - RED) / (NIR + RED)
            asset_band_regex = "(?P<asset>[A-Za-z][A-Za-z0-9]+)(?:\[(?P<band>\d+)\])?"
            matches = list(set(re.findall(asset_band_regex, stac_expr)))

            # sorted list of assets and bands
            # like [('B4', 0), ('B5', 0)]
            # or like [('NIR', 0), ('RED', 0)]
            asset_bands = sorted(list(set([(asset, int(band) if band else 0) for asset, band in matches])))

            # sorted list of asset names
            # like ['B4', 'B5']
            # or like ['NIR', 'RED']
            asset_names = sorted(list(set([asset for asset, band in asset_bands])))

            # convert expr from a format for running band math across multiple assets
            # into a format for running band math for a single file for the combined assets
            # from: (NIR - RED) / (NIR + RED)
            # to: (b1 - b2) / (b1 + b2)
            def repl(m):
                asset, band = m.groups()
                band = int(band) if band else 0
                # add one to index number because single-file band math expression
                # requires that band indexes starts at 1, i.e. b1, b2, b3...
                return 'b' + str(asset_bands.index((asset, band)) + 1)
            expr = re.sub(asset_band_regex, repl, stac_expr)
        else:
            asset_names = None
            expr = None

        tile = mercantile.Tile(x, y, z)

        tile_bounds = mercantile.bounds(tile)
        tile_bbox = [tile_bounds.west, tile_bounds.south, tile_bounds.east, tile_bounds.north]

        # we use the parent tile for searching because sometimes
        # a search engine might not return results
        # when the tile is really small
        parent_tile = mercantile.parent(tile)
        search_bounds = mercantile.bounds(parent_tile)

        search_bbox = [
            search_bounds.west,
            search_bounds.south,
            search_bounds.east,
            search_bounds.north
        ]

        tile_polygon = box(*tile_bbox)

        params = {
            'bbox': str(search_bbox).replace(' ', ''),
            'limit': 500,
        }
        if stac_datetime: params['datetime'] = stac_datetime

        with Timer("querying stac"):
            response = requests.get(stac_url, params=params)

        features = response.json()['features']
        LOG.info(f'number of features: {len(features)}')

        # filter features to those that overlap tile
        features = [feature for feature in features if box(*feature['bbox']).intersects(tile_polygon)]

        feature_count = len(features)
        LOG.info(f'number of features after filtering by feature extent: {feature_count}')

        if jq_filter:
            features = jq.compile(jq_filter).input(features).first()
            LOG.info(f'number of features after filtering by jq expression: {len(features)}')

        canvas_bounds = Bounds(bounds=mercantile.xy_bounds(tile), crs=WEB_MERCATOR_CRS)
        LOG.info(f'canvas bounds: {canvas_bounds}')

        assets = []
        for fid, feature in enumerate(features):
            images = {}
            if asset_names:
                for asset_name in asset_names:
                    images[asset_name] = feature['assets'][asset_name]['href']
            elif 'visual' in feature['assets']:
                images['visual'] = feature['assets']['visual']['href']
            else:
                raise "Not sure what assets to use to create the image"

            for asset_name, href in images.items():
                assets.append({
                    "fid": fid,
                    "name": asset_name,
                    "url": href
                })

        if expr and len(asset_names) > 0:
            def add_pixels_to_asset(asset):
                try:
                    url = asset['url']
                    with Timer(f'reading pixels for {url}'):
                        source = Source(url=url, name=url, resolution=None)
                        with get_source(url) as src:
                            with Timer(f'reading window for {url}'):
                                asset['pixels'] = read_window(src, canvas_bounds, shape, source)
                except Exception as e:
                    LOG.error(e)
                    raise e

            with Timer(f'reading all the pixels'):
                with futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    executor.map(add_pixels_to_asset, assets)

            sources = []
            for fid, assets in groupby(assets, lambda asset: asset['fid']):
                assets = list(assets)
                name_to_pixels = dict([(asset['name'], asset['pixels']) for asset in assets])
                windows = tuple([name_to_pixels[name].data[band] for name, band in asset_bands])
                stacked = np.ma.stack(windows)
                names = [asset['name'] for asset in assets]
                source = Source(
                    url=None,
                    name=str(fid) + '{' + ','.join(names) + '}',
                    resolution=None,
                    expr=expr,
                    pixels=PixelCollection(stacked, canvas_bounds),
                    recipes={ "expr": expr, "imagery": True } if expr else {}
                )
                sources.append(source)
        else:
            sources = [Source(
                url=asset['url'],
                name=asset['name'],
                resolution=None,
                recipes={ "expr": expr, "imagery": True } if expr else {}
            ) for asset in assets]

        headers, data = tiling.render_tile_from_sources(
            tile,
            sources,
            format=IMAGE_FORMAT,
            transformation=IMAGE_TRANSFORMATION,
            scale=scale,
        )

        return data, 200, headers


@app.route("/tiles/<int:z>/<int:x>/<int:y>")
@app.route("/tiles/<int:z>/<int:x>/<int:y>@<int:scale>x")
def render_png(z, x, y, scale=1):
    catalog = make_catalog(request.args)
    tile = mercantile.Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        catalog,
        format=IMAGE_FORMAT,
        transformation=IMAGE_TRANSFORMATION,
        scale=scale,
    )

    headers.update(catalog.headers)

    return data, 200, headers
