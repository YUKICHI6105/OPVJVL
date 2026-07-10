## B-6. Qt Designerレイアウト仕様（最重要）

### B-6-1. `.ui`ファイルの構成方針

タブ数が多く各タブの設定項目も多いため、**1タブ=1`.ui`ファイル**の構成を採る（Qt Designer初心者にとって1画面が肥大化しすぎるのを防ぐため）。

```
src/opvjvl/resources/ui/
├── main_window.ui        # QMainWindow本体。空のQTabWidgetを持つだけ
├── opv_tab.ui             # QWidgetフォーム(トップレベル)。OPVモードの全ウィジェット
├── jvl_tab.ui             # QWidgetフォーム。JVLモードの全ウィジェット
└── dual_channel_tab.ui    # QWidgetフォーム。2ch活用モードの全ウィジェット
```

`main_window.py`で各`.ui`をロードしたQWidgetインスタンスを生成し、`mainTabWidget.addTab(...)`でコード側から挿入する（Designer上で3タブぶんをすべて1ファイルに詰め込むと編集が煩雑になるため）。

### B-6-2. オブジェクト階層とobjectName命名規則

**共通規則**: `objectName`はcamelCase。タブ固有ウィジェットには接頭辞（`opv_`, `jvl_`, `dual_`）を付与し、モードBのチャンネル固有ウィジェットにはさらに`chA_`/`chB_`を付与する。

```
MainWindow (QMainWindow, objectName="MainWindow")
└── centralWidget (QWidget)
    └── mainTabWidget (QTabWidget)
        ├── [タブ0] "OPVモード" ← opv_tab.ui をロードしたQWidgetを挿入
        ├── [タブ1] "JVLモード" ← jvl_tab.ui
        └── [タブ2] "2ch活用モード" ← dual_channel_tab.ui
    ├── menuBar (QMenuBar)
    │   ├── menuFile ("ファイル") → actionExit
    │   └── menuHelp ("ヘルプ") → actionAbout
    └── statusbar (QStatusBar, objectName="statusbar")
```

**OPVタブ（`opv_tab.ui`）階層**:

```
OPVTabForm (QWidget, トップレベル)
└── opv_rootLayout (QHBoxLayout)
    └── opv_splitter (QSplitter, orientation=Horizontal)
        ├── opv_settingsScrollArea (QScrollArea, widgetResizable=true)
        │   └── opv_settingsContainer (QWidget)
        │       └── opv_settingsLayout (QVBoxLayout)
        │           ├── opv_connectionGroupBox (QGroupBox "接続設定")
        │           │   └── opv_connectionFormLayout (QFormLayout)
        │           │       ├── "機器選択:" — opv_deviceTypeCombo (QComboBox)
        │           │       ├── "モック使用:" — opv_useMockCheckBox (QCheckBox)
        │           │       ├── "接続先(COM/VISA):" — opv_connectionCombo (QComboBox, editable)
        │           │       └── (再検索ボタン) opv_refreshDevicesButton (QPushButton) ※QHBoxLayoutで接続先と横並び
        │           ├── opv_sweepGroupBox (QGroupBox "電圧掃引条件")
        │           │   └── opv_sweepFormLayout (QFormLayout)
        │           │       ├── "Vmin:" — opv_vMinSpin (QDoubleSpinBox)
        │           │       ├── "Vmax:" — opv_vMaxSpin (QDoubleSpinBox)
        │           │       ├── "Vstep:" — opv_vStepSpin (QDoubleSpinBox)
        │           │       └── "繰り返し回数:" — opv_iterationSpin (QSpinBox)
        │           ├── opv_timingGroupBox (QGroupBox "タイミング/コンプライアンス")
        │           │   └── opv_timingFormLayout (QFormLayout)
        │           │       ├── "積分時間(NPLC):" — opv_nplcSpin (QDoubleSpinBox)
        │           │       ├── "遅延時間[s]:" — opv_delaySpin (QDoubleSpinBox)
        │           │       └── "コンプライアンス電流[A]:" — opv_complianceSpin (QDoubleSpinBox)
        │           ├── opv_saveGroupBox (QGroupBox "保存")
        │           │   └── opv_saveFormLayout (QFormLayout)
        │           │       ├── "サンプル名:" — opv_sampleNameEdit (QLineEdit)
        │           │       └── "保存先:" — [opv_saveDirEdit (QLineEdit) + opv_browseSaveDirButton (QPushButton)] (QHBoxLayout)
        │           ├── opv_runGroupBox (QGroupBox "実行")
        │           │   └── opv_runLayout (QHBoxLayout)
        │           │       ├── opv_startButton (QPushButton "測定開始")
        │           │       └── opv_stopButton (QPushButton "中断", enabled=false)
        │           └── (Vertical Spacer)
        └── opv_displayPanel (QWidget)
            └── opv_displayLayout (QVBoxLayout)
                ├── opv_progressBar (QProgressBar)
                ├── opv_plotWidget (QWidget → **promote先**: pyqtgraph.PlotWidget)
                └── opv_logGroupBox (QGroupBox "ログ")
                    └── opv_logLayout (QVBoxLayout)
                        └── opv_logTextEdit (QTextEdit, readOnly=true)
```

**JVLタブ（`jvl_tab.ui`）**: OPVタブと同一構成に加え、`opv_luminanceGroupBox`相当を追加。

```
jvl_luminanceGroupBox (QGroupBox "輝度計(BM9)")
└── jvl_luminanceLayout (QVBoxLayout)
    ├── jvl_useLuminanceCheckBox (QCheckBox "BM9で輝度も測定する(OFFで暗IV測定)")
    └── jvl_luminanceFormLayout (QFormLayout)
        └── "ポート:" — jvl_bm9PortCombo (QComboBox, editable) + jvl_refreshBm9PortsButton
```

表示パネルは`QTabWidget jvl_plotTabWidget`を挟み、2ページ構成:
- ページ0 "I-V": `jvl_ivPlotWidget` (promoted PlotWidget)
- ページ1 "I-V-L": `jvl_ivlPlotWidget` (promoted PlotWidget、右軸に輝度を重ね描画。既存`OPVJVL2/main_gui.py`の`ViewBox`二重化パターンをコードで実装)

**2ch活用モードタブ（`dual_channel_tab.ui`）**:

```
DualChannelTabForm (QWidget)
└── dual_rootLayout (QVBoxLayout)
    ├── dual_modeSelectRow (QHBoxLayout)
    │   ├── "動作モード:" (QLabel)
    │   └── dual_modeSelectCombo (QComboBox: "モードA: 2ch低ノイズ計測" / "モードB: 2素子同時計測")
    └── dual_modeStack (QStackedWidget)
        ├── [page0] dual_modeAPage (QWidget)
        │   └── dual_a_splitter (QSplitter, Horizontal)
        │       ├── dual_a_settingsScrollArea → dual_a_settingsContainer
        │       │   ├── dual_a_connectionGroupBox ("接続設定": dual_a_useMockCheckBox, dual_a_connectionCombo)
        │       │   ├── dual_a_deviceModeGroupBox ("計測対象": dual_a_deviceModeCombo [太陽電池/発光素子])
        │       │   ├── dual_a_sweepGroupBox (dual_a_vMinSpin/vMaxSpin/vStepSpin/iterationSpin)
        │       │   ├── dual_a_timingGroupBox (dual_a_nplcSpin/delaySpin/complianceSpin)
        │       │   ├── dual_a_luminanceGroupBox (dual_a_bm9PortCombo, deviceMode=発光素子でのみenabled)
        │       │   ├── dual_a_saveGroupBox (dual_a_sampleNameEdit, dual_a_saveDirEdit+browseButton)
        │       │   └── dual_a_runGroupBox (dual_a_startButton, dual_a_stopButton)
        │       └── dual_a_displayPanel (dual_a_progressBar, dual_a_plotWidget[promoted], dual_a_logTextEdit)
        └── [page1] dual_modeBPage (QWidget)
            └── dual_b_rootLayout (QVBoxLayout)
                ├── dual_b_connectionGroupBox ("接続設定(2612B共通)": dual_b_useMockCheckBox, dual_b_connectionCombo)
                ├── dual_b_channelsSplitter (QSplitter, Horizontal)
                │   ├── dual_channelAGroupBox (QGroupBox "チャンネルA (smua)")
                │   │   └── dual_chA_formLayout (QFormLayout)
                │   │       ├── dual_chA_enableCheckBox (QCheckBox "有効")
                │   │       ├── "計測対象:" — dual_chA_deviceModeCombo (太陽電池/発光素子)
                │   │       ├── "Vmin/Vmax/Vstep:" — dual_chA_vMinSpin/vMaxSpin/vStepSpin
                │   │       ├── "繰り返し回数:" — dual_chA_iterationSpin
                │   │       ├── "NPLC/遅延:" — dual_chA_nplcSpin/delaySpin
                │   │       ├── dual_chA_luminanceGroupBox ("輝度計測(BM9共有)": dual_chA_useBm9CheckBox)
                │   │       └── "サンプル名:" — dual_chA_sampleNameEdit
                │   └── dual_channelBGroupBox (QGroupBox "チャンネルB (smub)")
                │       └── dual_chB_formLayout (同様に dual_chB_* )
                ├── dual_b_bm9GroupBox ("輝度計(BM9)ポート": dual_b_bm9PortCombo)  ※チャンネル横断で1つのみ
                ├── dual_b_saveGroupBox (dual_b_saveDirEdit + dual_b_browseSaveDirButton)
                ├── dual_b_runGroupBox (dual_b_startButton, dual_b_stopButton, dual_b_progressBar)
                └── dual_b_displayTabWidget (QTabWidget)
                    ├── [page0] "チャンネルA" — dual_chA_plotWidget (promoted PlotWidget)
                    ├── [page1] "チャンネルB" — dual_chB_plotWidget (promoted PlotWidget)
                    └── (共通) dual_b_logTextEdit (QTextEdit, readOnly) をタブ下部に配置
```

**モードB排他制御（発光素子は1チャンネルまで）のUI表現**: `.ui`ファイル自体には条件分岐は書けないため、`dual_chA_deviceModeCombo`と`dual_chB_deviceModeCombo`の`currentIndexChanged`シグナルをViewModel側の`on_channel_a_mode_changed`/`on_channel_b_mode_changed`スロットに接続し、一方が「発光素子」を選択した際にもう一方のコンボから「発光素子」項目を`removeItem`/再構築（またはQStandardItemModelの`setEnabled(False)`）する形でコード側から動的制御する。

### B-6-3. ウィジェット種類・レイアウト種別まとめ表

| 目的 | ウィジェット種類 | 配置レイアウト |
|---|---|---|
| タブ切替 | QTabWidget | QMainWindowのcentralWidget直下 |
| 左右分割(設定/表示) | QSplitter (Horizontal) | 各タブのルートQHBoxLayout内 |
| 設定パネルのスクロール対応 | QScrollArea + 内部QWidget | 左ペイン |
| 機能グルーピング | QGroupBox | QVBoxLayout内に縦積み |
| ラベル+入力の対応 | QFormLayout | 各QGroupBox内 |
| 数値入力(電圧/時間/電流) | QDoubleSpinBox | QFormLayoutの値側 |
| 整数入力(繰り返し回数) | QSpinBox | 同上 |
| 機種/モード選択 | QComboBox | 同上 |
| ON/OFF切替 | QCheckBox | QFormLayoutまたは単独行 |
| テキスト入力(サンプル名/ポート) | QLineEdit / QComboBox(editable) | 同上 |
| ディレクトリ選択 | QLineEdit + QPushButton | QHBoxLayoutで横並び |
| 開始/中断 | QPushButton (objectName末尾 `startButton`/`stopButton`でQSS適用) | QHBoxLayout |
| 進捗表示 | QProgressBar | 表示パネル上部 |
| グラフ表示 | QWidget→PlotWidgetへpromote | 表示パネル中央 |
| ログ表示 | QTextEdit (readOnly) | 表示パネル下部 |
| モードA/B切替 | QComboBox + QStackedWidget | dual_channel_tabルート |
| チャンネルA/B横並び | QSplitter (Horizontal) または QHBoxLayout | dual_modeBPage内 |

### B-6-4. `.ui`ファイルの命名・配置場所

- 配置場所: `src/opvjvl/resources/ui/`
- ファイル名: `main_window.ui`, `opv_tab.ui`, `jvl_tab.ui`, `dual_channel_tab.ui`（すべてsnake_case、拡張子`.ui`）
- 実行時ロードは`importlib.resources`または`pathlib.Path(__file__).parent / "resources/ui/xxx.ui"`でパッケージ相対パス解決する（PyInstaller等で将来配布する場合も考慮し、ハードコードの絶対パスは使わない）。

### B-6-5. Qt Designerでの配置作業手順（初心者向け）

1. **フォーム作成**: Qt Designer起動 → 「新規フォーム」→ タブ単体の`.ui`を作る場合は「Widget」テンプレートを選択（`QMainWindow`を選ぶのは`main_window.ui`のみ）。
2. **オブジェクト名の付け方**: 各ウィジェットを配置したら、プロパティエディタの`objectName`欄で本設計書のB-6-2節に従った名前を即座に設定する（Designerの自動採番`groupBox_2`等をそのまま残さない）。命名は「タブ接頭辞\_役割」の順（例: `opv_vMinSpin`）。
3. **レイアウト適用**: ウィジェットを複数配置したら、選択→右クリック→「レイアウト」→ 該当するもの（`Lay Out Vertically`=QVBoxLayout, `Lay Out in a Form Layout`=QFormLayout等）を適用する。レイアウト自体にも`objectName`を設定する（例: `opv_sweepFormLayout`）。
4. **QGroupBoxでのグルーピング**: 関連ウィジェット群を選択した状態で「レイアウト」→「グループボックスの中にレイアウトする」は無いため、先にQGroupBoxをパレットから配置し、その中にウィジェットをドラッグ&ドロップしてから上記3のレイアウト適用を行う。
5. **QSplitterの適用**: 左右2ペインを作る場合、2つのコンテナウィジェット（QScrollAreaとQWidget等）を選択した状態で右クリック→「レイアウト」→「Splitter(横)の中にレイアウトする」を選ぶと自動的にQSplitterに変換される。
6. **PlotWidgetのpromote手順（重要）**:
   1. パレットから通常の`QWidget`をドラッグし、グラフを表示したい位置に配置する。
   2. `objectName`を最終的な名前（例: `opv_plotWidget`）に設定する。
   3. そのウィジェットを右クリック→「昇格されたウィジェット (Promote to...)」を選択。
   4. ダイアログで以下を入力する。
      - **昇格されたクラス名 (Promoted class name)**: `PlotWidget`
      - **ヘッダファイル (Header file)**: `pyqtgraph` （※Pythonモジュール名。`.h`拡張子は付けない。「グローバルインクルード」チェックは外したままでよい）
   5. 「追加」ボタン→対象ウィジェットを選択した状態で「昇格する」ボタンをクリックして確定する。
   6. 以後、同じ`PlotWidget`への昇格は「昇格されたウィジェットの一覧」に登録済みとして再利用でき、2つ目以降のPlotWidgetは既存の昇格定義を選ぶだけでよい（Header file等の再入力は不要）。
   7. **注意**: Designer上のプレビュー（フォームプレビュー）では昇格されたウィジェットはプレースホルダのQWidget外観のまま表示され、実際のpyqtgraphグラフ外観にはならない。実際の見た目は`uic.loadUi()`でPythonから読み込んで実行した時にのみ確認できる。
7. **保存**: `.ui`ファイルは前述の`resources/ui/`配下に保存する。Gitでの差分レビューをしやすくするため、Designerの「名前を付けて保存」時にファイル名の大文字小文字・パスを本設計書の命名規則と厳密に一致させる。
8. **Python側のロード**: 各Viewクラスの`__init__`で以下のように読み込む（PyQt5/6共通、`qtcompat`経由）。
   ```python
   from opvjvl import qtcompat
   from opvjvl.qtcompat import QtWidgets

   class OPVTab(QtWidgets.QWidget):
       def __init__(self, parent=None):
           super().__init__(parent)
           ui_path = Path(__file__).parent.parent / "resources" / "ui" / "opv_tab.ui"
           qtcompat.uic.loadUi(str(ui_path), self)
           # これ以降 self.opv_vMinSpin 等、.ui内のobjectNameがそのまま属性として使える
   ```