ViewModels
==========

Viewから見える状態（プロパティ）とコマンド（スロット）を公開する層です。入力値
バリデーション（Vmax>=Vmin、2ch活用モードBの発光素子二重選択禁止等）、
Worker（QThread）の生成・破棄、そのシグナルのView向け中継を担います。機器制御
ロジックやCSV書式などの業務ロジックは一切持たず、Model層に委譲します。

Base ViewModel Helpers Module
--------------------------------

ViewModel層で共通に使う小さなヘルパー群です。バリデーション・ログ整形部分は
GUIコンポーネントへの依存を排除した純粋なロジックとして提供されます。

.. automodule:: viewmodels.base_viewmodel
   :members:
   :undoc-members:
   :show-inheritance:

OPV ViewModel Module
-----------------------

OPVモード（太陽電池 JV/IV特性測定）タブのViewModelです。

.. automodule:: viewmodels.opv_viewmodel
   :members:
   :undoc-members:
   :show-inheritance:

JVL ViewModel Module
-----------------------

JVLモード（発光素子IV-輝度測定/暗IV測定共通）タブのViewModelです。

.. automodule:: viewmodels.jvl_viewmodel
   :members:
   :undoc-members:
   :show-inheritance:

Dual Channel ViewModel Module
--------------------------------

2ch活用モード（モードA: 2ch低ノイズ計測 / モードB: 2素子同時計測）タブの
ViewModelです。モードBの排他制御バリデーション（発光素子モードを同時に選択
できるチャンネルは最大1つ）を担います。

.. automodule:: viewmodels.dual_channel_viewmodel
   :members:
   :undoc-members:
   :show-inheritance:

Device Discovery Module
--------------------------

COMポート/VISAリソースの列挙ヘルパーです。各Viewの「再検索」ボタンから
呼ばれ、pyserial/pyvisaが未インストールの環境でもクラッシュせず空リストを
返します。

.. automodule:: viewmodels.device_discovery
   :members:
   :undoc-members:
   :show-inheritance:
