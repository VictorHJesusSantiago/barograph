"""Statistical downscaling methods."""

from barograph.downscaling.bias_correction import BiasCorrectionDownscaler
from barograph.downscaling.mos_downscaling import MOSDownscaler
from barograph.downscaling.quantile_delta_transform import QDTDownscaler

__all__ = ["QDTDownscaler", "MOSDownscaler", "BiasCorrectionDownscaler"]
