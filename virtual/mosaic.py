# noqa
# coding=utf-8
from __future__ import absolute_import, division, print_function

import logging
import multiprocessing
from concurrent import futures

import numpy as np

from rasterio import warp

from virtual import recipes
from marblecutter.utils import Bounds, PixelCollection

LOG = logging.getLogger(__name__)


def composite(sources, bounds, shape, target_crs, band_count):
    """Composite data from sources into a single raster covering bounds, but in
    the target CRS."""
    # avoid circular dependencies
    from marblecutter import _nodata, get_resolution_in_meters, get_source, read_window

    # TODO this belongs in render
    if bounds.crs == target_crs:
        canvas_bounds = bounds
    else:
        canvas_bounds = Bounds(
            warp.transform_bounds(bounds.crs, target_crs, *bounds.bounds), target_crs
        )

    resolution = get_resolution_in_meters(bounds, shape)
    sources = recipes.preprocess(sources, resolution=resolution)

    def _read_window(source):
        with get_source(source.url) as src:
            LOG.info(
                "Compositing %s (%s) as band %s", source.url, source.name, source.band
            )

            # read a window from the source data
            # TODO ask for a buffer here, get back an updated bounding box
            # reflecting it
            try:
                window_data = read_window(src, canvas_bounds, shape, source.recipes)
            except Exception as e:
                LOG.exception("Error reading %s: %s", source.url, e)
                return

            return source, PixelCollection(
                window_data.data, window_data.bounds, source.band
            )

    # iterate over available sources, sorted by decreasing "quality"
    with futures.ThreadPoolExecutor(
        max_workers=multiprocessing.cpu_count() * 5
    ) as executor:
        ws = executor.map(_read_window, sources)

    sources_used = []

    ws = recipes.postprocess(ws)

    canvas_data = np.ma.zeros(
        (band_count,) + shape, dtype=np.float32, fill_value=_nodata(np.float32)
    )
    canvas_data.mask = True

    canvas = PixelCollection(canvas_data, canvas_bounds)

    for source, window_data in filter(None, ws):
        window_data = recipes.apply(source.recipes, window_data, source=source)

        if window_data.data is None:
            continue

        # paste the resulting data onto a canvas
        canvas = paste(
            PixelCollection(
                window_data.data.astype(np.float32),
                window_data.bounds,
                window_data.band,
            ),
            canvas,
        )
        sources_used.append(source)

        if not canvas.data.mask.any():
            # stop if all pixels are valid
            break

    return map(lambda s: (s.name, s.url), sources_used), canvas


def paste(window_pixels, canvas_pixels):
    """ "Reproject" src data into the correct position within a larger image"""
    window_data, (window_bounds, window_crs), band = window_pixels
    canvas, (canvas_bounds, canvas_crs), _ = canvas_pixels
    if window_crs != canvas_crs:
        raise Exception("CRSes must match: {} != {}".format(window_crs, canvas_crs))

    if window_bounds != canvas_bounds:
        raise Exception(
            "Bounds must match: {} != {}".format(window_bounds, canvas_bounds)
        )

    if band is None and window_data.shape != canvas.shape:
        raise Exception(
            "Data shapes must match: {} != {}".format(window_data.shape, canvas.shape)
        )

    if band is None:
        merged = np.ma.where(canvas.mask & ~window_data.mask, window_data, canvas)
        merged.fill_value = canvas.fill_value
    else:
        merged_band = np.ma.where(
            canvas.mask[band] & ~window_data.mask, window_data, canvas[band]
        )
        canvas[band] = merged_band[0]
        merged = canvas

    return PixelCollection(merged, canvas_pixels.bounds)
