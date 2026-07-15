Model Layer — Instruments (models.instruments)
=================================================

Keithley 2400 / Keithley 2612B / TOPCON BM9輝度計 を機種非依存に扱うための
抽象化レイヤーです。実機ドライバ・モッククラスは共通の抽象基底クラスを継承し、
上位層（測定シーケンス、Worker、ViewModel）は具象クラスを意識せずに扱えます。
すべてQt非依存の純Pythonモジュールです。

Abstract Base Classes Module
--------------------------------

機器抽象化の基底クラス群です。Keithley2400 / Keithley2612B を機種非依存に扱う
``AbstractSourceMeter`` と、TOPCON BM9輝度計を扱う ``AbstractLuminanceMeter``、
両者の例外基底クラス ``InstrumentError`` を定義します。

.. automodule:: models.instruments.base
   :members:
   :undoc-members:
   :show-inheritance:

Registry (Factory) Module
----------------------------

実機ドライバ/モッククラスを機種名から生成するファクトリです。ViewModel層は
このファクトリ経由でのみ機器インスタンスを生成し、実クラス/モッククラスの
別を意識しません。

.. automodule:: models.instruments.registry
   :members:
   :undoc-members:
   :show-inheritance:

Keithley 2400 Driver Module
--------------------------------

RS-232シリアル（9600bps, 8N1）経由でSCPIコマンドを送受信する実機ドライバです。
Keithley 2400は物理的に1チャンネルしか持たないため、``channel`` 引数は受け取る
が内部では使用しません。

.. automodule:: models.instruments.keithley2400
   :members:
   :undoc-members:
   :show-inheritance:

Keithley 2612B Driver Module
--------------------------------

PyVISA + TSP(Lua)コマンドでKeithley 2612Bを制御する実機ドライバです。
サードパーティの ``keithley2600`` パッケージには依存せず、TSPコマンドを
直接送受信する自前実装です。

.. automodule:: models.instruments.keithley2612b
   :members:
   :undoc-members:
   :show-inheritance:

BM9 Luminance Meter Driver Module
-------------------------------------

TOPCON BM9輝度計の実機ドライバです。RS-232シリアル（2400bps, ODD parity,
7bit, stop1）で通信し、コマンドは ``"DBR0ST"`` のみを使用します。

.. automodule:: models.instruments.bm9
   :members:
   :undoc-members:
   :show-inheritance:

Mock Instruments (models.instruments.mock)
----------------------------------------------

実機なしでの開発・GUI検証・pytestでの単体テストのためのモッククラス群です。
serial/pyvisaはimportせず、待機処理も持ちません（待機は測定シーケンス側の
``sleep_fn`` に委ねる設計）。

.. automodule:: models.instruments.mock.keithley2400_mock
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: models.instruments.mock.keithley2612b_mock
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: models.instruments.mock.bm9_mock
   :members:
   :undoc-members:
   :show-inheritance:
