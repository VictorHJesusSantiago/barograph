CLI Reference
=============

Barograph provides a Click-based command-line interface.

Commands
--------

ingest
^^^^^^

Ingest and parse NWP model files.

.. code-block:: bash

   barograph ingest --gfs-file path/to/gfs.grib2 --variable temperature
   barograph ingest --ecmwf-file path/to/ecmwf.grib --variable precipitation

Options:

- ``--gfs-file``: Path to GFS GRIB2 file
- ``--ecmwf-file``: Path to ECMWF GRIB file
- ``--variable, -var``: Variable name (temperature, precipitation, ...)

downscale
^^^^^^^^^

Statistically downscale a coarse forecast using QDT or bias correction.

.. code-block:: bash

   barograph downscale --field path/to/forecast.nc --variable precipitation

Options:

- ``--field, -f``: Path to a saved forecast NetCDF
- ``--variable, -var``: Variable to downscale

check-alerts
^^^^^^^^^^^^

Check a gridded forecast against threshold alert rules.

.. code-block:: bash

   barograph check-alerts --field path/to/field.nc --threshold 50 --variable precipitation

Options:

- ``--field, -f``: Path to saved NetCDF field to check
- ``--threshold``: Alert threshold value
- ``--variable, -var``: Variable name
- ``--lat-range``: Latitude min,max for region
- ``--lon-range``: Longitude min,max for region

verify
^^^^^^

Run verification on forecast ensembles.

.. code-block:: bash

   barograph verify --members-dir path/to/members/ --metric crps

Options:

- ``--members-dir, -d``: Directory of member NetCDF files
- ``--metric, -m``: Verification metric to compute

nowcast
^^^^^^^

Run radar nowcasting via optical flow.

.. code-block:: bash

   barograph nowcast --radar-dir path/to/radar/ --lead-minutes 60

Options:

- ``--radar-dir, -r``: Directory of radar sweep NetCDF files
- ``--lead-minutes, -l``: Lead time in minutes for nowcast

load-rules
^^^^^^^^^^

Load alert rules from a YAML file.

.. code-block:: bash

   barograph load-rules --rule-file configs/alert_rules.yaml

Options:

- ``--rule-file, -r``: YAML file of alert rules

raster
^^^^^^

Raster sub-commands operate on gridded geospatial layers.

.. code-block:: bash

   barograph raster summary --file path/to/dem.nc
   barograph raster rainfall --file path/to/reflectivity.nc --output rain.nc
   barograph raster terrain --file path/to/dem.nc --variable slope

Sub-commands and options:

- ``summary``: print layer summary, optionally with ``--lat``/``--lon`` to sample a point
- ``rainfall``: convert dBZ reflectivity to rainfall rate (``--format`` json/csv/netcdf/npy, ``--output``)
- ``terrain``: derive slope/aspect/curvature/hillshade/ruggedness (``--variable``, ``--output``)

notify
^^^^^^

Send a test notification through configured channels.

.. code-block:: bash

   barograph notify --title "Heavy rain" --body "50 mm expected" --severity warning

Options:

- ``--title, -t``: Notification title
- ``--body, -b``: Notification body
- ``--severity, -s``: info/warning/critical

export
^^^^^^

Export a field/analysis to a chosen format (including PNG rendering).

.. code-block:: bash

   barograph export --field path/to/field.nc --format netcdf --output out.nc

Options:

- ``--field, -f``: Path to a NetCDF grid field
- ``--format, -fmt``: json/csv/netcdf/zarr/npy/png
- ``--output, -o``: Output path

config-show
^^^^^^^^^^^

Print the active configuration as YAML.

.. code-block:: bash

   barograph config-show

climate
^^^^^^^

Fetch and summarize daily weather for a point via Open-Meteo.

.. code-block:: bash

   barograph climate --lats -23.5 --lons -46.6 --days 7

Options:

- `--lats/-la`: Latitude of the point
- `--lons/-lo`: Longitude of the point
- `--days/-d`: Number of forecast days to fetch

risk
^^^^

Compute a hazard index from a raster field (hail, wind or flood).

.. code-block:: bash

   barograph risk --file cape.nc --kind hail

Options:

- `--file, -f`: NetCDF raster field to evaluate
- `--kind, -k`: hail / wind / flood

model-train
^^^^^^^^^^^

Train a regression pipeline on a CSV and persist it.

.. code-block:: bash

   barograph model-train --data training.csv --target temperature --kind ridge --output model.pkl

Options:

- `--data, -d`: CSV with feature columns and a target column
- `--target, -t`: Target column name
- `--kind, -k`: linear / ridge / forest
- `--output, -o`: Output model path

qc
^^

Run quality-control checks on a time series CSV.

.. code-block:: bash

   barograph qc --file observations.csv --min-value -50 --max-value 50 --persistence 6

Options:

- `--file, -f`: CSV with a ``time`` (ISO-8601) and a ``value`` column
- `--min-value` / `--max-value`: Physical bounds for the gross-range check
- `--spike-sigma`: MAD threshold for spike detection
- `--persistence`: Run length above which identical values are flagged

derived
^^^^^^^

Compute derived meteorological quantities.

.. code-block:: bash

   barograph derived thermal --temperature 35 --rh 80 --wind 2
   barograph derived precip --series rain.csv

Options (``thermal``):

- `--temperature, -t`: Air temperature in Celsius
- `--rh`: Relative humidity in percent
- `--wind, -w`: Wind speed in m/s

Options (``precip``):

- `--series, -s`: CSV with a ``time`` and a ``value`` (mm) column

extreme
^^^^^^^

Fit an extreme-value distribution and report return levels, using either the
block-maxima GEV method or the peak-over-threshold (GPD) method.

.. code-block:: bash

   barograph extreme --file extremes.csv --period 10 --period 50 --block-size 5
   barograph extreme --file series.csv --method pot --threshold 8 --period 20

Options:

- `--file, -f`: CSV with a ``value`` column of observations/extremes
- `--period, -p`: Return periods (blocks) to report
- `--method, -m`: ``gev`` (block-maxima) or ``pot`` (peak-over-threshold)
- `--block-size, -b`: Group raw series into blocks of this many samples first
- `--threshold, -t`: Threshold for the peak-over-threshold method

spi
^^^

Compute the Standardized Precipitation Index from a precipitation series.

.. code-block:: bash

   barograph spi --file precip.csv --window 4 --current

Options:

- `--file, -f`: CSV with a ``value`` column of precipitation (mm)
- `--window, -w`: Accumulation window size (periods)
- `--current, -c`: Also print the index of the most recent accumulation

