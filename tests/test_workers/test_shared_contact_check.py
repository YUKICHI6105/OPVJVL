"""共有接続での接触確認が、電圧上限・保持と測定予約を守ることを検証する。"""
import pytest

from models.instruments.mock.keithley2612b_mock import Keithley2612BMock
from models.measurement.config import ChannelConfig
from workers.dual_channel_worker import DualChannelWorker


@pytest.mark.parametrize("threshold,expected_voltages", [
    (1.0, [0.0, 0.05, 0.1]),
    (1e-12, [0.0, 0.05, 0.05, 0.05]),
])
def test_shared_ramp_stops_at_limit_or_holds_threshold(qtbot, monkeypatch, threshold, expected_voltages):
    clock = [0.0]
    monkeypatch.setattr("workers.dual_channel_worker.time.monotonic", lambda: clock[0])
    smu = Keithley2612BMock("mock", noise_std=0)
    smu.connect()
    worker = DualChannelWorker(lambda _: iter(()), smu, 1)
    worker.reserve_measurement_channels({"A"})
    readings = []
    worker.contact_check_reading.connect(lambda _ch, voltage, _current: readings.append(voltage))
    assert not worker.request_contact_check("A", "発光素子", 0.01, 1, threshold, 0.1)
    assert worker.request_contact_check("B", "発光素子", 0.01, 1, threshold, 0.1)
    assert not worker.request_add_channel("B", ChannelConfig())
    worker.service_contact_check()
    for _ in range(len(expected_voltages)):
        clock[0] += 0.21
        worker.service_contact_check()
    assert readings == expected_voltages
    assert smu.reset_calls == 0
    assert [call[0] for call in smu.configure_calls] == ["smub"]
    if threshold == 1.0:
        assert worker._contact_request is None
    else:
        assert worker._contact_request is not None
        worker.request_stop_contact_check()
        worker.service_contact_check()
    assert smu.output_calls[-1] == ("smub", False)
    assert worker.request_add_channel("B", ChannelConfig())
    smu.close()
