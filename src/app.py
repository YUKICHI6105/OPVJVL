"""OPVJVLアプリケーションのエントリポイント。

互換レイヤー `qtcompat` を最初にインポートし、
メインウィンドウと各ViewModelを生成・紐付けして起動します。
EQEプロジェクト(`EQE/src/main.py`)のパターンに倣い、未捕捉例外を
ログファイルへ記録しエラーダイアログで通知するクラッシュハンドラを備える。
"""
from __future__ import annotations

import argparse
import signal
import sys
import traceback

# 規約に基づき、最初に互換レイヤーをインポートする
import qtcompat
from qtcompat import QTimer, QtWidgets, enum_value, qt_exec
from utils.logger import get_logger
from views.main_window import MainWindow

logger = get_logger("crash_handler")

# SIGINTタイマーの既定インターバル(review.md項目3)。
# Qtイベントループ実行中はPython側のシグナルハンドラがすぐには呼ばれないため、
# QTimerで定期的にPythonバイトコードを実行させ、シグナル配送の機会を作る。
_SIGINT_POLL_INTERVAL_MS = 200


def log_uncaught_exception(exctype, value, tb):
    """キャッチされなかった未処理例外を検知し、ログへCRITICALで記録するとともに、
    GUIが起動していればエラーダイアログで詳細を提示する(EQE main.py踏襲)。
    """
    # Ctrl+Cなどのキーボード割り込みは対象外にして標準の動作をさせる
    if issubclass(exctype, KeyboardInterrupt):
        sys.__excepthook__(exctype, value, tb)
        return

    tb_text = "".join(traceback.format_exception(exctype, value, tb))
    logger.critical("Unhandled Exception (Application Crash):\n%s", tb_text)

    # GUIが起動していれば、ユーザーにエラーダイアログと詳細を表示する
    try:
        if QtWidgets.QApplication.instance():
            msg = QtWidgets.QMessageBox()
            msg.setIcon(enum_value(QtWidgets.QMessageBox, "Critical"))
            msg.setWindowTitle("致命的なエラー")
            msg.setText("アプリケーションで予期しない致命的なエラーが発生しました。")
            msg.setInformativeText(str(value))
            msg.setDetailedText(tb_text)
            qt_exec(msg)
    except Exception as e:  # noqa: BLE001 - ダイアログ表示失敗はログのみに留める
        logger.error("Failed to show crash dialog: %s", e)

    # デフォルトの挙動(コンソールへのエラー出力など)も行う
    sys.__excepthook__(exctype, value, tb)


def install_sigint_handler(window, interval_ms: int = _SIGINT_POLL_INTERVAL_MS) -> QTimer:
    """Ctrl+C(SIGINT)でQtイベントループ実行中でも正常終了できるようにする(review.md項目3)。

    CPythonはPythonシグナルハンドラをバイトコード命令の合間でしか呼び出さないため、
    C++側で完全にブロックするQtイベントループ(``qt_exec``)の中では、Ctrl+Cを押しても
    ハンドラがいつまでも実行されない(コンソールで終了できなくなる)。
    定番の回避策として、短い間隔で空のPythonコードを実行するQTimerを走らせておくことで、
    定期的にPythonインタプリタへ制御を戻し、signalモジュールがハンドラを配送できる
    機会を作る。

    ハンドラ自体は ``window.close()`` を呼ぶだけにとどめる。これにより
    ``MainWindow.closeEvent``(測定パラメータの保存・実行中測定の安全停止)を
    通常のウィンドウクローズと同じ経路で必ず通過させる。

    ``window`` はテスト容易性のため ``close()`` メソッドを持つ任意のオブジェクト
    (本物のMainWindowでもスタブでもよい)を受け取れるようにしてある。

    戻り値のQTimerは呼び出し側が変数に保持し続けること(参照が切れるとGCされ、
    定期実行が止まってCtrl+Cが再び効かなくなる)。
    """

    def _on_sigint(signum, frame) -> None:  # noqa: ARG001 - signalハンドラの規定シグネチャ
        logger.info("SIGINT (Ctrl+C) を受信しました。ウィンドウを閉じて終了します。")
        window.close()

    signal.signal(signal.SIGINT, _on_sigint)

    timer = QTimer()
    timer.setObjectName("sigintPollTimer")
    timer.timeout.connect(lambda: None)
    timer.start(interval_ms)
    return timer


def main() -> int:
    """メインエントリポイント関数。"""
    # クラッシュ自己検知ハンドラを最初に登録する
    sys.excepthook = log_uncaught_exception

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
    logger.info("OPVJVL GUI application started (Qt binding: %s)", qtcompat.QT_API)

    # Ctrl+CでQtイベントループ中でも正常終了できるようにする(review.md項目3)。
    # タイマーはGCされないようwindowに参照を保持させる。
    window._sigint_timer = install_sigint_handler(window)

    # 5. イベントループの開始
    return qt_exec(app)


if __name__ == "__main__":
    sys.exit(main())
