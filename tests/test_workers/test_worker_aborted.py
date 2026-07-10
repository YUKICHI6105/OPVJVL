"""測定中断(aborted)と正常完了の区別に関するテスト。

過去の不具合: Workerは中断時も正常完了と同じ ``finished_ok`` を発火し、
GUIには「測定完了」と表示されていた。本テストは ``finished_ok`` の
abortedフラグとViewModelのメッセージ分岐を検証する。
"""
from __future__ import annotations

import functools
import json

from models.instruments.mock.keithley2400_mock import Keithley2400Mock
from models.measurement.config import ChannelConfig, OPVConfig
from models.measurement.sequences import run_opv_sequence
from viewmodels.dual_channel_viewmodel import DualChannelViewModel
from viewmodels.opv_viewmodel import OPVViewModel
from workers.measurement_worker import MeasurementWorker


def _make_worker(csv_save_fn=None):
    config = OPVConfig(
        device_type="keithley2400",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=0.2,
        v_step=0.1,  # 3点
        iteration=1,
        delay_time=0.0,
    )
    smu = Keithley2400Mock.for_opv("MOCK")
    make_iterator = functools.partial(run_opv_sequence, smu, config)
    total = len(config.build_voltage_list())
    return MeasurementWorker(make_iterator, smu, total, csv_save_fn=csv_save_fn)


def test_worker_normal_completion_emits_aborted_false(qtbot):
    worker = _make_worker()
    results = []
    worker.finished_ok.connect(
        lambda points, csv_path, aborted: results.append((points, csv_path, aborted))
    )

    # QThread.start()ではなくrun()を直接呼び、同一スレッドで同期実行する
    worker.run()

    assert len(results) == 1
    points, _csv_path, aborted = results[0]
    assert aborted is False
    assert len(points) == 3


def test_worker_stop_request_emits_aborted_true(qtbot):
    worker = _make_worker()
    results = []
    worker.finished_ok.connect(
        lambda points, csv_path, aborted: results.append((points, csv_path, aborted))
    )

    worker.request_stop()  # 開始前に中断要求 → 最初のis_aborted()チェックで停止
    worker.run()

    assert len(results) == 1
    points, _csv_path, aborted = results[0]
    assert aborted is True
    assert len(points) == 0


def test_viewmodel_logs_aborted_message_not_completion(qtbot):
    """中断時にViewModelが「測定完了」ではなく「測定中断」とログすることを検証。"""
    vm = OPVViewModel()
    logs = []
    vm.log_appended.connect(logs.append)
    emitted = []
    vm.finished_ok.connect(
        lambda points, csv_path, aborted: emitted.append(aborted)
    )

    vm._on_finished_ok([], "", True)

    assert len(logs) == 1
    assert "測定中断" in logs[0]
    assert "測定完了" not in logs[0]
    assert emitted == [True]


def test_viewmodel_logs_completion_message_when_not_aborted(qtbot):
    vm = OPVViewModel()
    logs = []
    vm.log_appended.connect(logs.append)

    vm._on_finished_ok([], "", False)

    assert len(logs) == 1
    assert "測定完了" in logs[0]
    assert "測定中断" not in logs[0]


def test_dual_b_meta_json_records_aborted(qtbot, tmp_path):
    """モードBのサイドカーJSONに中断有無が記録されることを検証。"""
    vm = DualChannelViewModel()
    chan_a = ChannelConfig(enabled=False, sample_name="chA")
    chan_b = ChannelConfig(enabled=False, sample_name="chB")

    vm._save_mode_b_results(
        [],
        [],
        True,  # aborted (Workerからcsv_save_fnの第3引数として渡される)
        channel_a=chan_a,
        channel_b=chan_b,
        save_dir=str(tmp_path),
        connection="MOCK",
        use_luminance_a=False,
        use_luminance_b=False,
    )

    meta_path = tmp_path / "chB_dualB_meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["aborted"] is True
