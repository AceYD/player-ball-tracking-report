"""Deterministic analysis summary used when no external API is available."""

from __future__ import annotations

import pandas as pd

from .data_loader import DataQualityReport


def generate_rule_based_report(
    player_stats: pd.DataFrame,
    team_stats: pd.DataFrame,
    quality: DataQualityReport,
) -> list[str]:
    """Generate a cautious Korean report using only verified statistics."""

    if player_stats.empty or team_stats.empty:
        return ["선택 조건에 해당하는 데이터가 없어 분석 문장을 만들 수 없습니다."]

    distance_leader = player_stats.loc[player_stats["distance_m"].idxmax()]
    speed_leader = player_stats.loc[player_stats["max_speed_mps"].idxmax()]
    coverage_ratio = team_stats["data_points"].max() / max(team_stats["data_points"].min(), 1)
    ball_points = int(team_stats["ball_points"].sum())

    def player_label(row: pd.Series) -> str:
        player_id = str(row["player_id"])
        player_name = str(row.get("player_name", player_id)).strip() or player_id
        return player_id if player_name == player_id else f"{player_name} ({player_id})"

    distance_leader_label = player_label(distance_leader)
    speed_leader_label = player_label(speed_leader)

    messages = [
        (
            f"{distance_leader_label} 선수가 유효 이동거리 "
            f"{distance_leader['distance_m']:.2f}m로 선택 구간에서 가장 높은 값을 기록했습니다."
        ),
        (
            f"최고 속도는 {speed_leader_label} 선수의 "
            f"{speed_leader['max_speed_mps']:.2f}m/s입니다."
        ),
    ]

    if ball_points:
        ball_leader = team_stats.loc[team_stats["ball_points"].idxmax()]
        messages.append(
            f"공 좌표는 총 {ball_points}개이며 {ball_leader['team']}의 기록이 "
            f"{int(ball_leader['ball_points'])}개로 더 많습니다. 이는 실제 점유율이 아니라 좌표 기록 수입니다."
        )
    else:
        messages.append("선택 구간에는 공 좌표가 없어 공 이동이나 소유 기록을 비교하지 않았습니다.")

    if coverage_ratio >= 1.5:
        messages.append(
            "팀별 데이터 관측량 차이가 커서 총 이동거리를 경기력 차이로 단정하지 않아야 합니다."
        )
    else:
        distance_team = team_stats.loc[team_stats["distance_m"].idxmax()]
        messages.append(
            f"유효 이동거리 합계는 {distance_team['team']}이 {distance_team['distance_m']:.2f}m로 가장 높습니다."
        )

    if quality.out_of_bounds_rows or quality.occluded_rows:
        messages.append(
            f"품질 확인 결과 가림 좌표 {quality.occluded_rows}개, 범위 초과 좌표 "
            f"{quality.out_of_bounds_rows}개가 있어 해석 시 참고해야 합니다."
        )
    return messages
