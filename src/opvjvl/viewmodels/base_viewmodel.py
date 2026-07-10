"""ViewModel層で共通に使う小さなヘルパー群。

要件定義書_基本設計書.md B-1節(ViewModelの責務)・B-7節(エラーハンドリング
方針)に対応する。各ViewModel(OPVViewModel/JVLViewModel/DualChannelViewModel)
はここに定義するヘルパーを使い回すことで、開始/中断ボタンの状態管理・
バリデーションダイアログ・ログ整形・プロット更新といった定型処理の重複を
避ける。Qt依存(``QMessageBox``等)を持つためこのモジュール自体もQt依存だが、
機器制御・CSV書式などの業務ロジックは一切持たない。
"""
from __future__ import annotations

from typing import List, Optional

import pyqtgraph as pg

from opvjvl.qtcompat import QtWidgets


# ---------------------------------------------------------------------------
# 開始/中断ボタンの状態管理(B-7節: 二重起動防止)
# ---------------------------------------------------------------------------


def set_running_state(
    start_button: QtWidgets.QPushButton,
    stop_button: QtWidgets.QPushButton,
    running: bool,
) -> None:
    """測定中は開始ボタンを無効化、中断ボタンを有効化する(逆も同様)。"""
    start_button.setEnabled(not running)
    stop_button.setEnabled(running)


# ---------------------------------------------------------------------------
# バリデーション
# ---------------------------------------------------------------------------


def validate_voltage_range(
    parent_widget: QtWidgets.QWidget, v_min: float, v_max: float
) -> bool:
    """Vmax > Vminであることを検証し、違反時は警告ダイアログを出す。"""
    if v_max <= v_min:
        QtWidgets.QMessageBox.warning(
            parent_widget,
            "入力エラー",
            f"Vmax({v_max})はVmin({v_min})より大きい値にしてください。",
        )
        return False
    return True


def validate_luminance_port(parent_widget: QtWidgets.QWidget, bm9_port: Optional[str]) -> bool:
    """輝度計測ON時にBM9接続ポートが未入力でないことを検証する(B-7節)。"""
    if not bm9_port or not bm9_port.strip():
        QtWidgets.QMessageBox.warning(
            parent_widget,
            "入力エラー",
            "輝度計測を使用する場合はBM9接続ポートを入力してください。",
        )
        return False
    return True


def show_warning(parent_widget: QtWidgets.QWidget, message: str) -> None:
    QtWidgets.QMessageBox.warning(parent_widget, "入力エラー", message)


def show_critical(parent_widget: QtWidgets.QWidget, message: str) -> None:
    QtWidgets.QMessageBox.critical(parent_widget, "エラー", message)


# ---------------------------------------------------------------------------
# ログ整形(B-7節: モック使用時は[MOCK MODE]を明示)
# ---------------------------------------------------------------------------


def mock_log_prefix(use_mock: bool) -> str:
    return "[MOCK MODE] " if use_mock else ""


def append_log(text_edit: QtWidgets.QTextEdit, message: str) -> None:
    text_edit.append(message)


def append_error_log(text_edit: QtWidgets.QTextEdit, message: str) -> None:
    """エラーメッセージを赤字でログ欄に追記する(B-1節: エラーは赤字で追記)。"""
    text_edit.append(f'<span style="color:#ff5555;">エラー: {message}</span>')


# ---------------------------------------------------------------------------
# プロット更新(pyqtgraphは1点ごとにplot()すると新規カーブが増え続けるため、
# 測定開始時にバッファを作り直し、1点ごとにsetData()で更新する)
# ---------------------------------------------------------------------------


class PlotBuffer:
    """単一カーブ(電圧-電流等)を持つプロットの点群バッファ。"""

    def __init__(self, plot_widget: pg.PlotWidget, pen=None) -> None:
        plot_widget.clear()
        self.plot_widget = plot_widget
        self.x: List[float] = []
        self.y: List[float] = []
        self.curve = plot_widget.plot([], [], pen=pen, symbol="o", symbolSize=4)

    def add_point(self, x: float, y: float) -> None:
        self.x.append(x)
        self.y.append(y)
        self.curve.setData(self.x, self.y)


class DualAxisPlotBuffer:
    """左軸(電流)・右軸(輝度)を同時更新するプロットバッファ(JVLのI-V-Lページ用)。

    ``jvl_tab.py``の``_setup_luminance_axis``が``plot_widget.luminance_viewbox``
    属性として右軸用のViewBoxを用意しているため、それを利用する。
    """

    def __init__(self, plot_widget: pg.PlotWidget) -> None:
        plot_widget.clear()
        self.plot_widget = plot_widget
        self.x: List[float] = []
        self.y_current: List[float] = []
        self.x_luminance: List[float] = []
        self.y_luminance: List[float] = []
        self.current_curve = plot_widget.plot([], [], pen=pg.mkPen("c"), symbol="o", symbolSize=4)
        self.luminance_curve = pg.PlotDataItem([], [], pen=pg.mkPen("m"))
        luminance_viewbox = getattr(plot_widget, "luminance_viewbox", None)
        if luminance_viewbox is not None:
            luminance_viewbox.addItem(self.luminance_curve)

    def add_point(self, x: float, current: float, luminance: Optional[float] = None) -> None:
        self.x.append(x)
        self.y_current.append(current)
        self.current_curve.setData(self.x, self.y_current)
        if luminance is not None:
            self.x_luminance.append(x)
            self.y_luminance.append(luminance)
            self.luminance_curve.setData(self.x_luminance, self.y_luminance)
