"""保存名・重複保存防止・チャネル別電流上限の入力経路を検証する。"""
import pytest

from qtcompat import QtWidgets
from views.dual_channel_tab import DualChannelTab


@pytest.fixture
def dual_tab(qtbot):
    tab = DualChannelTab()
    qtbot.addWidget(tab)
    yield tab
    tab.close()
    tab.deleteLater()
    app = QtWidgets.QApplication.instance()
    for _ in range(3):
        app.processEvents()


def test_channel_filename_preview_tracks_name_and_mode(dual_tab):
    tab = dual_tab
    tab.dual_chA_sampleNameEdit.setText("device_01")
    label = tab.findChild(QtWidgets.QLabel, "dual_chA_filenamePreview")
    assert label.text() == "保存名: device_01_OPV_measurement_data.csv"
    tab.dual_chA_deviceModeCombo.setCurrentText("発光素子")
    assert label.text() == "保存名: device_01_JVL_measurement_data.csv"


def test_duplicate_channel_names_do_not_start_measurement(dual_tab, tmp_path, monkeypatch):
    tab = dual_tab
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    for prefix in ("chA", "chB"):
        getattr(tab, f"dual_{prefix}_sampleNameEdit").setText("same_sample")
    starts, warnings = [], []
    monkeypatch.setattr(tab.viewModel, "start_mode_b", starts.append)
    monkeypatch.setattr(tab, "_show_warning_b", warnings.append)
    tab._on_mode_b_start_clicked()
    assert not starts
    assert len(warnings) == 1
    assert "サンプル名" in warnings[0]


def test_mode_b_current_limits_are_independent_and_used_for_contact_check(dual_tab, monkeypatch):
    tab = dual_tab
    tab.dual_chA_complianceSpin.setValue(0.0075)
    tab.dual_chB_complianceSpin.setValue(0.0125)

    assert tab._build_channel_config("chA").compliance_current == 0.0075
    assert tab._build_channel_config("chB").compliance_current == 0.0125

    checks = []
    monkeypatch.setattr(tab.viewModel, "start_contact_check_b", lambda *args: checks.append(args))
    tab._on_channel_contact_check_clicked("chB")
    assert checks[0][4] == 0.0125
