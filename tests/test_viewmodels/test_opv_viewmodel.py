"""OPVViewModel の動作検証テスト。"""
from __future__ import annotations

import pytest
from opvjvl.qtcompat import QtWidgets
from opvjvl.viewmodels.opv_viewmodel import OPVViewModel
from opvjvl.views.opv_tab import OPVTab


def test_opv_viewmodel_init(qtbot):
    """初期状態でのViewModelとWidgetの状態を検証。"""
    tab = OPVTab()
    qtbot.addWidget(tab)

    vm = OPVViewModel(tab)

    # 初期化時のボタンの状態
    assert tab.opv_startButton.isEnabled()
    assert not tab.opv_stopButton.isEnabled()


def test_opv_viewmodel_validation(qtbot):
    """電圧範囲のバリデーションを検証。"""
    tab = OPVTab()
    qtbot.addWidget(tab)

    vm = OPVViewModel(tab)

    # 異常値設定 (Vmin > Vmax)
    tab.opv_vMinSpin.setValue(1.5)
    tab.opv_vMaxSpin.setValue(1.0)

    # 開始ボタンクリック時のバリデーションで失敗し、ワーカーが生成されないこと
    # QMessageBox が警告を出すが、offscreenかつテスト中なのでQMessageBoxは自動で閉じられる、またはモック等でのハンドリングが必要。
    # 通常、base_viewmodel内のvalidate_voltage_rangeでQMessageBox.warningが呼ばれる。
    # qtbotを用いてダイアログを処理、あるいは単にメソッド呼び出しでバリデーション結果を確認する。

    # ここでは、直接 validate_voltage_range の挙動を確認する代わりに、
    # 測定開始処理がバリデーション失敗により早期リターンし、
    # _worker が設定されないことを検証。
    tab.opv_startButton.click()
    assert vm._worker is None
