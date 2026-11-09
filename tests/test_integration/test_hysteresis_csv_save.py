"""実際のモック測定からCSVと別名保存までの測定方向の伝達。"""
import csv
import pytest

from qtcompat import QtWidgets
from views.opv_tab import OPVTab
from views.jvl_tab import JVLTab
from views.dual_channel_tab import DualChannelTab



@pytest.fixture
def mode_b_tab(qtbot):
    from views.plot_buffer import cleanup_luminance_axis
    tab = DualChannelTab()
    qtbot.addWidget(tab)
    yield tab
    tab.viewModel.stop_and_wait_b()
    for plot in tab.plot_widgets():
        cleanup_luminance_axis(plot)
    tab.close()
    tab.deleteLater()
    app = QtWidgets.QApplication.instance()
    for _ in range(3):
        app.processEvents()


@pytest.mark.parametrize("measured", ["A", "B"])
@pytest.mark.parametrize("contact_mode", ["太陽電池", "発光素子"])
def test_idle_channel_contact_check_shares_measurement_connection(
    measured, contact_mode, qtbot, tmp_path, monkeypatch, mode_b_tab,
):
    tab = mode_b_tab
    idle = "B" if measured == "A" else "A"
    monkeypatch.setattr("views.dual_channel_tab.play_completion_sound", lambda *args: None)
    tab.apply_device_settings_mode_b("mock", "", True)
    tab.dual_modeSelectCombo.setCurrentIndex(1)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    for key in ("A", "B"):
        getattr(tab, f"dual_ch{key}_sampleNameEdit").setText(key)
        for field, value in (("vMinSpin", 0), ("vMaxSpin", 0.9), ("vStepSpin", 0.1),
                             ("iterationSpin", 1), ("delaySpin", 0.1)):
            getattr(tab, f"dual_ch{key}_{field}").setValue(value)
    getattr(tab, f"dual_ch{idle}_deviceModeCombo").setCurrentText(contact_mode)
    readings = []
    tab.viewModel.contact_check_reading_b.connect(lambda *args: readings.append(args))
    measured_signal = (tab.viewModel.point_measured_b_cha if measured == "A"
                       else tab.viewModel.point_measured_b_chb)
    with qtbot.waitSignal(measured_signal, timeout=10000):
        getattr(tab, f"dual_ch{measured}_startButton").click()
    worker = tab.viewModel._worker_b
    contact_button = getattr(tab, f"dual_ch{idle}_contactCheckButton")
    assert contact_button.isEnabled()
    assert not getattr(tab, f"dual_ch{measured}_contactCheckButton").isEnabled()
    contact_button.click()
    qtbot.waitUntil(lambda: bool(readings), timeout=5000)
    assert all(reading[0] == idle for reading in readings)
    assert not getattr(tab, f"dual_ch{idle}_startButton").isEnabled()
    assert getattr(tab, f"dual_ch{measured}_startButton").isEnabled()
    with qtbot.waitSignal(tab.viewModel.contact_check_running_changed_b, timeout=5000):
        contact_button.click()
    with qtbot.waitSignal(tab.viewModel.finished_ok_b, timeout=10000) as result:
        pass
    assert len(result.args[0]) == 10
    assert all(point.channel == measured for point in result.args[0])
    assert not result.args[3]
    assert worker._smu.reset_calls == 1
    assert worker._smu.connect_calls == 1


@pytest.mark.parametrize("restarted", ["A", "B"])
@pytest.mark.parametrize("rename", [False, True])
def test_stopped_channel_can_start_again_without_mixing_points(
    restarted, rename, qtbot, tmp_path, monkeypatch, mode_b_tab,
):
    import json
    tab = mode_b_tab
    monkeypatch.setattr("views.dual_channel_tab.play_completion_sound", lambda *args: None)
    overwritten = []
    monkeypatch.setattr("views.dual_channel_tab.confirm_overwrite",
                        lambda _parent, paths: overwritten.extend(paths) or True)
    tab.apply_device_settings_mode_b("mock", "", True)
    tab.dual_modeSelectCombo.setCurrentIndex(1)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    for key in ("A", "B"):
        getattr(tab, f"dual_ch{key}_sampleNameEdit").setText(f"old_{key}")
        for field, value in (("vMinSpin", 0), ("vMaxSpin", 1.9), ("vStepSpin", 0.1),
                             ("iterationSpin", 1), ("delaySpin", 0.1)):
            getattr(tab, f"dual_ch{key}_{field}").setValue(value)
    signal = (tab.viewModel.point_measured_b_cha if restarted == "A"
              else tab.viewModel.point_measured_b_chb)
    with qtbot.waitSignal(signal, timeout=10000):
        tab.dual_b_startButton.click()
    worker = tab.viewModel._worker_b
    button = getattr(tab, f"dual_ch{restarted}_startButton")
    with qtbot.waitSignal(tab.viewModel.channel_stopped_b, timeout=5000):
        button.click()
    assert button.isEnabled()
    assert button.text() == "このチャネルを測定開始"
    partial = tmp_path / f"old_{restarted}_OPV_measurement_data.csv"
    with partial.open(encoding="utf-8", newline="") as f:
        assert 0 < len(list(csv.DictReader(f))) < 20
    assert json.loads((tmp_path / f"old_{restarted}_dualB_meta.json").read_text(encoding="utf-8"))["aborted"]
    sample = f"new_{restarted}" if rename else f"old_{restarted}"
    getattr(tab, f"dual_ch{restarted}_sampleNameEdit").setText(sample)
    getattr(tab, f"dual_ch{restarted}_vMaxSpin").setValue(0.2)
    with qtbot.waitSignal(tab.viewModel.finished_ok_b, timeout=10000) as result:
        button.click()
    points = [p for p in result.args[0] if p.channel == restarted]
    assert [p.index for p in points] == [0, 1, 2]
    assert [p.voltage for p in points] == [0, 0.1, 0.2]
    assert len(result.args[0]) == 23
    assert result.args[3] is False
    assert worker._smu.reset_calls == 1
    assert worker._smu.connect_calls == 1
    with (tmp_path / f"{sample}_OPV_measurement_data.csv").open(encoding="utf-8", newline="") as f:
        assert len(list(csv.DictReader(f))) == 3
    assert str(tmp_path / f"{sample}_OPV_measurement_data.csv") in overwritten


def directions(path):
    with open(path, encoding="utf-8", newline="") as stream:
        return [row["sweep direction"] for row in csv.DictReader(stream)]


@pytest.mark.parametrize("kind", ["opv", "jvl", "dual_a"])
def test_auto_and_save_as_keep_original_sweep_settings(qtbot, tmp_path, monkeypatch, kind):
    cls = {"opv": OPVTab, "jvl": JVLTab, "dual_a": DualChannelTab}[kind]
    tab = cls()
    qtbot.addWidget(tab)
    monkeypatch.setattr(f"views.{ 'dual_channel' if kind == 'dual_a' else kind }_tab.play_completion_sound", lambda *args: None)
    if kind == "opv":
        tab.apply_device_settings("keithley2400", "COM5", "smua", True)
    elif kind == "jvl":
        tab.apply_device_settings("keithley2400", "COM5", "", "smua", True)
        monkeypatch.setattr("views.jvl_tab.confirm_luminance_use", lambda *args: False)
    else:
        tab.apply_device_settings_mode_a("mock", "", True)
    for name, value in [("vMinSpin", 0), ("vMaxSpin", 0.2), ("vStepSpin", 0.1),
                        ("iterationSpin", 2), ("delaySpin", 0)]:
        getattr(tab, f"{kind}_{name}").setValue(value)
    getattr(tab, f"{kind}_hysteresisCheckBox").setChecked(True)
    getattr(tab, f"{kind}_sampleNameEdit").setText("test")
    getattr(tab, f"{kind}_saveDirEdit").setText(str(tmp_path))
    signal = tab.viewModel.finished_ok_a if kind == "dual_a" else tab.viewModel.finished_ok
    with qtbot.waitSignal(signal, timeout=10000):
        getattr(tab, f"{kind}_startButton").click()
    qtbot.waitUntil(lambda: getattr(tab, f"{kind}_startButton").isEnabled(), timeout=5000)
    assert not getattr(tab, f"{kind}_stopButton").isEnabled()
    label = "JVL" if kind == "jvl" else "OPV"
    expected = ["Forward"] * 6 + ["Backward"] * 4
    assert directions(tmp_path / f"test_{label}_measurement_data.csv") == expected
    # 完了後の入力欄変更で、保存済み結果の方向境界が変わらないこと。
    getattr(tab, f"{kind}_hysteresisCheckBox").setChecked(False)
    getattr(tab, f"{kind}_iterationSpin").setValue(1)
    path = tmp_path / "renamed.csv"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    tab.save_last_result_as()
    assert directions(path) == expected


def test_dual_b_channels_keep_independent_direction_boundaries(qtbot, tmp_path, monkeypatch, mode_b_tab):
    tab = mode_b_tab
    monkeypatch.setattr("views.dual_channel_tab.play_completion_sound", lambda *args: None)
    tab.apply_device_settings_mode_b("mock", "", True)
    tab.dual_modeSelectCombo.setCurrentIndex(1)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    for channel, end in (("A", 0.1), ("B", 0.2)):
        prefix = f"dual_ch{channel}"
        getattr(tab, f"{prefix}_sampleNameEdit").setText(channel)
        getattr(tab, f"{prefix}_hysteresisCheckBox").setChecked(True)
        for name, value in [("vMinSpin", 0), ("vMaxSpin", end), ("vStepSpin", 0.1),
                            ("iterationSpin", 1), ("delaySpin", 0)]:
            getattr(tab, f"{prefix}_{name}").setValue(value)
    with qtbot.waitSignal(tab.viewModel.finished_ok_b, timeout=10000):
        tab.dual_b_startButton.click()
    for index, channel, expected in [(0, "A", ["Forward"] * 2 + ["Backward"]),
                                     (1, "B", ["Forward"] * 3 + ["Backward"] * 2)]:
        assert directions(tmp_path / f"{channel}_OPV_measurement_data.csv") == expected
        getattr(tab, f"dual_ch{channel}_hysteresisCheckBox").setChecked(False)
        tab.dual_b_displayTabWidget.setCurrentIndex(index)
        path = tmp_path / f"renamed_{channel}.csv"
        monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
        tab.save_last_result_as()
        assert directions(path) == expected


@pytest.mark.parametrize("channel", ["A", "B"])
def test_channel_start_saves_only_selected_channel(qtbot, tmp_path, monkeypatch, channel, mode_b_tab):
    tab = mode_b_tab
    monkeypatch.setattr("views.dual_channel_tab.play_completion_sound", lambda *args: None)
    tab.apply_device_settings_mode_b("mock", "", True)
    tab.dual_modeSelectCombo.setCurrentIndex(1)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    for name in ("A", "B"):
        prefix = f"dual_ch{name}"
        getattr(tab, f"{prefix}_sampleNameEdit").setText(f"sample_{name}")
        for field, value in (("vMinSpin", 0), ("vMaxSpin", 0.1),
                             ("vStepSpin", 0.1), ("iterationSpin", 1), ("delaySpin", 0)):
            getattr(tab, f"{prefix}_{field}").setValue(value)
    with qtbot.waitSignal(tab.viewModel.finished_ok_b, timeout=10000) as outcome:
        getattr(tab, f"dual_ch{channel}_startButton").click()
    path_a, path_b = outcome.args[1:3]
    chosen = tmp_path / f"sample_{channel}_OPV_measurement_data.csv"
    assert chosen.exists()
    assert (path_a, path_b) == ((str(chosen), "") if channel == "A" else ("", str(chosen)))
    other = "B" if channel == "A" else "A"
    assert not (tmp_path / f"sample_{other}_OPV_measurement_data.csv").exists()


def test_channel_b_joins_while_a_continues(qtbot, tmp_path, monkeypatch, mode_b_tab):
    tab = mode_b_tab
    monkeypatch.setattr("views.dual_channel_tab.play_completion_sound", lambda *args: None)
    tab.apply_device_settings_mode_b("mock", "", True)
    tab.dual_modeSelectCombo.setCurrentIndex(1)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    for name, maximum, delay in (("A", 0.9, 0.1), ("B", 0.2, 0)):
        prefix = f"dual_ch{name}"
        getattr(tab, f"{prefix}_sampleNameEdit").setText(f"join_{name}")
        for field, value in (("vMinSpin", 0), ("vMaxSpin", maximum),
                             ("vStepSpin", 0.1), ("iterationSpin", 1), ("delaySpin", delay)):
            getattr(tab, f"{prefix}_{field}").setValue(value)
    with qtbot.waitSignal(tab.viewModel.point_measured_b_cha, timeout=10000):
        tab.dual_chA_startButton.click()
    worker = tab.viewModel._worker_b
    assert tab.dual_chB_startButton.isEnabled()
    assert tab.dual_chA_startButton.isEnabled()
    assert tab.dual_chA_startButton.text() == "このチャネルを中断"
    with qtbot.waitSignal(tab.viewModel.finished_ok_b, timeout=10000) as outcome:
        tab.dual_chB_startButton.click()
    assert not outcome.args[3]
    points = outcome.args[0]
    a = [p for p in points if p.channel == "A"]
    b = [p for p in points if p.channel == "B"]
    assert [p.index for p in a] == list(range(10))
    assert [p.index for p in b] == [0, 1, 2]
    assert points.index(b[0]) > points.index(a[0])
    assert (tmp_path / "join_A_OPV_measurement_data.csv").exists()
    assert (tmp_path / "join_B_OPV_measurement_data.csv").exists()
    assert worker._smu.reset_calls == 1


def test_channel_a_joins_while_b_continues(qtbot, tmp_path, monkeypatch, mode_b_tab):
    tab = mode_b_tab
    monkeypatch.setattr("views.dual_channel_tab.play_completion_sound", lambda *args: None)
    tab.apply_device_settings_mode_b("mock", "", True)
    tab.dual_modeSelectCombo.setCurrentIndex(1)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    for name, maximum, delay in (("A", 0.2, 0), ("B", 0.9, 0.1)):
        prefix = f"dual_ch{name}"
        getattr(tab, f"{prefix}_sampleNameEdit").setText(f"reverse_{name}")
        for field, value in (("vMinSpin", 0), ("vMaxSpin", maximum),
                             ("vStepSpin", 0.1), ("iterationSpin", 1), ("delaySpin", delay)):
            getattr(tab, f"{prefix}_{field}").setValue(value)
    with qtbot.waitSignal(tab.viewModel.point_measured_b_chb, timeout=10000):
        tab.dual_chB_startButton.click()
    worker = tab.viewModel._worker_b
    assert tab.dual_chA_startButton.isEnabled()
    assert tab.dual_chB_startButton.isEnabled()
    assert tab.dual_chB_startButton.text() == "このチャネルを中断"
    with qtbot.waitSignal(tab.viewModel.finished_ok_b, timeout=10000) as outcome:
        tab.dual_chA_startButton.click()
    points = outcome.args[0]
    a = [p for p in points if p.channel == "A"]
    b = [p for p in points if p.channel == "B"]
    assert [p.index for p in a] == [0, 1, 2]
    assert [p.index for p in b] == list(range(10))
    assert points.index(a[0]) > points.index(b[0])
    assert (tmp_path / "reverse_A_OPV_measurement_data.csv").exists()
    assert (tmp_path / "reverse_B_OPV_measurement_data.csv").exists()
    assert worker._smu.reset_calls == 1


@pytest.mark.parametrize("stopped_channel", ["A", "B"])
def test_channel_button_interrupts_only_its_channel(
    stopped_channel, qtbot, tmp_path, monkeypatch, mode_b_tab,
):
    import json

    tab = mode_b_tab
    monkeypatch.setattr("views.dual_channel_tab.play_completion_sound", lambda *args: None)
    tab.apply_device_settings_mode_b("mock", "", True)
    tab.dual_modeSelectCombo.setCurrentIndex(1)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    for key in ("A", "B"):
        prefix = f"dual_ch{key}"
        getattr(tab, f"{prefix}_sampleNameEdit").setText(f"stop_{key}")
        for field, value in (("vMinSpin", 0), ("vMaxSpin", 1.0),
                             ("vStepSpin", 0.1), ("iterationSpin", 1),
                             ("delaySpin", 0.1)):
            getattr(tab, f"{prefix}_{field}").setValue(value)

    signal = (tab.viewModel.point_measured_b_cha if stopped_channel == "A"
              else tab.viewModel.point_measured_b_chb)
    with qtbot.waitSignal(signal, timeout=10000):
        tab.dual_b_startButton.click()
    worker = tab.viewModel._worker_b
    button = getattr(tab, f"dual_ch{stopped_channel}_startButton")
    assert button.text() == "このチャネルを中断"
    with qtbot.waitSignal(tab.viewModel.finished_ok_b, timeout=10000) as outcome:
        button.click()
        assert button.text() == "中断済み"

    points = outcome.args[0]
    other = "B" if stopped_channel == "A" else "A"
    assert outcome.args[3] is True
    assert 0 < len([p for p in points if p.channel == stopped_channel]) < 11
    assert len([p for p in points if p.channel == other]) == 11
    assert worker._smu.output_calls.count(("smua" if stopped_channel == "A" else "smub", False)) >= 2
    meta = json.loads((tmp_path / "stop_A_stop_B_dualB_meta.json").read_text(encoding="utf-8"))
    assert meta[f"channel_{stopped_channel.lower()}"]["aborted"] is True
    assert meta[f"channel_{other.lower()}"]["aborted"] is False


def test_jvl_channel_joins_and_connects_bm9(qtbot, tmp_path, monkeypatch, mode_b_tab):
    import csv
    tab = mode_b_tab
    monkeypatch.setattr("views.dual_channel_tab.play_completion_sound", lambda *args: None)
    tab.apply_device_settings_mode_b("mock", "MOCK", True)
    tab.dual_modeSelectCombo.setCurrentIndex(1)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    tab.dual_chB_deviceModeCombo.setCurrentText("発光素子")
    monkeypatch.setattr("views.dual_channel_tab.confirm_luminance_use", lambda *args: True)
    for name, maximum, delay in (("A", 0.5, 0.1), ("B", 0.1, 0)):
        prefix = f"dual_ch{name}"
        getattr(tab, f"{prefix}_sampleNameEdit").setText(f"lum_{name}")
        for field, value in (("vMinSpin", 0), ("vMaxSpin", maximum),
                             ("vStepSpin", 0.1), ("iterationSpin", 1), ("delaySpin", delay)):
            getattr(tab, f"{prefix}_{field}").setValue(value)
    with qtbot.waitSignal(tab.viewModel.point_measured_b_cha, timeout=10000):
        tab.dual_chA_startButton.click()
    with qtbot.waitSignal(tab.viewModel.finished_ok_b, timeout=10000) as outcome:
        tab.dual_chB_startButton.click()
    b_points = [point for point in outcome.args[0] if point.channel == "B"]
    assert [point.index for point in b_points] == [0, 1]
    assert all(point.luminance is not None for point in b_points)
    with open(tmp_path / "lum_B_JVL_measurement_data.csv", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert "luminance [cd/m2]" in rows[0]


def test_stop_after_channel_join_turns_both_outputs_off(qtbot, tmp_path, monkeypatch, mode_b_tab):
    tab = mode_b_tab
    monkeypatch.setattr("views.dual_channel_tab.play_completion_sound", lambda *args: None)
    tab.apply_device_settings_mode_b("mock", "", True)
    tab.dual_modeSelectCombo.setCurrentIndex(1)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    for name in ("A", "B"):
        prefix = f"dual_ch{name}"
        getattr(tab, f"{prefix}_sampleNameEdit").setText(f"stop_{name}")
        for field, value in (("vMinSpin", 0), ("vMaxSpin", 0.9),
                             ("vStepSpin", 0.1), ("iterationSpin", 1), ("delaySpin", 0.1)):
            getattr(tab, f"{prefix}_{field}").setValue(value)
    with qtbot.waitSignal(tab.viewModel.point_measured_b_cha, timeout=10000):
        tab.dual_chA_startButton.click()
    worker = tab.viewModel._worker_b
    with qtbot.waitSignal(tab.viewModel.point_measured_b_chb, timeout=10000):
        tab.dual_chB_startButton.click()
    with qtbot.waitSignal(tab.viewModel.finished_ok_b, timeout=10000) as outcome:
        tab.dual_b_stopButton.click()
    assert outcome.args[3]
    assert worker._smu._output_on == {"smua": False, "smub": False}
    assert (tmp_path / "stop_A_OPV_measurement_data.csv").exists()
    assert (tmp_path / "stop_B_OPV_measurement_data.csv").exists()
