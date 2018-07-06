# coding=utf-8
from __future__ import absolute_import

import logging

import numpy as np

from marblecutter import _isimage
from marblecutter.utils import PixelCollection
from marblecutter.formats.jpeg import JPEG
from marblecutter.formats.png import PNG

LOG = logging.getLogger(__name__)
JPEG_FORMAT = JPEG()
PNG_FORMAT = PNG()


def Optimalnd():

    def _format(pixels, data_format):
        if not _isimage(data_format):
            raise Exception("Must be an image format")

        alpha = pixels.data[:, :, 3]

        if np.equal(alpha, 255).all():
            # solid
            rgb_pixels = PixelCollection(
                pixels.data[:, :, 0:3], pixels.bounds, pixels.band
            )
            return JPEG_FORMAT(rgb_pixels, "RGB")
        else:
            # partially transparent
            return PNG_FORMAT(pixels, data_format)

    return _format
