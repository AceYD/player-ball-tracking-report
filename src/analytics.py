"""Movement segmentation and player/team statistics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_movement_segments(
    data: pd.DataFrame,
    max_gap_sec: float = 1.0,
    exclude_occluded: bool = True,
) -> pd.DataFrame:
    """Add path segment IDs and valid consecutive-point distances."""

    if data.empty:
        result = data.copy()
        result["time_gap_sec"] = pd.Series(dtype=float)
        result["segment_distance_m"] = pd.Series(dtype=float)
        result["valid_segment"] = pd.Series(dtype=bool)
        result["path_segment"] = pd.Series(dtype="string")
        return result

    result = data.sort_values(["player_id", "time_sec", "frame"], kind="stable").copy()
    grouped = result.groupby("player_id", sort=False)
    previous_x = grouped["player_x"].shift(1)
    previous_y = grouped["player_y"].shift(1)
    previous_time = grouped["time_sec"].shift(1)
    previous_occluded = grouped["occluded"].shift(1, fill_value=False).astype(bool)

    result["time_gap_sec"] = result["time_sec"] - previous_time
    consecutive = result["time_gap_sec"].gt(0) & result["time_gap_sec"].le(max_gap_sec)
    if exclude_occluded:
        consecutive &= ~result["occluded"] & ~previous_occluded

    distances = np.hypot(result["player_x"] - previous_x, result["player_y"] - previous_y)
    result["valid_segment"] = consecutive
    result["segment_distance_m"] = distances.where(consecutive, 0.0).fillna(0.0)

    first_in_player = result["player_id"].ne(result["player_id"].shift(1))
    segment_break = first_in_player | ~consecutive
    segment_number = segment_break.groupby(result["player_id"]).cumsum().astype(int)
    result["path_segment"] = result["player_id"].astype(str) + "-" + segment_number.astype(str)
    return result


def calculate_player_stats(
    segmented: pd.DataFrame,
    exclude_occluded: bool = True,
) -> pd.DataFrame:
    """Calculate documented MVP statistics for each player."""

    columns = [
        "player_id",
        "team",
        "distance_m",
        "distance_per_min",
        "avg_speed_mps",
        "max_speed_mps",
        "observed_time_sec",
        "data_points",
        "occluded_points",
        "occlusion_pct",
        "ball_points",
    ]
    if segmented.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for player_id, group in segmented.groupby("player_id", sort=True):
        speed_rows = group.loc[~group["occluded"]] if exclude_occluded else group
        speed_rows = speed_rows.loc[speed_rows["speed_mps"].ge(0)]
        distance_m = float(group["segment_distance_m"].sum())
        observed_time_sec = float(group.loc[group["valid_segment"], "time_gap_sec"].sum())
        distance_per_min = distance_m / (observed_time_sec / 60) if observed_time_sec > 0 else 0.0
        rows.append(
            {
                "player_id": player_id,
                "team": group["team"].mode().iloc[0],
                "distance_m": distance_m,
                "distance_per_min": distance_per_min,
                "avg_speed_mps": speed_rows["speed_mps"].mean() if not speed_rows.empty else 0.0,
                "max_speed_mps": speed_rows["speed_mps"].max() if not speed_rows.empty else 0.0,
                "observed_time_sec": observed_time_sec,
                "data_points": len(group),
                "occluded_points": int(group["occluded"].sum()),
                "occlusion_pct": group["occluded"].mean() * 100,
                "ball_points": int(group[["ball_x", "ball_y"]].notna().all(axis=1).sum()),
            }
        )

    stats = pd.DataFrame(rows, columns=columns)
    numeric = [
        "distance_m",
        "distance_per_min",
        "avg_speed_mps",
        "max_speed_mps",
        "observed_time_sec",
        "occlusion_pct",
    ]
    stats[numeric] = stats[numeric].round(2)
    return stats


def calculate_team_stats(
    segmented: pd.DataFrame,
    player_stats: pd.DataFrame,
    exclude_occluded: bool = True,
) -> pd.DataFrame:
    """Aggregate movement and coverage information by team."""

    columns = [
        "team",
        "players",
        "distance_m",
        "avg_speed_mps",
        "max_speed_mps",
        "data_points",
        "occlusion_pct",
        "ball_points",
    ]
    if segmented.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for team, group in segmented.groupby("team", sort=True):
        speed_rows = group.loc[~group["occluded"]] if exclude_occluded else group
        speed_rows = speed_rows.loc[speed_rows["speed_mps"].ge(0)]
        team_players = player_stats.loc[player_stats["team"].eq(team)]
        rows.append(
            {
                "team": team,
                "players": int(group["player_id"].nunique()),
                "distance_m": team_players["distance_m"].sum(),
                "avg_speed_mps": speed_rows["speed_mps"].mean() if not speed_rows.empty else 0.0,
                "max_speed_mps": speed_rows["speed_mps"].max() if not speed_rows.empty else 0.0,
                "data_points": len(group),
                "occlusion_pct": group["occluded"].mean() * 100,
                "ball_points": int(group[["ball_x", "ball_y"]].notna().all(axis=1).sum()),
            }
        )

    stats = pd.DataFrame(rows, columns=columns)
    numeric = ["distance_m", "avg_speed_mps", "max_speed_mps", "occlusion_pct"]
    stats[numeric] = stats[numeric].round(2)
    return stats
