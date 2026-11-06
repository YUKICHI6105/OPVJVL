"""測定開始前のBM9接続確認と、輝度なし測定への切り替え確認。"""
from __future__ import annotations

from typing import Optional

from models.instruments import registry
from qtcompat import QtWidgets, enum_value, qt_exec


def _unavailable_reason(port: Optional[str], use_mock: bool) -> Optional[str]:
    if not port or not port.strip():
        return "BM9接続ポートが設定されていません。"

    meter = None
    reason = None
    try:
        meter = registry.create_luminance_meter(port, use_mock=use_mock)
        meter.connect()
        meter.get_luminance()  # ポートだけでなくBM9本体からの応答も確認する。
    except Exception as exc:
        reason = str(exc) or "BM9から応答を取得できませんでした。"
    finally:
        if meter is not None:
            try:
                meter.close()
            except Exception as exc:
                if reason is None:
                    reason = str(exc) or "BM9との接続を閉じられませんでした。"
    return reason


def confirm_luminance_use(parent: QtWidgets.QWidget, port: Optional[str], use_mock: bool) -> Optional[bool]:
    """True=BM9使用、False=輝度なしで続行、None=測定中止。"""
    reason = _unavailable_reason(port, use_mock)
    dialog = QtWidgets.QMessageBox(parent)
    use_bm9 = None
    if reason is None:
        dialog.setIcon(enum_value(QtWidgets.QMessageBox, "Question"))
        dialog.setWindowTitle("輝度計測の確認")
        dialog.setText("BM9で輝度も測定しますか？")
        use_bm9 = dialog.addButton("BM9を使用", enum_value(QtWidgets.QMessageBox, "AcceptRole"))
        dialog.setDefaultButton(use_bm9)
    else:
        dialog.setIcon(enum_value(QtWidgets.QMessageBox, "Warning"))
        dialog.setWindowTitle("輝度計を使用できません")
        dialog.setText("BM9を使用できません。輝度なしで測定しますか？")
        dialog.setInformativeText(reason)
    without_luminance = dialog.addButton(
        "輝度なしで測定", enum_value(QtWidgets.QMessageBox, "ActionRole")
    )
    cancel = dialog.addButton("測定を中止", enum_value(QtWidgets.QMessageBox, "RejectRole"))
    if reason is not None:
        dialog.setDefaultButton(cancel)
    qt_exec(dialog)
    if dialog.clickedButton() is use_bm9 and use_bm9 is not None:
        return True
    if dialog.clickedButton() is without_luminance:
        return False
    return None
