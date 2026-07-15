"""PyQt5 / PyQt6 の差異を吸収する薄い互換レイヤー。

アプリケーション内の全モジュールはPyQt5/PyQt6を直接importせず、
必ず `from opvjvl import qtcompat` あるいは
`from opvjvl.qtcompat import QtCore, QtGui, QtWidgets, ...` を使うこと。

このモジュールは他の全モジュールより先にimportされ、pyqtgraphが使用する
Qtバインディングを一致させるために PYQTGRAPH_QT_LIB 環境変数をここで確定させる。
"""
from __future__ import annotations

import enum
import os

# High DPIスケーリングに関する環境変数は、PyQt5/PyQt6のいずれのバインディングを
# importするよりも前に設定しておく必要がある(Qtがバインディングのimport時点で
# これらを読み取るため)。setdefaultなので、呼び出し側や外部環境が既に値を
# 設定している場合はそれを尊重する。
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

try:
    from PyQt6 import QtCore, QtGui, QtWidgets, uic
    from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
    from PyQt6.QtGui import QAction, QKeySequence, QShortcut
    from PyQt6.QtWidgets import QApplication

    QT_API = "PyQt6"
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets, uic
    from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
    from PyQt5.QtGui import QKeySequence
    from PyQt5.QtWidgets import QAction, QApplication, QShortcut

    QT_API = "PyQt5"

# pyqtgraphが起動時に検出するQtバインディングを、上で確定させたものと一致させる。
# これを怠ると、両方インストールされた環境でpyqtgraphが別バインディングを掴んで
# QApplicationの二重生成/クラッシュを引き起こす可能性がある。
os.environ.setdefault("PYQTGRAPH_QT_LIB", QT_API)

__all__ = [
    "QT_API",
    "QAction",
    "QApplication",
    "QKeySequence",
    "QObject",
    "QShortcut",
    "Qt",
    "QThread",
    "QTimer",
    "QtCore",
    "QtGui",
    "QtWidgets",
    "configure_high_dpi",
    "enum_value",
    "pyqtSignal",
    "pyqtSlot",
    "qt_exec",
    "uic",
]


def configure_high_dpi() -> None:
    """High DPIスケーリングを有効化する。``QApplication`` 生成前に呼ぶこと。

    PyQt5(Qt5)ではHigh DPIスケーリングが既定で無効なため、
    ``Qt.AA_EnableHighDpiScaling`` / ``Qt.AA_UseHighDpiPixmaps`` 属性を
    明示的に有効化する必要がある。一方PyQt6(Qt6)ではHigh DPIスケーリングは
    常時有効であり、これらの属性自体が廃止されているため、参照すると
    AttributeErrorになる。そのためPyQt6では何もしない。
    """
    if QT_API != "PyQt5":
        return
    # hasattrで存在確認してから使う(Qtのバージョンによっては
    # 属性が無い可能性があるため防御的に書く)。
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


def qt_exec(app_or_dialog):
    """PyQt5の ``exec_()`` とPyQt6の ``exec()`` の差異を吸収する。"""
    fn = getattr(app_or_dialog, "exec", None) or getattr(app_or_dialog, "exec_")
    return fn()


def enum_value(container, name: str):
    """PyQt5(フラットEnum: ``Qt.AlignCenter``)とPyQt6(スコープドEnum:
    ``Qt.AlignmentFlag.AlignCenter``)の差異を吸収して定数を取得する。

    使用例: ``enum_value(Qt, "AlignCenter")``
    """
    if hasattr(container, name):
        return getattr(container, name)
    for attr_name in dir(container):
        attr = getattr(container, attr_name)
        if isinstance(attr, type) and issubclass(attr, enum.Enum) and hasattr(attr, name):
            return getattr(attr, name)
    raise AttributeError(f"{container!r} に列挙値 {name!r} が見つかりません")
