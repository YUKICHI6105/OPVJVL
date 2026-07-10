"""モック機器を用いた測定のE2Eテスト。"""
from __future__ import annotations

import os
import pytest
from opvjvl.qtcompat import QtWidgets
from opvjvl.views.main_window import MainWindow
from opvjvl.viewmodels.opv_viewmodel import OPVViewModel
from opvjvl.viewmodels.jvl_viewmodel import JVLViewModel
from opvjvl.viewmodels.dual_channel_viewmodel import DualChannelViewModel


def test_e2e_opv_measurement(qtbot, tmp_path):
    """OPVモードでのモックE2E測定を検証。"""
    window = MainWindow()
    qtbot.addWidget(window)

    # ViewModelのバインド
    window.opv_vm = OPVViewModel(window.opv_tab)

    tab = window.opv_tab

    # パラメータ設定 (高速テストのため極小掃引)
    tab.opv_useMockCheckBox.setChecked(True)
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

    window.jvl_vm = JVLViewModel(window.jvl_tab)
    tab = window.jvl_tab

    tab.jvl_useMockCheckBox.setChecked(True)
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
