"""全タブ共通のレイアウトビルダー(View層)。

OPV/JVL/2ch活用モードA・Bの各タブは、これまでタブごとにレイアウト構築コードを
重複実装していたため、タブ間で微妙なレイアウト差(余白・分割比・ログ位置など)が
発生していた(review.md指摘#3)。本モジュールに測定設定・保存実行グループの
共通ビルダーと、「設定カラム(スクロール)」「表示パネル(進捗+グラフ)」の
共通骨格を集約し、全タブが同一コードでレイアウトを構築することで差異を構造的に
排除する。左右分割(設定カラム/ログ ←→ グラフ表示)はメインウィンドウ直下の
QSplitterが担う(review.md指摘#1)ため、各タブは``build_settings_column()``で
自身のレイアウトを構築し、``build_display_panel()``で表示パネルを、
ログウィジェットをそのままMainWindowへ渡す(``display_panel()``/``log_widget()``)。

タブ固有のウィジェットは ``build_measurement_group()`` の
``extra_rows`` で配置する。
"""
from __future__ import annotations

from typing import Callable, List, Optional

from qtcompat import Qt, QtWidgets, enum_value
from views.widgets.no_scroll_spinbox import NoScrollDoubleSpinBox, NoScrollSpinBox


# スピンボックスの最大幅。設定カラムを狭めるための上限だが、狭くしすぎると
# 桁数の多い値(例: 電圧掃引の -20.000)が見切れる。実測でスピンボックス自身が
# 必要とする幅は最大71pxのため、その直上の72pxを共通の上限とする。
_SPIN_MAX_WIDTH = 72


def labeled_fields(object_name: str, fields) -> QtWidgets.QGridLayout:
    """各入力欄の真上にラベルを配置し、狭い設定欄でも対応を明確にする。"""
    grid = QtWidgets.QGridLayout()
    grid.setObjectName(object_name)
    for column, (title, widget) in enumerate(fields):
        label = QtWidgets.QLabel(title)
        label.setWordWrap(True)
        label.setBuddy(widget)
        grid.addWidget(label, 0, column)
        grid.addWidget(widget, 1, column)
        grid.setColumnStretch(column, 1)
        widget.setAccessibleName(title)
    return grid


def filename_preview(prefix, sample_edit, filename_fn, mode_combo=None):
    label = QtWidgets.QLabel(objectName=f"{prefix}_filenamePreview")
    label.setWordWrap(True)
    label.setTextFormat(enum_value(Qt, "PlainText"))
    label.setTextInteractionFlags(enum_value(Qt, "TextSelectableByMouse"))
    def refresh(*_):
        filename = filename_fn(sample_edit.text().strip() or "sample")
        label.setText(f"保存名: {filename}")
        label.setToolTip(filename)
    sample_edit.textChanged.connect(refresh)
    if mode_combo is not None:
        mode_combo.currentTextChanged.connect(refresh)
    refresh()
    return label


def make_double_spin(
    object_name: str,
    minimum: float,
    maximum: float,
    decimals: int,
    step: float,
    value: float,
    suffix: str = "",
) -> QtWidgets.QDoubleSpinBox:
    """全タブ共通仕様(最大幅72px・ホイール無効)のDoubleSpinBoxを生成する。"""
    spin = NoScrollDoubleSpinBox(objectName=object_name)
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSingleStep(step)
    spin.setValue(value)
    if suffix:
        spin.setSuffix(suffix)
    spin.setMaximumWidth(_SPIN_MAX_WIDTH)
    return spin


def make_iteration_spin(object_name: str) -> QtWidgets.QSpinBox:
    """全タブ共通仕様の繰り返し回数SpinBoxを生成する。"""
    spin = NoScrollSpinBox(objectName=object_name)
    spin.setRange(1, 1000)
    spin.setValue(3)
    spin.setMaximumWidth(_SPIN_MAX_WIDTH)
    return spin


def _apply_form_wrap_policy(settings_groups: List[QtWidgets.QWidget]) -> None:
    """設定グループ内の全QFormLayoutに「長い行は折り返す」方針を適用する。

    設定カラムの必要横幅は、これまで「最も長いラベル + 最も広い入力欄」の
    合計(QFormLayoutの既定=DontWrapRows)で決まっていた。そのため、
    「遅延時間[s]/コンプライアンス電流[A]:」のような長いラベルを持つタブが
    カラム全体の幅を押し広げ、他タブでは余白として無駄になっていた。

    ``WrapLongRows`` にすると、幅が足りない行だけラベルを入力欄の上へ
    折り返すため、必要横幅が「max(ラベル, 入力欄)」まで下がる。幅に余裕が
    ある行はこれまで通り横並びのまま描画されるので、見た目はほぼ変わらない。
    """
    wrap_long_rows = enum_value(QtWidgets.QFormLayout, "WrapLongRows")
    for group in settings_groups:
        for form_layout in group.findChildren(QtWidgets.QFormLayout):
            form_layout.setRowWrapPolicy(wrap_long_rows)


def build_settings_column(
    container: QtWidgets.QWidget,
    prefix: str,
    settings_groups: List[QtWidgets.QWidget],
    footer: Optional[QtWidgets.QWidget] = None,
) -> QtWidgets.QScrollArea:
    """タブ(またはモードページ)自身のレイアウトとして「設定グループの縦積み
    スクロールエリア」を構築する(review.md指摘#1: 左右分割はメインウィンドウ
    直下へ移動したため、タブ側は設定カラムの中身だけを持てばよい)。

    Args:
        container: レイアウトを設置するタブ(またはモードページ)ウィジェット。
        prefix: objectName接頭辞(``opv``/``jvl``/``dual_a``/``dual_b``)。
        settings_groups: 上から積む設定グループ群。
        footer: スクロールせず常時表示する実行操作などのグループ。

    Returns:
        構築したQScrollArea。
    """
    _apply_form_wrap_policy(settings_groups)

    root_layout = QtWidgets.QVBoxLayout(container)
    root_layout.setObjectName(f"{prefix}_rootLayout")
    root_layout.setContentsMargins(4, 4, 4, 4)

    scroll_area = QtWidgets.QScrollArea(objectName=f"{prefix}_settingsScrollArea")
    scroll_area.setWidgetResizable(True)
    # 設定カラム幅は固定レンジで運用するため、横スクロールは常に無効化する
    # (前回修正で下部にうっすら現れていた不要な横スクロールバーの解消)。
    scroll_area.setHorizontalScrollBarPolicy(enum_value(Qt, "ScrollBarAlwaysOff"))
    # 縦スクロールバーは常時表示にする。タブによって設定項目の数が違うため、
    # 「必要なときだけ表示」だとスクロールバーの有無で設定欄の実効幅が
    # タブ切り替えのたびに約28px変動していた(OPV/JVLでは非表示、2ch活用モードでは
    # 表示)。常に同じ幅を確保することで、どのタブでも設定欄の横幅を揃える。
    scroll_area.setVerticalScrollBarPolicy(enum_value(Qt, "ScrollBarAlwaysOn"))
    scroll_area.setFrameShape(enum_value(QtWidgets.QFrame, "NoFrame"))

    settings_container = QtWidgets.QWidget(objectName=f"{prefix}_settingsContainer")
    settings_layout = QtWidgets.QVBoxLayout(settings_container)
    settings_layout.setObjectName(f"{prefix}_settingsLayout")
    for group in settings_groups:
        settings_layout.addWidget(group)
    settings_layout.addStretch()
    scroll_area.setWidget(settings_container)

    root_layout.addWidget(scroll_area, 1)
    if footer is not None:
        root_layout.addWidget(footer)
    return scroll_area


def build_display_panel(
    prefix: str,
    display_widget: QtWidgets.QWidget,
    progress_bar: Optional[QtWidgets.QProgressBar] = None,
) -> QtWidgets.QWidget:
    """「進捗バー(最上部)+表示ウィジェット(残り全部)」の表示パネルを構築する。

    MainWindow右カラムの``displayStack``(QStackedWidget)へ積まれる、タブ横断で
    共通の表示パネル(review.md指摘#1)。

    Args:
        prefix: objectName接頭辞(``opv``/``jvl``/``dual_a``/``dual_b``)。
        display_widget: 主表示ウィジェット(プロット等)。余剰スペースを全て使う。
        progress_bar: 最上部に置く進捗バー(省略可)。

    Returns:
        構築したQWidget。
    """
    display_panel = QtWidgets.QWidget(objectName=f"{prefix}_displayPanel")
    display_layout = QtWidgets.QVBoxLayout(display_panel)
    display_layout.setObjectName(f"{prefix}_displayLayout")
    display_layout.setContentsMargins(4, 4, 4, 4)
    if progress_bar is not None:
        display_layout.addWidget(progress_bar, 0)
    # review.md指摘#1: グラフ(表示ウィジェット)が縦横の余剰スペースを使い切る。
    display_layout.addWidget(display_widget, 1)
    return display_panel


def build_measurement_group(
    prefix: str,
    v_min_default: float,
    v_max_default: float,
    v_step_default: float,
    sweep_single_step: float,
    extra_rows: Optional[Callable[[QtWidgets.QFormLayout], None]] = None,
):
    """OPV/JVL共通の「測定設定」グループ(掃引・繰り返し・NPLC・遅延・コンプライアンス)を構築する。

    Args:
        prefix: objectName接頭辞(``opv``/``jvl``)。
        v_min_default/v_max_default/v_step_default: 電圧掃引の初期値。
        sweep_single_step: 開始/終了スピンボックスのステップ量。
        extra_rows: タブ固有の行をフォームレイアウト末尾へ差し込むフック。

    Returns:
        (QGroupBox, ウィジェット辞書) のタプル。辞書キー:
        ``v_min``/``v_max``/``v_step``/``iteration``/``nplc``/``delay``/``compliance``/
        ``hysteresis``。
    """
    group_box = QtWidgets.QGroupBox("測定設定", objectName=f"{prefix}_measurementGroupBox")
    form_layout = QtWidgets.QFormLayout(group_box)
    form_layout.setObjectName(f"{prefix}_measurementFormLayout")

    # 電圧掃引(Vmin/Vmax/Vstepを1行)
    v_min_spin = make_double_spin(
        f"{prefix}_vMinSpin", -20.0, 20.0, 3, sweep_single_step, v_min_default
    )
    v_max_spin = make_double_spin(
        f"{prefix}_vMaxSpin", -20.0, 20.0, 3, sweep_single_step, v_max_default
    )
    v_step_spin = make_double_spin(f"{prefix}_vStepSpin", 0.001, 10.0, 3, 0.01, v_step_default)

    form_layout.addRow(labeled_fields(f"{prefix}_sweepRow", [
        ("開始 [V]", v_min_spin), ("終了 [V]", v_max_spin), ("ステップ [V]", v_step_spin),
    ]))

    # 測定回数・NPLC・遅延・電流上限
    iteration_spin = make_iteration_spin(f"{prefix}_iterationSpin")
    nplc_spin = make_double_spin(f"{prefix}_nplcSpin", 0.01, 10.0, 2, 0.1, 1.0)
    delay_spin = make_double_spin(f"{prefix}_delaySpin", 0.0, 60.0, 2, 0.1, 1.0)
    compliance_spin = make_double_spin(f"{prefix}_complianceSpin", 0.0001, 1.0, 4, 0.001, 0.02)
    timing_fields = [
        ("各電圧の回数", iteration_spin), ("NPLC", nplc_spin),
        ("遅延 [s]", delay_spin), ("電流上限 [A]", compliance_spin),
    ]
    form_layout.addRow(labeled_fields(f"{prefix}_timingRow", timing_fields))

    # ヒステリシス測定(往復掃引)チェックボックス
    hysteresis_checkbox = QtWidgets.QCheckBox(
        "ヒステリシス測定(往復掃引)", objectName=f"{prefix}_hysteresisCheckBox"
    )
    form_layout.addRow(hysteresis_checkbox)

    # タブ固有の追加行
    if extra_rows is not None:
        extra_rows(form_layout)

    widgets = {
        "v_min": v_min_spin,
        "v_max": v_max_spin,
        "v_step": v_step_spin,
        "iteration": iteration_spin,
        "nplc": nplc_spin,
        "delay": delay_spin,
        "compliance": compliance_spin,
        "hysteresis": hysteresis_checkbox,
    }
    return group_box, widgets


def build_save_run_group(
    prefix: str,
    external_sample_name_edit: Optional[QtWidgets.QLineEdit],
    external_save_dir_edit: Optional[QtWidgets.QLineEdit],
    on_browse: Callable[[], None],
):
    """OPV/JVL共通の「保存・実行」グループ(サンプル名/保存先/開始/中断)を構築する。

    共通保存設定パネル(MainWindow側)のウィジェットが渡された場合は
    それをそのまま参照し、タブ内には重複表示しない(従来仕様の維持)。

    Returns:
        (QGroupBox, ウィジェット辞書) のタプル。辞書キー:
        ``sample_name``/``save_dir``/``start``/``stop``/``browse``(browseはNoneの場合あり)。
    """
    group_box = QtWidgets.QGroupBox("保存・実行", objectName=f"{prefix}_saveRunGroupBox")
    save_run_layout = QtWidgets.QVBoxLayout(group_box)
    save_run_layout.setObjectName(f"{prefix}_saveRunLayout")

    save_form_layout = QtWidgets.QFormLayout()
    save_form_layout.setObjectName(f"{prefix}_saveFormLayout")

    browse_button = None
    if external_sample_name_edit is not None:
        sample_name_edit = external_sample_name_edit
    else:
        sample_name_edit = QtWidgets.QLineEdit(objectName=f"{prefix}_sampleNameEdit")
        save_form_layout.addRow("サンプル名:", sample_name_edit)

    if external_save_dir_edit is not None:
        save_dir_edit = external_save_dir_edit
    else:
        save_dir_edit = QtWidgets.QLineEdit(objectName=f"{prefix}_saveDirEdit")
        browse_button = QtWidgets.QPushButton("参照...", objectName=f"{prefix}_browseSaveDirButton")
        browse_button.clicked.connect(on_browse)

        save_dir_row = QtWidgets.QHBoxLayout()
        save_dir_row.setObjectName(f"{prefix}_saveDirRow")
        save_dir_row.addWidget(save_dir_edit)
        save_dir_row.addWidget(browse_button)
        save_form_layout.addRow("保存先:", save_dir_row)

    save_run_layout.addLayout(save_form_layout)
    from models.measurement.csv_writer import jvl_csv_filename, opv_csv_filename
    save_run_layout.addWidget(filename_preview(
        prefix, sample_name_edit, opv_csv_filename if prefix == "opv" else jvl_csv_filename
    ))

    # ショートカット(F5/Esc)をボタンのラベルに明記する(review.md項目4)。
    # QSSの `text*="開始"`/`text*="中断"` セレクタは部分一致のため配色は維持される。
    start_button = QtWidgets.QPushButton("測定開始 (F5)", objectName=f"{prefix}_startButton")
    stop_button = QtWidgets.QPushButton("中断 (Esc)", objectName=f"{prefix}_stopButton")
    stop_button.setEnabled(False)

    run_row = QtWidgets.QHBoxLayout()
    run_row.setObjectName(f"{prefix}_runRow")
    run_row.addWidget(start_button)
    run_row.addWidget(stop_button)
    save_run_layout.addLayout(run_row)

    widgets = {
        "sample_name": sample_name_edit,
        "save_dir": save_dir_edit,
        "start": start_button,
        "stop": stop_button,
        "browse": browse_button,
    }
    return group_box, widgets
