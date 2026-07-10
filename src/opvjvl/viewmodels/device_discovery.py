"""COMポート/VISAリソースの列挙ヘルパー。

要件定義書_基本設計書.md B-1節(ViewModelの責務)に対応する。各Viewの
「再検索」ボタン(``opv_refreshDevicesButton``等)から呼ばれる想定。
pyserial/pyvisaが未インストールの環境、またはVISAライブラリが見つからない
環境でもクラッシュせず空リストを返す(A-6節: モック実装がserial/pyvisaに
非依存である方針と揃える)。
"""
from __future__ import annotations


def list_serial_ports() -> list[str]:
    """利用可能なシリアルポート名の一覧を返す。取得できない場合は空リスト。"""
    try:
        import serial.tools.list_ports
    except ImportError:
        return []

    try:
        return [port.device for port in serial.tools.list_ports.comports()]
    except Exception:  # noqa: BLE001 - 列挙失敗時は空リストにフォールバック
        return []


def list_visa_resources() -> list[str]:
    """利用可能なVISAリソース文字列の一覧を返す。取得できない場合は空リスト。"""
    try:
        import pyvisa
    except ImportError:
        return []

    try:
        resource_manager = pyvisa.ResourceManager()
        return list(resource_manager.list_resources())
    except Exception:  # noqa: BLE001 - VISAライブラリ未検出等は空リストにフォールバック
        return []
