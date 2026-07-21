"""OPVViewModel の動作検証テスト。"""
from __future__ import annotations

import pytest
from qtcompat import QtWidgets
from models.measurement.config import OPVConfig
from viewmodels.opv_viewmodel import OPVViewModel
from views.opv_tab import OPVTab



def test_opv_viewmodel_init(qtbot):
    """初期状態でのViewModelとWidgetの状態を検証。"""
    tab = OPVTab()
    qtbot.addWidget(tab)

    # ViewModelはTab内部で自動生成される
    vm = tab.viewModel

    # 初期化時のボタンの状態
    assert tab.opv_startButton.isEnabled()
    assert not tab.opv_stopButton.isEnabled()


def test_opv_viewmodel_validation(qtbot):
    """電圧範囲のバリデーションを検証。"""
    tab = OPVTab()
    qtbot.addWidget(tab)

    vm = tab.viewModel

    # 異常値設定 (Vmin > Vmax)
    config = OPVConfig(
        device_type="keithley2400",
        connection="COM5",
        use_mock=True,
        v_min=1.5,
        v_max=1.0,
        v_step=0.02,
        iteration=3,
        compliance_current=0.02,
        nplc=1.0,
        delay_time=1.0,
        sample_name="sample",
        save_dir=".",
    )

    # errorシグナルの発火を監視
    errors = []
    vm.error.connect(errors.append)

    # 測定開始処理がバリデーション失敗により早期リターンし、
    # _worker が設定されないことを検証。
    vm.start_measurement(config)
    assert vm._worker is None
    assert len(errors) == 1
    assert "Vmax" in errors[0]


def test_opv_contact_check_start_stop_emits_signals(qtbot):
    """接触確認の開始/停止で running_changed と contact_check_running_changed の
    両方がTrue/False順にemitされ、電流readingを受信できることを検証。
    """
    tab = OPVTab()
    qtbot.addWidget(tab)
    vm = tab.viewModel

    running_events = []
    contact_running_events = []
    readings = []
    vm.running_changed.connect(running_events.append)
    vm.contact_check_running_changed.connect(contact_running_events.append)
    vm.contact_check_reading.connect(lambda v, i: readings.append((v, i)))

    vm.start_contact_check("keithley2400", "MOCK", "smua", True, 0.02, 1.0)

    assert vm._contact_worker is not None
    worker = vm._contact_worker
    qtbot.waitUntil(lambda: len(readings) >= 2, timeout=5000)

    vm.stop_contact_check()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
    worker.wait(3000)
    qtbot.waitUntil(lambda: contact_running_events[-1] is False, timeout=5000)

    assert running_events[0] is True
    assert running_events[-1] is False
    assert contact_running_events[0] is True
    assert contact_running_events[-1] is False
    assert all(v == 0.0 for v, _ in readings)


def test_opv_contact_check_and_measurement_are_mutually_exclusive(qtbot):
    """接触確認中は本測定を開始できず、本測定中は接触確認を開始できないことを検証。"""
    tab = OPVTab()
    qtbot.addWidget(tab)
    vm = tab.viewModel

    readings = []
    vm.contact_check_reading.connect(lambda v, i: readings.append((v, i)))

    # 接触確認を開始
    vm.start_contact_check("keithley2400", "MOCK", "smua", True, 0.02, 1.0)
    qtbot.waitUntil(lambda: len(readings) >= 1, timeout=5000)

    # 接触確認実行中は本測定を開始できない
    config = OPVConfig(
        device_type="keithley2400",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=0.1,
        v_step=0.1,
        iteration=1,
        compliance_current=0.02,
        nplc=1.0,
        delay_time=0.0,
        sample_name="sample",
        save_dir=".",
    )
    vm.start_measurement(config)
    assert vm._worker is None

    contact_worker = vm._contact_worker
    vm.stop_contact_check()
    qtbot.waitUntil(lambda: not contact_worker.isRunning(), timeout=5000)
    contact_worker.wait(3000)

    # 接触確認終了後は本測定を開始できる(排他解除の確認)
    vm.start_measurement(config)
    assert vm._worker is not None
    worker = vm._worker
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
    worker.wait(3000)

    # 本測定実行中は接触確認を開始できないことも別途検証
    vm2 = OPVViewModel()
    long_config = OPVConfig(
        device_type="keithley2400",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=2.0,
        v_step=0.001,
        iteration=1,
        compliance_current=0.02,
        nplc=1.0,
        delay_time=0.05,
        sample_name="sample",
        save_dir=".",
    )
    vm2.start_measurement(long_config)
    assert vm2._worker is not None
    worker2 = vm2._worker
    vm2.start_contact_check("keithley2400", "MOCK", "smua", True, 0.02, 1.0)
    assert vm2._contact_worker is None
    vm2.stop_measurement()
    qtbot.waitUntil(lambda: not worker2.isRunning(), timeout=10000)
    worker2.wait(3000)

