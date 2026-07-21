"""JVLViewModel の動作検証テスト。"""
from __future__ import annotations

import pytest
from qtcompat import QtWidgets
from viewmodels.jvl_viewmodel import JVLViewModel
from views.jvl_tab import JVLTab


def test_jvl_viewmodel_init(qtbot):
    """初期化時の状態検証。"""
    tab = JVLTab()
    qtbot.addWidget(tab)

    vm = tab.viewModel

    assert tab.jvl_startButton.isEnabled()
    assert not tab.jvl_stopButton.isEnabled()


def test_jvl_viewmodel_luminance_checkbox(qtbot):
    """輝度計チェックボックスの切り替えに伴い、Config構築時のuse_luminance/bm9_portが変化することを検証。"""
    tab = JVLTab()
    qtbot.addWidget(tab)
    tab.apply_device_settings("keithley2400", "COM5", "COM4")

    assert tab.jvl_useLuminanceCheckBox.isChecked()
    config = tab._build_config()
    assert config.use_luminance
    assert config.bm9_port == "COM4"

    tab.jvl_useLuminanceCheckBox.setChecked(False)
    config = tab._build_config()
    assert not config.use_luminance
    assert config.bm9_port is None

    tab.jvl_useLuminanceCheckBox.setChecked(True)
    config = tab._build_config()
    assert config.use_luminance
    assert config.bm9_port == "COM4"


def test_jvl_contact_check_start_stop_emits_signals(qtbot):
    """接触確認(JVL式)は電流閾値に到達してもその電圧を維持し続け、
    ``stop_contact_check()``を呼ぶまで停止しないこと、また停止時に
    running_changed / contact_check_running_changedの両方がemitされる
    ことを検証する。
    """
    tab = JVLTab()
    qtbot.addWidget(tab)
    vm = tab.viewModel

    running_events = []
    contact_running_events = []
    readings = []
    vm.running_changed.connect(running_events.append)
    vm.contact_check_running_changed.connect(contact_running_events.append)
    vm.contact_check_reading.connect(lambda v, i: readings.append((v, i)))

    # 閾値を極小にして即座に到達させる(到達後は保持フェーズに入り、
    # 手動で停止するまで動作し続けるはず)
    vm.start_contact_check("keithley2400", "MOCK", "smua", True, 0.02, 1.0, 1e-9, 5.0)
    worker = vm._contact_worker

    qtbot.waitUntil(lambda: len(readings) >= 3, timeout=5000)
    # 閾値到達後も自動停止せず動作し続けていること
    assert worker.isRunning()

    vm.stop_contact_check()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=10000)
    worker.wait(3000)

    assert running_events[0] is True
    assert running_events[-1] is False
    assert contact_running_events[0] is True
    assert contact_running_events[-1] is False
    assert len(readings) >= 3


def test_jvl_contact_check_and_measurement_are_mutually_exclusive(qtbot):
    """接触確認と本測定が相互に排他されることを検証。"""
    tab = JVLTab()
    qtbot.addWidget(tab)
    vm = tab.viewModel

    readings = []
    vm.contact_check_reading.connect(lambda v, i: readings.append((v, i)))

    # 閾値を非常に大きくして自動停止させず、実行中の状態を作る
    vm.start_contact_check("keithley2400", "MOCK", "smua", True, 0.02, 1.0, 10.0, 5.0)
    qtbot.waitUntil(lambda: len(readings) >= 1, timeout=5000)

    from models.measurement.config import JVLConfig

    config = JVLConfig(
        device_type="keithley2400",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=0.1,
        v_step=0.1,
        iteration=1,
        use_luminance=False,
    )
    vm.start_measurement(config)
    assert vm._worker is None  # 接触確認中は本測定を開始できない

    worker = vm._contact_worker
    vm.stop_contact_check()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
    worker.wait(3000)

