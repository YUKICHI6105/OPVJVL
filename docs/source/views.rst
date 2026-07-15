Views
=====

UI（見た目・ウィジェット構築）を担当するモジュール群です。MVVM設計に基づき、測定の
実処理ロジックはViewModel層・Model層に委譲され、本モジュール群はウィジェットツリーの
構築・表示状態の切り替え・ユーザー操作のViewModelスロットへの委譲を担います。

Main Window Module
-------------------

アプリケーションのメインウィンドウ（``MainWindow``）を定義するモジュールです。
OPV/JVL/2ch活用の各タブをコードで構築して挿入し、共通保存設定パネル・メニューバー・
測定パラメータの永続化・測定の排他制御（機器共有ベース）を担います。

.. automodule:: views.main_window
   :members:
   :undoc-members:
   :show-inheritance:

Tab Layout Builder Module
----------------------------

OPV/JVL/2ch活用モードA・Bの各タブで共通のレイアウトビルダーです。測定設定・保存実行
グループの共通ビルダーと、「設定カラム（スクロール）」「表示パネル（進捗＋グラフ）」の
共通骨格を提供し、タブ間のレイアウト差異を構造的に排除します。

.. automodule:: views.tab_layout
   :members:
   :undoc-members:
   :show-inheritance:

OPV Tab Module
----------------

OPVモード（太陽電池 JV/IV特性測定）タブのViewです。電圧掃引条件・タイミング/
コンプライアンス・保存設定のウィジェットツリーを構築します。

.. automodule:: views.opv_tab
   :members:
   :undoc-members:
   :show-inheritance:

JVL Tab Module
----------------

JVLモード（発光素子 IV-輝度測定 / 暗IV測定共通）タブのViewです。OPVタブと同一構成に
加え、輝度計(BM9)グループと2ページ構成（I-V / I-V-L）のプロットタブを持ちます。

.. automodule:: views.jvl_tab
   :members:
   :undoc-members:
   :show-inheritance:

Dual Channel Tab Module
--------------------------

2ch活用モード（モードA: 2ch低ノイズ計測 / モードB: 2素子同時計測）タブのViewです。
モードB選択時は、チャンネルA・チャンネルBそれぞれ独立した測定設定グループと、
発光素子モードの二重選択を防ぐ排他制御UIを提供します。

.. automodule:: views.dual_channel_tab
   :members:
   :undoc-members:
   :show-inheritance:

Plot Buffer Module
--------------------

pyqtgraphのプロットバッファとグラフスタイル適用を専門に管理するモジュールです。
測定開始時にバッファを作り直し、1点ごとに ``setData()`` で更新することで、
測定点数が増えてもカーブが増殖しないようにします。線幅・シンボルサイズ・目盛
フォント・グリッドなどのグラフ表示スタイルの適用も担います。

.. automodule:: views.plot_buffer
   :members:
   :undoc-members:
   :show-inheritance:

Settings Dialogs Module
-----------------------

機器設定（``DeviceSettingsDialog``）および表示の設定（``DisplaySettingsDialog``）を
提供するモジュールです。OPV/JVL/2ch活用モードA/Bの各タブに個別に存在していた接続先
入力欄を、メニューバーから呼び出す1つの設定ダイアログに統合します。

.. automodule:: views.dialogs
   :members:
   :undoc-members:
   :show-inheritance:

Data Viewer Module
--------------------

「ファイル」→「データを開く」で使う、測定CSVの表示専用ビューアです。過去に保存した
測定CSVを、アプリを再測定せずに単体で読み込んでグラフ表示できます。CSVの解析
（``parse_measurement_csv``）はQt非依存の純Pythonロジックとして分離されています。

.. automodule:: views.data_viewer
   :members:
   :undoc-members:
   :show-inheritance:

Save Confirmation Module
--------------------------

測定開始前の「上書き保存」確認ダイアログを提供する共有ヘルパーです。保存予定のCSV
パスが既に存在する場合のみ確認ダイアログを表示します。

.. automodule:: views.save_confirm
   :members:
   :undoc-members:
   :show-inheritance:

Theme Module
--------------

アプリケーションのスタイルシートテーマ（ダークテーマ）とレイアウト寸法定数を
定義するモジュールです。

.. automodule:: views.theme
   :members:
   :undoc-members:
   :show-inheritance:

No-Scroll SpinBox Widget Module
----------------------------------

マウスホイールでの誤操作を防止し、増減ボタンを非表示にしたスピンボックスウィジェット
です。``QScrollArea`` 内に配置された数値入力欄が、パネル全体をスクロールしようとした
際に意図せず値変更されてしまう問題を防ぎます。

.. automodule:: views.widgets.no_scroll_spinbox
   :members:
   :undoc-members:
   :show-inheritance:
