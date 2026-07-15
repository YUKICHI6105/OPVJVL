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
        QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **kw: (path2, "")
    )
    dialog._on_add_file_clicked()

    assert len(dialog._series) == 2
    assert "2件" in dialog.windowTitle()
    color1 = dialog._series[0]["current_curve"].opts["pen"].color().name()
    color2 = dialog._series[1]["current_curve"].opts["pen"].color().name()
    assert color1 != color2

    legend = dialog.plot_widget.getPlotItem().legend
    labels = {item[1].text for item in legend.items}
    assert "Current" in labels
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
        QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **kw: (path2, "")
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
