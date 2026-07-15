Workers
=======

ViewModelとModelの橋渡しを行うQThreadインフラ層です。QThread上でModel層
（``models.measurement.sequences``）の純粋なジェネレータ関数を駆動し、1測定点
ごとに ``pyqtSignal`` へ変換して発火します。Qt依存はこの層に閉じ込め、
Model層はQt非依存のまま保たれます。

Measurement Worker Module
----------------------------

OPV/JVL/2ch活用モードA共通のWorkerです。``measurement/sequences.py`` の
ジェネレータ関数を ``functools.partial`` で機器・設定を束縛したCallableとして
受け取り、QThread上で駆動します。

.. automodule:: workers.measurement_worker
   :members:
   :undoc-members:
   :show-inheritance:

Dual Channel Worker Module
------------------------------

2ch活用モードB（2素子同時計測）専用のWorkerです。``run_dual_b_sequence`` が
生成する ``ChannelPoint``（``channel`` 属性が ``"A"`` または ``"B"``）を、
チャンネルごとに別シグナルへ振り分けます。

.. automodule:: workers.dual_channel_worker
   :members:
   :undoc-members:
   :show-inheritance:
