Entry Point & Compatibility Layer
==================================

アプリケーションのエントリーポイント (``app.py``) と、PyQt5/PyQt6の差異を
吸収する互換レイヤー (``qtcompat.py``) です。

Entry Point Module
-------------------

未処理例外を検知するクラッシュハンドラの登録、``--developer`` オプションの
解析、``QApplication``・``MainWindow`` の生成、Ctrl+C（SIGINT）での正常終了
対応を行います。

.. automodule:: app
   :members:
   :undoc-members:
   :show-inheritance:

Qt Compatibility Layer Module
-------------------------------

本番環境（Python 3.9 + PyQt5）と開発環境（Python 3.13 + PyQt6）の両方で
同一コードを動作させるための互換レイヤーです。全モジュールはPyQt5/PyQt6を
直接importせず、必ず本モジュール経由でQtの型・関数を取得します。

.. automodule:: qtcompat
   :members:
   :undoc-members:
   :show-inheritance:
