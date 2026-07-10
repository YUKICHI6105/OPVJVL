"""View層専用のプロットバッファ。

pyqtgraphは1点ごとにplot()すると新規カーブが増え続けるため、
測定開始時にバッファを作り直し、1点ごとにsetData()で更新する。
"""
from __future__ import annotations

from typing import List, Optional
import pyqtgraph as pg


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
    """左軸(電流)・右軸(輝度)を同時更新するプロットバッファ(JVLのI-V-Lページ用)。"""

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
