"""OPVJVLアプリケーションのエントリポイント。

互換レイヤー `qtcompat` を最初にインポートし、
メインウィンドウと各ViewModelを生成・紐付けして起動します。
"""
from __future__ import annotations

import sys

# 規約に基づき、最初に互換レイヤーをインポートする
from opvjvl import qtcompat
from opvjvl.qtcompat import QtWidgets
from opvjvl.viewmodels.dual_channel_viewmodel import DualChannelViewModel
from opvjvl.viewmodels.jvl_viewmodel import JVLViewModel
from opvjvl.viewmodels.opv_viewmodel import OPVViewModel
from opvjvl.views.main_window import MainWindow


def main() -> int:
    """メインエントリポイント関数。"""
    # 1. QApplication の作成
    app = QtWidgets.QApplication(sys.argv)

    # 2. メインウィンドウの作成
    window = MainWindow()

    # 3. 各 ViewModel のインスタンス化と結線
    # ガベージコレクションを避けるため、window オブジェクトに保持させる
    window.opv_vm = OPVViewModel(window.opv_tab)
    window.jvl_vm = JVLViewModel(window.jvl_tab)
    window.dual_vm = DualChannelViewModel(window.dual_channel_tab)

    # 4. メインウィンドウの表示
    window.show()

    # 5. イベントループの開始
    return qtcompat.qt_exec(app)


if __name__ == "__main__":
    sys.exit(main())
