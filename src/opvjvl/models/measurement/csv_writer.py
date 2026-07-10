"""測定結果のCSV(・サイドカーJSON)出力。

要件定義書_基本設計書.md B-5-3節のフォーマット表に従う。既存解析資産との
互換性のため、列名は厳密に``"voltage [V]"``, ``"current [A]"``,
``"luminance [cd/m2]"``を用いる。Qt非依存の純Pythonモジュール。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Literal, Sequence, Union

from .result import ChannelPoint, IVLPoint, IVPoint

_DEVICE_MODE_LABEL: Dict[str, str] = {"太陽電池": "OPV", "発光素子": "JVL"}


# --- ファイル名生成 -------------------------------------------------------


def opv_csv_filename(sample_name: str) -> str:
    return f"{sample_name}_OPV_measurement_data.csv"


def jvl_csv_filename(sample_name: str) -> str:
    return f"{sample_name}_JVL_measurement_data.csv"


def dual_a_csv_filename(sample_name: str, device_mode: str) -> str:
    label = _DEVICE_MODE_LABEL[device_mode]
    return f"{sample_name}_dualA_{label}_measurement_data.csv"


def dual_b_csv_filename(sample_name: str, channel: Literal["A", "B"], device_mode: str) -> str:
    label = _DEVICE_MODE_LABEL[device_mode]
    return f"{sample_name}_dualB_ch{channel}_{label}_measurement_data.csv"


def dual_b_meta_json_filename(sample_name: str) -> str:
    return f"{sample_name}_dualB_meta.json"


# --- CSV書き込み -----------------------------------------------------------


def _write_csv(
    points: Sequence[Union[IVPoint, IVLPoint, ChannelPoint]],
    include_luminance: bool,
    save_dir: str,
    filename: str,
) -> str:
    directory = Path(save_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename

    headers = ["voltage [V]", "current [A]"]
    if include_luminance:
        headers.append("luminance [cd/m2]")

    with open(path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for p in points:
            row = [p.voltage, p.current]
            if include_luminance:
                row.append(getattr(p, "luminance", None))
            writer.writerow(row)

    return str(path)


# --- 保存関数 ---------------------------------------------------------------


def save_opv_csv(points: Sequence[IVPoint], sample_name: str, save_dir: str) -> str:
    """OPVモードの測定結果を保存する。2列(voltage, current)固定。"""
    return _write_csv(points, include_luminance=False, save_dir=save_dir, filename=opv_csv_filename(sample_name))


def save_jvl_csv(
    points: Sequence[Union[IVPoint, IVLPoint]],
    sample_name: str,
    save_dir: str,
    use_luminance: bool,
) -> str:
    """JVLモードの測定結果を保存する。輝度計測ONなら3列、OFFなら2列(暗IV)。"""
    return _write_csv(points, include_luminance=use_luminance, save_dir=save_dir, filename=jvl_csv_filename(sample_name))


def save_dual_a_csv(
    points: Sequence[Union[IVPoint, IVLPoint]],
    sample_name: str,
    save_dir: str,
    device_mode: str,
    use_luminance: bool,
) -> str:
    """モードAの測定結果を保存する。計測対象モードに応じ2列 or 3列。"""
    include = use_luminance and device_mode == "発光素子"
    filename = dual_a_csv_filename(sample_name, device_mode)
    return _write_csv(points, include_luminance=include, save_dir=save_dir, filename=filename)


def save_dual_b_channel_csv(
    points: Sequence[ChannelPoint],
    sample_name: str,
    save_dir: str,
    channel: Literal["A", "B"],
    device_mode: str,
    use_luminance: bool,
) -> str:
    """モードBの1チャンネル分の測定結果を保存する。チャンネルA/Bは別ファイル。"""
    include = use_luminance and device_mode == "発光素子"
    filename = dual_b_csv_filename(sample_name, channel, device_mode)
    return _write_csv(points, include_luminance=include, save_dir=save_dir, filename=filename)


def save_dual_b_meta_json(sample_name: str, save_dir: str, meta: dict) -> str:
    """モードBの掃引条件・機種IDN・実行日時等をサイドカーJSONとして保存する。

    CSV本体をコメント行で汚さずpandas互換を保つための設計(B-5-3節)。
    """
    directory = Path(save_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / dual_b_meta_json_filename(sample_name)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
