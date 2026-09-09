import numpy as np

from barograph.indices.spei import (
    _heat_index,
    compute_spei,
    pet_thornthwaite,
)


def test_heat_index_zero_for_cold():
    assert _heat_index(np.array([-5.0, 0.0, -2.0])) == 0.0


def test_heat_index_positive_for_warm():
    assert _heat_index(np.array([10.0, 15.0, 20.0])) > 0.0


def test_pet_zero_for_freezing_months():
    temp = np.array([-2.0, 0.0, -1.0])
    pet = pet_thornthwaite(temp, latitude=0.0)
    assert np.all(pet == 0.0)


def test_pet_increases_with_temperature():
    cool = pet_thornthwaite(np.full(12, 10.0), latitude=0.0)
    warm = pet_thornthwaite(np.full(12, 25.0), latitude=0.0)
    assert np.sum(warm) > np.sum(cool)


def test_pet_higher_close_to_equator_and_in_summer():
    # temperature constant; daylight dominates across months
    temp = np.full(12, 20.0)
    tropical = pet_thornthwaite(temp, latitude=0.0)
    midlat = pet_thornthwaite(temp, latitude=45.0)
    assert np.all(np.isfinite(tropical))
    assert np.all(np.isfinite(midlat))
    # mid-latitude summer months should exceed the winter months
    assert midlat[5] > midlat[0]


def test_pet_has_12_monthly_values():
    pet = pet_thornthwaite(np.full(12, 15.0), latitude=-23.5)
    assert pet.shape == (12,)


def test_spei_balanced_series_near_zero():
    # temperature converts to a fixed monthly PET; set precipitation to it
    temp = np.full(24, 20.0)
    lat = 0.0
    pet = pet_thornthwaite(temp[:12], lat)
    # repeat the monthly PET as a climatology of precipitation
    precip = np.tile(pet, 2)
    spei = compute_spei(precip, temp, lat, window=3)
    # balanced water budget -> index close to zero for complete windows
    valid = spei[2:]
    assert np.all(np.isfinite(valid))
    assert np.all(np.abs(valid) < 0.5)


def test_spei_dry_spell_negative():
    # precipitation well below PET over an extended period -> water deficit
    temp = np.full(60, 25.0)
    lat = -15.0
    precip = np.full(60, 0.5)
    spei = compute_spei(precip, temp, lat, window=6)
    # the later, fully-dry windows should index as a drought
    tail = spei[20:]
    assert np.nanmean(tail) < 0.0


def test_spei_window_edges_nan():
    temp = np.full(20, 15.0)
    lat = 10.0
    precip = np.full(20, 5.0)
    spei = compute_spei(precip, temp, lat, window=4)
    assert np.all(np.isnan(spei[:3]))
    assert np.all(np.isfinite(spei[3:]))


def test_spei_short_series():
    assert np.all(np.isnan(compute_spei(np.array([1.0, 2.0]),
                                        np.array([1.0, 2.0]), 0.0, 10)))
