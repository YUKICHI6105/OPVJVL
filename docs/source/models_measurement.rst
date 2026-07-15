Model Layer — Measurement (models.measurement)
=================================================

測定シーケンス（ジェネレータ関数）、設定・結果のデータクラス、CSV
（・サイドカーJSON）出力を担うQt非依存の純Pythonパッケージです。pytestで
直接呼び出して単体テストできます。

Config Module
---------------

測定シーケンスの設定オブジェクト群です。``OPVConfig``/``JVLConfig``/
``DualAConfig``/``ChannelConfig``/``DualBConfig`` は、対応するシーケンス関数
（``models.measurement.sequences``）への入力パラメータをまとめたdataclassです。
ヒステリシス測定（往復掃引）用の電圧リスト生成ロジックもここに含まれます。

.. automodule:: models.measurement.config
   :members:
   :undoc-members:
   :show-inheritance:

Result Module
---------------

測定結果の値オブジェクト群です。``IVPoint``/``IVLPoint``/``ChannelPoint`` は、
1測定点を表す不変（frozen）なdataclassです。

.. automodule:: models.measurement.result
   :members:
   :undoc-members:
   :show-inheritance:

Sequences Module
-------------------

測定シーケンスのジェネレータ関数群です。``run_opv_sequence``/
``run_jvl_sequence``/``run_dual_a_sequence``/``run_dual_b_sequence`` を
提供します。各シーケンスは ``try/finally`` で必ず機器の出力をOFFにし、
``is_aborted()`` をループ内で毎回チェックして協調的中断を行います。
``sleep_fn`` を注入可能にすることでテスト時に実待機をスキップできます。

.. automodule:: models.measurement.sequences
   :members:
   :undoc-members:
   :show-inheritance:

CSV Writer Module
--------------------

測定結果のCSV（・サイドカーJSON）出力を担うモジュールです。既存解析資産との
互換性のため、列名は厳密に ``"voltage [V]"``、``"current [A]"``、
``"luminance [cd/m2]"`` を用います。依存ライブラリ肥大化防止のため、標準の
``csv`` モジュールのみを使用し ``pandas`` には依存しません。

.. automodule:: models.measurement.csv_writer
   :members:
   :undoc-members:
   :show-inheritance:
