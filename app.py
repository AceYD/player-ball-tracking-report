"""Offline Streamlit dashboard for the tracking report class project."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.analytics import add_movement_segments, calculate_player_stats, calculate_team_stats
from src.data_loader import TrackingDataError, load_tracking_data
from src.report_generator import generate_rule_based_report
from src.visualizations import (
    create_ball_figure,
    create_heatmap_figure,
    create_movement_figure,
    create_team_comparison_figure,
)


BASE_DIR = Path(__file__).resolve().parent
SAMPLE_CSV = BASE_DIR / "data" / "tracking" / "tracking_sample.csv"
SAMPLE_JSON = BASE_DIR / "data" / "tracking" / "tracking_sample.json"

st.set_page_config(
    page_title="선수·공 이동 경기 분석",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #07151c; }
    [data-testid="stSidebar"] { background: #0b2530; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #0e3440 0%, #102a35 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 14px;
        padding: 16px;
    }
    .report-card {
        background: #0b2530;
        border-left: 4px solid #38bdf8;
        border-radius: 10px;
        padding: 14px 18px;
        margin: 10px 0;
        color: #e2e8f0;
    }
    .eyebrow { color: #38bdf8; font-weight: 700; letter-spacing: .08em; }
    </style>
    """,
    unsafe_allow_html=True,
)


def display_player_stats(stats: pd.DataFrame) -> pd.DataFrame:
    return stats.rename(
        columns={
            "player_id": "선수 ID",
            "player_name": "선수 이름",
            "team": "팀",
            "distance_m": "이동거리(m)",
            "distance_per_min": "분당 이동거리(m)",
            "avg_speed_mps": "평균속도(m/s)",
            "max_speed_mps": "최고속도(m/s)",
            "observed_time_sec": "유효관측시간(초)",
            "data_points": "좌표 수",
            "occluded_points": "가림 좌표",
            "occlusion_pct": "가림 비율(%)",
            "ball_points": "공 좌표",
        }
    )


def player_display_label(player_id: str, player_names: dict[str, str]) -> str:
    player_name = str(player_names.get(player_id, player_id)).strip() or player_id
    return player_id if player_name == player_id else f"{player_name} ({player_id})"


def activity_range(data: pd.DataFrame, player_id: str, exclude_occluded: bool) -> dict[str, float]:
    player = data.loc[data["player_id"].eq(player_id)].copy()
    if exclude_occluded:
        player = player.loc[~player["occluded"]]
    if player.empty:
        return {"x_span": 0.0, "y_span": 0.0, "area": 0.0}
    x_span = float(player["player_x"].max() - player["player_x"].min())
    y_span = float(player["player_y"].max() - player["player_y"].min())
    return {"x_span": x_span, "y_span": y_span, "area": x_span * y_span}


def comparison_heatmap(data: pd.DataFrame, title: str):
    figure = create_heatmap_figure(data, title)
    figure.update_layout(
        height=360,
        margin={"l": 45, "r": 55, "t": 60, "b": 45},
    )
    figure.update_yaxes(
        range=[-0.5, 20.5],
        scaleanchor=None,
        scaleratio=None,
        constrain="domain",
    )
    figure.update_traces(
        colorbar={"title": "좌표 수", "thickness": 12, "len": 0.8},
        selector={"type": "heatmap"},
    )
    return figure


def display_team_stats(stats: pd.DataFrame) -> pd.DataFrame:
    return stats.rename(
        columns={
            "team": "팀",
            "players": "선수 수",
            "distance_m": "이동거리(m)",
            "avg_speed_mps": "평균속도(m/s)",
            "max_speed_mps": "최고속도(m/s)",
            "data_points": "좌표 수",
            "occlusion_pct": "가림 비율(%)",
            "ball_points": "공 좌표",
        }
    )


def analysis_json(
    player_stats: pd.DataFrame,
    team_stats: pd.DataFrame,
    report_lines: list[str],
) -> bytes:
    payload = {
        "player_stats": player_stats.to_dict(orient="records"),
        "team_stats": team_stats.to_dict(orient="records"),
        "summary": report_lines,
        "summary_method": "rule_based_no_external_api",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


st.markdown('<div class="eyebrow">SPONJY · OFFLINE TRACKING REPORT</div>', unsafe_allow_html=True)
st.title("⚽ 선수·공 이동 데이터 경기 분석")
st.caption("CSV·JSON 좌표를 통계, 히트맵, 이동경로와 자동 분석 문장으로 변환합니다.")

with st.sidebar:
    st.header("분석 설정")
    source_option = st.radio(
        "데이터 선택",
        ["샘플 CSV", "샘플 JSON", "내 파일 업로드"],
        help="CSV와 JSON은 같은 샘플 데이터입니다.",
    )

    uploaded_file = None
    if source_option == "내 파일 업로드":
        uploaded_file = st.file_uploader("추적 데이터", type=["csv", "json"])
        if uploaded_file is None:
            st.info("CSV 또는 JSON 파일을 선택하세요.")
            st.stop()

    st.divider()
    st.subheader("계산 기준")
    max_gap_sec = st.select_slider(
        "연속 좌표 최대 간격",
        options=[0.5, 1.0, 1.5, 2.0],
        value=1.0,
        format_func=lambda value: f"{value:.1f}초",
        help="이 시간보다 멀리 떨어진 두 좌표는 이동경로와 거리에 연결하지 않습니다.",
    )
    exclude_occluded = st.checkbox(
        "가림 좌표를 거리·속도에서 제외",
        value=False,
        key="exclude_occluded_v2",
        help="가려진 선수 좌표 전후 구간을 신뢰할 수 없는 구간으로 처리합니다.",
    )

try:
    if source_option == "샘플 CSV":
        data, quality = load_tracking_data(SAMPLE_CSV)
    elif source_option == "샘플 JSON":
        data, quality = load_tracking_data(SAMPLE_JSON)
    else:
        data, quality = load_tracking_data(uploaded_file.getvalue(), uploaded_file.name)
except TrackingDataError as exc:
    st.error(str(exc))
    st.stop()

with st.sidebar:
    teams = sorted(data["team"].unique().tolist())
    selected_teams = st.multiselect("팀", teams, default=teams)
    if not selected_teams:
        st.warning("한 팀 이상을 선택하세요.")
        st.stop()

    min_time = float(data["time_sec"].min())
    max_time = float(data["time_sec"].max())
    if max_time > min_time:
        selected_time = st.slider(
            "분석 시간",
            min_value=min_time,
            max_value=max_time,
            value=(min_time, max_time),
            step=max((max_time - min_time) / 500, 0.1),
            format="%.1f초",
        )
    else:
        selected_time = (min_time, max_time)

    all_player_ids = sorted(data["player_id"].unique().tolist())
    for player_id in all_player_ids:
        st.session_state.setdefault(f"player_name_{player_id}", player_id)
        st.session_state.setdefault(f"path_visible_{player_id}", True)

    st.divider()
    st.subheader("선수 이동경로")
    with st.expander("선수 이름 변경"):
        st.caption("원본 선수 ID는 유지되고 화면에 표시되는 이름만 변경됩니다.")
        for player_id in all_player_ids:
            st.text_input(
                f"{player_id} 이름",
                key=f"player_name_{player_id}",
                placeholder=player_id,
            )

    player_names = {
        player_id: (str(st.session_state[f"player_name_{player_id}"]).strip() or player_id)
        for player_id in all_player_ids
    }

    enable_column, disable_column = st.columns(2)
    enable_all = enable_column.button("12명 모두 켜기", use_container_width=True)
    disable_all = disable_column.button("모두 끄기", use_container_width=True)
    if enable_all or disable_all:
        for player_id in all_player_ids:
            st.session_state[f"path_visible_{player_id}"] = enable_all

    st.caption("체크한 선수의 이동경로와 선택 선수 히트맵이 표시됩니다.")
    selected_players: list[str] = []
    player_columns = st.columns(2)
    for index, player_id in enumerate(all_player_ids):
        player_name = player_names[player_id]
        label = player_id if player_name == player_id else f"{player_name} ({player_id})"
        with player_columns[index % 2]:
            if st.checkbox(label, key=f"path_visible_{player_id}"):
                selected_players.append(player_id)

filtered = data.loc[
    data["team"].isin(selected_teams)
    & data["time_sec"].between(selected_time[0], selected_time[1], inclusive="both")
].copy()

if filtered.empty:
    st.warning("선택 조건에 해당하는 좌표가 없습니다.")
    st.stop()

segmented = add_movement_segments(filtered, max_gap_sec, exclude_occluded)
player_stats = calculate_player_stats(segmented, exclude_occluded)
player_stats.insert(
    1,
    "player_name",
    player_stats["player_id"].map(player_names).fillna(player_stats["player_id"]),
)
team_stats = calculate_team_stats(segmented, player_stats, exclude_occluded)
report_lines = generate_rule_based_report(player_stats, team_stats, quality)

duration = max(float(filtered["time_sec"].max() - filtered["time_sec"].min()), 0.0)
ball_count = int(filtered[["ball_x", "ball_y"]].notna().all(axis=1).sum())
metric_columns = st.columns(5)
metric_columns[0].metric("유효 데이터(행)", f"{len(filtered):,}")
metric_columns[1].metric("선수", f"{filtered['player_id'].nunique()}명")
metric_columns[2].metric("팀", f"{filtered['team'].nunique()}개")
metric_columns[3].metric("분석 시간", f"{duration / 60:.1f}분")
metric_columns[4].metric("공 좌표", f"{ball_count:,}개")

overview_tab, path_tab, heatmap_tab, comparison_tab, ball_tab, quality_tab = st.tabs(
    ["종합 리포트", "이동경로", "히트맵", "선수 비교", "공 좌표", "데이터 품질"]
)

with overview_tab:
    left, right = st.columns([1.15, 0.85])
    with left:
        st.subheader("선수별 통계")
        st.dataframe(
            display_player_stats(player_stats),
            use_container_width=True,
            hide_index=True,
        )
    with right:
        st.plotly_chart(
            create_team_comparison_figure(team_stats),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    st.subheader("팀별 통계")
    st.dataframe(display_team_stats(team_stats), use_container_width=True, hide_index=True)

    st.subheader("자동 경기 분석 요약")
    st.caption("외부 API를 사용하지 않고 프로그램이 계산한 수치만으로 작성했습니다.")
    for line in report_lines:
        st.markdown(f'<div class="report-card">{line}</div>', unsafe_allow_html=True)

    download_left, download_center, download_right = st.columns(3)
    download_left.download_button(
        "선수 통계 CSV",
        data=player_stats.to_csv(index=False).encode("utf-8-sig"),
        file_name="player_statistics.csv",
        mime="text/csv",
        use_container_width=True,
    )
    download_center.download_button(
        "팀 통계 CSV",
        data=team_stats.to_csv(index=False).encode("utf-8-sig"),
        file_name="team_statistics.csv",
        mime="text/csv",
        use_container_width=True,
    )
    download_right.download_button(
        "전체 분석 JSON",
        data=analysis_json(player_stats, team_stats, report_lines),
        file_name="tracking_report.json",
        mime="application/json",
        use_container_width=True,
    )

with path_tab:
    if not selected_players:
        st.info("왼쪽의 선수 이동경로에서 한 명 이상을 켜세요.")
    path_figure = create_movement_figure(segmented, selected_players, player_names)
    st.plotly_chart(
        path_figure,
        use_container_width=True,
        config={"displaylogo": False, "scrollZoom": True},
    )
    st.caption("선 사이가 끊긴 곳은 설정한 시간 간격을 넘거나 가림 좌표가 포함된 구간입니다.")

with heatmap_tab:
    heatmap_mode = st.radio("히트맵 범위", ["선택 선수", "선택 팀 전체"], horizontal=True)
    if heatmap_mode == "선택 선수":
        heatmap_data = filtered.loc[filtered["player_id"].isin(selected_players)]
        heatmap_title = "선택 선수 활동 위치 히트맵"
    else:
        heatmap_data = filtered
        heatmap_title = "선택 팀 전체 활동 위치 히트맵"
    if exclude_occluded:
        heatmap_data = heatmap_data.loc[~heatmap_data["occluded"]]
    st.plotly_chart(
        create_heatmap_figure(heatmap_data, heatmap_title),
        use_container_width=True,
        config={"displaylogo": False, "scrollZoom": True},
    )
    st.caption(f"히트맵에 사용된 좌표: {len(heatmap_data):,}개")

with comparison_tab:
    st.subheader("두 선수 비교")
    st.caption("현재 선택한 팀과 분석 시간 범위 안에서 두 선수의 활동량과 위치를 비교합니다.")
    comparison_options = player_stats["player_id"].tolist()

    if len(comparison_options) < 2:
        st.info("비교하려면 현재 필터에 선수가 두 명 이상 있어야 합니다.")
    else:
        selector_left, selector_right = st.columns(2)
        with selector_left:
            first_player = st.selectbox(
                "첫 번째 선수",
                comparison_options,
                index=0,
                format_func=lambda player_id: player_display_label(player_id, player_names),
                key="comparison_player_a",
            )
        with selector_right:
            second_player = st.selectbox(
                "두 번째 선수",
                comparison_options,
                index=1,
                format_func=lambda player_id: player_display_label(player_id, player_names),
                key="comparison_player_b",
            )

        if first_player == second_player:
            st.warning("서로 다른 두 선수를 선택하세요.")
        else:
            first_stats = player_stats.loc[player_stats["player_id"].eq(first_player)].iloc[0]
            second_stats = player_stats.loc[player_stats["player_id"].eq(second_player)].iloc[0]
            first_range = activity_range(filtered, first_player, exclude_occluded)
            second_range = activity_range(filtered, second_player, exclude_occluded)
            first_label = player_display_label(first_player, player_names)
            second_label = player_display_label(second_player, player_names)

            comparison_rows = [
                ("팀", str(first_stats["team"]), str(second_stats["team"])),
                ("이동거리", f"{first_stats['distance_m']:.2f}m", f"{second_stats['distance_m']:.2f}m"),
                (
                    "분당 이동거리",
                    f"{first_stats['distance_per_min']:.2f}m/분",
                    f"{second_stats['distance_per_min']:.2f}m/분",
                ),
                (
                    "평균 속도",
                    f"{first_stats['avg_speed_mps']:.2f}m/s",
                    f"{second_stats['avg_speed_mps']:.2f}m/s",
                ),
                (
                    "최고 속도",
                    f"{first_stats['max_speed_mps']:.2f}m/s",
                    f"{second_stats['max_speed_mps']:.2f}m/s",
                ),
                (
                    "유효 관측시간",
                    f"{first_stats['observed_time_sec'] / 60:.2f}분",
                    f"{second_stats['observed_time_sec'] / 60:.2f}분",
                ),
                ("좌표 수", f"{int(first_stats['data_points']):,}개", f"{int(second_stats['data_points']):,}개"),
                ("공 좌표 수", f"{int(first_stats['ball_points']):,}개", f"{int(second_stats['ball_points']):,}개"),
                (
                    "가림 비율",
                    f"{first_stats['occlusion_pct']:.2f}%",
                    f"{second_stats['occlusion_pct']:.2f}%",
                ),
                (
                    "X 활동 범위",
                    f"{first_range['x_span']:.2f}m",
                    f"{second_range['x_span']:.2f}m",
                ),
                (
                    "Y 활동 범위",
                    f"{first_range['y_span']:.2f}m",
                    f"{second_range['y_span']:.2f}m",
                ),
                (
                    "활동 범위 사각면적",
                    f"{first_range['area']:.2f}㎡",
                    f"{second_range['area']:.2f}㎡",
                ),
            ]
            comparison_table = pd.DataFrame(
                comparison_rows,
                columns=["비교 지표", first_label, second_label],
            )
            st.dataframe(comparison_table, use_container_width=True, hide_index=True)
            st.caption(
                "분당 이동거리는 유효 이동거리를 연결된 유효 관측시간으로 나눈 값입니다. "
                "활동 범위 사각면적은 선수 좌표의 X·Y 최솟값과 최댓값으로 만든 범위입니다."
            )

            heatmap_left, heatmap_right = st.columns(2)
            first_heatmap_data = filtered.loc[filtered["player_id"].eq(first_player)]
            second_heatmap_data = filtered.loc[filtered["player_id"].eq(second_player)]
            if exclude_occluded:
                first_heatmap_data = first_heatmap_data.loc[~first_heatmap_data["occluded"]]
                second_heatmap_data = second_heatmap_data.loc[~second_heatmap_data["occluded"]]
            with heatmap_left:
                st.plotly_chart(
                    comparison_heatmap(first_heatmap_data, f"{first_label} 활동 히트맵"),
                    use_container_width=True,
                    config={"displaylogo": False, "scrollZoom": True},
                )
            with heatmap_right:
                st.plotly_chart(
                    comparison_heatmap(second_heatmap_data, f"{second_label} 활동 히트맵"),
                    use_container_width=True,
                    config={"displaylogo": False, "scrollZoom": True},
                )

with ball_tab:
    st.plotly_chart(
        create_ball_figure(filtered, max_gap_sec, player_names),
        use_container_width=True,
        config={"displaylogo": False, "scrollZoom": True},
    )
    st.caption("공 좌표가 기록된 행의 player_id를 해당 시점의 소유 선수로 해석했습니다.")

with quality_tab:
    st.subheader(f"입력 파일 품질 · {quality.source_name}")
    quality_columns = st.columns(4)
    quality_columns[0].metric("원본 행", f"{quality.raw_rows:,}")
    quality_columns[1].metric("정상 처리 행", f"{quality.valid_rows:,}")
    quality_columns[2].metric("가림 좌표", f"{quality.occluded_rows:,}")
    quality_columns[3].metric("범위 초과", f"{quality.out_of_bounds_rows:,}")

    if quality.messages:
        for message in quality.messages:
            st.warning(message)
    else:
        st.success("검사한 데이터에서 별도 품질 경고가 발견되지 않았습니다.")

    st.markdown(
        f"""
        - 분석용 코트 범위: **X 0-40m, Y 0-20m**
        - 중복 제거: **{quality.duplicate_rows:,}행**
        - 필수 값 오류로 제외: **{quality.dropped_rows:,}행**
        - 불완전한 공 좌표: **{quality.partial_ball_rows:,}행**
        - 공 좌표가 있는 정상 행: **{quality.ball_rows:,}행**
        """
    )
