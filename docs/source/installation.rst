==========================
Installation & Setup Guide
==========================

本ページでは、OPVJVL計測ソフトウェアの動作に必要なドライバのセットアップから、
本番環境（Python 3.9 + PyQt5）・開発環境（Python 3.13 + PyQt6）それぞれの
仮想環境構築までの手順を説明します。

.. important::

   セットアップは **2つのステップ** で構成されています。
   :ref:`ステップ 1（計測器ドライバ） <opvjvl-step1-driver>` は、本番環境・開発環境
   の**どちらを使う場合でも必ず最初に実施してください。**
   ドライバがインストールされていない場合、アプリは起動しますが測定器を検出できず
   エラーになります。

セットアップの全体像
--------------------

.. list-table::
   :widths: 12 48 40
   :header-rows: 1

   * - ステップ
     - 内容
     - 対象者
   * - **1**
     - 計測器通信ドライバ（シリアル / NI-VISA）のインストール
     - **全員（必須）**
   * - **2a**
     - 本番環境（Python 3.9 + PyQt5）の構築
     - 研究室PCで測定のみ行うユーザー
   * - **2b**
     - 開発環境（Python 3.13 + PyQt6）の構築
     - ソースコードを編集・デバッグしたい開発者

----

.. _opvjvl-step1-driver:

ステップ 1: 計測器通信ドライバのインストール
--------------------------------------------

PCからKeithley 2400（RS-232シリアル）、Keithley 2612B（USB/GPIB経由VISA）、
TOPCON BM9輝度計（RS-232シリアル）と通信するためには、以下のドライバの導入が必要です。

シリアル通信（Keithley 2400 / BM9）
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

RS-232シリアル接続の機器は、Windows標準のUSB-シリアル変換ドライバ（またはUSB-RS232
変換アダプタ付属のドライバ）が導入されていれば、追加のドライバなしで
``pyserial`` から利用できます。デバイスマネージャーで「ポート (COM と LPT)」
配下に対象機器のCOMポートが表示されることを確認してください。

NI-VISA のインストール（Keithley 2612B）
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Keithley 2612BをUSB/GPIB経由のVISA通信で使用する場合は、National Instruments社の
NI-VISAドライバが必要です。

`National Instrumentsの公式サイト (NI-VISA) <https://www.ni.com/ja-jp/support/downloads/drivers/download.ni-visa.html>`_

ダウンロードしたインストーラーを実行し、デフォルト構成のまま完了させてください。

.. note::

   ドライバのインストール完了後は、設定を有効にするために **PCの再起動** を
   行うことを推奨します。

接続確認（NI MAX / デバイスマネージャー）
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**NI MAX（Measurement & Automation Explorer）** はNI-VISAのインストール時に
自動的にインストールされるシステム診断用ユーティリティです。スタートメニューから
「**NI MAX**」を検索して起動し、左側のツリーから「**デバイスとインターフェース**」を
展開して、Keithley 2612Bが正しく認識されているかを確認します。

.. list-table:: 認識確認の目安
   :widths: 35 65
   :header-rows: 1

   * - 測定器
     - 認識時の表示例
   * - Keithley 2612B（VISA）
     - ``USB0::0x05E6::0x2612::xxxxxxx::INSTR`` などのVISAリソース名
   * - Keithley 2400 / BM9（シリアル）
     - デバイスマネージャーの「ポート (COM と LPT)」に表示される ``COM4`` 等

ここで確認したリソース名／COMポート番号を、本ソフトウェアの「測定の設定」画面
（メニューバー「設定」→「測定の設定...」、``Ctrl+,``）に入力します。

----

.. _opvjvl-step2-app:

ステップ 2: Python実行環境のセットアップ
------------------------------------------

本プロジェクトは **グローバル環境へのpip installを禁止** しており、必ずプロジェクト
直下に仮想環境（venv）を作成してその中に依存パッケージをインストールします。
用途に応じて以下のいずれか（または両方）をセットアップしてください。

.. list-table::
   :widths: 30 70
   :stub-columns: 1

   * - OS
     - Windows 10 / 11 (64bit)
   * - 本番環境
     - Python 3.9 + PyQt5（研究室PCでの測定運用を想定）
   * - 開発環境
     - Python 3.13 + PyQt6（ソースコードの編集・テストを想定）

----

.. _opvjvl-step2a-production:

2a. 本番環境の構築（Python 3.9 + PyQt5）
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

研究室PC等、実機を使って測定のみを行う環境向けのセットアップです。

.. code-block:: powershell

   # プロジェクトルート(OPVJVL)で実行
   python -m venv .venv39
   .venv39\Scripts\python.exe -m pip install --upgrade pip
   .venv39\Scripts\python.exe -m pip install -r requirements-pyqt5.txt

セットアップ完了後は、以下のコマンドでアプリケーションを起動します。

.. code-block:: powershell

   .venv39\Scripts\python.exe src\app.py

----

.. _opvjvl-step2b-development:

2b. 開発環境の構築（Python 3.13 + PyQt6）
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

ソースコードの編集・デバッグ・テスト実行を行う場合は、以下の手順でPython実行環境を
構築します。

.. code-block:: powershell

   # プロジェクトルート(OPVJVL)で実行
   python -m venv .venv313
   .venv313\Scripts\python.exe -m pip install --upgrade pip
   .venv313\Scripts\python.exe -m pip install -r requirements-pyqt6.txt -r requirements-dev.txt

``requirements-dev.txt`` には、テスト・Lint用の ``pytest`` / ``pytest-qt`` /
``ruff`` が含まれます。

.. note::

   ``.venv313/``、``.venv39/`` はいずれもGit管理対象外（``.gitignore`` 済み）です。
   以降、本プロジェクトでのPythonコマンド実行・テスト実行・アプリ起動は、必ず
   ``.venv313\Scripts\python.exe``（開発環境）または ``.venv39\Scripts\python.exe``
   （本番環境）を明示的に使用してください。グローバルの ``python`` コマンドを
   直接使わないことを推奨します。

開発環境でのアプリ起動・テスト実行
""""""""""""""""""""""""""""""""""

.. code-block:: powershell

   # アプリの起動（実機接続なしで動作確認する場合は --developer を付与）
   .venv313\Scripts\python.exe src\app.py --developer

   # テストの実行（133件）
   .venv313\Scripts\python.exe -m pytest tests -q

   # Lintの実行
   .venv313\Scripts\ruff.exe check src

----

PyQt5/PyQt6の切り替えについて
------------------------------

本ソフトウェアは独自の互換レイヤー ``qtcompat.py`` を持ち、起動時にまずPyQt6の
インポートを試み、失敗した場合（本番環境等でPyQt6が未インストールの場合）は
自動的にPyQt5へフォールバックします。開発者がどちらのバインディングで動作しているかを
意識する必要はほとんどありませんが、両方が同一環境に混在する場合は
``PYQTGRAPH_QT_LIB`` 環境変数で使用中のバインディングが自動的に固定され、
pyqtgraphとの不整合を防ぎます。詳細は :doc:`concepts` の
「ソフトウェアアーキテクチャ」を参照してください。
