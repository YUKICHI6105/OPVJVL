"""測定方向表示・保存名プレビュー・重複保存防止の回帰テスト。"""
import pytest

from qtcompat import QtWidgets
from views.dual_channel_tab import DualChannelTab
from views.jvl_tab import JVLTab
from views.opv_tab import OPVTab


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


def test_direction_explanation_is_not_shown(qtbot):
    tab = OPVTab()
    qtbot.addWidget(tab)
    tab.opv_hysteresisCheckBox.setChecked(True)
    assert tab.findChild(QtWidgets.QLabel, "opv_sweepDirectionLabel") is None


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


def test_dual_run_controls_remain_outside_scrolling_settings(dual_tab):
    tab = dual_tab
    scroll = tab.findChild(QtWidgets.QScrollArea, "dual_b_settingsScrollArea")
    assert not scroll.isAncestorOf(tab.dual_b_startButton)
    assert not scroll.isAncestorOf(tab.dual_b_stopButton)


def test_channel_start_buttons_select_only_their_channel(dual_tab, tmp_path, monkeypatch):
    tab = dual_tab
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    configs = []
    monkeypatch.setattr(tab.viewModel, "start_mode_b", configs.append)
    tab.dual_chA_sampleNameEdit.setText("sample_A")
    tab.dual_chB_sampleNameEdit.setText("sample_B")
    assert tab.findChild(QtWidgets.QCheckBox, "dual_chA_enableCheckBox") is None
    assert tab.findChild(QtWidgets.QCheckBox, "dual_chB_enableCheckBox") is None
    for button, enabled in (
        (tab.dual_chA_startButton, (True, False)),
        (tab.dual_chB_startButton, (False, True)),
        (tab.dual_b_startButton, (True, True)),
    ):
        button.click()
        assert (configs[-1].channel_a.enabled, configs[-1].channel_b.enabled) == enabled


def test_mode_b_start_and_contact_buttons_share_a_row(dual_tab):
    for prefix in ("chA", "chB"):
        row = dual_tab.findChild(QtWidgets.QHBoxLayout, f"dual_{prefix}_actionRow")
        form = dual_tab.findChild(QtWidgets.QFormLayout, f"dual_{prefix}_formLayout")
        assert row.itemAt(0).widget() is getattr(dual_tab, f"dual_{prefix}_startButton")
        assert row.itemAt(1).widget() is getattr(dual_tab, f"dual_{prefix}_contactCheckButton")
        assert form.itemAt(form.rowCount() - 2, QtWidgets.QFormLayout.ItemRole.SpanningRole).layout() is row
        assert form.itemAt(form.rowCount() - 1, QtWidgets.QFormLayout.ItemRole.SpanningRole).widget() is getattr(
            dual_tab, f"dual_{prefix}_contactCheckReadingLabel"
        )


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


def test_mode_a_timing_fields_match_opv_layout(dual_tab, qtbot):
    opv = OPVTab()
    qtbot.addWidget(opv)
    dual_row = dual_tab.findChild(QtWidgets.QGridLayout, "dual_a_timingRow")
    opv_row = opv.findChild(QtWidgets.QGridLayout, "opv_timingRow")
    assert dual_row is not None
    assert opv_row is not None
    for column, field in enumerate(("iterationSpin", "nplcSpin", "delaySpin", "complianceSpin")):
        dual_item = dual_row.itemAtPosition(1, column)
        opv_item = opv_row.itemAtPosition(1, column)
        assert dual_item.widget() is getattr(dual_tab, f"dual_a_{field}")
        assert opv_item.widget() is getattr(opv, f"opv_{field}")


def test_mode_a_hysteresis_is_beside_device_mode(dual_tab):
    row = dual_tab.findChild(QtWidgets.QHBoxLayout, "dual_a_deviceModeRow")
    assert row.itemAt(0).widget() is dual_tab.dual_a_deviceModeCombo
    assert row.itemAt(1).widget() is dual_tab.dual_a_hysteresisCheckBox


def test_jvl_has_hysteresis_without_bm9_checkbox(qtbot):
    tab = JVLTab()
    qtbot.addWidget(tab)
    assert tab.jvl_hysteresisCheckBox is not None
    assert tab.findChild(QtWidgets.QCheckBox, "jvl_useLuminanceCheckBox") is None


def test_mode_a_keeps_automatic_bm9_selection(dual_tab):
    dual_tab.dual_a_deviceModeCombo.setCurrentText("発光素子")
    assert dual_tab._build_mode_a_config().use_luminance is True
    assert dual_tab.findChild(QtWidgets.QCheckBox, "dual_a_useBm9CheckBox") is None


def test_mode_b_hysteresis_replaces_bm9_beside_device_mode(dual_tab):
    tab = dual_tab
    tab.dual_modeSelectCombo.setCurrentIndex(1)
    tab.show()
    QtWidgets.QApplication.processEvents()
    row_a = tab.findChild(QtWidgets.QHBoxLayout, "dual_chA_deviceModeRow")
    row_b = tab.findChild(QtWidgets.QHBoxLayout, "dual_chB_deviceModeRow")
    assert row_a.itemAt(0).widget() is tab.dual_chA_deviceModeCombo
    assert row_a.itemAt(1).widget() is tab.dual_chA_hysteresisCheckBox
    assert row_b.itemAt(0).widget() is tab.dual_chB_deviceModeCombo
    assert row_b.itemAt(1).widget() is tab.dual_chB_hysteresisCheckBox
    assert tab.findChild(QtWidgets.QCheckBox, "dual_chA_useBm9CheckBox") is None
    assert tab.findChild(QtWidgets.QCheckBox, "dual_chB_useBm9CheckBox") is None

    combo_width = tab.dual_chA_deviceModeCombo.width()

    tab.dual_chA_deviceModeCombo.setCurrentText("発光素子")
    QtWidgets.QApplication.processEvents()
    assert tab.dual_chA_deviceModeCombo.width() == combo_width

    tab.dual_chA_deviceModeCombo.setCurrentText("太陽電池")
    QtWidgets.QApplication.processEvents()
    assert tab.dual_chA_deviceModeCombo.width() == combo_width
