"""CSV書き込み機能のテスト。"""
from __future__ import annotations

import json
import os
from opvjvl.models.measurement import csv_writer
from opvjvl.models.measurement.result import ChannelPoint, IVLPoint, IVPoint


def test_filename_helpers():
    """ファイル名生成ヘルパーの動作検証。"""
    assert csv_writer.opv_csv_filename("test") == "test_OPV_measurement_data.csv"
    assert csv_writer.jvl_csv_filename("sample") == "sample_JVL_measurement_data.csv"
    assert (
        csv_writer.dual_a_csv_filename("s", "太陽電池")
        == "s_dualA_OPV_measurement_data.csv"
    )
    assert (
        csv_writer.dual_b_csv_filename("s", "A", "発光素子")
        == "s_dualB_chA_JVL_measurement_data.csv"
    )
    assert csv_writer.dual_b_meta_json_filename("s") == "s_dualB_meta.json"


def test_save_opv_csv(tmp_path):
    """OPV用CSV保存の検証。"""
    points = [
        IVPoint(index=0, voltage=-0.1, current=0.001),
        IVPoint(index=1, voltage=0.0, current=0.0),
        IVPoint(index=2, voltage=0.1, current=-0.002),
    ]

    save_dir = str(tmp_path)
    file_path = csv_writer.save_opv_csv(points, "sample_opv", save_dir)

    assert os.path.exists(file_path)
    assert os.path.basename(file_path) == "sample_opv_OPV_measurement_data.csv"

    # ファイルの中身の検証 (pandas非依存で読み取る)
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert lines[0].strip() == "voltage [V],current [A]"
    assert lines[1].strip() == "-0.1,0.001"
    assert lines[2].strip() == "0.0,0.0"
    assert lines[3].strip() == "0.1,-0.002"


def test_save_jvl_csv(tmp_path):
    """JVL用CSV保存の検証。"""
    points = [
        IVLPoint(index=0, voltage=0.0, current=0.0, luminance=0.0),
        IVLPoint(index=1, voltage=1.0, current=0.01, luminance=150.5),
    ]

    save_dir = str(tmp_path)

    # 輝度あり
    path_with_lum = csv_writer.save_jvl_csv(points, "sample_jvl", save_dir, use_luminance=True)
    assert os.path.exists(path_with_lum)
    with open(path_with_lum, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert lines[0].strip() == "voltage [V],current [A],luminance [cd/m2]"
    assert lines[1].strip() == "0.0,0.0,0.0"
    assert lines[2].strip() == "1.0,0.01,150.5"

    # 輝度なし (暗IV用途など)
    path_no_lum = csv_writer.save_jvl_csv(points, "sample_jvl_no", save_dir, use_luminance=False)
    assert os.path.exists(path_no_lum)
    with open(path_no_lum, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert lines[0].strip() == "voltage [V],current [A]"
    assert lines[1].strip() == "0.0,0.0"
    assert lines[2].strip() == "1.0,0.01"


def test_save_dual_b_channel_csv(tmp_path):
    """モードB用CSV保存の検証。"""
    points = [
        ChannelPoint(channel="A", index=0, voltage=0.0, current=0.001, luminance=None),
        ChannelPoint(channel="A", index=1, voltage=0.1, current=0.002, luminance=None),
    ]

    save_dir = str(tmp_path)
    file_path = csv_writer.save_dual_b_channel_csv(
        points, "sample_b", save_dir, channel="A", device_mode="太陽電池", use_luminance=False
    )

    assert os.path.exists(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert lines[0].strip() == "voltage [V],current [A]"
    assert lines[1].strip() == "0.0,0.001"
    assert lines[2].strip() == "0.1,0.002"


def test_save_dual_b_meta_json(tmp_path):
    """モードBメタデータJSON保存の検証。"""
    meta = {
        "timestamp": "2026-07-10 11:00:00",
        "instrument": "Keithley 2612B",
        "chA": {"v_min": -0.1, "v_max": 1.1},
    }

    save_dir = str(tmp_path)
    file_path = csv_writer.save_dual_b_meta_json("sample_meta", save_dir, meta)

    assert os.path.exists(file_path)
    assert os.path.basename(file_path) == "sample_meta_dualB_meta.json"

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["instrument"] == "Keithley 2612B"
    assert data["chA"]["v_min"] == -0.1
