"""Guard rails on the ingest contract and the trained model's behaviour."""
import pandas as pd
import pytest
from sklearn.metrics import r2_score

from src.config import FORBIDDEN, LAG_WARMUP, TARGET
from src.features import build_features, feature_columns, reindex_to_calendar
from src.ingest import load_raw
from src.train import MODELS, temporal_split

# Raw columns the model consumes verbatim. They must be named explicitly.
# build_features() copies the raw frame wholesale and feature_columns()
# keeps every numeric column outside FORBIDDEN, so "reaches the model" is
# not a decision anyone made -- a numeric column appended to the CSV
# tomorrow would become a feature with no edit to src/ and no failing test.
# Listing them here is what turns that accident back into a decision.
RAW_PASSTHROUGH_FEATURES = {"temp", "atemp", "hum", "windspeed"}

# Raw columns that are neither model features nor in FORBIDDEN. Three are
# consumed by build_features under a new name; three are present in the
# mirror and deliberately unused (all redundant with dteday). Each is known
# at time t, so none of them can leak.
EXPECTED_RAW_INPUTS = {
    "holiday": "consumed -> is_holiday",
    "workday": "consumed -> is_workday",
    "weather": "consumed -> weather_severity",
    "season": "present, unused: redundant with dteday month",
    "mnth": "present, unused: redundant with dteday month",
    "weekday": "present, unused: redundant with dteday dayofweek",
}


@pytest.fixture(scope="module")
def raw():
    return load_raw().sort_values("dteday").reset_index(drop=True)


@pytest.fixture(scope="module")
def feats(raw):
    return build_features(raw)


def test_calendar_is_complete_before_lagging(raw):
    """The reindexed frame must have no gaps, or the lags are wrong."""
    grid = reindex_to_calendar(raw)
    assert set(grid.dteday.diff().dropna().dt.days.unique()) == {1}


def test_only_expected_rows_are_dropped(raw, feats):
    """Rows may only vanish for the lag warm-up or downstream of a genuinely
    absent day -- never because an encoder produced a silent NaN.

    Accounting: the first LAG_WARMUP days have no complete history. Each
    absent calendar day m costs the LAG_WARMUP rows after it (cnt_lag_1 is
    NaN on m+1, cnt_roll_7 is NaN on m+1..m+7, cnt_lag_7 on m+7; their
    union is 7 rows). Day m itself was never in `raw`, so it is not a loss.
    The bound is exact for the current feature set; add a longer lag and
    LAG_WARMUP in src/config.py must grow with it.
    """
    full = pd.date_range(raw.dteday.min(), raw.dteday.max(), freq="D")
    missing_days = len(full) - len(raw)
    allowed_loss = LAG_WARMUP + LAG_WARMUP * missing_days
    lost = len(raw) - len(feats)
    assert lost <= allowed_loss, f"lost {lost} rows; expected at most {allowed_loss}"


def test_beats_the_mean_baseline(feats):
    """A model that cannot beat predicting the training mean is not a result."""
    cols = feature_columns(feats)
    train, _, test = temporal_split(feats)
    ridge = MODELS["ridge"]
    ridge.fit(train[cols], train[TARGET])
    assert r2_score(test[TARGET], ridge.predict(test[cols])) > 0.4


def test_persistence_baseline_is_reported():
    """The baseline that matters for a lag-driven model is 'yesterday again'.
    It must be in the comparison, whatever its score."""
    assert "baseline_persistence" in MODELS


def test_every_raw_column_is_classified(raw, feats):
    """A column appended to the raw CSV must not enter the model silently.

    build_features() copies the raw frame wholesale and feature_columns()
    keeps every numeric column not in FORBIDDEN -- so a new numeric column
    downloaded tomorrow becomes a feature with no edit to src/ and no
    failing test. This is the gap that matters: the other guard,
    test_no_forbidden_features, checks that FORBIDDEN is respected, but
    nothing checks that a column was ever considered for FORBIDDEN.

    Every raw column must therefore fall in exactly one bucket: dteday (the
    calendar index), FORBIDDEN, EXPECTED_RAW_INPUTS, or
    RAW_PASSTHROUGH_FEATURES. An unclassified column means someone must
    decide which bucket it belongs in and say why -- which is the entire
    point.

    Note what is deliberately NOT a bucket: "is a feature column". Every raw
    column is either numeric-and-not-forbidden, hence already a feature, or
    it is not. Accepting that as classification would let exactly the column
    this test exists to catch arrive silently, since it would qualify by
    default. The pass-throughs are named instead.
    """
    cols = set(feature_columns(feats))
    unclassified = [
        c
        for c in raw.columns
        if c != "dteday"
        and c not in FORBIDDEN
        and c not in EXPECTED_RAW_INPUTS
        and c not in RAW_PASSTHROUGH_FEATURES
    ]
    assert not unclassified, (
        f"raw columns classified nowhere: {sorted(unclassified)}. "
        "Add each to FORBIDDEN (with a reason), or to EXPECTED_RAW_INPUTS "
        "or RAW_PASSTHROUGH_FEATURES in this file -- do not let a new column "
        "reach the model by default."
    )

    # The buckets must be disjoint. Without this, a column could be moved
    # into EXPECTED_RAW_INPUTS to silence the check above while still
    # flowing to the model, defeating the test while it stays green.
    overlap = (set(FORBIDDEN) | set(EXPECTED_RAW_INPUTS)) & cols
    assert not overlap, f"columns both classified as non-features and used as features: {sorted(overlap)}"

    # Every declared pass-through must really be one. If the raw file gains
    # such a column it is covered above; if src/ drops one, this fires
    # rather than leaving a stale claim behind.
    missing = RAW_PASSTHROUGH_FEATURES - set(raw.columns)
    assert not missing, f"declared pass-through columns absent from the raw file: {sorted(missing)}"
    not_in_model = RAW_PASSTHROUGH_FEATURES - cols
    assert not not_in_model, f"pass-through columns not actually in the feature set: {sorted(not_in_model)}"

    # And nothing may be classified that the raw file does not actually
    # have, or a stale entry would hide that column's real arrival later.
    stale = (set(EXPECTED_RAW_INPUTS) | FORBIDDEN) - set(raw.columns)
    assert not stale, f"classified columns absent from the raw file: {sorted(stale)}"
