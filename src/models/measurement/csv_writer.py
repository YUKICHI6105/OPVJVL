"""測定結果のCSV(・サイドカーJSON)出力。

要件定義書_基本設計書.md B-5-3節のフォーマット表に従う。既存解析資産との
互換性のため、列名は厳密に``"voltage [V]"``, ``"current [A]"``,
``"luminance [cd/m2]"``を用いる。Qt非依存の純Pythonモジュール。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Literal, Optional, Sequence, Union

from .result import ChannelPoint, IVLPoint, IVPoint

_DEVICE_MODE_LABEL: Dict[str, str] = {"太陽電池": "OPV", "発光素子": "JVL"}


# --- ファイル名生成 -------------------------------------------------------


def opv_csv_filename(sample_name: str) -> str:
    return f"{sample_name}_OPV_measurement_data.csv"


def jvl_csv_filename(sample_name: str) -> str:
    return f"{sample_name}_JVL_measurement_data.csv"


def dual_a_csv_filename(sample_name: str, device_mode: str) -> str:
    label = _DEVICE_MODE_LABEL[device_mode]
    return f"{sample_name}_{label}_measurement_data.csv"


def dual_b_csv_filename(sample_name: str, channel: Literal["A", "B"], device_mode: str) -> str:
    """1素子測定と共通の命名。チャンネルの対応はメタ情報に保存する。"""
    label = _DEVICE_MODE_LABEL[device_mode]
    return f"{sample_name}_{label}_measurement_data.csv"


def validate_dual_b_filenames(channel_a, channel_b, save_dir: str) -> None:
    """同一測定で2つのCSVが同じパスに保存されることを防ぐ。"""
    if not (channel_a.enabled and channel_b.enabled):
        return
    paths = [
        str((Path(save_dir) / dual_b_csv_filename(c.sample_name, ch, c.device_mode)).resolve()).casefold()
        for ch, c in (("A", channel_a), ("B", channel_b))
    ]
    if paths[0] == paths[1]:
        raise ValueError("チャンネルA・Bの保存ファイル名が同じです。サンプル名を別々に設定してください。")


def dual_b_meta_json_filename(sample_name: str) -> str:
    return f"{sample_name}_dualB_meta.json"


# --- CSV書き込み -----------------------------------------------------------


def save_points_csv(
    points: Sequence[Union[IVPoint, IVLPoint, ChannelPoint]],
    path: Union[str, Path],
    include_luminance: bool,
    forward_point_count: Optional[int] = None,
) -> str:
    """測定点列を明示的なパスへCSV保存する(公開API)。

    「別名保存」等、保存先ディレクトリ+ファイル名の組み立てをView側が
    既に済ませている場合に使う。親ディレクトリが存在しなければ作成する。
    ヒステリシス測定では往路の予定点数を渡し、末尾に測定方向の列を追加する。
    中断時も予定点数を使うため、往路しか取得していない場合に誤分類しない。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = ["voltage [V]", "current [A]"]
    if include_luminance:
        headers.append("luminance [cd/m2]")
    if forward_point_count is not None:
        headers.append("sweep direction")

    with open(path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for index, p in enumerate(points):
            row = [p.voltage, p.current]
            if include_luminance:
                row.append(getattr(p, "luminance", None))
            if forward_point_count is not None:
                row.append("Forward" if index < forward_point_count else "Backward")
            writer.writerow(row)

    return str(path)


def _write_csv(
    points: Sequence[Union[IVPoint, IVLPoint, ChannelPoint]],
    include_luminance: bool,
    save_dir: str,
    filename: str,
    forward_point_count: Optional[int] = None,
) -> str:
    return save_points_csv(points, Path(save_dir) / filename, include_luminance, forward_point_count)


# --- 保存関数 ---------------------------------------------------------------


def save_opv_csv(
    points: Sequence[IVPoint],
    sample_name: str,
    save_dir: str,
    forward_point_count: Optional[int] = None,
) -> str:
    """OPVモードの測定結果を保存する。往復測定では測定方向を末尾に追加する。"""
    return _write_csv(points, include_luminance=False, save_dir=save_dir,
                      filename=opv_csv_filename(sample_name), forward_point_count=forward_point_count)


def save_jvl_csv(
    points: Sequence[Union[IVPoint, IVLPoint]],
    sample_name: str,
    save_dir: str,
    use_luminance: bool,
    forward_point_count: Optional[int] = None,
) -> str:
    """JVL結果を保存する。電圧・電流に、必要なら輝度と測定方向を追加する。"""
    return _write_csv(points, include_luminance=use_luminance, save_dir=save_dir,
                      filename=jvl_csv_filename(sample_name), forward_point_count=forward_point_count)


def save_dual_a_csv(
    points: Sequence[Union[IVPoint, IVLPoint]],
    sample_name: str,
    save_dir: str,
    device_mode: str,
    use_luminance: bool,
    forward_point_count: Optional[int] = None,
) -> str:
    """モードAの結果を保存する。輝度・測定方向は測定条件に従う。"""
    include = use_luminance and device_mode == "発光素子"
    filename = dual_a_csv_filename(sample_name, device_mode)
    return _write_csv(points, include_luminance=include, save_dir=save_dir,
                      filename=filename, forward_point_count=forward_point_count)


def save_dual_b_channel_csv(
    points: Sequence[ChannelPoint],
    sample_name: str,
    save_dir: str,
    channel: Literal["A", "B"],
    device_mode: str,
    use_luminance: bool,
    forward_point_count: Optional[int] = None,
) -> str:
    """モードBの1チャンネル分の測定結果を保存する。チャンネルA/Bは別ファイル。"""
    include = use_luminance and device_mode == "発光素子"
    filename = dual_b_csv_filename(sample_name, channel, device_mode)
    return _write_csv(points, include_luminance=include, save_dir=save_dir,
                      filename=filename, forward_point_count=forward_point_count)


def save_dual_b_meta_json(sample_name: str, save_dir: str, meta: dict) -> str:
    """モードBの掃引条件・機種IDN・実行日時等をサイドカーJSONとして保存する。

    CSV本体をコメント行で汚さずpandas互換を保つための設計(B-5-3節)。
    """
    directory = Path(save_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / dual_b_meta_json_filename(sample_name)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
