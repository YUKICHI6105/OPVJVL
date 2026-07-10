"""OPVJVL アプリケーションのスタイルシートテーマ。

EQEプロジェクトの `dark_qss` を移植したコンパクトな余白設計のダークテーマ。
"""
from __future__ import annotations

STYLE_SHEET = """
/* === ダークテーマ QSS === */
QWidget {
    background-color: #1e1e1e;
    color: #cfcfcf;
    font-family: "Segoe UI", "Meiryo UI", sans-serif;
    font-size: 11px;
}

QMainWindow, QDialog {
    background-color: #1e1e1e;
}

QScrollArea {
    border: none;
    background-color: #1e1e1e;
}

QScrollArea > QWidget > QWidget {
    background-color: #1e1e1e;
}

/* グループボックス（枠線）のスタイル */
QGroupBox {
    border: 1px solid #ffffff; /* 1pxの白枠 */
    border-radius: 5px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
    color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
}

/* テキスト入力、スピンボックス、コンボボックス */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #252526;
    border: 1px solid #3e3e42;
    border-radius: 3px;
    padding: 3px 5px;
    color: #ffffff;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #007acc;
    background-color: #2d2d30;
}

QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
    border-color: #555559;
}

/* ボタンのスタイル */
QPushButton {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    border-radius: 3px;
    padding: 3px 10px;
    color: #ffffff;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #3e3e42;
    border-color: #555559;
}

QPushButton:pressed {
    background-color: #1e1e1e;
    border-color: #007acc;
}

QPushButton:disabled {
    background-color: #181818;
    color: #666666;
    border-color: #2d2d2d;
}

/* 測定開始ボタンを目立たせる (青アクセント) */
QPushButton[text*="開始"]:enabled, QPushButton[text*="Start"]:enabled, QPushButton[text*="計算"]:enabled, QPushButton[text*="Calculate"]:enabled {
    background-color: #007acc;
    border-color: #008be5;
    color: #ffffff;
}

QPushButton[text*="開始"]:hover, QPushButton[text*="Start"]:hover, QPushButton[text*="計算"]:hover, QPushButton[text*="Calculate"]:hover {
    background-color: #008be5;
}

QPushButton[text*="開始"]:pressed, QPushButton[text*="Start"]:pressed, QPushButton[text*="計算"]:pressed, QPushButton[text*="Calculate"]:pressed {
    background-color: #005a9e;
}

/* 中断ボタンを目立たせる (赤アクセント) */
QPushButton[text*="中断"]:enabled, QPushButton[text*="Stop"]:enabled {
    background-color: #a1260d;
    border-color: #c72e10;
    color: #ffffff;
}

QPushButton[text*="中断"]:hover, QPushButton[text*="Stop"]:hover {
    background-color: #c72e10;
}

QPushButton[text*="中断"]:pressed, QPushButton[text*="Stop"]:pressed {
    background-color: #7a1c09;
}

/* チェックボックス */
QCheckBox {
    spacing: 5px;
}

QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #3e3e42;
    border-radius: 2px;
    background-color: #252526;
}

QCheckBox::indicator:hover {
    border-color: #007acc;
}

QCheckBox::indicator:checked {
    background-color: #007acc;
    border-color: #007acc;
    image: url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAd0lEQVRIie2TsQmAMBQFX3AIS4dxcAexTCycQeVsPggSJRrTSK76zbuDQKRK5QnAUFIegAWglHzFqPI8OdCXlHeAB/znchuPtttiEWDKfnMOViDkyt1VxM5N0mx3K6mRJOdcdJcciET0Rn4bOEX0Rp5EkU9U+Rc7D3HSuynbfOoAAAAASUVORK5CYII=");
}

/* メニューバー & メニュー */
QMenuBar {
    background-color: #1e1e1e;
    border-bottom: 1px solid #2d2d2d;
}

QMenuBar::item {
    background-color: transparent;
    padding: 5px 10px;
}

QMenuBar::item:selected {
    background-color: #2d2d30;
}

QMenu {
    background-color: #1e1e1e;
    border: 1px solid #2d2d2d;
    padding: 2px 0px;
}

QMenu::item {
    padding: 5px 20px 5px 18px;
}

QMenu::item:selected {
    background-color: #007acc;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #2d2d2d;
    margin: 4px 0px;
}

/* スプリッター（左右境界線） */
QSplitter::handle {
    background-color: #2d2d2d;
}

/* スクロールバー */
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #3e3e42;
    min-height: 20px;
    border-radius: 5px;
    border: 2px solid #1e1e1e;
}

QScrollBar::handle:vertical:hover {
    background-color: #4e4e52;
}

QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {
    height: 0px;
}

QLabel {
    background-color: transparent;
}

QLabel#sectionLabel {
    color: #4fc1ff;
    font-weight: 700;
    letter-spacing: 2px;
}

QProgressBar {
    border: none;
    border-radius: 2px;
    background-color: #252526;
    height: 4px;
}

QProgressBar::chunk {
    background-color: #007acc;
    border-radius: 2px;
}

QPlainTextEdit {
    background-color: #0b0e12;
    border: 1px solid #3e3e42;
    border-radius: 3px;
    color: #cfcfcf;
    font-family: Consolas, "Courier New", monospace;
    font-size: 11px;
}
"""
