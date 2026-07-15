.. OPVJVL 太陽電池と発光素子計測プログラム documentation master file

OPVJVL 太陽電池と発光素子計測プログラム
========================================

本ソフトウェアは、研究室で使用しているKeithley 2400 / Keithley 2612B（ソースメータ）と
TOPCON BM9（輝度計）を用いて、太陽電池（OPV）のJV特性・発光素子（LED/OLED等）のIV-輝度
（JVL）特性を計測するデスクトップGUIアプリケーションです。単発実行のCUI/matplotlibベース
だった既存スクリプト群を、MVVMアーキテクチャに基づくPyQtアプリケーションとして再構築し、
機種選択・掃引条件設定・リアルタイムプロット・モック機器による実機なし検証を可能にします。

主な特徴
--------

* **3つの測定モード**: 太陽電池のJV/IV特性を測定する **OPVモード**、発光素子のIV-輝度
  特性（暗IV測定にも流用可）を測定する **JVLモード**、Keithley 2612Bの2チャンネルを
  活用する **2ch活用モード**（モードA: 低ノイズ計測 / モードB: 2素子同時計測）。
* **PyQt5/PyQt6両対応**: 独自の互換レイヤー ``qtcompat`` により、本番環境
  （Python 3.9 + PyQt5）と開発環境（Python 3.13 + PyQt6）の両方で同一コードが動作します。
* **モック機器による実機なし検証**: 開発者モード（``--developer``）では、ダイオード方程式
  に基づく擬似IV特性を返すモッククラスに切り替えて、実機なしでGUI・測定フローを検証できます。
* **リアルタイムプロット**: pyqtgraphにより、測定点ごとにグラフをリアルタイム更新します。
* **測定の排他制御**: 機器共有に基づき、OPV⇔JVL・2chモードA⇔B・（機種が2612Bの場合は）
  OPV/JVL群⇔2ch群を自動的に相互排他し、同一機器への同時アクセスを防止します。
* **測定パラメータ・機器設定の永続化**: ``settings.json`` に測定条件・接続先・グラフ表示
  設定を保存し、次回起動時に復元します。
* **安全な中断・終了**: 協調的な中断フラグと ``finally`` 節による出力OFFの保証、
  Ctrl+C（SIGINT）での正常終了、測定中のWindowsスリープ防止に対応します。

.. toctree::
   :maxdepth: 2
   :caption: ユーザーマニュアル:
   :hidden:

   getting_started
   installation
   tutorials
   logging_specification

.. toctree::
   :maxdepth: 2
   :caption: 背景・概念:
   :hidden:

   concepts

.. toctree::
   :maxdepth: 2
   :caption: APIリファレンス:
   :hidden:

   app
   views
   viewmodels
   workers
   models_instruments
   models_measurement
   utils

----

ドキュメント案内
----------------

はじめに
^^^^^^^^

* :doc:`getting_started` — 起動と初回設定〜最初の測定までのクイックスタート
* :doc:`installation` — Python環境（PyQt5/PyQt6）、ドライバ（NI-VISA/シリアル）、
  開発環境（``.venv313``）のセットアップ

操作手順
^^^^^^^^

* :doc:`tutorials` — OPV測定・JVL測定・2ch活用モードA/B測定、ヒステリシス測定、
  データを開く・別名保存、測定の排他ルール、ショートカット一覧
* :doc:`logging_specification` — ログの保存先・レベル設計・カスタマイズ

背景・概念
^^^^^^^^^^

* :doc:`concepts` — JV/JVL測定とは何か・測定システムの構成・ソフトウェアアーキテクチャ
  （MVVM）

APIリファレンス
^^^^^^^^^^^^^^^

* :doc:`app` — アプリケーションのエントリーポイント (``app.py``) およびPyQt5/PyQt6
  互換レイヤー (``qtcompat.py``) のAPIリファレンス
* :doc:`views` — メインウィンドウ・各測定タブ・ダイアログなどUIモジュールのAPIリファレンス
* :doc:`viewmodels` — 各タブのViewModel（状態管理・バリデーション・Worker結線）の
  APIリファレンス
* :doc:`workers` — QThread上でModel層の測定シーケンスを駆動するWorkerインフラ層の
  APIリファレンス
* :doc:`models_instruments` — Keithley 2400/2612B・BM9輝度計の抽象化レイヤーと
  実機ドライバ・モッククラスのAPIリファレンス
* :doc:`models_measurement` — 測定シーケンス・設定・結果データクラス・CSV出力の
  APIリファレンス
* :doc:`utils` — ロガー・設定永続化・パス解決などユーティリティモジュールの
  APIリファレンス

----

.. rubric:: 著作権および開発支援について

* **著作権者**: 石井深川研究室 (Ishii & Fukagawa Lab), 千葉大学 (Chiba University)
* **開発支援**: 本ソフトウェアの開発（コード生成、リファクタリング、ドキュメント作成など）
  においては、開発支援ツールとしてAIアシスタント（Claude by Anthropic）を使用しています。


索引と検索テーブル
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
