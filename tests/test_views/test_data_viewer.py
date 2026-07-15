"""views/data_viewer.py のテスト(review.md項目5: ファイル > データを開く)。

``parse_measurement_csv`` はQt非依存の純ロジックなので通常のpytest関数で検証し、
``DataViewerDialog`` はQtウィジェットのためqtbotフィクスチャで構築・検証する。
"""
from __future__ import annotations

from views.data_viewer import DataViewerDialog, parse_measurement_csv


def _write_csv(tmp_path, name, lines):
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


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


def test_data_viewer_dialog_builds_curves_and_legend(tmp_path, qtbot):
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
    dialog = DataViewerDialog(path)
    qtbot.addWidget(dialog)

    assert "for_dialog.csv" in dialog.windowTitle()
    assert dialog.current_curve is not None
    assert dialog.luminance_curve is not None
    legend = dialog.plot_widget.getPlotItem().legend
    assert legend is not None


def test_data_viewer_dialog_without_luminance(tmp_path, qtbot):
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
    dialog = DataViewerDialog(path)
    qtbot.addWidget(dialog)

    assert dialog.current_curve is not None
    assert dialog.luminance_curve is None
