"""Plotly figures for paths, heatmaps and ball possession points."""

from __future__ import annotations

from itertools import cycle

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .data_loader import COURT_HEIGHT_M, COURT_WIDTH_M


PLAYER_COLORS = [
    "#38bdf8",
    "#f97316",
    "#a78bfa",
    "#22c55e",
    "#f43f5e",
    "#eab308",
    "#14b8a6",
    "#fb7185",
    "#818cf8",
    "#84cc16",
    "#06b6d4",
    "#c084fc",
]

TEAM_COLORS = {"TEAM_A": "#38bdf8", "TEAM_B": "#f97316"}


def _player_label(player_id: str, player_names: dict[str, str] | None) -> str:
    if not player_names:
        return player_id
    player_name = str(player_names.get(player_id, player_id)).strip() or player_id
    return player_id if player_name == player_id else f"{player_name} ({player_id})"


def _court_figure(title: str) -> go.Figure:
    figure = go.Figure()
    line = {"color": "rgba(226, 232, 240, 0.85)", "width": 2}
    shapes = [
        {
            "type": "rect",
            "x0": 0,
            "y0": 0,
            "x1": COURT_WIDTH_M,
            "y1": COURT_HEIGHT_M,
            "line": line,
            "layer": "above",
        },
        {
            "type": "line",
            "x0": COURT_WIDTH_M / 2,
            "y0": 0,
            "x1": COURT_WIDTH_M / 2,
            "y1": COURT_HEIGHT_M,
            "line": line,
            "layer": "above",
        },
        {
            "type": "circle",
            "x0": COURT_WIDTH_M / 2 - 3,
            "y0": COURT_HEIGHT_M / 2 - 3,
            "x1": COURT_WIDTH_M / 2 + 3,
            "y1": COURT_HEIGHT_M / 2 + 3,
            "line": line,
            "layer": "above",
        },
    ]
    figure.update_layout(
        title={"text": title, "x": 0.02},
        template="plotly_dark",
        paper_bgcolor="#07151c",
        plot_bgcolor="#0f3d35",
        height=540,
        margin={"l": 45, "r": 25, "t": 65, "b": 45},
        shapes=shapes,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        hovermode="closest",
    )
    figure.update_xaxes(
        title="코트 X (m)",
        range=[-0.5, COURT_WIDTH_M + 0.5],
        constrain="domain",
        gridcolor="rgba(255,255,255,0.08)",
    )
    figure.update_yaxes(
        title="코트 Y (m)",
        range=[-0.5, COURT_HEIGHT_M + 0.5],
        scaleanchor="x",
        scaleratio=1,
        gridcolor="rgba(255,255,255,0.08)",
    )
    return figure


def create_movement_figure(
    segmented: pd.DataFrame,
    player_ids: list[str],
    player_names: dict[str, str] | None = None,
) -> go.Figure:
    figure = _court_figure("선수 이동경로")
    selected = segmented.loc[segmented["player_id"].isin(player_ids)].copy()
    color_map = dict(zip(player_ids, cycle(PLAYER_COLORS)))

    for player_id in player_ids:
        player = selected.loc[selected["player_id"].eq(player_id)]
        player_label = _player_label(player_id, player_names)
        first_trace = True
        for _, segment in player.groupby("path_segment", sort=False):
            if len(segment) < 2:
                continue
            figure.add_trace(
                go.Scatter(
                    x=segment["player_x"],
                    y=segment["player_y"],
                    mode="lines+markers",
                    name=player_label,
                    legendgroup=player_id,
                    showlegend=first_trace,
                    line={"color": color_map[player_id], "width": 2.5},
                    marker={"size": 4, "opacity": 0.65},
                    customdata=segment[["time_sec", "speed_mps", "team", "occluded"]],
                    hovertemplate=(
                        f"<b>{player_label}</b><br>"
                        "시간 %{customdata[0]:.1f}초<br>"
                        "속도 %{customdata[1]:.2f}m/s<br>"
                        "팀 %{customdata[2]}<br>"
                        "가림 %{customdata[3]}<extra></extra>"
                    ),
                )
            )
            first_trace = False

        if not player.empty:
            endpoints = player.iloc[[0, -1]]
            figure.add_trace(
                go.Scatter(
                    x=endpoints["player_x"],
                    y=endpoints["player_y"],
                    mode="markers+text",
                    text=["시작", "종료"],
                    textposition="top center",
                    name=f"{player_label} 시작/종료",
                    legendgroup=player_id,
                    showlegend=False,
                    marker={"size": 11, "color": color_map[player_id], "line": {"width": 2, "color": "white"}},
                    hoverinfo="skip",
                )
            )

    if selected.empty:
        figure.add_annotation(text="표시할 선수를 선택하세요.", x=20, y=10, showarrow=False, font={"size": 18})
    return figure


def create_heatmap_figure(data: pd.DataFrame, title: str = "활동 위치 히트맵") -> go.Figure:
    figure = _court_figure(title)
    figure.update_layout(plot_bgcolor="#1b5548")
    if data.empty:
        figure.add_annotation(text="선택 조건에 해당하는 데이터가 없습니다.", x=20, y=10, showarrow=False)
        return figure

    counts, x_edges, y_edges = np.histogram2d(
        data["player_x"],
        data["player_y"],
        bins=[40, 20],
        range=[[0, COURT_WIDTH_M], [0, COURT_HEIGHT_M]],
    )
    heat_values = counts.T.astype(float)
    heat_values[heat_values == 0] = np.nan
    x_centers = (x_edges[:-1] + x_edges[1:]) / 2
    y_centers = (y_edges[:-1] + y_edges[1:]) / 2

    figure.add_trace(
        go.Heatmap(
            x=x_centers,
            y=y_centers,
            z=heat_values,
            zmin=1,
            zmax=max(float(np.nanmax(heat_values)), 1.0),
            colorscale=[
                [0.0, "#bae6fd"],
                [0.18, "#22d3ee"],
                [0.42, "#34d399"],
                [0.65, "#facc15"],
                [0.82, "#fb923c"],
                [1.0, "#ef4444"],
            ],
            colorbar={"title": "좌표 수"},
            hoverongaps=False,
            hovertemplate="X %{x:.1f}m<br>Y %{y:.1f}m<br>좌표 수 %{z:.0f}<extra></extra>",
        )
    )
    return figure


def create_ball_figure(
    data: pd.DataFrame,
    max_gap_sec: float = 1.0,
    player_names: dict[str, str] | None = None,
) -> go.Figure:
    figure = _court_figure("공 좌표 존재 구간")
    ball = data.loc[data[["ball_x", "ball_y"]].notna().all(axis=1)].sort_values("time_sec").copy()
    if ball.empty:
        figure.add_annotation(text="선택 구간에 공 좌표가 없습니다.", x=20, y=10, showarrow=False)
        return figure

    time_gap = ball["time_sec"].diff()
    segment_break = time_gap.isna() | time_gap.le(0) | time_gap.gt(max_gap_sec)
    ball["ball_segment"] = segment_break.cumsum()
    ball["player_label"] = ball["player_id"].map(
        lambda player_id: _player_label(str(player_id), player_names)
    )

    for _, segment in ball.groupby("ball_segment", sort=False):
        team = str(segment["team"].iloc[0])
        figure.add_trace(
            go.Scatter(
                x=segment["ball_x"],
                y=segment["ball_y"],
                mode="lines+markers",
                name=team,
                legendgroup=team,
                showlegend=team not in {trace.legendgroup for trace in figure.data},
                line={"color": TEAM_COLORS.get(team, "#facc15"), "width": 2},
                marker={"size": 10, "color": "#facc15", "line": {"width": 2, "color": "#111827"}},
                customdata=segment[["time_sec", "player_label", "team"]],
                hovertemplate=(
                    "<b>공 좌표</b><br>시간 %{customdata[0]:.1f}초<br>"
                    "소유 선수 %{customdata[1]}<br>팀 %{customdata[2]}<extra></extra>"
                ),
            )
        )
    return figure


def create_team_comparison_figure(team_stats: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    for _, row in team_stats.iterrows():
        team = str(row["team"])
        figure.add_trace(
            go.Bar(
                x=[team],
                y=[row["distance_m"]],
                name=team,
                marker_color=TEAM_COLORS.get(team, "#94a3b8"),
                text=[f"{row['distance_m']:.1f}m"],
                textposition="outside",
                hovertemplate="%{x}<br>이동거리 %{y:.2f}m<extra></extra>",
            )
        )
    figure.update_layout(
        title="팀별 유효 이동거리",
        template="plotly_dark",
        paper_bgcolor="#07151c",
        plot_bgcolor="#0b2530",
        showlegend=False,
        height=350,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        yaxis_title="이동거리 (m)",
    )
    return figure
