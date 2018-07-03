# coding=utf-8
from __future__ import absolute_import

import logging

import mercantile
from affine import Affine
from rasterio.crs import CRS

from marblecutter import Bounds, render

LOG = logging.getLogger(__name__)
TILE_SHAPE = (256, 256)
WEB_MERCATOR_CRS = CRS.from_epsg(3857)
WGS84_CRS = CRS.from_epsg(4326)


# coding=utf-8
from __future__ import absolute_import, division, print_function

import logging
import math
import unicodedata

from haversine import haversine
import numpy as np
import rasterio
from rasterio import transform, warp, windows
from rasterio._err import CPLE_OutOfMemoryError
from rasterio.crs import CRS
from rasterio.enums import MaskFlags
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling

from marblecutter import mosaic
from marblecutter.stats import Timer
from marblecutter.utils import Bounds, PixelCollection
from marblecutter import get_resolution_in_meters, NoDataAvailable



def render_nd_tile(tile, catalog, transformation=None, format=None, scale=1, data_band_count=3):
    """Render a tile into Web Mercator."""
    bounds = Bounds(mercantile.xy_bounds(tile), WEB_MERCATOR_CRS)
    shape = tuple(map(int, Affine.scale(scale) * TILE_SHAPE))

    catalog.validate(tile)

    return render_nd(
        bounds,
        shape,
        WEB_MERCATOR_CRS,
        catalog=catalog,
        format=format,
        data_band_count=data_band_count,
        transformation=transformation,
    )


def performBandMath(pixels, catalog):

    if (catalog.band1 is not None) and (catalog.band2 is not None):

        band1 = int(catalog.band1) if isinstance(catalog.band1, str) else catalog.band1
        band2 = int(catalog.band2) if isinstance(catalog.band2, str) else catalog.band2

        bandTile1 = pixels.data[band1]
        bandTile2 = pixels.data[band2]

        np.seterr(divide='ignore', invalid='ignore')
        new_pixel_collection =  PixelCollection((bandTile2.astype(float) - bandTile1.astype(float)) / (bandTile2.astype(float) + bandTile1.astype(float)),
                         pixels.bounds,
                         pixels.band)

    else:
        ##TODO introduce new error
        raise NoDataAvailable()

    return new_pixel_collection

def render_nd(
    bounds,
    shape,
    target_crs,
    format,
    data_band_count,
    catalog=None,
    sources=None,
    transformation=None,
    nd_calc=True

):
    """Render data intersecting bounds into shape using an optional
    transformation. And perform normative diference using bands specified in catalog"""
    resolution_m = get_resolution_in_meters(bounds, shape)
    stats = []

    if sources is None and catalog is None:
        raise Exception("Either sources or a catalog must be provided.")

    if transformation:
        bounds, shape, offsets = transformation.expand(bounds, shape)

    if sources is None and catalog is not None:
        with Timer() as t:
            sources = catalog.get_sources(bounds, resolution_m)
        stats.append(("Get Sources", t.elapsed))

    # TODO try to avoid materializing the iterator
    sources = list(sources)

    if sources is None or len(sources) == 0:
        raise NoDataAvailable()

    with Timer() as t:
        sources_used, pixels = mosaic.composite(
            sources, bounds, shape, target_crs, data_band_count
        )
    stats.append(("Composite", t.elapsed))

    if pixels.data is None:
        raise NoDataAvailable()

    data_format = "raw"

    if transformation:
        with Timer() as t:
            pixels, data_format = transformation.transform(pixels)
        stats.append(("Transform", t.elapsed))

        with Timer() as t:
            pixels = transformation.postprocess(pixels, data_format, offsets)

        stats.append(("Post-process", t.elapsed))

    if nd_calc:
        pixels = performBandMath(pixels, catalog)

    with Timer() as t:
        (content_type, formatted) = format(pixels, data_format)
    stats.append(("Format", t.elapsed))

    headers = {
        "Content-Type": content_type,
        "Server-Timing": [
            'op{};desc="{}";dur={:0.2f}'.format(i, name, time)
            for (i, (name, time)) in enumerate(stats)
        ]
        + [
            'src{};desc="{} - {}"'.format(
                i,
                unicodedata.normalize("NFKD", unicode(name)).encode(
                    "ascii", "ignore"
                ).replace(
                    '"', '\\"'
                ),
                url,
            )
            for (i, (name, url)) in enumerate(sources_used)
        ],
    }

    return (headers, formatted)
