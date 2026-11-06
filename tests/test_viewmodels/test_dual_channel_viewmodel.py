"""DualChannelViewModel の動作検証テスト。"""
from __future__ import annotations

import pytest
from qtcompat import QtWidgets
from viewmodels.dual_channel_viewmodel import DualChannelViewModel
from views.dual_channel_tab import DualChannelTab


def test_duplicate_filenames_rejected_before_instrument_creation(qtbot, tmp_path, monkeypatch):
    from models.measurement.config import ChannelConfig, DualBConfig
    from viewmodels import dual_channel_viewmodel

    vm = DualChannelViewModel()
    errors = []
    vm.error_b.connect(errors.append)
    def unexpected_creation(*args, **kwargs):
        pytest.fail("重複保存先の場合に機器を作成してはいけない")
    monkeypatch.setattr(dual_channel_viewmodel.registry, "create_source_meter", unexpected_creation)
    vm.start_mode_b(DualBConfig(
        channel_a=ChannelConfig(sample_name="Sample"),
        channel_b=ChannelConfig(sample_name="sample"), save_dir=str(tmp_path),
    ))
    assert len(errors) == 1


def test_dual_results_use_single_measurement_names_and_keep_channel_mapping(tmp_path):
    import json
    from models.measurement.config import ChannelConfig
    from models.measurement.result import ChannelPoint

    vm = DualChannelViewModel()
    a = ChannelConfig(sample_name="device_01", hysteresis=True)
    b = ChannelConfig(sample_name="device_02")
    point_a = ChannelPoint(channel="A", index=0, voltage=0, current=0.001)
    point_b = ChannelPoint(channel="B", index=0, voltage=0, current=0.002)
    paths = vm._save_mode_b_results([point_a], [point_b], False, a, b, str(tmp_path), "mock", False, False)
    assert paths == (str(tmp_path / "device_01_OPV_measurement_data.csv"),
                     str(tmp_path / "device_02_OPV_measurement_data.csv"))
    assert "0.001" in (tmp_path / "device_01_OPV_measurement_data.csv").read_text()
    assert "0.002" in (tmp_path / "device_02_OPV_measurement_data.csv").read_text()
    meta = json.loads((tmp_path / "device_01_device_02_dualB_meta.json").read_text(encoding="utf-8"))
    assert meta["channel_a"]["csv_path"] == paths[0]
    assert meta["channel_b"]["csv_path"] == paths[1]
    assert meta["channel_a"]["hysteresis"] is True


def test_dual_results_record_only_the_stopped_channel(tmp_path):
    import json
    from models.measurement.config import ChannelConfig
    from models.measurement.result import ChannelPoint

    vm = DualChannelViewModel()
    a = ChannelConfig(sample_name="a")
    b = ChannelConfig(sample_name="b")
    points_a = [ChannelPoint(channel="A", index=0, voltage=0, current=0.001)]
    points_b = [ChannelPoint(channel="B", index=i, voltage=i, current=0.002)
                for i in range(2)]
    vm._save_mode_b_results(points_a, points_b, True, a, b, str(tmp_path),
                            "mock", False, False, frozenset({"A"}))
    meta = json.loads((tmp_path / "a_b_dualB_meta.json").read_text(encoding="utf-8"))
    assert meta["channel_a"]["aborted"] is True
    assert meta["channel_b"]["aborted"] is False
    assert meta["aborted"] is True


def test_mode_b_channel_button_switches_to_stop(qtbot, monkeypatch):
    tab = DualChannelTab()
    qtbot.addWidget(tab)
    stopped = []
    monkeypatch.setattr(tab.viewModel, "mode_b_is_running", lambda: True)
    monkeypatch.setattr(tab.viewModel, "stop_mode_b_channel",
                        lambda channel: stopped.append(channel) or True)
    tab._mode_b_reserved_channels["A"] = True
    tab._on_running_changed_b(True)
    assert tab.dual_chA_startButton.text() == "このチャネルを中断"
    tab._on_mode_b_channel_button_clicked("A")
    assert stopped == ["A"]
    assert tab.dual_chA_startButton.text() == "中断済み"
    assert not tab.dual_chA_startButton.isEnabled()


def test_dual_channel_viewmodel_init(qtbot):
    """初期状態の検証。"""
    tab = DualChannelTab()
    qtbot.addWidget(tab)

    vm = tab.viewModel

    # モードA初期値
    assert tab.dual_a_startButton.isEnabled()
    assert not tab.dual_a_stopButton.isEnabled()

    # モードB初期値
    assert tab.dual_b_startButton.isEnabled()
    assert not tab.dual_b_stopButton.isEnabled()


def test_dual_channel_mode_b_mutual_exclusion(qtbot):
    """モードBにおいて、チャンネルAとBで同時に「発光素子」を選択できない排他制御の検証。"""
    tab = DualChannelTab()
    qtbot.addWidget(tab)

    vm = tab.viewModel

    # 初期状態 (チャンネルA: 太陽電池, チャンネルB: 太陽電池)
    assert tab.dual_chA_deviceModeCombo.currentText() == "太陽電池"
    assert tab.dual_chB_deviceModeCombo.currentText() == "太陽電池"

    # チャンネルAを「発光素子」にする
    tab.dual_chA_deviceModeCombo.setCurrentText("発光素子")

    # 排他制御により、チャンネルBの「発光素子」は選択不可、または「太陽電池」に強制され、コンボボックス項目から消えるか無効になる
    # 設計書によると「発光素子モード選択肢を無効化（disable）し太陽電池モードのみ選択可能にする」
    assert tab.dual_chB_deviceModeCombo.currentText() == "太陽電池"
    
    model = tab.dual_chB_deviceModeCombo.model()
    for index in range(tab.dual_chB_deviceModeCombo.count()):
        if tab.dual_chB_deviceModeCombo.itemText(index) == "発光素子":
            item = model.item(index)
            assert not item.isEnabled()

    # チャンネルAを「太陽電池」に戻す
    tab.dual_chA_deviceModeCombo.setCurrentText("太陽電池")
    for index in range(tab.dual_chB_deviceModeCombo.count()):
        if tab.dual_chB_deviceModeCombo.itemText(index) == "発光素子":
            item = model.item(index)
            assert item.isEnabled()


def test_dual_contact_check_a_start_stop_emits_signals(qtbot):
    """接触確認(モードA)の開始/停止で running_changed_a /
    contact_check_running_changed_a の両方がemitされることを検証。
    """
    tab = DualChannelTab()
    qtbot.addWidget(tab)
    vm = tab.viewModel

    running_events = []
    contact_running_events = []
    readings = []
    vm.running_changed_a.connect(running_events.append)
    vm.contact_check_running_changed_a.connect(contact_running_events.append)
    vm.contact_check_reading_a.connect(lambda v, i: readings.append((v, i)))

    # 太陽電池モード(hold式)で接触確認を開始
    vm.start_contact_check_a("太陽電池", "MOCK", True, 0.02, 1.0, 0.001, 5.0)
    qtbot.waitUntil(lambda: len(readings) >= 2, timeout=5000)

    worker = vm._contact_worker_a
    vm.stop_contact_check_a()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
    worker.wait(3000)

    assert running_events[0] is True
    assert running_events[-1] is False
    assert contact_running_events[0] is True
    assert contact_running_events[-1] is False


def test_dual_contact_check_a_and_mode_a_are_mutually_exclusive(qtbot):
    """接触確認(モードA)と本測定(モードA)が相互に排他されることを検証。"""
    tab = DualChannelTab()
    qtbot.addWidget(tab)
    vm = tab.viewModel

    readings = []
    vm.contact_check_reading_a.connect(lambda v, i: readings.append((v, i)))

    vm.start_contact_check_a("太陽電池", "MOCK", True, 0.02, 1.0, 0.001, 5.0)
    qtbot.waitUntil(lambda: len(readings) >= 1, timeout=5000)

    from models.measurement.config import DualAConfig

    config = DualAConfig(
        device_type="keithley2612b",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=0.1,
        v_step=0.1,
        iteration=1,
        device_mode="太陽電池",
    )
    vm.start_mode_a(config)
    assert vm._worker_a is None  # 接触確認中は本測定を開始できない

    worker = vm._contact_worker_a
    vm.stop_contact_check_a()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
    worker.wait(3000)


def test_dual_contact_check_b_shares_single_slot_across_channels(qtbot):
    """モードBの接触確認は物理SMU1台をチャンネルA/Bで共有するため、片方が
    実行中はもう片方を同時に開始できないことを検証。
    """
    tab = DualChannelTab()
    qtbot.addWidget(tab)
    vm = tab.viewModel

    running_events = []
    readings = []
    vm.running_changed_b.connect(running_events.append)
    vm.contact_check_reading_b.connect(lambda ch, v, i: readings.append((ch, v, i)))

    vm.start_contact_check_b("smua", "太陽電池", "MOCK", True, 0.02, 1.0, 0.001, 5.0)
    qtbot.waitUntil(lambda: len(readings) >= 1, timeout=5000)

    # smub側の接触確認は同一スロットのため開始できない
    vm.start_contact_check_b("smub", "太陽電池", "MOCK", True, 0.02, 1.0, 0.001, 5.0)
    assert all(ch == "A" for ch, _, _ in readings)

    worker = vm._contact_worker_b
    vm.stop_contact_check_b()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
    worker.wait(3000)

    assert running_events[0] is True
    assert running_events[-1] is False


def test_dual_contact_check_b_and_mode_b_are_mutually_exclusive(qtbot):
    """接触確認(モードB)と本測定(モードB)が相互に排他されることを検証。"""
    tab = DualChannelTab()
    qtbot.addWidget(tab)
    vm = tab.viewModel

    readings = []
    vm.contact_check_reading_b.connect(lambda ch, v, i: readings.append((ch, v, i)))

    vm.start_contact_check_b("smua", "太陽電池", "MOCK", True, 0.02, 1.0, 0.001, 5.0)
    qtbot.waitUntil(lambda: len(readings) >= 1, timeout=5000)

    from models.measurement.config import ChannelConfig, DualBConfig

    config = DualBConfig(
        connection="MOCK",
        use_mock=True,
        channel_a=ChannelConfig(enabled=True, device_mode="太陽電池", v_min=0.0, v_max=0.1, v_step=0.1, iteration=1),
        channel_b=ChannelConfig(enabled=False),
    )
    vm.start_mode_b(config)
    assert vm._worker_b is None  # 接触確認中は本測定を開始できない

    worker = vm._contact_worker_b
    vm.stop_contact_check_b()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
    worker.wait(3000)

