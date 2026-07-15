"""ファイル > データを開く で使う、測定CSVの表示専用ビューア(View層)。

review.md項目5: 過去に保存した測定CSVを、アプリを再測定せずに単体で
読み込んでグラフ表示できるようにする。CSVの解析(``parse_measurement_csv``)は
Qt非依存の純Pythonロジックとして分離し、単体テスト可能にしてある
(``models/measurement/csv_writer.py``は書き出し専用のため、読み込み処理は
本モジュールに置く)。

表示部分(``DataViewerDialog``)は``views/plot_buffer.py``の共通ヘルパー
(``set_iv_axis_labels``/``setup_luminance_axis``/``install_auto_range_menu``/
``current_graph_style``)を流用し、既存タブのグラフと見た目を揃える。
非モーダル(``show()``で開く)にすることで、複数ファイルを同時に見比べられる
ようにする。

review.md項目1: 開いた後から「ファイルを追加...」ボタンで別の測定CSVを
同じプロットへ重ね描きし、比較できるようにする。ファイルごとに色を変え、
凡例はファイル名(拡張子なしのstem)で区別する。
"""
from __future__ import annotations

import csv
import os
from typing import List, Optional, Tuple

import pyqtgraph as pg

from qtcompat import QtWidgets
from views import plot_buffer

# views/plot_buffer.pyの配色(電流=青系/輝度=赤系)に合わせる。
_CURRENT_LINE_COLOR = "#1f77b4"
_LUMINANCE_LINE_COLOR = "#d62728"

# review.md項目1: 2ファイル目以降に割り当てるカテゴリカルな色サイクル
# (Matplotlib/Vega既定の"tab10"系配色に準拠。1ファイル目は現行色を維持するため
# 先頭の青は使わず、2ファイル目以降のみをこの並びから順に割り当てる)。
_FILE_COLOR_CYCLE = [
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#17becf",  # cyan
]


def parse_measurement_csv(
    path: str,
) -> Tuple[List[float], List[float], List[Optional[float]]]:
    """測定CSVを寛容にパースする(Qt非依存の純ロジック、単体テスト対象)。

    ヘッダ行の有無や列名の厳密一致(``"voltage [V]"``等)は要求しない。
    各行を「1列目=電圧, 2列目=電流, 3列目(あれば)=輝度」として解釈し、
    数値へ変換できない行(ヘッダ行・空行・破損した行)は黙ってスキップする。
    これにより、ヘッダ行は「1列目・2列目が数値変換できない行」として
    自然にスキップされる(明示的な行数指定に依存しない)。

    Args:
        path: 読み込むCSVファイルのパス。

    Returns:
        ``(voltages, currents, luminances)`` のタプル。3つとも同じ長さで、
        ``luminances`` はファイル中に輝度列を持つ行が1件も無ければ全要素が
        ``None``(2列CSV/暗IV等)。輝度列を持つ行が1件でもあれば、
        値の無い行(空セル・パース不能)は個別に``None``として保持する。
    """
    voltages: List[float] = []
    currents: List[float] = []
    luminances: List[Optional[float]] = []
    has_luminance = False

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                voltage = float(row[0])
                current = float(row[1])
            except (ValueError, IndexError):
                continue

            luminance: Optional[float] = None
            if len(row) >= 3 and row[2].strip():
                try:
                    luminance = float(row[2])
                    has_luminance = True
                except ValueError:
                    luminance = None

            voltages.append(voltage)
            currents.append(current)
            luminances.append(luminance)

    if not has_luminance:
        luminances = [None] * len(voltages)

    return voltages, currents, luminances


class DataViewerDialog(QtWidgets.QDialog):
    """測定CSVを読み込んでpyqtgraphで表示する非モーダルビューア(review.md項目5)。

    ``MainWindow``側が``show()``で開き、参照をリストに保持してGCを防ぐ
    (複数同時に開ける)。ウィンドウを閉じたら``MainWindow``側が参照を解放する。

    review.md項目1: 「ファイルを追加...」ボタンで開いた後から別ファイルを
    同じプロットへ重ね描きできる。``self._series``に読み込んだファイルごとの
    カーブ情報を保持し、色は``_FILE_COLOR_CYCLE``から順に割り当てる
    (1ファイル目は従来通り``_CURRENT_LINE_COLOR``/``_LUMINANCE_LINE_COLOR``)。
    """

    def __init__(self, path: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DataViewerDialog")
        self._series: List[dict] = []  # 各要素: {"path", "current_curve", "luminance_curve"}
        self._build_ui()
        self._add_file(path)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        button_row = QtWidgets.QHBoxLayout()
        button_row.setObjectName("dataViewer_buttonRow")
        self.add_file_button = QtWidgets.QPushButton(
            "ファイルを追加...", objectName="dataViewer_addFileButton"
        )
        self.add_file_button.clicked.connect(self._on_add_file_clicked)
        button_row.addWidget(self.add_file_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.plot_widget = pg.PlotWidget(objectName="dataViewer_plotWidget")
        layout.addWidget(self.plot_widget)

        plot_buffer.set_iv_axis_labels(self.plot_widget)
        plot_buffer.install_auto_range_menu(self.plot_widget)

        self.legend = self.plot_widget.getPlotItem().addLegend()

        self.resize(720, 520)

    # ------------------------------------------------------------------
    # ファイル追加(初回・以降とも共通の内部処理)
    # ------------------------------------------------------------------
    def _on_add_file_clicked(self) -> None:
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "測定CSVを追加", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return
        self._add_file(path)

    def _add_file(self, path: str) -> None:
        """1ファイル分のカーブを読み込み、既存プロットへ重ね描きする。

        パース結果が0点(空ファイル・全行パース不能)の場合はエラーダイアログを
        出し、カーブを追加しない(review.md項目1)。
        """
        voltages, currents, luminances = parse_measurement_csv(path)
        if not voltages:
            QtWidgets.QMessageBox.warning(
                self, "読み込みエラー",
                f"数値データを読み取れませんでした:\n{path}",
            )
            return

        index = len(self._series)
        stem = os.path.splitext(os.path.basename(path))[0]
        style = plot_buffer.current_graph_style()
        line_width = float(style.get("graph_line_width", 2.0))
        symbol_size = int(style.get("graph_symbol_size", 6))

        if index == 0:
            current_color = _CURRENT_LINE_COLOR
            luminance_color = _LUMINANCE_LINE_COLOR
            current_label = "Current"
            luminance_label = "Luminance"
        else:
            current_color = _FILE_COLOR_CYCLE[(index - 1) % len(_FILE_COLOR_CYCLE)]
            luminance_color = current_color
            current_label = stem
            luminance_label = f"{stem} (L)"

        current_pen = pg.mkPen(current_color, width=line_width)
        current_curve = self.plot_widget.plot(
            voltages,
            currents,
            pen=current_pen,
            symbol="o",
            symbolSize=symbol_size,
            name=current_label,
        )

        has_luminance = any(v is not None for v in luminances)
        luminance_curve = None
        if has_luminance:
            plot_buffer.setup_luminance_axis(self.plot_widget)
            lum_x = [v for v, lum in zip(voltages, luminances) if lum is not None]
            lum_y = [lum for lum in luminances if lum is not None]
            luminance_pen = pg.mkPen(luminance_color, width=line_width)
            luminance_curve = pg.PlotDataItem(
                lum_x, lum_y, pen=luminance_pen, symbol="o", symbolSize=symbol_size
            )
            self.plot_widget.luminance_viewbox.addItem(luminance_curve)
            self.legend.addItem(luminance_curve, luminance_label)

        self._series.append({
            "path": path,
            "current_curve": current_curve,
            "luminance_curve": luminance_curve,
        })

        # 1ファイル目の互換属性(既存テスト・呼び出し元との後方互換のため維持)。
        if index == 0:
            self.current_curve = current_curve
            self.luminance_curve = luminance_curve

        filename = os.path.basename(path)
        count = len(self._series)
        if count == 1:
            self.setWindowTitle(f"データビューア - {filename}")
        else:
            self.setWindowTitle(f"データビューア ({count}件)")

        # 現在のグラフ表示設定(目盛フォント・グリッド・凡例表示等)を反映する。
        plot_buffer.apply_graph_style([self.plot_widget], style)
