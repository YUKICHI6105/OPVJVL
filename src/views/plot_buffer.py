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

from qtcompat import QAction, QtGui
from views import theme

# review.md指摘#1: JVグラフを「散布図のみ」から「折れ線+シンボル」表示にするための
# デフォルト線色(白背景で視認しやすい青系)。DualAxisPlotBufferの電流・輝度カーブにも
# 同系統の配色(電流=青系/輝度=赤系)を用いる。
_DEFAULT_LINE_COLOR = "#1f77b4"
_LUMINANCE_LINE_COLOR = "#d62728"

# review.md指摘#3: アプリ全体はダークテーマQSSだが、グラフ(pyqtgraph)は
# 白背景・黒前景(軸/目盛/ラベル)に固定する。pyqtgraphの背景・前景色は
# PlotWidget生成より前に設定する必要があるため、全タブ(opv_tab/jvl_tab/
# dual_channel_tab)が必ず先にimportする本モジュールのトップレベルで設定する。
pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")

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
    * 凡例(存在する場合)の表示/非表示・フォントサイズ(review.md指摘#6)
    """
    set_graph_style(style)

    tick_font = QtGui.QFont()
    tick_font.setPointSize(int(_GRAPH_STYLE["graph_font_size"]))
    show_grid = bool(_GRAPH_STYLE["graph_show_grid"])
    symbol_size = int(_GRAPH_STYLE["graph_symbol_size"])
    line_width = float(_GRAPH_STYLE["graph_line_width"])
    show_legend = bool(_GRAPH_STYLE["graph_show_legend"])
    legend_font_size = int(_GRAPH_STYLE["graph_legend_font_size"])

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
        # 凡例(curve_name等を指定して生成された場合のみ存在)の表示/フォントサイズ
        legend = getattr(plot_item, "legend", None)
        if legend is not None:
            legend.setVisible(show_legend)
            if hasattr(legend, "setLabelTextSize"):
                legend.setLabelTextSize(f"{legend_font_size}pt")


def _apply_style_to_data_item(item, symbol_size: int, line_width: float) -> None:
    """1つのPlotDataItemへシンボルサイズ・線幅を適用する。"""
    if item.opts.get("symbol") is not None:
        item.setSymbolSize(symbol_size)
    pen = item.opts.get("pen")
    if pen is not None:
        new_pen = pg.mkPen(pen)
        new_pen.setWidthF(line_width)
        item.setPen(new_pen)


def set_iv_axis_labels(plot_widget: pg.PlotWidget) -> None:
    """電圧-電流プロットの軸ラベルを設定する共通ヘルパー(review.md指摘#1)。

    JVLタブで先行して使われていた流儀(下軸=Voltage[V]、左軸=Current[A])を
    OPV/2ch活用モードの各プロットにも揃える。
    """
    plot_widget.setLabel("bottom", "Voltage", units="V")
    plot_widget.setLabel("left", "Current", units="A")


def _clear_luminance_curves(plot_widget: pg.PlotWidget) -> None:
    """輝度用ViewBox(``luminance_viewbox``)内の旧PlotDataItemを全て除去する。

    review.md指摘#2: ``plot_widget.clear()`` はメインのPlotItem内のみを
    クリアし、``setup_luminance_axis()`` で右軸に重ねたViewBox内のカーブは
    消えない。そのため新規測定開始時(PlotBuffer/DualAxisPlotBuffer生成時)に
    ここで明示的に取り除き、前回の輝度カーブが残置される不具合を防ぐ。
    """
    luminance_viewbox = getattr(plot_widget, "luminance_viewbox", None)
    if luminance_viewbox is None:
        return
    for item in list(luminance_viewbox.addedItems):
        if isinstance(item, pg.PlotDataItem):
            luminance_viewbox.removeItem(item)


def _reset_legend(plot_widget: pg.PlotWidget) -> pg.LegendItem:
    """凡例(LegendItem)を用意し、既存エントリをクリアして返す(review.md指摘#6)。

    pyqtgraphは ``plot_widget.clear()`` を呼んでも凡例エントリ自体は
    残ることがあるため、新規バッファ生成のたびにここで明示的にクリアしてから
    登録し直す(プロットごとにLegendItemは1個を維持する)。
    """
    plot_item = plot_widget.getPlotItem()
    legend = getattr(plot_item, "legend", None)
    if legend is None:
        legend = plot_item.addLegend()
    elif hasattr(legend, "clear"):
        legend.clear()
    else:
        # 古いpyqtgraphにclear()が無い場合のフォールバック
        for _sample, label in list(getattr(legend, "items", [])):
            legend.removeItem(label.text)
    legend_font_size = int(
        _GRAPH_STYLE.get("graph_legend_font_size", theme.GRAPH_STYLE_DEFAULTS["graph_legend_font_size"])
    )
    if hasattr(legend, "setLabelTextSize"):
        legend.setLabelTextSize(f"{legend_font_size}pt")
    legend.setVisible(bool(_GRAPH_STYLE.get("graph_show_legend", True)))
    return legend


class PlotBuffer:
    """単一カーブ(電圧-電流等)を持つプロットの点群バッファ。

    review.md指摘#1: 従来は ``pen=None`` により散布図(点のみ)だったが、
    折れ線+シンボルで表示する。呼び出し側が明示的に ``pen`` を渡した場合は
    それを尊重し、``pen=None``(未指定)の場合のみ既定の実線を適用する。

    review.md指摘#6: ``curve_name`` を指定した場合のみ凡例へ登録する
    (JVLタブのみ使用。他タブは名前なし=凡例なしで従来通り)。
    """

    def __init__(self, plot_widget: pg.PlotWidget, pen=None, curve_name: Optional[str] = None) -> None:
        plot_widget.clear()
        _clear_luminance_curves(plot_widget)
        self.plot_widget = plot_widget
        self.x: List[float] = []
        self.y: List[float] = []
        if pen is None:
            pen = pg.mkPen(_DEFAULT_LINE_COLOR, width=float(_GRAPH_STYLE["graph_line_width"]))
        plot_kwargs = {}
        if curve_name is not None:
            _reset_legend(plot_widget)
            plot_kwargs["name"] = curve_name
        self.curve = plot_widget.plot(
            [], [], pen=pen, symbol="o", symbolSize=int(_GRAPH_STYLE["graph_symbol_size"]), **plot_kwargs
        )
        # review.md指摘#2: 新規測定開始時は、前回のズーム状態に関わらず
        # xy両軸ともauto rangeへ戻す(輝度用ViewBoxがあれば同様)。
        plot_widget.getPlotItem().enableAutoRange()
        luminance_viewbox = getattr(plot_widget, "luminance_viewbox", None)
        if luminance_viewbox is not None:
            luminance_viewbox.enableAutoRange(x=True, y=True)

    def add_point(self, x: float, y: float) -> None:
        self.x.append(x)
        self.y.append(y)
        self.curve.setData(self.x, self.y)


class DualAxisPlotBuffer:
    """左軸(電流)・右軸(輝度)を同時更新するプロットバッファ(JVLのI-V-Lページ用)。

    review.md指摘#6: ``current_name``/``luminance_name`` を指定した場合のみ
    凡例へ登録する。輝度カーブは別ViewBox(``luminance_viewbox``)に直接
    addItemしており ``plot_widget.plot(name=...)`` を通らないため、
    LegendItemへは手動で ``addItem()`` する。
    """

    def __init__(
        self,
        plot_widget: pg.PlotWidget,
        current_name: Optional[str] = None,
        luminance_name: Optional[str] = None,
    ) -> None:
        plot_widget.clear()
        _clear_luminance_curves(plot_widget)
        self.plot_widget = plot_widget
        self.x: List[float] = []
        self.y_current: List[float] = []
        self.x_luminance: List[float] = []
        self.y_luminance: List[float] = []
        line_width = float(_GRAPH_STYLE["graph_line_width"])

        legend = None
        if current_name is not None or luminance_name is not None:
            legend = _reset_legend(plot_widget)

        plot_kwargs = {}
        if current_name is not None:
            plot_kwargs["name"] = current_name
        self.current_curve = plot_widget.plot(
            [],
            [],
            pen=pg.mkPen(_DEFAULT_LINE_COLOR, width=line_width),
            symbol="o",
            symbolSize=int(_GRAPH_STYLE["graph_symbol_size"]),
            **plot_kwargs,
        )
        self.luminance_curve = pg.PlotDataItem(
            [], [], pen=pg.mkPen(_LUMINANCE_LINE_COLOR, width=line_width)
        )
        luminance_viewbox = getattr(plot_widget, "luminance_viewbox", None)
        if luminance_viewbox is not None:
            luminance_viewbox.addItem(self.luminance_curve)
        if legend is not None and luminance_name is not None:
            legend.addItem(self.luminance_curve, luminance_name)
        # review.md指摘#2: 新規測定開始時はxy両軸ともauto rangeへ戻す。
        plot_widget.getPlotItem().enableAutoRange()
        if luminance_viewbox is not None:
            luminance_viewbox.enableAutoRange(x=True, y=True)

    def add_point(self, x: float, current: float, luminance: Optional[float] = None) -> None:
        self.x.append(x)
        self.y_current.append(current)
        self.current_curve.setData(self.x, self.y_current)
        if luminance is not None:
            self.x_luminance.append(x)
            self.y_luminance.append(luminance)
            self.luminance_curve.setData(self.x_luminance, self.y_luminance)


def install_auto_range_menu(plot_widget: pg.PlotWidget) -> None:
    """ViewBoxの右クリックメニュー先頭に「両軸を自動スケーリング」を追加する。

    EQEプロジェクト(``EQE/src/views/plot_controller.py``)のパターンを踏襲し、
    トリガで ``plot_item.enableAutoRange()`` を実行する(x/y両軸を自動スケーリング状態に
    戻す)。輝度用ViewBox(``luminance_viewbox``)を持つプロットでは、そちらにも
    auto rangeを適用する。多重インストールを避けるため、既に追加済みなら何もしない。
    """
    plot_item = plot_widget.getPlotItem()
    view_box = plot_item.getViewBox()
    menu = getattr(view_box, "menu", None)
    if menu is None:
        return
    if getattr(view_box, "_auto_range_both_action", None) is not None:
        return

    def _auto_range_both() -> None:
        plot_item.enableAutoRange()
        luminance_viewbox = getattr(plot_widget, "luminance_viewbox", None)
        if luminance_viewbox is not None:
            luminance_viewbox.enableAutoRange(x=True, y=True)

    auto_both_action = QAction("両軸を自動スケーリング (Auto Range Both)", plot_widget)
    auto_both_action.triggered.connect(_auto_range_both)

    actions = menu.actions()
    if actions:
        menu.insertAction(actions[0], auto_both_action)
        menu.insertSeparator(actions[0])
    else:
        menu.addAction(auto_both_action)

    # 参照保持(GC防止)と多重インストール防止フラグを兼ねる。
    view_box._auto_range_both_action = auto_both_action


def setup_luminance_axis(plot_widget: pg.PlotWidget) -> None:
    """右軸に輝度用ViewBoxを重ねる(JVLのI-V-Lページ・2ch活用モード共通)。

    遅延インストール: 既に ``luminance_viewbox`` 属性を持つ場合は何もしない
    (冪等)。実際のデータプロットはViewModel/Worker側の役割であり、
    ここでは右軸ViewBoxの土台(表示制御)のみを用意する。

    位置同期(``resizeEvent`` での ``setGeometry`` 呼び出し)は呼び出し側の
    タブ(JVLTab/DualChannelTab)の責務のまま維持する。

    ライフサイクル管理: 生成したViewBoxはPlotWidgetの ``destroyed`` シグナルで
    右軸(AxisItem)・sigResized・シーンから確実に切り離す。AxisItem.linkedViewは
    weakrefでViewBoxを参照するため、切り離しを怠るとPlotWidget/ViewBoxの
    C++オブジェクトの破棄順序次第でAxisItemが破棄済みViewBoxを参照し、
    後続の描画イベント(boundingRect等)で
    「wrapped C/C++ object of type ViewBox has been deleted」クラッシュが起こる。
    """
    if getattr(plot_widget, "luminance_viewbox", None) is not None:
        return

    luminance_viewbox = pg.ViewBox()
    plot_widget.scene().addItem(luminance_viewbox)
    right_axis = plot_widget.getAxis("right")
    right_axis.linkToView(luminance_viewbox)
    luminance_viewbox.setXLink(plot_widget)
    plot_widget.showAxis("right")
    right_axis.setLabel("Luminance", units="cd/m2")
    plot_widget.luminance_viewbox = luminance_viewbox

    main_viewbox = plot_widget.getViewBox()

    def _sync_luminance_viewbox() -> None:
        luminance_viewbox.setGeometry(main_viewbox.sceneBoundingRect())

    _sync_luminance_viewbox()
    main_viewbox.sigResized.connect(_sync_luminance_viewbox)

    def _cleanup_luminance_viewbox() -> None:
        """PlotWidget破棄時にViewBoxを右軸・シーン・シグナルから切り離す。

        QObjectの ``destroyed`` はデストラクタで子オブジェクト削除より前に
        emitされるため、この時点ではシーン・AxisItem・ViewBoxのC++オブジェクトは
        まだ生きており、安全に切り離せる。各ステップは破棄順序の揺らぎに備えて
        個別にRuntimeError(破棄済みラッパー参照)を握りつぶす。
        """
        # 1) メインViewBoxからの位置同期シグナルを切断する
        try:
            main_viewbox.sigResized.disconnect(_sync_luminance_viewbox)
        except (RuntimeError, TypeError):
            pass
        # 2) X軸リンク(setXLink)を解除する
        try:
            luminance_viewbox.setXLink(None)
        except RuntimeError:
            pass
        # 3) 右軸(AxisItem)のweakref参照を解除する(本質的な対処。
        #    ViewBoxが先に破棄されてもAxisItemが参照しなくなる)。
        #    unlinkFromViewはpyqtgraph 0.12.2以降。無い場合(本番環境の
        #    古いpyqtgraph)は内部weakrefを直接クリアする。
        try:
            if hasattr(right_axis, "unlinkFromView"):
                right_axis.unlinkFromView()
            else:
                right_axis._linkedView = None
        except RuntimeError:
            pass
        # 4) シーンから除去し、以後の描画イベントの対象から外す
        try:
            viewbox_scene = luminance_viewbox.scene()
            if viewbox_scene is not None:
                viewbox_scene.removeItem(luminance_viewbox)
        except RuntimeError:
            pass

    plot_widget.destroyed.connect(_cleanup_luminance_viewbox)
