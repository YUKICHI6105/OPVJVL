"""全タブ共通のレイアウトビルダー(View層)。

OPV/JVL/2ch活用モードA・Bの各タブは、これまでタブごとにレイアウト構築コードを
重複実装していたため、タブ間で微妙なレイアウト差(余白・分割比・ログ位置など)が
発生していた(review.md指摘#3)。本モジュールに「左=設定カラム+ログ / 右=グラフ」
という共通骨格と、測定設定・保存実行グループの共通ビルダーを集約し、
全タブが同一コードでレイアウトを構築することで差異を構造的に排除する。

タブ固有のウィジェット(例: JVLの輝度計チェックボックス)は
``build_measurement_group()`` の ``extra_rows`` フックで差し込む。
"""
from __future__ import annotations

from typing import Callable, List, Optional

from qtcompat import Qt, QtWidgets, enum_value
from views import theme
from views.widgets.no_scroll_spinbox import NoScrollDoubleSpinBox, NoScrollSpinBox


def make_double_spin(
    object_name: str,
    minimum: float,
    maximum: float,
    decimals: int,
    step: float,
    value: float,
    suffix: str = "",
) -> QtWidgets.QDoubleSpinBox:
    """全タブ共通仕様(最大幅80px・ホイール無効)のDoubleSpinBoxを生成する。"""
    spin = NoScrollDoubleSpinBox(objectName=object_name)
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSingleStep(step)
    spin.setValue(value)
    if suffix:
        spin.setSuffix(suffix)
    spin.setMaximumWidth(80)
    return spin


def make_iteration_spin(object_name: str) -> QtWidgets.QSpinBox:
    """全タブ共通仕様の繰り返し回数SpinBoxを生成する。"""
    spin = NoScrollSpinBox(objectName=object_name)
    spin.setRange(1, 1000)
    spin.setValue(3)
    spin.setMaximumWidth(80)
    return spin


def build_split_tab(
    container: QtWidgets.QWidget,
    prefix: str,
    settings_groups: List[QtWidgets.QWidget],
    display_widget: QtWidgets.QWidget,
    log_text_edit: QtWidgets.QTextEdit,
    progress_bar: Optional[QtWidgets.QProgressBar] = None,
) -> QtWidgets.QSplitter:
    """「左=設定カラム(スクロール)+ログ / 右=進捗+表示」の共通2カラム分割を構築する。

    Args:
        container: レイアウトを設置するタブ(またはモードページ)ウィジェット。
        prefix: objectName接頭辞(``opv``/``jvl``/``dual_a``/``dual_b``)。
        settings_groups: 左カラムに上から積む設定グループ群。
        display_widget: 右カラムの主表示ウィジェット(プロット等)。余剰スペースを全て使う。
        log_text_edit: 左カラム下部の「ログ」グループに収めるログ表示ウィジェット
            (review.md指摘#2: ログは左側へ移動)。
        progress_bar: 右カラム最上部に置く進捗バー(省略可)。

    Returns:
        構築したQSplitter。
    """
    root_layout = QtWidgets.QHBoxLayout(container)
    root_layout.setObjectName(f"{prefix}_rootLayout")
    root_layout.setContentsMargins(4, 4, 4, 4)

    splitter = QtWidgets.QSplitter(objectName=f"{prefix}_splitter")
    splitter.setOrientation(enum_value(Qt, "Horizontal"))
    splitter.setChildrenCollapsible(False)
    root_layout.addWidget(splitter)

    # ------------------------------------------------------------------
    # 左カラム: 設定スクロールエリア + ログ
    # ------------------------------------------------------------------
    settings_panel = QtWidgets.QWidget(objectName=f"{prefix}_settingsPanel")
    settings_panel_layout = QtWidgets.QVBoxLayout(settings_panel)
    settings_panel_layout.setObjectName(f"{prefix}_settingsPanelLayout")
    settings_panel_layout.setContentsMargins(0, 0, 0, 0)
    # 設定カラム幅は全タブ共通(theme.SETTINGS_PANEL_*)。
    settings_panel.setMinimumWidth(theme.SETTINGS_PANEL_MIN_WIDTH)
    settings_panel.setMaximumWidth(theme.SETTINGS_PANEL_MAX_WIDTH)

    scroll_area = QtWidgets.QScrollArea(objectName=f"{prefix}_settingsScrollArea")
    scroll_area.setWidgetResizable(True)
    # 設定カラム幅は固定レンジで運用するため、横スクロールは常に無効化する
    # (前回修正で下部にうっすら現れていた不要な横スクロールバーの解消)。
    scroll_area.setHorizontalScrollBarPolicy(enum_value(Qt, "ScrollBarAlwaysOff"))
    scroll_area.setFrameShape(enum_value(QtWidgets.QFrame, "NoFrame"))

    settings_container = QtWidgets.QWidget(objectName=f"{prefix}_settingsContainer")
    settings_layout = QtWidgets.QVBoxLayout(settings_container)
    settings_layout.setObjectName(f"{prefix}_settingsLayout")
    for group in settings_groups:
        settings_layout.addWidget(group)
    settings_layout.addStretch()
    scroll_area.setWidget(settings_container)

    log_group_box = QtWidgets.QGroupBox("ログ", objectName=f"{prefix}_logGroupBox")
    log_layout = QtWidgets.QVBoxLayout(log_group_box)
    log_layout.setObjectName(f"{prefix}_logLayout")
    log_text_edit.setReadOnly(True)
    log_layout.addWidget(log_text_edit)
    log_group_box.setMinimumHeight(120)

    settings_panel_layout.addWidget(scroll_area, 3)
    settings_panel_layout.addWidget(log_group_box, 1)

    # ------------------------------------------------------------------
    # 右カラム: 進捗バー + 表示ウィジェット(余剰スペースを全て使う)
    # ------------------------------------------------------------------
    display_panel = QtWidgets.QWidget(objectName=f"{prefix}_displayPanel")
    display_layout = QtWidgets.QVBoxLayout(display_panel)
    display_layout.setObjectName(f"{prefix}_displayLayout")
    display_layout.setContentsMargins(0, 0, 0, 0)
    if progress_bar is not None:
        display_layout.addWidget(progress_bar, 0)
    # review.md指摘#1: グラフ(表示ウィジェット)が縦横の余剰スペースを使い切る。
    display_layout.addWidget(display_widget, 1)

    splitter.addWidget(settings_panel)
    splitter.addWidget(display_panel)
    splitter.setSizes(theme.DISPLAY_PANEL_STRETCH_SIZES)
    # 設定カラムは伸縮時も横幅を保持し、表示パネル側にのみ余剰スペースを割り当てる。
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    return splitter


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
        extra_rows: タブ固有の行(例: JVLの輝度計チェックボックス)を
            フォームレイアウト末尾へ差し込むフック。

    Returns:
        (QGroupBox, ウィジェット辞書) のタプル。辞書キー:
        ``v_min``/``v_max``/``v_step``/``iteration``/``nplc``/``delay``/``compliance``。
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

    sweep_row = QtWidgets.QHBoxLayout()
    sweep_row.setObjectName(f"{prefix}_sweepRow")
    sweep_row.addWidget(QtWidgets.QLabel("開始:"))
    sweep_row.addWidget(v_min_spin)
    sweep_row.addWidget(QtWidgets.QLabel("終了:"))
    sweep_row.addWidget(v_max_spin)
    sweep_row.addWidget(QtWidgets.QLabel("ステップ:"))
    sweep_row.addWidget(v_step_spin)
    form_layout.addRow("電圧掃引 (V):", sweep_row)

    # 繰り返し回数 / NPLC(1行に統合)
    iteration_spin = make_iteration_spin(f"{prefix}_iterationSpin")
    nplc_spin = make_double_spin(f"{prefix}_nplcSpin", 0.01, 10.0, 2, 0.1, 1.0)

    iteration_nplc_row = QtWidgets.QHBoxLayout()
    iteration_nplc_row.setObjectName(f"{prefix}_iterationNplcRow")
    iteration_nplc_row.addWidget(QtWidgets.QLabel("繰り返し:"))
    iteration_nplc_row.addWidget(iteration_spin)
    iteration_nplc_row.addWidget(QtWidgets.QLabel("NPLC:"))
    iteration_nplc_row.addWidget(nplc_spin)
    form_layout.addRow(iteration_nplc_row)

    # 遅延 / コンプライアンス(1行に統合)
    delay_spin = make_double_spin(f"{prefix}_delaySpin", 0.0, 60.0, 2, 0.1, 1.0)
    compliance_spin = make_double_spin(f"{prefix}_complianceSpin", 0.0001, 1.0, 4, 0.001, 0.02)

    delay_compliance_row = QtWidgets.QHBoxLayout()
    delay_compliance_row.setObjectName(f"{prefix}_delayComplianceRow")
    delay_compliance_row.addWidget(QtWidgets.QLabel("遅延[s]:"))
    delay_compliance_row.addWidget(delay_spin)
    delay_compliance_row.addWidget(QtWidgets.QLabel("コンプライアンス[A]:"))
    delay_compliance_row.addWidget(compliance_spin)
    form_layout.addRow(delay_compliance_row)

    # タブ固有の行の差し込み口(JVLの輝度計チェックボックス等)
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

    start_button = QtWidgets.QPushButton("測定開始", objectName=f"{prefix}_startButton")
    stop_button = QtWidgets.QPushButton("中断", objectName=f"{prefix}_stopButton")
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
