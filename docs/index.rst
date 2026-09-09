Barograph Documentation
=======================

Weather forecast **modeling**, **post-processing**, and **verification** toolkit.

Barograph ingests NWP model output (GFS, ECMWF, ERA5), applies statistical
downscaling, MOS, and ensemble calibration (EMOS, quantile mapping), verifies
forecasts (CRPS, Brier, reliability diagrams), performs radar nowcasting by
optical flow, and issues threshold-based alerts. It also provides a raster
data layer (terrain, reflectivity, algebra, masking), forecast cycle/blending,
multi-format output (NetCDF, Zarr, CSV, JSON, PNG), delivery of notifications
(Slack, Discord, webhooks, email) and verification dashboards.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   quickstart
   api/index
   cli
   configuration

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
