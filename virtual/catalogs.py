# coding=utf-8

import math
from marblecutter import Bounds, get_resolution_in_meters, get_source, get_zoom
from marblecutter.catalogs import WGS84_CRS, Catalog
from marblecutter.utils import Source
from rasterio import warp


class VirtualCatalog(Catalog):

    def __init__(self, uri, rgb=None, nodata=None, linear_stretch=None):
        self._uri = uri
        self._rgb = rgb
        self._nodata = nodata
        self._linear_stretch = nodata

        with get_source(self._uri) as src:
            self._bounds = warp.transform_bounds(src.crs, WGS84_CRS, *src.bounds)
            self._resolution = get_resolution_in_meters(
                Bounds(src.bounds, src.crs), (src.height, src.width)
            )
            approximate_zoom = get_zoom(max(self._resolution), op=math.ceil)

        self._center = [
            (self._bounds[0] + self.bounds[2]) / 2,
            (self._bounds[1] + self.bounds[3]) / 2,
            approximate_zoom - 3,
        ]
        self._maxzoom = approximate_zoom + 3
        self._minzoom = approximate_zoom - 10

    @property
    def uri(self):
        return self._uri

    def get_sources(self, bounds, resolution):
        recipes = {"imagery": True}

        if self._nodata is not None:
            recipes["nodata"] = self._nodata

        yield Source(self._uri, self._name, self._resolution, {}, {}, recipes)
