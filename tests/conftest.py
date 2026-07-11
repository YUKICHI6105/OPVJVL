"""pytest用の共通設定およびフィクスチャ定義。"""
from __future__ import annotations

import os
import pytest

# テスト実行時のヘッドレス表示モード設定
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 先に qtcompat をインポートして、正しい Qt API (PyQt5/PyQt6) を決定させる
import qtcompat

# pytest-qt が使用するバインディングを qtcompat.QT_API と一致させる
# これを行わないと、pytest-qtがPyQt5/PyQt6の不整合でクラッシュする可能性がある
os.environ["PYTEST_QT_API"] = qtcompat.QT_API.lower()


@pytest.fixture(scope="session", autouse=True)
def isolate_settings_file(tmp_path_factory):
    """テスト実行がプロジェクトルートの settings.json を読み書きしないよう隔離する。

    utils.paths.get_settings_path() は OPVJVL_SETTINGS_PATH 環境変数を優先する。
    """
    settings_path = tmp_path_factory.mktemp("settings") / "settings.json"
    os.environ["OPVJVL_SETTINGS_PATH"] = str(settings_path)
    yield
    os.environ.pop("OPVJVL_SETTINGS_PATH", None)


@pytest.fixture(scope="session", autouse=True)
def setup_qt_environment():
    """Qtテスト環境の初期化。"""
    # QMessageBoxがテスト実行中にポップアップしてイベントループをブロックするのを防ぐ
    from qtcompat import QtWidgets
    QtWidgets.QMessageBox.warning = lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.Ok
    QtWidgets.QMessageBox.critical = lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.Ok
    QtWidgets.QMessageBox.information = lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.Ok
    QtWidgets.QMessageBox.question = lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.Yes

    # pyqtgraphがオフスクリーン環境で描画してクラッシュするのを防ぐため、PlotBufferをモック化する
    from viewmodels import base_viewmodel
    class DummyPlotBuffer:
        def __init__(self, plot_widget, pen=None):
            pass
        def add_point(self, x, y):
            pass
    class DummyDualAxisPlotBuffer:
        def __init__(self, plot_widget):
            pass
        def add_point(self, x, current, luminance=None):
            pass

    base_viewmodel.PlotBuffer = DummyPlotBuffer
    base_viewmodel.DualAxisPlotBuffer = DummyDualAxisPlotBuffer
    yield
