"""views.plot_buffer の軸ラベル・輝度カーブリセット・凡例に関するテスト。

review.md指摘#1(軸ラベル)・#2(輝度リセット)・#6(凡例)を検証する。
"""
from __future__ import annotations

import pyqtgraph as pg
import pytest

from views import plot_buffer, theme
from views.plot_buffer import (
    DualAxisPlotBuffer,
    PlotBuffer,
    set_iv_axis_labels,
    setup_luminance_axis,
)


@pytest.fixture(autouse=True)
def _restore_graph_style():
    """plot_buffer._GRAPH_STYLE はモジュール全体で共有されるため、テスト間の汚染を防ぐ。"""
    yield
    plot_buffer.set_graph_style(dict(theme.GRAPH_STYLE_DEFAULTS))


def _luminance_curve_count(plot_widget) -> int:
    luminance_viewbox = plot_widget.luminance_viewbox
    return sum(1 for item in luminance_viewbox.addedItems if isinstance(item, pg.PlotDataItem))


# ----------------------------------------------------------------------
# review.md指摘#1: 軸ラベル
# ----------------------------------------------------------------------
def test_set_iv_axis_labels_sets_voltage_current(qtbot):
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    set_iv_axis_labels(widget)

    plot_item = widget.getPlotItem()
    assert plot_item.getAxis("bottom").labelText == "Voltage"
    assert plot_item.getAxis("left").labelText == "Current"


# ----------------------------------------------------------------------
# review.md指摘#2: 輝度カーブのリセット
# ----------------------------------------------------------------------
def test_dual_axis_plot_buffer_resets_stale_luminance_curve(qtbot):
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    setup_luminance_axis(widget)

    buffer1 = DualAxisPlotBuffer(widget)
    buffer1.add_point(0.0, 1.0, 10.0)
    buffer1.add_point(0.1, 1.1, 11.0)
    assert _luminance_curve_count(widget) == 1

    # 2回目の測定開始: 新しいバッファ生成で旧輝度カーブが増殖しないこと
    buffer2 = DualAxisPlotBuffer(widget)
    assert _luminance_curve_count(widget) == 1
    assert widget.luminance_viewbox.addedItems[-1] is buffer2.luminance_curve


def test_plot_buffer_clears_luminance_curve_when_switching_to_single_curve(qtbot):
    """発光素子(輝度あり)→太陽電池(PlotBuffer)へ切り替えても旧輝度カーブが残らないこと。"""
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    setup_luminance_axis(widget)

    dual_buffer = DualAxisPlotBuffer(widget)
    dual_buffer.add_point(0.0, 1.0, 10.0)
    assert _luminance_curve_count(widget) == 1

    PlotBuffer(widget)
    assert _luminance_curve_count(widget) == 0


# ----------------------------------------------------------------------
# review.md指摘#6: 凡例
# ----------------------------------------------------------------------
def test_plot_buffer_without_curve_name_has_no_legend(qtbot):
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    PlotBuffer(widget)
    assert widget.getPlotItem().legend is None


def test_plot_buffer_with_curve_name_registers_legend(qtbot):
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    PlotBuffer(widget, curve_name="Current")

    legend = widget.getPlotItem().legend
    assert legend is not None
    assert len(legend.items) == 1


def test_dual_axis_plot_buffer_registers_current_and_luminance_legend(qtbot):
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    setup_luminance_axis(widget)

    DualAxisPlotBuffer(widget, current_name="Current", luminance_name="Luminance")

    legend = widget.getPlotItem().legend
    assert legend is not None
    assert len(legend.items) == 2


def test_new_buffer_clears_old_legend_entries(qtbot):
    """新規バッファ生成時に古い凡例エントリが残らないこと(pyqtgraphのclear()仕様対策)。"""
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)

    PlotBuffer(widget, curve_name="Current")
    PlotBuffer(widget, curve_name="Current")

    legend = widget.getPlotItem().legend
    assert len(legend.items) == 1


def test_apply_graph_style_toggles_legend_visibility_and_font_size(qtbot):
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    PlotBuffer(widget, curve_name="Current")
    legend = widget.getPlotItem().legend

    style = dict(plot_buffer.current_graph_style())
    style["graph_show_legend"] = False
    style["graph_legend_font_size"] = 14
    plot_buffer.apply_graph_style([widget], style)

    assert legend.isVisible() is False
    assert legend.opts["labelTextSize"] == "14pt"

    style["graph_show_legend"] = True
    plot_buffer.apply_graph_style([widget], style)
    assert legend.isVisible() is True
