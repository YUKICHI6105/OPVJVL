"""アプリケーションのメインウィンドウ(View層)。

`resources/ui/main_window.ui`(Qt Designer作成済み)をロードし、
OPV/JVL/2ch活用の各タブをコードで構築して挿入する。
業務ロジックは持たない(B-6-1節: ハイブリッド方式)。
"""
from __future__ import annotations

from pathlib import Path

from opvjvl import qtcompat
from opvjvl.qtcompat import QtWidgets
from opvjvl.views.dual_channel_tab import DualChannelTab
from opvjvl.views.jvl_tab import JVLTab
from opvjvl.views.opv_tab import OPVTab


class MainWindow(QtWidgets.QMainWindow):
    """`main_window.ui` をロードし、3つのタブを挿入するメインウィンドウ。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = Path(__file__).resolve().parent.parent / "resources" / "ui" / "main_window.ui"
        qtcompat.uic.loadUi(str(ui_path), self)
        self.setWindowTitle("太陽電池と発光素子計測プログラム")

        self.opv_tab = OPVTab()
        self.jvl_tab = JVLTab()
        self.dual_channel_tab = DualChannelTab()

        self.mainTabWidget.addTab(self.opv_tab, "OPVモード")
        self.mainTabWidget.addTab(self.jvl_tab, "JVLモード")
        self.mainTabWidget.addTab(self.dual_channel_tab, "2ch活用モード")

        self.actionExit.triggered.connect(self.close)
        self.actionAbout.triggered.connect(self._show_about)

    def _show_about(self) -> None:
        """簡易なバージョン情報ダイアログを表示する。"""
        QtWidgets.QMessageBox.information(
            self,
            "バージョン情報",
            "太陽電池と発光素子計測プログラム\nOPVJVL",
        )
