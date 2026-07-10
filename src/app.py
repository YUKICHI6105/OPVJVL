"""OPVJVLアプリケーションのエントリポイント。

互換レイヤー `qtcompat` を最初にインポートし、
メインウィンドウと各ViewModelを生成・紐付けして起動します。
"""
from __future__ import annotations

import argparse
import sys

# 規約に基づき、最初に互換レイヤーをインポートする
import qtcompat
from qtcompat import QtWidgets
from views.main_window import MainWindow


def main() -> int:
    """メインエントリポイント関数。"""
    # pytestや他ツールが余分な引数を渡してもクラッシュしないよう parse_known_args を使う
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--developer", action="store_true")
    args, _unknown = parser.parse_known_args()

    # QApplication生成前でなければHigh DPI属性設定が効かないため、先に呼ぶ
    qtcompat.configure_high_dpi()

    # 1. QApplication の作成
    app = QtWidgets.QApplication(sys.argv)

    # テーマスタイルシートのロードと適用
    from views.theme import STYLE_SHEET
    app.setStyleSheet(STYLE_SHEET)

    # 2. メインウィンドウの作成
    window = MainWindow(developer_mode=args.developer)

    # 3. 各 ViewModel のインスタンス化と結線
    # 各Tabが作成したViewModelインスタンスを取得し、ガベージコレクションを避けるためwindowに保持させる
    window.opv_vm = window.opv_tab.viewModel
    window.jvl_vm = window.jvl_tab.viewModel
    window.dual_vm = window.dual_channel_tab.viewModel

    # 4. メインウィンドウの表示
    window.show()

    # 5. イベントループの開始
    return qtcompat.qt_exec(app)


if __name__ == "__main__":
    sys.exit(main())
