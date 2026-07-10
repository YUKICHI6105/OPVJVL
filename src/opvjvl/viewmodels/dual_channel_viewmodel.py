"""2ch活用モード(モードA: 2ch低ノイズ計測 / モードB: 2素子同時計測)タブの
ViewModel。

要件定義書_基本設計書.md A-4-4節・B-1節に対応する。``dual_modeSelectCombo``
による画面切替自体はView側(``dual_channel_tab.py``)が既に行うため、ここでは
モードA/モードBそれぞれの開始/中断ボタンのロジックのみを扱う。モードBでは
「発光素子モードを同時選択できるチャンネルは最大1つ」というA-4-4-2節の
排他制御を、UIレベルの制御(View側)に加えてViewModel側でも二重チェックする。
"""
from __future__ import annotations

import datetime
import functools
from typing import Optional

from opvjvl.models.instruments import registry
from opvjvl.models.measurement import csv_writer
from opvjvl.models.measurement.config import ChannelConfig, DualAConfig, DualBConfig
from opvjvl.models.measurement.sequences import run_dual_a_sequence, run_dual_b_sequence
from opvjvl.qtcompat import QObject
from opvjvl.viewmodels import base_viewmodel as bvm
from opvjvl.workers.dual_channel_worker import DualChannelWorker
from opvjvl.workers.measurement_worker import MeasurementWorker

_DEVICE_TYPE_2612B = "keithley2612b"


class DualChannelViewModel(QObject):
    """2ch活用モードタブ用ViewModel。モードA/モードBを個別に扱う。"""

    def __init__(self, dual_channel_tab, parent=None) -> None:
        super().__init__(parent)
        self.view = dual_channel_tab
        self._worker_a: Optional[MeasurementWorker] = None
        self._worker_b: Optional[DualChannelWorker] = None
        self._plot_buffer_a: Optional[bvm.PlotBuffer] = None
        self._plot_buffer_b_cha: Optional[bvm.PlotBuffer] = None
        self._plot_buffer_b_chb: Optional[bvm.PlotBuffer] = None

        view = self.view
        view.dual_a_startButton.clicked.connect(self._on_mode_a_start_clicked)
        view.dual_a_stopButton.clicked.connect(self._on_mode_a_stop_clicked)
        view.dual_b_startButton.clicked.connect(self._on_mode_b_start_clicked)
        view.dual_b_stopButton.clicked.connect(self._on_mode_b_stop_clicked)

    # ==================================================================
    # モードA(2ch低ノイズ計測)
    # ==================================================================
    def _build_mode_a_config(self) -> DualAConfig:
        view = self.view
        device_mode = view.dual_a_deviceModeCombo.currentText()
        use_luminance = device_mode == "発光素子"
        bm9_port = view.dual_a_bm9PortCombo.currentText().strip() if use_luminance else None
        return DualAConfig(
            device_type=_DEVICE_TYPE_2612B,
            connection=view.dual_a_connectionCombo.currentText(),
            use_mock=view.dual_a_useMockCheckBox.isChecked(),
            v_min=view.dual_a_vMinSpin.value(),
            v_max=view.dual_a_vMaxSpin.value(),
            v_step=view.dual_a_vStepSpin.value(),
            iteration=view.dual_a_iterationSpin.value(),
            compliance_current=view.dual_a_complianceSpin.value(),
            nplc=view.dual_a_nplcSpin.value(),
            delay_time=view.dual_a_delaySpin.value(),
            sample_name=view.dual_a_sampleNameEdit.text().strip() or "sample",
            save_dir=view.dual_a_saveDirEdit.text().strip() or ".",
            device_mode=device_mode,
            use_luminance=use_luminance,
            bm9_port=bm9_port,
        )

    def _on_mode_a_start_clicked(self) -> None:
        if self._worker_a is not None and self._worker_a.isRunning():
            return  # 二重起動防止(B-7節)

        view = self.view
        config = self._build_mode_a_config()
        if not bvm.validate_voltage_range(view, config.v_min, config.v_max):
            return
        if config.use_luminance and not bvm.validate_luminance_port(view, config.bm9_port):
            return

        preset = "jvl" if config.device_mode == "発光素子" else "opv"
        smu = registry.create_source_meter(
            config.device_type, config.connection, use_mock=config.use_mock, preset=preset
        )
        luminance_meter = None
        if config.use_luminance:
            luminance_meter = registry.create_luminance_meter(
                config.bm9_port, use_mock=config.use_mock
            )

        total_points = len(config.build_voltage_list())
        make_iterator = functools.partial(
            run_dual_a_sequence, smu, config, luminance_meter=luminance_meter
        )
        csv_save_fn = functools.partial(
            csv_writer.save_dual_a_csv,
            sample_name=config.sample_name,
            save_dir=config.save_dir,
            device_mode=config.device_mode,
            use_luminance=config.use_luminance,
        )

        bvm.append_log(
            view.dual_a_logTextEdit,
            f"{bvm.mock_log_prefix(config.use_mock)}モードA測定を開始します"
            f" ({config.connection}, 計測対象={config.device_mode})",
        )
        self._plot_buffer_a = bvm.PlotBuffer(view.dual_a_plotWidget)

        worker = MeasurementWorker(
            make_iterator,
            smu,
            total_points,
            luminance_meter=luminance_meter,
            csv_save_fn=csv_save_fn,
        )
        worker.point_measured.connect(self._on_mode_a_point_measured)
        worker.progress.connect(self._on_mode_a_progress)
        worker.finished_ok.connect(self._on_mode_a_finished_ok)
        worker.error.connect(self._on_mode_a_error)
        self._worker_a = worker

        bvm.set_running_state(view.dual_a_startButton, view.dual_a_stopButton, True)
        worker.start()

    def _on_mode_a_stop_clicked(self) -> None:
        if self._worker_a is not None:
            self._worker_a.request_stop()

    def _on_mode_a_point_measured(self, point) -> None:
        if self._plot_buffer_a is not None:
            self._plot_buffer_a.add_point(point.voltage, point.current)
        luminance = getattr(point, "luminance", None)
        message = f"V={point.voltage:.4f} V, I={point.current:.6e} A"
        if luminance is not None:
            message += f", L={luminance:.4f} cd/m2"
        bvm.append_log(self.view.dual_a_logTextEdit, message)

    def _on_mode_a_progress(self, current: int, total: int) -> None:
        self.view.dual_a_progressBar.setMaximum(max(total, 1))
        self.view.dual_a_progressBar.setValue(current)

    def _on_mode_a_finished_ok(self, points: list, csv_path: str) -> None:
        message = f"モードA測定完了: {len(points)}点。"
        if csv_path:
            message += f" 保存先: {csv_path}"
        bvm.append_log(self.view.dual_a_logTextEdit, message)
        self._reset_mode_a_running_state()

    def _on_mode_a_error(self, message: str) -> None:
        bvm.append_error_log(self.view.dual_a_logTextEdit, message)
        bvm.show_critical(self.view, message)
        self._reset_mode_a_running_state()

    def _reset_mode_a_running_state(self) -> None:
        bvm.set_running_state(self.view.dual_a_startButton, self.view.dual_a_stopButton, False)
        self._worker_a = None

    # ==================================================================
    # モードB(2素子同時計測)
    # ==================================================================
    def _build_channel_config(self, prefix: str) -> ChannelConfig:
        view = self.view
        enable_checkbox = getattr(view, f"dual_{prefix}_enableCheckBox")
        device_mode_combo = getattr(view, f"dual_{prefix}_deviceModeCombo")
        v_min_spin = getattr(view, f"dual_{prefix}_vMinSpin")
        v_max_spin = getattr(view, f"dual_{prefix}_vMaxSpin")
        v_step_spin = getattr(view, f"dual_{prefix}_vStepSpin")
        iteration_spin = getattr(view, f"dual_{prefix}_iterationSpin")
        nplc_spin = getattr(view, f"dual_{prefix}_nplcSpin")
        delay_spin = getattr(view, f"dual_{prefix}_delaySpin")
        sample_name_edit = getattr(view, f"dual_{prefix}_sampleNameEdit")

        return ChannelConfig(
            enabled=enable_checkbox.isChecked(),
            device_mode=device_mode_combo.currentText(),
            v_min=v_min_spin.value(),
            v_max=v_max_spin.value(),
            v_step=v_step_spin.value(),
            iteration=iteration_spin.value(),
            nplc=nplc_spin.value(),
            delay_time=delay_spin.value(),
            sample_name=sample_name_edit.text().strip() or "sample",
        )

    def _on_mode_b_start_clicked(self) -> None:
        if self._worker_b is not None and self._worker_b.isRunning():
            return  # 二重起動防止(B-7節)

        view = self.view
        chan_a = self._build_channel_config("chA")
        chan_b = self._build_channel_config("chB")

        if not chan_a.enabled and not chan_b.enabled:
            bvm.show_warning(
                view, "チャンネルA・チャンネルBのうち少なくとも一方を有効にしてください。"
            )
            return

        # A-4-4-2節: 発光素子モードを同時選択できるチャンネルは最大1つ。
        # UIレベル(View)で既に選択不可のはずだが、ViewModelでも二重に検証する。
        if (
            chan_a.enabled
            and chan_b.enabled
            and chan_a.device_mode == "発光素子"
            and chan_b.device_mode == "発光素子"
        ):
            bvm.show_warning(
                view,
                "チャンネルA・チャンネルBの両方を「発光素子」モードにすることはできません"
                "(輝度計は1台のため同時計測できません)。",
            )
            return

        if chan_a.enabled and not bvm.validate_voltage_range(view, chan_a.v_min, chan_a.v_max):
            return
        if chan_b.enabled and not bvm.validate_voltage_range(view, chan_b.v_min, chan_b.v_max):
            return

        led_channel = None
        if chan_a.enabled and chan_a.device_mode == "発光素子":
            led_channel = "A"
        elif chan_b.enabled and chan_b.device_mode == "発光素子":
            led_channel = "B"

        use_luminance_a = False
        use_luminance_b = False
        bm9_port = None
        if led_channel == "A" and view.dual_chA_useBm9CheckBox.isChecked():
            bm9_port = view.dual_b_bm9PortCombo.currentText().strip()
            if not bvm.validate_luminance_port(view, bm9_port):
                return
            use_luminance_a = True
        elif led_channel == "B" and view.dual_chB_useBm9CheckBox.isChecked():
            bm9_port = view.dual_b_bm9PortCombo.currentText().strip()
            if not bvm.validate_luminance_port(view, bm9_port):
                return
            use_luminance_b = True

        config = DualBConfig(
            connection=view.dual_b_connectionCombo.currentText(),
            use_mock=view.dual_b_useMockCheckBox.isChecked(),
            channel_a=chan_a,
            channel_b=chan_b,
            bm9_port=bm9_port,
            save_dir=view.dual_b_saveDirEdit.text().strip() or ".",
        )

        preset = "jvl" if led_channel is not None else "opv"
        smu = registry.create_source_meter(
            _DEVICE_TYPE_2612B, config.connection, use_mock=config.use_mock, preset=preset
        )
        luminance_meter = None
        if bm9_port:
            luminance_meter = registry.create_luminance_meter(bm9_port, use_mock=config.use_mock)

        va_len = len(chan_a.build_voltage_list()) if chan_a.enabled else 0
        vb_len = len(chan_b.build_voltage_list()) if chan_b.enabled else 0
        total_points = va_len + vb_len

        make_iterator = functools.partial(
            run_dual_b_sequence, smu, config, luminance_meter=luminance_meter
        )
        csv_save_fn = functools.partial(
            self._save_mode_b_results,
            channel_a=chan_a,
            channel_b=chan_b,
            save_dir=config.save_dir,
            connection=config.connection,
            use_luminance_a=use_luminance_a,
            use_luminance_b=use_luminance_b,
        )

        bvm.append_log(
            view.dual_b_logTextEdit,
            f"{bvm.mock_log_prefix(config.use_mock)}モードB測定を開始します ({config.connection})",
        )
        self._plot_buffer_b_cha = (
            bvm.PlotBuffer(view.dual_chA_plotWidget) if chan_a.enabled else None
        )
        self._plot_buffer_b_chb = (
            bvm.PlotBuffer(view.dual_chB_plotWidget) if chan_b.enabled else None
        )

        worker = DualChannelWorker(
            make_iterator,
            smu,
            total_points,
            luminance_meter=luminance_meter,
            csv_save_fn=csv_save_fn,
        )
        worker.point_measured_a.connect(self._on_mode_b_point_measured_a)
        worker.point_measured_b.connect(self._on_mode_b_point_measured_b)
        worker.progress.connect(self._on_mode_b_progress)
        worker.finished_ok.connect(self._on_mode_b_finished_ok)
        worker.error.connect(self._on_mode_b_error)
        self._worker_b = worker

        bvm.set_running_state(view.dual_b_startButton, view.dual_b_stopButton, True)
        worker.start()

    def _on_mode_b_stop_clicked(self) -> None:
        if self._worker_b is not None:
            self._worker_b.request_stop()

    def _save_mode_b_results(
        self,
        points_a: list,
        points_b: list,
        channel_a: ChannelConfig,
        channel_b: ChannelConfig,
        save_dir: str,
        connection: str,
        use_luminance_a: bool,
        use_luminance_b: bool,
    ) -> "tuple[str, str]":
        """チャンネルA/Bを別々のCSVに保存し、掃引条件をサイドカーJSONに残す(A-4-4-2節)。"""
        path_a = ""
        path_b = ""
        if channel_a.enabled:
            path_a = csv_writer.save_dual_b_channel_csv(
                points_a,
                sample_name=channel_a.sample_name,
                save_dir=save_dir,
                channel="A",
                device_mode=channel_a.device_mode,
                use_luminance=use_luminance_a,
            )
        if channel_b.enabled:
            path_b = csv_writer.save_dual_b_channel_csv(
                points_b,
                sample_name=channel_b.sample_name,
                save_dir=save_dir,
                channel="B",
                device_mode=channel_b.device_mode,
                use_luminance=use_luminance_b,
            )

        meta_sample_name = self._combined_sample_name(channel_a, channel_b)
        csv_writer.save_dual_b_meta_json(
            sample_name=meta_sample_name,
            save_dir=save_dir,
            meta={
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "connection": connection,
                "channel_a": self._channel_meta(channel_a),
                "channel_b": self._channel_meta(channel_b),
            },
        )
        return path_a, path_b

    @staticmethod
    def _channel_meta(channel: ChannelConfig) -> dict:
        return {
            "enabled": channel.enabled,
            "device_mode": channel.device_mode,
            "v_min": channel.v_min,
            "v_max": channel.v_max,
            "v_step": channel.v_step,
            "iteration": channel.iteration,
            "nplc": channel.nplc,
            "delay_time": channel.delay_time,
            "sample_name": channel.sample_name,
        }

    @staticmethod
    def _combined_sample_name(channel_a: ChannelConfig, channel_b: ChannelConfig) -> str:
        if channel_a.enabled and channel_b.enabled:
            return f"{channel_a.sample_name}_{channel_b.sample_name}"
        if channel_a.enabled:
            return channel_a.sample_name
        return channel_b.sample_name

    def _on_mode_b_point_measured_a(self, point) -> None:
        if self._plot_buffer_b_cha is not None:
            self._plot_buffer_b_cha.add_point(point.voltage, point.current)
        self._log_mode_b_point("A", point)

    def _on_mode_b_point_measured_b(self, point) -> None:
        if self._plot_buffer_b_chb is not None:
            self._plot_buffer_b_chb.add_point(point.voltage, point.current)
        self._log_mode_b_point("B", point)

    def _log_mode_b_point(self, channel: str, point) -> None:
        message = f"[ch{channel}] V={point.voltage:.4f} V, I={point.current:.6e} A"
        if point.luminance is not None:
            message += f", L={point.luminance:.4f} cd/m2"
        bvm.append_log(self.view.dual_b_logTextEdit, message)

    def _on_mode_b_progress(self, current: int, total: int) -> None:
        self.view.dual_b_progressBar.setMaximum(max(total, 1))
        self.view.dual_b_progressBar.setValue(current)

    def _on_mode_b_finished_ok(self, points: list, csv_path_a: str, csv_path_b: str) -> None:
        message = f"モードB測定完了: 合計{len(points)}点。"
        if csv_path_a:
            message += f" chA保存先: {csv_path_a}"
        if csv_path_b:
            message += f" chB保存先: {csv_path_b}"
        bvm.append_log(self.view.dual_b_logTextEdit, message)
        self._reset_mode_b_running_state()

    def _on_mode_b_error(self, message: str) -> None:
        bvm.append_error_log(self.view.dual_b_logTextEdit, message)
        bvm.show_critical(self.view, message)
        self._reset_mode_b_running_state()

    def _reset_mode_b_running_state(self) -> None:
        bvm.set_running_state(self.view.dual_b_startButton, self.view.dual_b_stopButton, False)
        self._worker_b = None
