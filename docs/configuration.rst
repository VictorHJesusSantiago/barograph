Configuration
=============

Barograph uses YAML configuration files for all settings.

Settings File
-------------

The main configuration file (``configs/settings.yaml``) contains settings for all subsystems:

.. code-block:: yaml

   ingestion:
     gfs_base_url: "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
     era5_cds_dataset: "reanalysis-era5-single-levels"
     cache_dir: "data/cache"

   downscaling:
     method: "quantile_delta_transform"
     qdt_method: "linear"

   mos:
     algorithm: "gradient_boosting"
     n_estimators: 100
     cross_validation_folds: 5

   ensemble:
     method: "parametric"
     distribution: "normal"

   postprocessing:
     emos_loss: "crps"
     quantile_mapping_method: "empirical"

   verification:
     crps_method: "ensemble"
     n_bootstrap: 1000

   nowcasting:
     optical_flow_method: "farneback"
     advection_method: "semi_lagrangian"

   alerts:
     cooldown_minutes: 60
     notification_channels:
       - stdout
       - webhook
     webhook_url: ""

   raster:
     input_dir: "data/raster"
     output_dir: "output/raster"
     default_crs: 4326
     nodata: -9999.0
     resample_method: nearest

   notifications:
     channels:
       - console
     webhook_url: ""
     max_retries: 3
     backoff_base: 1.0
     timeout_seconds: 5.0
     file_path: "logs/notifications.jsonl"
     smtp_host: ""
     smtp_port: 587

   output:
     format: netcdf
     base_dir: "output"
     render_png: false
     png_dpi: 100
     cmap: viridis

   log_level: "INFO"
   n_workers: 4

Alert Rules File
----------------

Alert rules are defined in ``configs/alert_rules.yaml``:

.. code-block:: yaml

   rules:
     - name: "heavy_rain"
       variable: "precipitation"
       threshold: 50.0
       operator: "greater_or_equal"
       severity: "warning"
       duration_minutes: 60

     - name: "extreme_rain"
       variable: "precipitation"
       threshold: 100.0
       operator: "greater_or_equal"
       severity: "severe"
       duration_minutes: 30

Environment Variables
---------------------

Configuration values can be overridden using environment variables with the prefix ``BAROGRAPH_``:

.. code-block:: bash

   export BAROGRAPH_LOG_LEVEL=DEBUG
   export BAROGRAPH_N_WORKERS=8

Dataclasses
-----------

All configuration is validated using Python dataclasses defined in
``barograph.core.config``:

- ``IngestionConfig``
- ``DownscalingConfig``
- ``MOSConfig``
- ``EnsembleConfig``
- ``PostprocessingConfig``
- ``VerificationConfig``
- ``NowcastingConfig``
- ``AlertsConfig``
- ``RasterConfig``
- ``NotificationsConfig``
- ``OutputConfig``
- ``Settings`` (top-level container)
