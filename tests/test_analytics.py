import pandas as pd

from src.analytics import add_movement_segments, calculate_player_stats


def _tracking_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "frame": 0,
                "time_sec": 0.0,
                "player_id": "P01",
                "team": "TEAM_A",
                "player_x": 0.0,
                "player_y": 0.0,
                "speed_mps": 0.0,
                "ball_x": None,
                "ball_y": None,
                "occluded": False,
            },
            {
                "frame": 1,
                "time_sec": 0.5,
                "player_id": "P01",
                "team": "TEAM_A",
                "player_x": 3.0,
                "player_y": 4.0,
                "speed_mps": 5.0,
                "ball_x": None,
                "ball_y": None,
                "occluded": False,
            },
            {
                "frame": 2,
                "time_sec": 10.0,
                "player_id": "P01",
                "team": "TEAM_A",
                "player_x": 30.0,
                "player_y": 15.0,
                "speed_mps": 6.0,
                "ball_x": None,
                "ball_y": None,
                "occluded": False,
            },
        ]
    )


def test_long_tracking_gap_is_not_counted_as_distance():
    segmented = add_movement_segments(_tracking_rows(), max_gap_sec=1.0)
    stats = calculate_player_stats(segmented)

    assert segmented["segment_distance_m"].sum() == 5.0
    assert stats.loc[0, "distance_m"] == 5.0
    assert stats.loc[0, "observed_time_sec"] == 0.5
    assert stats.loc[0, "distance_per_min"] == 600.0


def test_occluded_segment_can_be_excluded():
    rows = _tracking_rows().iloc[:2].copy()
    rows.loc[1, "occluded"] = True

    excluded = add_movement_segments(rows, max_gap_sec=1.0, exclude_occluded=True)
    included = add_movement_segments(rows, max_gap_sec=1.0, exclude_occluded=False)

    assert excluded["segment_distance_m"].sum() == 0.0
    assert included["segment_distance_m"].sum() == 5.0


def test_stationary_valid_segment_counts_as_observed_time():
    rows = _tracking_rows().iloc[:2].copy()
    rows.loc[1, ["player_x", "player_y", "speed_mps"]] = [0.0, 0.0, 0.0]

    segmented = add_movement_segments(rows, max_gap_sec=1.0, exclude_occluded=False)
    stats = calculate_player_stats(segmented, exclude_occluded=False)

    assert stats.loc[0, "distance_m"] == 0.0
    assert stats.loc[0, "observed_time_sec"] == 0.5
    assert stats.loc[0, "distance_per_min"] == 0.0
