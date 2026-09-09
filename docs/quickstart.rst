Quick Start
===========

Installation
------------

.. code-block:: bash

   pip install -e ".[dev]"

Basic Usage
-----------

Ingesting GFS Data
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from barograph.ingestion import GFSIngester
   from barograph.core.config import load_config

   settings = load_config()
   ingester = GFSIngester(settings.ingestion)
   field = ingester.parse_grib("path/to/gfs.grib2", "temperature")

Ensemble Processing
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from barograph.ensemble.statistics import EnsembleStatistics

   stats = EnsembleStatistics()
   mean = stats.ensemble_mean(ensemble)
   spread = stats.ensemble_spread(ensemble)

Verification
^^^^^^^^^^^^

.. code-block:: python

   from barograph.verification.metrics import VerificationMetrics

   metrics = VerificationMetrics()
   mae = metrics.mae(obs, pred)
   rmse = metrics.rmse(obs, pred)

Alerts
^^^^^^

.. code-block:: python

   from barograph.alerts import AlertEngine
   from barograph.alerts.rules import AlertRule, Operator, Severity

   engine = AlertEngine(notification_channels=["stdout"])
   engine.add_rule(AlertRule(
       variable=Variable.PRECIPITATION,
       threshold=50.0,
       operator=Operator.GREATER_OR_EQUAL,
       severity=Severity.SEVERE,
   ))
   alerts = engine.evaluate_field(field)

Raster Analysis
^^^^^^^^^^^^^^^

.. code-block:: python

   from barograph.raster.layer import RasterLayer, CRS
   from barograph.raster.terrain import Terrain
   from barograph.raster.reflectivity import Reflectivity

   dem = RasterLayer(data=..., lats=..., lons=..., name="dem", crs=CRS(epsg=4326))
   slope = Terrain.slope(dem)
   rain_rate = Reflectivity().rainfall_rate(dbz_band)

Notifications
^^^^^^^^^^^^^

.. code-block:: python

   from barograph.notifications import NotificationManager, NotificationMessage

   manager = NotificationManager(channels=["console", "slack"], webhook_url="https://hooks.slack.com/...")
   manager.notify(NotificationMessage(title="Heavy rain", body="50 mm expected", severity="warning"))

Multi-format Output
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from barograph.output.serializers import OutputWriter

   OutputWriter(fmt="netcdf").write(field, "out.nc")
   OutputWriter(fmt="zarr").write(field, "out.zarr")

CLI Usage
---------

.. code-block:: bash

   barograph --config configs/settings.yaml ingest --gfs-file data/model.grib2 --variable temperature
   barograph --config configs/settings.yaml check-alerts --field out.nc --threshold 50
   barograph --config configs/settings.yaml nowcast --radar-dir data/radar --lead-minutes 60
   barograph --config configs/settings.yaml raster summary --file data/dem.nc
   barograph --config configs/settings.yaml notify --title "Heavy rain" --body "50 mm expected"
   barograph --config configs/settings.yaml export --field out.nc --format netcdf --output exported.nc
   barograph --config configs/settings.yaml config-show
