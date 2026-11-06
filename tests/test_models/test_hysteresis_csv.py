"""保存データの測定方向と従来CSVとの互換性。"""
import csv
import pytest

from models.measurement import csv_writer
from models.measurement.config import OPVConfig
from models.measurement.result import IVLPoint
from views.data_viewer import parse_measurement_csv


@pytest.mark.parametrize("mode", ["opv", "jvl", "dual_a", "dual_b"])
@pytest.mark.parametrize("limit", [0, 2, 7, 10])
def test_csv_directions_cover_repeats_turnaround_and_interruption(tmp_path, mode, limit):
    config = OPVConfig(v_min=0, v_max=0.2, v_step=0.1, iteration=2, hysteresis=True)
    points = [IVLPoint(i, float(v), 0.001 * i, i * 10.0)
              for i, v in enumerate(config.build_voltage_list()[:limit])]
    kwargs = dict(points=points, sample_name=mode, save_dir=str(tmp_path),
                  forward_point_count=config.forward_point_count())
    if mode != "opv":
        kwargs["use_luminance"] = True
    if mode.startswith("dual"):
        kwargs["device_mode"] = "発光素子"
    if mode == "dual_b":
        kwargs["channel"] = "A"
    fn = getattr(csv_writer, "save_dual_b_channel_csv" if mode == "dual_b" else f"save_{mode}_csv")
    path = fn(**kwargs)
    with open(path, encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["sweep direction"] for row in rows] == ["Forward"] * min(limit, 6) + ["Backward"] * max(0, limit - 6)
    assert [float(row["voltage [V]"]) for row in rows] == [p.voltage for p in points]
    # 方向列を輝度として誤読せず、既存ビューアでも開けること。
    voltages, currents, luminances = parse_measurement_csv(path)
    assert voltages == [p.voltage for p in points]
    assert currents == [p.current for p in points]
    assert luminances == ([None] * len(points) if mode == "opv" else [p.luminance for p in points])
