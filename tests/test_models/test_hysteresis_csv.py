"""保存データの測定方向と従来CSVとの互換性。"""
import csv
import pytest

from models.measurement import csv_writer
from models.measurement.config import OPVConfig
from models.measurement.result import IVLPoint
from views.data_viewer import parse_measurement_csv


@pytest.mark.parametrize("limit", [0, 2, 7, 10])
def test_csv_directions_cover_repeats_turnaround_and_interruption(tmp_path, limit):
    config = OPVConfig(v_min=0, v_max=0.2, v_step=0.1, iteration=2, hysteresis=True)
    points = [IVLPoint(i, float(v), 0.001 * i, i * 10.0)
              for i, v in enumerate(config.build_voltage_list()[:limit])]
    # モード別の引数伝達は統合テストで検証し、境界値は共通writerで検証する。
    path = csv_writer.save_points_csv(points, tmp_path / "sweep.csv", True,
                                      config.forward_point_count())
    with open(path, encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        assert reader.fieldnames == ["voltage [V]", "current [A]", "luminance [cd/m2]", "sweep direction"]
    assert [row["sweep direction"] for row in rows] == ["Forward"] * min(limit, 6) + ["Backward"] * max(0, limit - 6)
    assert [float(row["voltage [V]"]) for row in rows] == [p.voltage for p in points]
    # 方向列を輝度として誤読せず、既存ビューアでも開けること。
    voltages, currents, luminances = parse_measurement_csv(path)
    assert voltages == [p.voltage for p in points]
    assert currents == [p.current for p in points]
    assert luminances == [p.luminance for p in points]
