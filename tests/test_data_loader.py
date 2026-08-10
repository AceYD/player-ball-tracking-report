from pathlib import Path

import pandas as pd
import pytest

from src.data_loader import TrackingDataError, load_tracking_data


PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_sample_csv_and_json_normalize_to_same_records():
    csv_data, csv_quality = load_tracking_data(
        PROJECT_DIR / "data" / "tracking" / "tracking_sample.csv"
    )
    json_data, json_quality = load_tracking_data(
        PROJECT_DIR / "data" / "tracking" / "tracking_sample.json"
    )

    assert csv_quality.valid_rows == json_quality.valid_rows == 3995
    assert csv_quality.ball_rows == json_quality.ball_rows == 120
    columns = [
        "frame",
        "time_sec",
        "player_id",
        "team",
        "player_x",
        "player_y",
        "speed_mps",
        "ball_x",
        "ball_y",
        "occluded",
    ]
    pd.testing.assert_frame_equal(
        csv_data[columns],
        json_data[columns],
        check_dtype=False,
        check_exact=False,
        rtol=1e-9,
    )


def test_out_of_bounds_coordinate_is_reported_and_clipped():
    raw = (
        "frame,time_sec,player_id,team,player_x,player_y,speed_mps,ball_x,ball_y,occluded\n"
        "1,0.1,P01,TEAM_A,40.5,21,1.2,,,False\n"
    ).encode("utf-8")

    data, quality = load_tracking_data(raw, "test.csv")

    assert quality.out_of_bounds_rows == 1
    assert data.loc[0, "player_x_raw"] == 40.5
    assert data.loc[0, "player_x"] == 40.0
    assert data.loc[0, "player_y"] == 20.0


def test_partial_ball_coordinate_is_removed():
    raw = (
        "frame,time_sec,player_id,team,player_x,player_y,speed_mps,ball_x,ball_y,occluded\n"
        "1,0.1,P01,TEAM_A,10,10,1.2,10,,False\n"
    ).encode("utf-8")

    data, quality = load_tracking_data(raw, "test.csv")

    assert quality.partial_ball_rows == 1
    assert pd.isna(data.loc[0, "ball_x"])
    assert pd.isna(data.loc[0, "ball_y"])


def test_missing_required_column_has_clear_error():
    raw = b"frame,time_sec,player_id\n1,0.1,P01\n"

    with pytest.raises(TrackingDataError, match="필수 열"):
        load_tracking_data(raw, "test.csv")

