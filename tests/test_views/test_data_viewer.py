"""views/data_viewer.py のテスト(review.md項目5: ファイル > データを開く、
項目1: 後からファイルを追加して比較)。

``parse_measurement_csv`` はQt非依存の純ロジックなので通常のpytest関数で検証し、
``DataViewerDialog`` はQtウィジェットのためqtbotフィクスチャで構築・検証する。
"""
from __future__ import annotations

import pytest

from qtcompat import QtWidgets
from views import plot_buffer
from views.data_viewer import DataViewerDialog, parse_measurement_csv


def _write_csv(tmp_path, name, lines):
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


@pytest.fixture
def make_dialog(qtbot):
    """DataViewerDialogを生成し、終了時に輝度軸を明示的にクリーンアップする。

    輝度列を持つCSVを開くと ``setup_luminance_axis`` がXLink済みViewBoxを
    生成するため、破棄タイミングをGC任せにせず、テスト終了時に
    ``cleanup_luminance_axis`` → ``deleteLater`` → イベント処理で確実に切り離す。
    """
    dialogs = []

    def _make(path):
        dialog = DataViewerDialog(path)
        qtbot.addWidget(dialog)
        dialogs.append(dialog)
        return dialog

    yield _make

    app = QtWidgets.QApplication.instance()
    for dialog in dialogs:
        plot_buffer.cleanup_luminance_axis(dialog.plot_widget)
        dialog.deleteLater()
    for _ in range(3):
        app.processEvents()


def test_parse_measurement_csv_three_columns(tmp_path):
    """ヘッダ+電圧/電流/輝度3列の正常系。"""
    path = _write_csv(
        tmp_path,
        "three_col.csv",
        [
            "voltage [V],current [A],luminance [cd/m2]",
            "0.0,0.001,10.5",
            "0.1,0.002,20.0",
            "0.2,0.003,30.0",
        ],
    )
    voltages, currents, luminances = parse_measurement_csv(path)
    assert voltages == [0.0, 0.1, 0.2]
    assert currents == [0.001, 0.002, 0.003]
    assert luminances == [10.5, 20.0, 30.0]


def test_parse_measurement_csv_two_columns(tmp_path):
    """ヘッダ+電圧/電流2列(暗IV等、輝度列なし)の正常系。"""
    path = _write_csv(
        tmp_path,
        "two_col.csv",
        [
            "voltage [V],current [A]",
            "-0.1,0.0001",
            "0.0,0.0",
            "0.1,-0.0002",
        ],
    )
    voltages, currents, luminances = parse_measurement_csv(path)
    assert voltages == [-0.1, 0.0, 0.1]
    assert currents == [0.0001, 0.0, -0.0002]
    assert luminances == [None, None, None]


def test_parse_measurement_csv_tolerates_different_header(tmp_path):
    """ヘッダ名が厳密一致しなくても、数値行として1/2/3列目を解釈する。"""
    path = _write_csv(
        tmp_path,
        "different_header.csv",
        [
            "V,I,L",
            "0.0,1e-3,5.0",
            "0.5,2e-3,6.0",
        ],
    )
    voltages, currents, luminances = parse_measurement_csv(path)
    assert voltages == [0.0, 0.5]
    assert currents == [0.001, 0.002]
    assert luminances == [5.0, 6.0]


def test_parse_measurement_csv_skips_invalid_rows(tmp_path):
    """パース不能な行(空セル・文字列混入等)はスキップされる。"""
    path = _write_csv(
        tmp_path,
        "invalid_rows.csv",
        [
            "voltage [V],current [A],luminance [cd/m2]",
            "0.0,0.001,10.0",
            "",  # 空行
            "not_a_number,0.002,20.0",  # 電圧がパース不能
            "0.2,,30.0",  # 電流が空
            "0.3,0.004,",  # 輝度が空セル(電圧/電流は有効なので残る)
        ],
    )
    voltages, currents, luminances = parse_measurement_csv(path)
    assert voltages == [0.0, 0.3]
    assert currents == [0.001, 0.004]
    assert luminances == [10.0, None]


def test_parse_measurement_csv_empty_file(tmp_path):
    """空ファイルは空のリストを返す(例外を出さない)。"""
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    voltages, currents, luminances = parse_measurement_csv(str(path))
    assert voltages == []
    assert currents == []
    assert luminances == []


def test_data_viewer_dialog_builds_curves_and_legend(tmp_path, make_dialog):
    """3列CSVからDataViewerDialogを生成すると、電流・輝度2本のカーブと凡例が構築される。"""
    path = _write_csv(
        tmp_path,
        "for_dialog.csv",
        [
            "voltage [V],current [A],luminance [cd/m2]",
            "0.0,0.001,10.0",
            "0.1,0.002,20.0",
        ],
    )
    dialog = make_dialog(path)

    assert "for_dialog.csv" in dialog.windowTitle()
    assert dialog.current_curve is not None
    assert dialog.luminance_curve is not None
    legend = dialog.plot_widget.getPlotItem().legend
    assert legend is not None


def test_data_viewer_dialog_without_luminance(tmp_path, make_dialog):
    """2列CSVでは輝度カーブが生成されない。"""
    path = _write_csv(
        tmp_path,
        "no_luminance.csv",
        [
            "voltage [V],current [A]",
            "0.0,0.001",
            "0.1,0.002",
        ],
    )
    dialog = make_dialog(path)

    assert dialog.current_curve is not None
    assert dialog.luminance_curve is None


# ----------------------------------------------------------------------
# review.md項目1: ファイルを追加して比較
# ----------------------------------------------------------------------
def test_add_file_button_appends_second_curve_with_different_color(tmp_path, make_dialog, monkeypatch):
    """「ファイルを追加...」で2つ目のCSVを開くと、色違いのカーブが重ね描きされる。"""
    path1 = _write_csv(
        tmp_path, "first.csv",
        ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"],
    )
    path2 = _write_csv(
        tmp_path, "second.csv",
        ["voltage [V],current [A]", "0.0,0.003", "0.1,0.004"],
    )

    dialog = make_dialog(path1)
    assert dialog.windowTitle() == "データビューア - first.csv"

    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **kw: ([path2], "")
    )
    dialog._on_add_file_clicked()

    assert len(dialog._series) == 2
    assert "2件" in dialog.windowTitle()
    color1 = dialog._series[0]["current_curve"].opts["pen"].color().name()
    color2 = dialog._series[1]["current_curve"].opts["pen"].color().name()
    assert color1 != color2

    legend = dialog.plot_widget.getPlotItem().legend
    labels = {item[1].text for item in legend.items}
    assert "first" in labels
    assert "second" in labels


def test_add_file_with_luminance_adds_right_axis_curve(tmp_path, make_dialog, monkeypatch):
    """輝度列を持つ追加ファイルは右軸へ輝度カーブを重ね描きし、凡例で区別される。"""
    path1 = _write_csv(
        tmp_path, "first.csv",
        ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"],
    )
    path2 = _write_csv(
        tmp_path, "with_lum.csv",
        [
            "voltage [V],current [A],luminance [cd/m2]",
            "0.0,0.001,5.0",
            "0.1,0.002,6.0",
        ],
    )

    dialog = make_dialog(path1)

    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **kw: ([path2], "")
    )
    dialog._on_add_file_clicked()

    assert dialog._series[1]["luminance_curve"] is not None
    legend = dialog.plot_widget.getPlotItem().legend
    labels = {item[1].text for item in legend.items}
    assert "with_lum (L)" in labels


def test_add_file_empty_parse_shows_error_and_does_not_add(tmp_path, make_dialog, monkeypatch):
    """0点パースの場合はエラーダイアログを出し、カーブを追加しない。"""
    path1 = _write_csv(
        tmp_path, "first.csv",
        ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"],
    )
    empty_path = tmp_path / "empty.csv"
    empty_path.write_text("", encoding="utf-8")

    dialog = make_dialog(path1)

    warn_calls = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning", lambda *a, **kw: warn_calls.append(a)
    )
    dialog._add_file(str(empty_path))

    assert len(warn_calls) == 1
    assert len(dialog._series) == 1
    assert dialog.windowTitle() == "データビューア - first.csv"


def test_legend_uses_filename_even_for_single_file(tmp_path, make_dialog):
    """1ファイルだけでも凡例はファイル名になる(複数ファイル時と表記を揃えるため)。"""
    path = _write_csv(
        tmp_path, "only_one.csv",
        [
            "voltage [V],current [A],luminance [cd/m2]",
            "0.0,0.001,5.0",
            "0.1,0.002,6.0",
        ],
    )
    dialog = make_dialog(path)

    legend = dialog.plot_widget.getPlotItem().legend
    labels = {item[1].text for item in legend.items}
    assert labels == {"only_one", "only_one (L)"}


# ----------------------------------------------------------------------
# 複数ファイルの同時選択
# ----------------------------------------------------------------------
def test_dialog_accepts_multiple_paths_at_construction(tmp_path, make_dialog):
    """コンストラクタに複数パスを渡すと、まとめて重ね描きされる。"""
    paths = [
        _write_csv(tmp_path, f"multi{i}.csv",
                   ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"])
        for i in range(3)
    ]

    dialog = make_dialog(paths)

    assert len(dialog._series) == 3
    assert "3件" in dialog.windowTitle()


def test_add_file_button_accepts_multiple_selection(tmp_path, make_dialog, monkeypatch):
    """「ファイルを追加...」でも複数選択したぶんをまとめて追加できる。"""
    path1 = _write_csv(
        tmp_path, "first.csv",
        ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"],
    )
    extra = [
        _write_csv(tmp_path, f"extra{i}.csv",
                   ["voltage [V],current [A]", "0.0,0.003", "0.1,0.004"])
        for i in range(2)
    ]

    dialog = make_dialog(path1)
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **kw: (extra, "")
    )
    dialog._on_add_file_clicked()

    assert len(dialog._series) == 3


def test_dialog_is_independent_window(tmp_path, make_dialog):
    """ビューアは親の手前に固定されない独立ウィンドウ(Qt.Window)である。"""
    from qtcompat import Qt, enum_value

    path = _write_csv(
        tmp_path, "one.csv",
        ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"],
    )
    dialog = make_dialog(path)

    window_flag = enum_value(Qt, "Window")
    dialog_flag = enum_value(Qt, "Dialog")
    flags = dialog.windowFlags()
    assert flags & window_flag
    # Qt.Dialog は Window ビットを含むため、Dialog型そのものでないことを確認する
    assert (flags & dialog_flag) != dialog_flag


# ----------------------------------------------------------------------
# 素子面積 → 電流密度(J-V)表示
# ----------------------------------------------------------------------
def test_current_density_conversion_pure_logic():
    """J[mA/cm2] = I[A] * 1000 / (面積[mm2] / 100)。"""
    from views.data_viewer import current_density_ma_per_cm2

    # 4mm2 = 0.04cm2 なので 1mA / 0.04cm2 = 25 mA/cm2
    assert current_density_ma_per_cm2(0.001, 4.0) == pytest.approx(25.0)
    # 100mm2 = 1cm2 なので係数は1000倍(A→mA)のみ
    assert current_density_ma_per_cm2(0.001, 100.0) == pytest.approx(1.0)
    # 面積0以下は換算不能として0.0
    assert current_density_ma_per_cm2(0.001, 0.0) == 0.0


def test_area_spin_defaults_to_4mm2(tmp_path, make_dialog):
    """素子面積の初期値は4mm2で、初期表示は電流[A]のまま。"""
    from views.data_viewer import DEFAULT_DEVICE_AREA_MM2

    path = _write_csv(
        tmp_path, "one.csv",
        ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"],
    )
    dialog = make_dialog(path)

    assert DEFAULT_DEVICE_AREA_MM2 == 4.0
    assert dialog.area_spin.value() == pytest.approx(4.0)
    assert not dialog.current_density_checkbox.isChecked()
    assert dialog.current_curve.getData()[1].tolist() == pytest.approx([0.001, 0.002])


def test_toggling_current_density_rescales_all_curves(tmp_path, make_dialog, monkeypatch):
    """J-V表示へ切り替えると、既に描画済みの全ファイルの縦軸値が電流密度になる。"""
    path1 = _write_csv(
        tmp_path, "first.csv",
        ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"],
    )
    path2 = _write_csv(
        tmp_path, "second.csv",
        ["voltage [V],current [A]", "0.0,0.004", "0.1,0.008"],
    )
    dialog = make_dialog([path1, path2])

    dialog.current_density_checkbox.setChecked(True)

    # 面積4mm2(=0.04cm2)なので係数は25000倍
    assert dialog._series[0]["current_curve"].getData()[1].tolist() == pytest.approx([25.0, 50.0])
    assert dialog._series[1]["current_curve"].getData()[1].tolist() == pytest.approx([100.0, 200.0])

    # 元に戻すと電流[A]へ復帰する(生データを保持しているため往復して劣化しない)
    dialog.current_density_checkbox.setChecked(False)
    assert dialog._series[0]["current_curve"].getData()[1].tolist() == pytest.approx([0.001, 0.002])


def test_changing_area_updates_current_density(tmp_path, make_dialog):
    """面積を変えると電流密度が再計算される。"""
    path = _write_csv(
        tmp_path, "one.csv",
        ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"],
    )
    dialog = make_dialog(path)
    dialog.current_density_checkbox.setChecked(True)
    dialog.area_spin.setValue(100.0)  # 1cm2

    assert dialog.current_curve.getData()[1].tolist() == pytest.approx([1.0, 2.0])


def test_file_added_while_in_density_mode_is_also_converted(tmp_path, make_dialog, monkeypatch):
    """J-V表示中に追加したファイルも電流密度で描画される。"""
    path1 = _write_csv(
        tmp_path, "first.csv",
        ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"],
    )
    path2 = _write_csv(
        tmp_path, "second.csv",
        ["voltage [V],current [A]", "0.0,0.004", "0.1,0.008"],
    )
    dialog = make_dialog(path1)
    dialog.current_density_checkbox.setChecked(True)

    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **kw: ([path2], "")
    )
    dialog._on_add_file_clicked()

    assert dialog._series[1]["current_curve"].getData()[1].tolist() == pytest.approx([100.0, 200.0])


def test_current_density_axis_label(tmp_path, make_dialog):
    """縦軸ラベルが表示設定に応じて切り替わる。"""
    path = _write_csv(
        tmp_path, "one.csv",
        ["voltage [V],current [A]", "0.0,0.001", "0.1,0.002"],
    )
    dialog = make_dialog(path)
    left_axis = dialog.plot_widget.getPlotItem().getAxis("left")

    assert "Current" in left_axis.labelText
    assert "density" not in left_axis.labelText

    dialog.current_density_checkbox.setChecked(True)
    assert "Current density" in left_axis.labelText
    assert "mA/cm2" in left_axis.labelText
    # units指定だとpyqtgraphがSI接頭辞を付けてしまうため、単位はラベル文字列側に持つ
    assert left_axis.labelUnits == ""
