"""ViewModel層で共通に使う小さなヘルパー群。

要件定義書_基本設計書.md B-1節(ViewModelの責務)・B-7節(エラーハンドリング
方針)に対応する。
バリデーション/ログ整形部分はQtWidgetsなどのGUIコンポーネントへの依存を排除した
純粋なビジネス/バリデーションロジックのみを保持する。

なお``views/opv_tab.py``・``views/jvl_tab.py``は``from viewmodels import
base_viewmodel as bvm``でインポートした上で``bvm.PlotBuffer``・
``bvm.DualAxisPlotBuffer``を参照する(View側は変更不可の既定仕様のため)。
そのため実体は``views/plot_buffer.py``のままとしつつ、ここで再エクスポートし
互換性を保つ。
"""
from __future__ import annotations

from typing import Optional

from views.plot_buffer import DualAxisPlotBuffer, PlotBuffer  # noqa: F401 - View互換のための再エクスポート


# ---------------------------------------------------------------------------
# バリデーション (エラーメッセージ文字列を返す。正常時は None)
# ---------------------------------------------------------------------------

def validate_voltage_range(v_min: float, v_max: float) -> Optional[str]:
    """Vmax > Vminであることを検証し、違反時はエラーメッセージを返す。"""
    if v_max <= v_min:
        return f"Vmax({v_max})はVmin({v_min})より大きい値にしてください。"
    return None


def validate_luminance_port(bm9_port: Optional[str]) -> Optional[str]:
    """輝度計測ON時にBM9接続ポートが未入力でないことを検証し、違反時はエラーメッセージを返す。"""
    if not bm9_port or not bm9_port.strip():
        return "輝度計測を使用する場合はBM9接続ポートを入力してください。"
    return None


def validate_sweep_parameters(v_step: float, iteration: int) -> Optional[str]:
    """v_step > 0 かつ iteration >= 1 であることを検証し、違反時はエラーメッセージを返す。"""
    if v_step <= 0:
        return "Vstepは0より大きい値にしてください。"
    if iteration < 1:
        return "繰り返し回数は1回以上にしてください。"
    return None


# ---------------------------------------------------------------------------
# ログ整形(B-7節: モック使用時は[MOCK MODE]を明示)
# ---------------------------------------------------------------------------

def mock_log_prefix(use_mock: bool) -> str:
    return "[MOCK MODE] " if use_mock else ""


def format_error_log(message: str) -> str:
    """エラーメッセージを赤字用のHTMLフォーマットに整形する。"""
    return f'<span style="color:#ff5555;">エラー: {message}</span>'
