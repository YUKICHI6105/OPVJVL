Utilities
=========

本ページでは、OPVJVL計測ソフトウェアのシステム基盤ユーティリティ（``utils``）の
APIを自動生成して掲載します。いずれもQt非依存の純Pythonモジュールです。

Version Module (utils.version)
---------------------------------

アプリケーションのバージョン文字列（``__version__``）を一元管理するモジュール
です。ドキュメント（本Sphinxビルドの ``conf.py``）を含め、バージョン番号を
参照する箇所はすべてこのモジュールを経由します。

.. automodule:: utils.version
   :members:
   :undoc-members:
   :show-inheritance:

Persistence Module (utils.persistence)
------------------------------------------

設定ファイル（``settings.json``）の読み書きを担うモジュールです。機器接続
設定と各タブの測定パラメータ・グラフ表示設定を単一の ``settings.json`` に
保存・復元します。``DEFAULT_SETTINGS`` は初回起動時・キー欠落時のフォール
バック値の唯一の正（Single Source of Truth）です。

.. automodule:: utils.persistence
   :members:
   :undoc-members:
   :show-inheritance:

Device Settings Module (utils.device_settings)
----------------------------------------------------

機器設定（接続先ポート・機器種別等）のロード・保存を担当するモジュールです。
実体は ``utils.persistence`` に統合されており、本モジュールは機器設定キーの
みを抜き出す薄いラッパーです。旧バージョンの ``settings.json`` からの
キー移行も担います。

.. automodule:: utils.device_settings
   :members:
   :undoc-members:
   :show-inheritance:

Logger Module (utils.logger)
--------------------------------

カスタムログレベル（``DEBUG1``/``DEBUG2``/``DEBUG3``）の登録、ロガーのセット
アップ（ファイルローテーション・コンソール出力）を行うモジュールです。
詳細は :doc:`logging_specification` を参照してください。

.. automodule:: utils.logger
   :members:
   :undoc-members:
   :show-inheritance:

Paths Module (utils.paths)
------------------------------

通常のPython実行とPyInstallerによるEXE実行の両方で、アプリケーション本体・
設定ファイル・ログファイルの配置先をWindowsの推奨基準に従って解決する
ユーティリティモジュールです。

.. automodule:: utils.paths
   :members:
   :undoc-members:
   :show-inheritance:

Win32 Utilities Module (utils.win32_utils)
------------------------------------------------

Windows環境における、長時間の掃引測定中にスリープ・ディスプレイ消灯が発生
して測定が中断されるのを防ぐスリープ抑制ユーティリティです。win32以外の
プラットフォームでは何もしません。

.. automodule:: utils.win32_utils
   :members:
   :undoc-members:
   :show-inheritance:
