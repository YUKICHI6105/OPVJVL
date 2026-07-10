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

