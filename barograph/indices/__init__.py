"""Climate indices for drought and water-resource monitoring."""

from barograph.indices.spei import (
    SPEIResult,
    compute_spei,
    pet_thornthwaite,
)
from barograph.indices.spi import (
    SPIResult,
    classify_drought,
    compute_spi,
    compute_spi_series,
)

__all__ = [
    "SPIResult",
    "compute_spi",
    "compute_spi_series",
    "classify_drought",
    "SPEIResult",
    "compute_spei",
    "pet_thornthwaite",
]
