"""CSV/JSON loading and validation for tracking data."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import json
from pathlib import Path
from typing import BinaryIO

import pandas as pd


COURT_WIDTH_M = 40.0
COURT_HEIGHT_M = 20.0

REQUIRED_COLUMNS = [
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

NUMERIC_REQUIRED = [
    "frame",
    "time_sec",
    "player_x",
    "player_y",
    "speed_mps",
]


class TrackingDataError(ValueError):
    """Raised when an input file cannot be used as tracking data."""


@dataclass
class DataQualityReport:
    """Counts and messages generated while cleaning one input file."""

    source_name: str
    raw_rows: int
    valid_rows: int = 0
    dropped_rows: int = 0
    duplicate_rows: int = 0
    out_of_bounds_rows: int = 0
    partial_ball_rows: int = 0
    invalid_occluded_rows: int = 0
    occluded_rows: int = 0
    ball_rows: int = 0
    messages: list[str] = field(default_factory=list)


def _read_bytes(source: str | Path | bytes | BinaryIO) -> bytes:
    if isinstance(source, bytes):
        return source
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    if hasattr(source, "read"):
        value = source.read()
        return value.encode("utf-8") if isinstance(value, str) else value
    raise TrackingDataError("지원하지 않는 입력 형식입니다.")


def _parse_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return None
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return None


def _read_dataframe(raw: bytes, extension: str) -> pd.DataFrame:
    if extension == ".csv":
        try:
            return pd.read_csv(BytesIO(raw))
        except Exception as exc:  # pandas exposes several parser exception types
            raise TrackingDataError(f"CSV 파일을 읽을 수 없습니다: {exc}") from exc

    if extension == ".json":
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TrackingDataError(f"JSON 파일을 읽을 수 없습니다: {exc}") from exc

        if isinstance(payload, dict) and isinstance(payload.get("records"), list):
            payload = payload["records"]
        if not isinstance(payload, list):
            raise TrackingDataError("JSON에는 records 배열 또는 행 배열이 필요합니다.")
        return pd.DataFrame(payload)

    raise TrackingDataError("CSV 또는 JSON 파일만 사용할 수 있습니다.")


def load_tracking_data(
    source: str | Path | bytes | BinaryIO,
    filename: str | None = None,
) -> tuple[pd.DataFrame, DataQualityReport]:
    """Load, normalize and validate a tracking CSV or JSON file.

    Raw coordinates are preserved in ``player_x_raw`` and ``player_y_raw``.
    Clean coordinates are clipped to the documented 40 x 20 metre court.
    """

    source_name = filename or (Path(source).name if isinstance(source, (str, Path)) else "uploaded")
    extension = Path(source_name).suffix.lower()
    raw = _read_bytes(source)
    frame = _read_dataframe(raw, extension)
    report = DataQualityReport(source_name=source_name, raw_rows=len(frame))

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise TrackingDataError(f"필수 열이 없습니다: {', '.join(missing)}")

    frame = frame[REQUIRED_COLUMNS].copy()
    for column in NUMERIC_REQUIRED + ["ball_x", "ball_y"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["player_id"] = frame["player_id"].astype("string").str.strip()
    frame["team"] = frame["team"].astype("string").str.strip()

    invalid_required = frame[NUMERIC_REQUIRED].isna().any(axis=1)
    invalid_required |= frame["player_id"].isna() | frame["player_id"].eq("")
    invalid_required |= frame["team"].isna() | frame["team"].eq("")
    report.dropped_rows = int(invalid_required.sum())
    if report.dropped_rows:
        report.messages.append(f"필수 값이 잘못된 {report.dropped_rows}행을 제외했습니다.")
        frame = frame.loc[~invalid_required].copy()

    parsed_occluded = frame["occluded"].map(_parse_bool)
    invalid_occluded = parsed_occluded.isna()
    report.invalid_occluded_rows = int(invalid_occluded.sum())
    if report.invalid_occluded_rows:
        report.messages.append(
            f"가림 여부를 해석할 수 없는 {report.invalid_occluded_rows}행을 False로 처리했습니다."
        )
    frame["occluded"] = parsed_occluded.fillna(False).astype(bool)

    partial_ball = frame[["ball_x", "ball_y"]].isna().sum(axis=1).eq(1)
    report.partial_ball_rows = int(partial_ball.sum())
    if report.partial_ball_rows:
        frame.loc[partial_ball, ["ball_x", "ball_y"]] = float("nan")
        report.messages.append(
            f"공 X/Y 중 하나만 있는 {report.partial_ball_rows}행의 공 좌표를 제외했습니다."
        )

    duplicate_mask = frame.duplicated(subset=["player_id", "time_sec"], keep="first")
    report.duplicate_rows = int(duplicate_mask.sum())
    if report.duplicate_rows:
        frame = frame.loc[~duplicate_mask].copy()
        report.messages.append(f"선수·시각이 중복된 {report.duplicate_rows}행을 제외했습니다.")

    frame["player_x_raw"] = frame["player_x"]
    frame["player_y_raw"] = frame["player_y"]
    out_of_bounds = (
        frame["player_x"].lt(0)
        | frame["player_x"].gt(COURT_WIDTH_M)
        | frame["player_y"].lt(0)
        | frame["player_y"].gt(COURT_HEIGHT_M)
    )
    report.out_of_bounds_rows = int(out_of_bounds.sum())
    if report.out_of_bounds_rows:
        report.messages.append(
            f"코트 범위를 벗어난 {report.out_of_bounds_rows}행은 시각화·거리 계산용 좌표만 보정했습니다."
        )
    frame["player_x"] = frame["player_x"].clip(0, COURT_WIDTH_M)
    frame["player_y"] = frame["player_y"].clip(0, COURT_HEIGHT_M)
    frame["ball_x"] = frame["ball_x"].clip(0, COURT_WIDTH_M)
    frame["ball_y"] = frame["ball_y"].clip(0, COURT_HEIGHT_M)

    frame["frame"] = frame["frame"].round().astype("int64")
    frame = frame.sort_values(["player_id", "time_sec", "frame"], kind="stable").reset_index(drop=True)

    report.valid_rows = len(frame)
    report.occluded_rows = int(frame["occluded"].sum())
    report.ball_rows = int(frame[["ball_x", "ball_y"]].notna().all(axis=1).sum())
    return frame, report

