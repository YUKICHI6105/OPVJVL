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
    install_auto_range_menu,
    set_iv_axis_labels,
    setup_luminance_axis,
)


@pytest.fixture(autouse=True)
def _restore_graph_style():
    """plot_buffer._GRAPH_STYLE はモジュール全体で共有されるため、テスト間の汚染を防ぐ。"""
    yield
    plot_buffer.set_graph_style(dict(theme.GRAPH_STYLE_DEFAULTS))


@pytest.fixture
def plot_widget(qtbot):
    """テスト用PlotWidgetを生成し、終了時に輝度軸を明示的にクリーンアップする。

    破棄タイミングをGC/qtbot任せにすると、XLink済みの輝度ViewBoxが破棄済み
    PlotWidgetを参照したまま ``linkedXChanged`` を処理してアクセス違反クラッシュに
    至ることがあるため、テスト終了時に ``cleanup_luminance_axis`` → ``deleteLater``
    → イベント処理数回、の順で確実に切り離す。
    """
    from qtcompat import QtWidgets

    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    yield widget
    plot_buffer.cleanup_luminance_axis(widget)
    widget.deleteLater()
    app = QtWidgets.QApplication.instance()
    for _ in range(3):
        app.processEvents()


def _luminance_curve_count(plot_widget) -> int:
    luminance_viewbox = plot_widget.luminance_viewbox
    return sum(1 for item in luminance_viewbox.addedItems if isinstance(item, pg.PlotDataItem))


# ----------------------------------------------------------------------
# review.md指摘#1: 軸ラベル
# ----------------------------------------------------------------------
def test_set_iv_axis_labels_sets_voltage_current(plot_widget):
    widget = plot_widget
    set_iv_axis_labels(widget)

    plot_item = widget.getPlotItem()
    assert plot_item.getAxis("bottom").labelText == "Voltage"
    assert plot_item.getAxis("left").labelText == "Current"


# ----------------------------------------------------------------------
# review.md指摘#2: 輝度カーブのリセット
# ----------------------------------------------------------------------
def test_dual_axis_plot_buffer_resets_stale_luminance_curve(plot_widget):
    widget = plot_widget
    setup_luminance_axis(widget)

    buffer1 = DualAxisPlotBuffer(widget)
    buffer1.add_point(0.0, 1.0, 10.0)
    buffer1.add_point(0.1, 1.1, 11.0)
    assert _luminance_curve_count(widget) == 1

    # 2回目の測定開始: 新しいバッファ生成で旧輝度カーブが増殖しないこと
    buffer2 = DualAxisPlotBuffer(widget)
    assert _luminance_curve_count(widget) == 1
    assert widget.luminance_viewbox.addedItems[-1] is buffer2.luminance_curve


def test_plot_buffer_clears_luminance_curve_when_switching_to_single_curve(plot_widget):
    """発光素子(輝度あり)→太陽電池(PlotBuffer)へ切り替えても旧輝度カーブが残らないこと。"""
    widget = plot_widget
    setup_luminance_axis(widget)

    dual_buffer = DualAxisPlotBuffer(widget)
    dual_buffer.add_point(0.0, 1.0, 10.0)
    assert _luminance_curve_count(widget) == 1

    PlotBuffer(widget)
    assert _luminance_curve_count(widget) == 0


# ----------------------------------------------------------------------
# review.md指摘#6: 凡例
# ----------------------------------------------------------------------


def test_dual_axis_plot_buffer_registers_current_and_luminance_legend(plot_widget):
    widget = plot_widget
    setup_luminance_axis(widget)

    DualAxisPlotBuffer(widget, current_name="Current", luminance_name="Luminance")

    legend = widget.getPlotItem().legend
    assert legend is not None
    assert len(legend.items) == 2


def test_new_buffer_clears_old_legend_entries(plot_widget):
    """新規バッファ生成時に古い凡例エントリが残らないこと(pyqtgraphのclear()仕様対策)。"""
    widget = plot_widget

    PlotBuffer(widget, curve_name="Current")
    PlotBuffer(widget, curve_name="Current")

    legend = widget.getPlotItem().legend
    assert len(legend.items) == 1


def test_apply_graph_style_toggles_legend_visibility_and_font_size(plot_widget):
    widget = plot_widget
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


# ----------------------------------------------------------------------
# review.md項目2: ヒステリシス往復分割(reverse_from_index)
# ----------------------------------------------------------------------
def test_plot_buffer_without_reverse_from_index_stays_single_curve(plot_widget):
    """reverse_from_index未指定時は従来通り1カーブのみで、凡例も付かない。"""
    widget = plot_widget
    buf = PlotBuffer(widget)
    for i in range(5):
        buf.add_point(float(i), float(i) * 2)

    assert buf.reverse_curve is None
    assert widget.getPlotItem().legend is None
    assert len(buf.x) == 5


def test_plot_buffer_reverse_from_index_splits_into_two_curves(plot_widget):
    """reverse_from_index指定時、通算点数がその値以上になった点から復路カーブへ切り替わる。"""
    widget = plot_widget
    buf = PlotBuffer(widget, reverse_from_index=3)
    for i in range(5):
        buf.add_point(float(i), float(i))

    assert len(buf.x) == 3
    assert len(buf.reverse_x) == 2
    assert buf.curve.opts["pen"].color().name() == "#1f77b4"
    assert buf.reverse_curve.opts["pen"].color().name() == "#ff7f0e"

    legend = widget.getPlotItem().legend
    assert legend is not None
    assert len(legend.items) == 2
    labels = {item[1].text for item in legend.items}
    assert labels == {"Current / Forward（往路）", "Current / Backward（復路）"}


def test_dual_axis_plot_buffer_reverse_from_index_splits_current_and_luminance(plot_widget):
    """電流カーブのみ往路/復路で分割され、輝度カーブは単一のまま。"""
    widget = plot_widget
    setup_luminance_axis(widget)
    buf = DualAxisPlotBuffer(
        widget, current_name="Current", luminance_name="Luminance", reverse_from_index=2
    )
    for i in range(4):
        buf.add_point(float(i), float(i), float(i) * 10)

    assert len(buf.x) == 2
    assert len(buf.reverse_x) == 2
    assert len(buf.x_luminance) == 2
    assert len(buf.reverse_x_luminance) == 2
    assert _luminance_curve_count(widget) == 2

    legend = widget.getPlotItem().legend
    assert legend is not None
    labels = {item[1].text for item in legend.items}
    assert labels == {"Current / Forward（往路）", "Current / Backward（復路）", "Luminance / Forward（往路）", "Luminance / Backward（復路）"}


def test_missing_luminance_does_not_shift_backward_boundary(plot_widget):
    setup_luminance_axis(plot_widget)
    buf = DualAxisPlotBuffer(plot_widget, reverse_from_index=3)
    buf.add_point(0, 0, 10)
    buf.add_point(1, 1, None)
    buf.add_point(2, 2, 30)
    buf.add_point(1, 3, 40)
    assert buf.x_luminance == [0, 2]
    assert buf.reverse_x_luminance == [1]
    assert buf.reverse_y_luminance == [40]
    from qtcompat import Qt, enum_value
    assert buf.reverse_current_curve.opts["pen"].style() == enum_value(Qt, "DashLine")
    assert buf.reverse_luminance_curve.opts["pen"].style() == enum_value(Qt, "DashLine")


# ----------------------------------------------------------------------
# 右クリックメニュー「両軸を自動スケーリング」
# ----------------------------------------------------------------------
_AUTO_RANGE_TEXT = "両軸を自動スケーリング (Auto Range Both)"


def _has_auto_range_action(view_box) -> bool:
    menu = getattr(view_box, "menu", None)
    if menu is None:
        return False
    return any(action.text() == _AUTO_RANGE_TEXT for action in menu.actions())


def test_install_auto_range_menu_is_idempotent(plot_widget):
    """複数回呼んでも項目は重複しない。"""
    install_auto_range_menu(plot_widget)
    install_auto_range_menu(plot_widget)

    menu = plot_widget.getPlotItem().getViewBox().menu
    assert [a.text() for a in menu.actions()].count(_AUTO_RANGE_TEXT) == 1


def test_luminance_viewbox_created_later_also_gets_auto_range_action(plot_widget):
    """測定開始時に後から輝度軸を足しても自動スケーリング項目が失われない。

    輝度用ViewBoxはメインViewBoxの上に重なり、プロット領域の右クリックを
    横取りするため、そちら側のメニューにも同じ項目が必要になる
    (2ch活用モードの発光素子計測で項目が消えていた不具合の回帰テスト)。
    """
    install_auto_range_menu(plot_widget)
    setup_luminance_axis(plot_widget)

    assert _has_auto_range_action(plot_widget.luminance_viewbox)


def test_install_auto_range_menu_covers_existing_luminance_viewbox(plot_widget):
    """輝度軸を先に用意してから呼んだ場合も、両方のViewBoxへ項目が入る。"""
    setup_luminance_axis(plot_widget)
    install_auto_range_menu(plot_widget)

    assert _has_auto_range_action(plot_widget.getPlotItem().getViewBox())
    assert _has_auto_range_action(plot_widget.luminance_viewbox)
