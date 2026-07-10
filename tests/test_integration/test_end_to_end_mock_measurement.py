"""モック機器を用いた測定のE2Eテスト。"""
from __future__ import annotations

import os
import pytest
from qtcompat import QtWidgets
from views.main_window import MainWindow
from viewmodels.opv_viewmodel import OPVViewModel
from viewmodels.jvl_viewmodel import JVLViewModel
from viewmodels.dual_channel_viewmodel import DualChannelViewModel


def test_e2e_opv_measurement(qtbot, tmp_path):
    """OPVモードでのモックE2E測定を検証。"""
    window = MainWindow()
    qtbot.addWidget(window)

    # ViewModelのバインド
    window.opv_vm = window.opv_tab.viewModel

    tab = window.opv_tab

    # パラメータ設定 (高速テストのため極小掃引)
    tab.apply_device_settings("keithley2400", "COM5", "smua", True)
    tab.opv_vMinSpin.setValue(0.0)
    tab.opv_vMaxSpin.setValue(0.1)
    tab.opv_vStepSpin.setValue(0.1)  # 0.0, 0.1 (2点)
    tab.opv_iterationSpin.setValue(1)
    tab.opv_sampleNameEdit.setText("e2e_opv_test")
    tab.opv_saveDirEdit.setText(str(tmp_path))

    # 測定開始
    tab.opv_startButton.click()

    assert window.opv_vm._worker is not None
    # workerの終了を待つ
    worker = window.opv_vm._worker
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=10000)

    # CSVが生成されているか検証
    expected_csv = tmp_path / "e2e_opv_test_OPV_measurement_data.csv"
    assert os.path.exists(expected_csv)

    # 終了後にボタン状態が復元していることを検証
    assert tab.opv_startButton.isEnabled()
    assert not tab.opv_stopButton.isEnabled()


def test_e2e_jvl_measurement(qtbot, tmp_path):
    """JVLモードでのモックE2E測定を検証。"""
    window = MainWindow()
    qtbot.addWidget(window)

    window.jvl_vm = window.jvl_tab.viewModel
    tab = window.jvl_tab

    tab.apply_device_settings("keithley2400", "COM5", "COM4", "smua", True)
    tab.jvl_useLuminanceCheckBox.setChecked(True)
    tab.jvl_vMinSpin.setValue(0.0)
    tab.jvl_vMaxSpin.setValue(0.1)
    tab.jvl_vStepSpin.setValue(0.1)
    tab.jvl_iterationSpin.setValue(1)
    tab.jvl_sampleNameEdit.setText("e2e_jvl_test")
    tab.jvl_saveDirEdit.setText(str(tmp_path))

    tab.jvl_startButton.click()

    assert window.jvl_vm._worker is not None
    worker = window.jvl_vm._worker
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=10000)

    expected_csv = tmp_path / "e2e_jvl_test_JVL_measurement_data.csv"
    assert os.path.exists(expected_csv)

    # 3列 (voltage, current, luminance) のCSVであることを確認
    with open(expected_csv, "r", encoding="utf-8") as f:
        header = f.readline().strip()
    assert header == "voltage [V],current [A],luminance [cd/m2]"


def test_e2e_dual_a_measurement(qtbot, tmp_path):
    """モードAでのモックE2E測定を検証。特にsmubの電流が採用されていることを厳密に検証する。"""
    window = MainWindow()
    qtbot.addWidget(window)

    window.dual_vm = window.dual_channel_tab.viewModel
    tab = window.dual_channel_tab

    # パラメータ設定 (高速テストのため極小掃引)
    tab.apply_device_settings_mode_a("COM5", "COM4", True)
    tab.dual_a_vMinSpin.setValue(0.0)
    tab.dual_a_vMaxSpin.setValue(0.2)
    tab.dual_a_vStepSpin.setValue(0.1)  # 0.0, 0.1, 0.2 (3点)
    tab.dual_a_iterationSpin.setValue(1)
    tab.dual_a_sampleNameEdit.setText("e2e_duala_test")
    tab.dual_a_saveDirEdit.setText(str(tmp_path))
    tab.dual_a_deviceModeCombo.setCurrentText("太陽電池")

    # registry.create_source_meterをフックして、生成されるKeithley2612BMockのmeasure_currentをモック化する
    import models.instruments.registry as reg
    from models.instruments.mock.keithley2612b_mock import Keithley2612BMock

    original_create = reg.create_source_meter
    measured_channels = []

    def mock_create_source_meter(device_type, connection, use_mock=False, preset=None):
        smu = original_create(device_type, connection, use_mock=use_mock, preset=preset)
        if isinstance(smu, Keithley2612BMock):
            def mock_measure_current(channel: str) -> float:
                measured_channels.append(channel)
                if channel == "smua":
                    return 999.0
                elif channel == "smub":
                    return -0.00123
                return 0.0
            smu.measure_current = mock_measure_current
        return smu

    reg.create_source_meter = mock_create_source_meter

    try:
        tab.dual_a_startButton.click()

        assert window.dual_vm._worker_a is not None
        worker = window.dual_vm._worker_a
        qtbot.waitUntil(lambda: not worker.isRunning(), timeout=10000)

        # CSVが生成されているか検証
        expected_csv = tmp_path / "e2e_duala_test_dualA_OPV_measurement_data.csv"
        assert os.path.exists(expected_csv)

        # CSVの中身を検証し、smubの電流（符号反転された 0.00123）が保存されているか確認
        import csv
        with open(expected_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["voltage [V]", "current [A]"]
            rows = list(reader)
            assert len(rows) == 3
            for r in rows:
                assert float(r[1]) == pytest.approx(0.00123)

        # 測定されたチャンネルがすべて smub であることを確認
        assert len(measured_channels) == 3
        assert all(ch == "smub" for ch in measured_channels)

    finally:
        reg.create_source_meter = original_create
