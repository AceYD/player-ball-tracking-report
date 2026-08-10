import pandas as pd

from src.data_loader import DataQualityReport
from src.report_generator import generate_rule_based_report
from src.visualizations import create_heatmap_figure, create_movement_figure


def test_custom_player_name_is_used_in_path_legend():
    segmented = pd.DataFrame(
        [
            {
                "player_id": "P01",
                "path_segment": "P01-1",
                "player_x": 1.0,
                "player_y": 2.0,
                "time_sec": 0.0,
                "speed_mps": 1.0,
                "team": "TEAM_A",
                "occluded": False,
            },
            {
                "player_id": "P01",
                "path_segment": "P01-1",
                "player_x": 2.0,
                "player_y": 3.0,
                "time_sec": 0.5,
                "speed_mps": 2.0,
                "team": "TEAM_A",
                "occluded": False,
            },
        ]
    )

    figure = create_movement_figure(segmented, ["P01"], {"P01": "김민수"})

    assert any(trace.name == "김민수 (P01)" for trace in figure.data)


def test_custom_player_name_is_used_in_summary():
    player_stats = pd.DataFrame(
        [
            {
                "player_id": "P01",
                "player_name": "김민수",
                "team": "TEAM_A",
                "distance_m": 100.0,
                "avg_speed_mps": 2.0,
                "max_speed_mps": 8.0,
            }
        ]
    )
    team_stats = pd.DataFrame(
        [
            {
                "team": "TEAM_A",
                "distance_m": 100.0,
                "data_points": 10,
                "ball_points": 1,
            }
        ]
    )
    quality = DataQualityReport(source_name="test.csv", raw_rows=10, valid_rows=10)

    summary = generate_rule_based_report(player_stats, team_stats, quality)

    assert "김민수 (P01)" in " ".join(summary)


def test_heatmap_uses_bright_color_for_low_density_cells():
    data = pd.DataFrame(
        [
            {"player_x": 1.0, "player_y": 1.0},
            {"player_x": 30.0, "player_y": 15.0},
        ]
    )

    figure = create_heatmap_figure(data)
    heatmap = figure.data[0]

    assert heatmap.type == "heatmap"
    assert heatmap.zmin == 1
    assert heatmap.colorscale[0][1] == "#bae6fd"
