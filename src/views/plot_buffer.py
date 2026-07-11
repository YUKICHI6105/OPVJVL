"""View層専用のプロットバッファとグラフスタイル適用。

pyqtgraphは1点ごとにplot()すると新規カーブが増え続けるため、
測定開始時にバッファを作り直し、1点ごとにsetData()で更新する。

グラフ表示スタイル(線幅・シンボルサイズ・目盛フォント・グリッド)は
メニューバー「表示 > グラフ表示の設定...」(EQEから移植)で変更でき、
``set_graph_style()``で本モジュールへ反映後、新規カーブに適用される。
既存プロットへは ``apply_graph_style()`` が即時適用する。
"""
from __future__ import annotations

from typing import Iterable, List, Optional
import pyqtgraph as pg

from qtcompat import QtGui
from views import theme

# 現在有効なグラフスタイル(唯一の正はtheme.GRAPH_STYLE_DEFAULTS。
# MainWindowがsettings.jsonから復元した値で起動時に更新する)。
_GRAPH_STYLE = dict(theme.GRAPH_STYLE_DEFAULTS)


def set_graph_style(style: dict) -> None:
    """新規カーブ生成時に使うグラフスタイルを更新する。"""
    _GRAPH_STYLE.update(style)


def current_graph_style() -> dict:
    """現在有効なグラフスタイルのコピーを返す。"""
    return dict(_GRAPH_STYLE)


def apply_graph_style(plot_widgets: Iterable[pg.PlotWidget], style: dict) -> None:
    """既存のプロットウィジェット群へグラフスタイルを即時適用する。

    * 軸(左/下/右)の目盛フォントサイズ
    * グリッド表示の有無
    * 既存カーブのシンボルサイズ・線幅
    """
    set_graph_style(style)

    tick_font = QtGui.QFont()
    tick_font.setPointSize(int(_GRAPH_STYLE["graph_font_size"]))
    show_grid = bool(_GRAPH_STYLE["graph_show_grid"])
    symbol_size = int(_GRAPH_STYLE["graph_symbol_size"])
    line_width = float(_GRAPH_STYLE["graph_line_width"])

    for plot_widget in plot_widgets:
        plot_item = plot_widget.getPlotItem()
        for axis_name in ("left", "bottom", "right"):
            axis = plot_item.getAxis(axis_name)
            if axis is not None:
                axis.setStyle(tickFont=tick_font)
        plot_item.showGrid(x=show_grid, y=show_grid, alpha=0.2)
        for item in plot_item.listDataItems():
            _apply_style_to_data_item(item, symbol_size, line_width)
        # JVLのI-V-Lページ等、右軸ViewBoxに載っている輝度カーブにも適用する
        luminance_viewbox = getattr(plot_widget, "luminance_viewbox", None)
        if luminance_viewbox is not None:
            for item in luminance_viewbox.addedItems:
                if isinstance(item, pg.PlotDataItem):
                    _apply_style_to_data_item(item, symbol_size, line_width)


def _apply_style_to_data_item(item, symbol_size: int, line_width: float) -> None:
    """1つのPlotDataItemへシンボルサイズ・線幅を適用する。"""
    if item.opts.get("symbol") is not None:
        item.setSymbolSize(symbol_size)
    pen = item.opts.get("pen")
    if pen is not None:
        new_pen = pg.mkPen(pen)
        new_pen.setWidthF(line_width)
        item.setPen(new_pen)


class PlotBuffer:
    """単一カーブ(電圧-電流等)を持つプロットの点群バッファ。"""

    def __init__(self, plot_widget: pg.PlotWidget, pen=None) -> None:
        plot_widget.clear()
        self.plot_widget = plot_widget
        self.x: List[float] = []
        self.y: List[float] = []
        self.curve = plot_widget.plot(
            [], [], pen=pen, symbol="o", symbolSize=int(_GRAPH_STYLE["graph_symbol_size"])
        )

    def add_point(self, x: float, y: float) -> None:
        self.x.append(x)
        self.y.append(y)
        self.curve.setData(self.x, self.y)


class DualAxisPlotBuffer:
    """左軸(電流)・右軸(輝度)を同時更新するプロットバッファ(JVLのI-V-Lページ用)。"""

    def __init__(self, plot_widget: pg.PlotWidget) -> None:
        plot_widget.clear()
        self.plot_widget = plot_widget
        self.x: List[float] = []
        self.y_current: List[float] = []
        self.x_luminance: List[float] = []
        self.y_luminance: List[float] = []
        line_width = float(_GRAPH_STYLE["graph_line_width"])
        self.current_curve = plot_widget.plot(
            [],
            [],
            pen=pg.mkPen("c", width=line_width),
            symbol="o",
            symbolSize=int(_GRAPH_STYLE["graph_symbol_size"]),
        )
        self.luminance_curve = pg.PlotDataItem([], [], pen=pg.mkPen("m", width=line_width))
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
