# 調査レポート: EQEリポジトリとの構造比較・OPVJVLの不足/不整合分析

- 調査日: 2026-07-11
- 対象:
  - EQE: `..\EQE`(参照実装。src配下 約6,500行)
  - OPVJVL: 本リポジトリ `src\`(約4,800行)+ `tests\` + `docs\`
- 本レポートはコード変更を伴わない調査結果のみをまとめたもの。

---

## 1. EQEリポジトリの構造(参照実装の把握)

### 1-1. ディレクトリ構成と層の分け方

```
EQE/src/
├── main.py                        # エントリポイント + クラッシュハンドラ(sys.excepthook)
├── controllers/                   # ロジック層(EQEは厳密にはMVVMではなく MVC+Protocol)
│   ├── measurement_controller.py  # 測定/IVスレッドのライフサイクル管理 (493行)
│   ├── calculation_controller.py  # EQE計算・保存 (522行)
│   └── settings_controller.py     # 設定ロード/セーブとUI反映 (269行)
├── eqe_core/                      # Qt非依存に近いコア層
│   ├── params.py                  # MeasurementParams等のdataclass
│   ├── view_interface.py          # ★ typing.Protocol による View契約 (125行)
│   ├── data/ (calculation.py, result_saver.py)
│   ├── instruments/               # base_smu / base_mono + 実機 + dummy_*
│   └── threads/measurement.py     # MeasurementThread / IVCheckThread (QThread継承)
├── utils/system/
│   ├── logger.py                  # ★ カスタムロガー(DEBUG1〜3レベル、ファイル+コンソール)
│   ├── paths.py                   # ★ AppData(Roaming/Local)への設定・ログ配置、旧配置からの移行
│   ├── persistence.py             # ★ settings.json 永続化 + DEFAULT_SETTINGS(単一の真実)
│   ├── version.py                 # __version__ 一元管理
│   └── win32_utils.py             # ★ prevent_sleep(測定中のWindowsスリープ防止)
└── views/
    ├── main_window.py (1184行)    # UI構築(コード構築、.uiなし)
    ├── bias_panel.py / dialogs.py / log_console.py / plot_controller.py
    ├── scientific_axis.py / theme.py (ライト/ダーク/システム追従、404行)
```

その他: `build_pipeline/`(PyInstaller配布物)、`docs/source/conf.py`(Sphinx)、
`CODE_CONVENTIONS.md`、`BUG_REVIEW_DECISIONS.md`、`README.md`。

### 1-2. EQEの設計上の特徴(OPVJVLが倣うべき点)

| 観点 | EQEの実装 |
|---|---|
| View抽象化 | `eqe_core/view_interface.py` の `MeasurementView`/`CalculationView`(typing.Protocol)。Controllerは Protocol型にのみ依存し、Qtウィジェットを知らない。テストは `src/tests/test_view_mock.py` のモックViewで GUI無しにロジック検証 |
| スレッド | `QThread` 継承(`MeasurementThread`/`IVCheckThread`)。`stop()`で協調的中断、`finally`で機器切断・出力OFF・退避(mono 0nm復帰)を保証。`smu_released`/`mono_reset_finished` など終了フェーズを細分化したシグナル設計 |
| スレッド内対話 | `request_shield_removal`/`request_filter_change` シグナル + `wait_for_*`フラグ + `msleep(100)`ポーリングで「測定中にユーザー操作を待つ」パターンを実現 |
| 機器抽象化 | `base_smu.py`/`base_mono.py` + 実機(`keithley_2612.py`/`bsm25c_mono.py`) + `dummy_smu.py`/`dummy_mono.py`。アドレス欄に `DUMMY` と入力するだけで実行時にモックへ切替(measurement_controller.py:141) |
| 設定永続化 | `persistence.py` の `DEFAULT_SETTINGS`(約40キー: 測定条件・機器アドレス・グラフ体裁・テーマ・ログレベルまで)を単一の真実として、起動時 `ensure_settings_exist()`、保存はマージ書き込み。保存先は `paths.py` がAppDataに解決 |
| エラー処理 | main.pyの `sys.excepthook` でクラッシュをログ+ダイアログ表示。スレッド内は全例外を `error` シグナル化。`on_error` はモーダル表示順序の競合まで考慮(measurement_controller.py:401-421) |
| ロギング | `logger.py` に DEBUG1/2/3 の独自レベル、ファイル+GUIログコンソール(`views/log_console.py`)。設定でレベル変更可 |
| 長時間測定対策 | `win32_utils.prevent_sleep()` で測定中のスリープ抑止 |
| 配布 | `build_pipeline/`(PyInstaller)+ `.claude/skills/build_app` |

---

## 2. OPVJVLリポジトリの現状構造

### 2-1. ディレクトリ構成

```
OPVJVL/src/
├── app.py                 # エントリポイント (51行)
├── qtcompat.py            # ★ PyQt5/PyQt6互換レイヤー (98行、良く出来ている)
├── models/
│   ├── instruments/       # base.py(ABC) + keithley2400/2612b + bm9 + mock/ + registry.py
│   └── measurement/       # config.py(dataclass) + sequences.py(ジェネレータ) + result.py + csv_writer.py
├── viewmodels/            # base_viewmodel.py + opv/jvl/dual_channel + device_discovery.py
├── views/                 # main_window + opv_tab/jvl_tab/dual_channel_tab + dialogs + plot_buffer + theme + widgets/
├── workers/               # measurement_worker.py / dual_channel_worker.py (QThread)
├── utils/device_settings.py  # 機器設定のみのJSON永続化
└── resources/ui/main_window.ui  # 未使用(残置)
tests/  … conftest.py + test_models / test_viewmodels / test_views / test_integration (17ファイル)
docs/   … 要件定義書_基本設計書.md、引継ぎドキュメント.md 等
```

### 2-2. OPVJVLの層構造の評価(良い点)

- Model層(`sequences.py`/`config.py`/`result.py`/`csv_writer.py`)はQt非依存で、`sleep_fn`注入・`is_aborted`コールバックによりテスタブル。EQEの「スレッド内に測定ロジック直書き」より筋が良い。
- 機器抽象化(`AbstractSourceMeter`/`AbstractLuminanceMeter` + `registry.py`ファクトリ + mockクラス)はEQEの DUMMY 方式より整理されている。モックは呼び出し回数記録(`connect_calls`等)までありテスト向き。
- `qtcompat.py`(High DPI・`qt_exec`・`enum_value`)はPyQt5/6両対応の要件を概ね満たす。
- テスト構成(モデル/ViewModel/View/統合)はEQEより充実。

---

## 3. 比較: 欠落・乖離・バグ

### 3-1. EQEにあってOPVJVLに欠けている構造・機能

| # | 欠落項目 | EQE側の該当 | OPVJVL側の現状 |
|---|---|---|---|
| 1 | **ロガー基盤**(ファイルログ・独自DEBUGレベル・GUIログコンソール) | `utils/system/logger.py`(242行)、`views/log_console.py`(262行)。全Controller/Threadが `get_logger()` でログ出力 | `logging`すら未使用。ログはタブ内`QTextEdit`への追記のみで、クラッシュ後の原因追跡手段がない |
| 2 | **クラッシュハンドラ** | `main.py:29-65` `log_uncaught_exception` を `sys.excepthook` に登録し、CRITICALログ+`QMessageBox`詳細表示 | `app.py` に無し。GUIスレッドで未捕捉例外が起きると無言で異常終了し得る |
| 3 | **測定パラメータの永続化** | `persistence.py` `DEFAULT_SETTINGS`(掃引条件・保存先・グラフ体裁・テーマ等約40キー)+ `settings_controller.py` がUIへ復元 | `utils/device_settings.py` は接続先/機器種別/モックフラグのみ。Vmin/Vmax/Vstep・NPLC・サンプル名・保存先は毎回入力し直し |
| 4 | **設定ファイルの配置戦略** | `paths.py` がAppData(Roaming/Local)に解決、旧配置からの `migrate_legacy_files()` あり | `settings.json` はプロジェクトルート直下固定(`device_settings.py:37-46`)。EXE化・多ユーザー環境で破綻する。しかも `.gitignore` に入っているためリポジトリにサンプルもない |
| 5 | **スリープ防止** | `utils/system/win32_utils.py` `prevent_sleep()`(測定開始/終了で呼ぶ: `measurement_controller.py:167,485-493`) | 無し。数十分オーダーの掃引測定中にWindowsがスリープすると測定が壊れる |
| 6 | **バージョン一元管理** | `utils/system/version.py` `__version__`(AppUserModelIDやAboutに使用) | 無し。`main_window.py:_show_about` はハードコード文字列のみ |
| 7 | **View契約(Protocol)** | `eqe_core/view_interface.py` の `MeasurementView` 等。ロジック層はProtocolにのみ依存 | 無し。逆に ViewModel が View実体(タブ)を直接保持し `tab._bind_viewmodel()` を呼ぶ(後述3-2の乖離) |
| 8 | **測定中断とUI対話**(遮光解除待ち・フィルタ交換待ちのような「スレッドを止めてユーザー確認」パターン) | `request_shield_removal`/`request_filter_change` + `wait_for_*` + `msleep`ループ(`threads/measurement.py:139-145,211-230`) | 仕組み自体が無い(OPVJVLの現行要件では必須ではないが、光照射確認等を将来入れる場合の土台が無い) |
| 9 | **中断(aborted)と正常完了の区別** | `on_meas_finished` が `thread.is_running` で中断を判定し、完了ポップアップ・自動計算を抑止(`measurement_controller.py:324-349`) | `MeasurementWorker.run()` は中断時も `finished_ok` を発火し、ViewModelは「測定完了: N点。」とログする。ユーザーには中断が成功完了に見える |
| 10 | **タスクバー/アプリID設定・起動時間計測** | `main.py:74-79`(SetCurrentProcessExplicitAppUserModelID)、起動時間ログ | 無し(優先度低) |
| 11 | **配布ビルドパイプライン** | `build_pipeline/`(PyInstaller一式)+ビルドスキル | 無し。本番機(Python3.9)への配布手段が未整備 |
| 12 | **I-V接触確認(コンタクトチェック)機能** | `IVCheckThread`(`threads/measurement.py:289-381`)+コンプライアンス超過時の自動停止シグナル | 無し(OPVJVL要件に含めるかは要判断。コンプライアンス到達の検知・通知も無い) |
| 13 | **README / CODE_CONVENTIONS** | `README.md`、`CODE_CONVENTIONS.md`、`BUG_REVIEW_DECISIONS.md` | ルートREADMEが無い。規約文書無し |

### 3-2. 構造がEQEと乖離している箇所とその影響

1. **ViewModel→View の逆依存(MVVM崩れ)**
   - `viewmodels/opv_viewmodel.py:31-38`(jvl/dual も同様): `OPVViewModel.__init__(opv_tab)` が `opv_tab.viewModel = self` を代入し、さらに View のプライベートメソッド `opv_tab._bind_viewmodel()` を呼ぶ。
   - EQEは「Controller は Protocol 契約にのみ依存」でGUI無しテストが可能。OPVJVLはViewModelがViewの実装詳細(結線メソッド名)を知っており、層の依存方向が逆転している。
   - **さらにこれが下記3-3(1)の二重結線バグの直接原因になっている。**

2. **設定ダイアログとタブの状態二重化**
   - 機器設定は `MainWindow._apply_device_settings()`(`views/main_window.py:127-156`)がタブのプライベート属性(`_device_type` 等)へ注入する方式。EQEの settings_controller のような「設定→UI→保存」の一方向フローに比べ、設定の所有者が MainWindow/タブ/ダイアログ に分散。
   - 測定条件(掃引パラメータ)は永続化対象外のため、`DeviceSettingsDialog` と `device_settings.py` のキー集合だけが保存される非対称な設計。

3. **パッケージ構成の混乱(旧 `src/opvjvl/` パッケージ → フラット `src/` への移行が中途半端)** ※git実測で確定
   - `git status` 実測: HEAD(コミット acaff86)のツリーは `src/opvjvl/**` パッケージ構成。作業ツリーではそれが**全ファイル削除(未ステージ)**され、現行のフラットな `src/models` 等は**全て未追跡(??)**。`docs/`・`bases/` ディレクトリも丸ごと未追跡。つまり現在動かしているコードは1行もgit管理されていない。さらに:
     - `pyproject.toml:18-22`: `[project.scripts] opvjvl = "app:main"` + `packages.find where=["src"]`。この構成では `models`/`views`/`viewmodels`/`workers`/`utils` という**一般名の最上位パッケージ**がインストールされ(名前衝突リスク大)、かつ `app.py`/`qtcompat.py` は単独モジュールのため `py-modules` 指定が無く**エントリポイントが壊れる**。
     - `qtcompat.py:4-5` のdocstringは「`from opvjvl import qtcompat` を使うこと」と旧パッケージ名のまま。
     - `base_viewmodel.py:8-12` のdocstringは「View側は `bvm.PlotBuffer` を参照する」と書くが、実際のView(`views/jvl_tab.py:14`等)は `views.plot_buffer` から直接importしており記述と実装が食い違う。→ この食い違いのため `tests/conftest.py:28-42` の PlotBuffer モック差し替え(`base_viewmodel.PlotBuffer = DummyPlotBuffer`)は **View には効いていない**。
   - 直近コミット acaff86「pandasの廃止…」は `src/opvjvl/models/measurement/csv_writer.py` を標準csvモジュール化しているが、作業ツリー(フラット `src/`)の `csv_writer.py:13` は `import pandas as pd` のままで、`pyproject.toml`/`requirements-*.txt` も pandas に依存。一方フラット側は同コミットの「輝度換算(*100)・`update_reference_current`」変更は取り込んでいる。**つまりフラット化の際に一部の修正だけが失われており(部分的な巻き戻り)、「修正したはずが直っていない」という本件の症状と合致する**。修正が2つのツリーのどちらに当たるかで結果が変わる状態。

4. **`.ui`ファイルの残置**
   - `src/resources/ui/main_window.ui` は「未使用・残置」(`views/main_window.py:3-5` に明記)。実UIはコード構築でEQE方式に寄せたが、リソースが残っており混乱の元。

5. **EQEのメニュー/ステータスバー活用との差**
   - `MainWindow.setStatusBar()` は設置だけで一切使われていない(`views/main_window.py:37`)。進捗・保存結果の通知はタブ内ログのみ。

### 3-3. 明らかなバグ・未完成箇所

1. **【重大】ViewModelシグナルの二重結線 — 全タブ共通**
   - 経路: `OPVTab.__init__`(`views/opv_tab.py:41-42`)で `OPVViewModel(self)` を生成 → VM側 `__init__`(`viewmodels/opv_viewmodel.py:36-38`)が `opv_tab._bind_viewmodel()` を呼ぶ(1回目) → 直後にTab側が `self._bind_viewmodel()` を再度呼ぶ(2回目)。
   - `_bind_viewmodel()` はボタンの `clicked` は `disconnect()` してから繋ぎ直すが、**ViewModel→View のシグナル(`running_changed`/`point_measured`/`log_appended`/`error` 等)は disconnect していない**ため全て二重接続になる。
   - 影響: ログが全行2回表示、エラー時に警告ダイアログが2回出る、プロットへ同一点が2回追加、など。`views/jvl_tab.py:45-68`、`views/dual_channel_tab.py:78-120` も同一パターン。
2. **【重大】モードB(2素子同時計測)で SMU の初期化・コンプライアンス設定が行われない**
   - `models/measurement/sequences.py:135-214` `run_dual_b_sequence` は `smu.reset()` も `configure_source_voltage()` も呼ばずにいきなり `set_output(...,True)`。`ChannelConfig.compliance_current`/`nplc`(`config.py:80-81`)は**定義されているのに一切使われない**。実機では前回設定のままの電流制限・積分時間で出力ONになり、素子破壊リスクがある(run_opv/jvl/dual_a は正しく reset→configure している: `sequences.py:31-32,60-61,98-99`)。
3. **中断時も「測定完了」扱い**(3-1 #9 再掲): `workers/measurement_worker.py:58-85` は abort でも `finished_ok` を発火し、`viewmodels/*: _on_finished_ok` が「測定完了: N点。」とログ。中断/完了の区別情報がシグナルに乗っていない。
4. **`MeasurementWorker._close_instruments` のチャンネル固定**(`workers/measurement_worker.py:87-97`): 常に `set_output("default", False)` を呼ぶため、Keithley2612B(チャンネル `smua`/`smub`)では `_validate_channel` が `ValueError` を投げ、握り潰される(出力OFFの最終防衛線が2612B使用時に機能しない。ジェネレータ側 finally が唯一の防衛線になる)。
5. **モードBで発光素子チャンネル選択+BM9ポート未設定時に無警告で輝度測定が省略される**: `dual_channel_viewmodel.py:198-217`(`led_channel` があっても `config.bm9_port` が空なら黙って `use_luminance_*=False`)。JVL側は同条件をエラーにしている(`jvl_viewmodel.py:68-70`)ので非対称。
6. **バリデーション関数の重複・不使用**: `viewmodels/base_viewmodel.py:25-45` に `validate_voltage_range` 等が用意されているが、各ViewModelは同じ検証をインラインで重複実装(`opv_viewmodel.py:56-64` ほか)しており、共通関数は実質デッドコード。
7. **conftestのPlotBufferモックが効いていない**(3-2(3)参照): オフスクリーンでのpyqtgraph描画抑止という目的を果たせておらず、View系テストは実PlotBufferで動いている。
8. **`finished_ok` 発火前のCSV保存エラー時の二重通知経路**: `measurement_worker.py:76-85` はCSV保存失敗時に `error` を発火した上で `finished_ok` も発火する。ViewModel側では `_on_error` → `_reset_running_state()`(worker=None) の後に `_on_finished_ok` が来て再び `_reset_running_state()` が走る。実害は小さいが `running_changed(False)` が2回飛ぶ。
9. **`app.py` の再代入は冗長**(`app.py:39-41`): `window.opv_vm = window.opv_tab.viewModel` はGC対策と書かれているが、VMは既にタブの属性として保持されており不要(バグではない)。

### 3-4. PyQt5(Python3.9本番)/PyQt6(Python3.13開発)互換性の観点

全体としては `qtcompat.py` 経由が徹底されており大きな問題は少ないが、以下に留意:

1. **pyqtgraph のimport順序が module 内で逆転**: `views/jvl_tab.py:9-11`、`views/opv_tab.py:8-10`、`views/dual_channel_tab.py:8-10` は `import pyqtgraph as pg` を `qtcompat` より**先**に書いている。アプリ経由(`app.py` が最初に `qtcompat` をimport)なら `PYQTGRAPH_QT_LIB` 設定済みで問題ないが、これらのモジュールを単体で最初にimportすると、PyQt5/6両方入った環境でpyqtgraphが意図しないバインディングを掴む恐れがある。各Viewモジュール内でも `qtcompat` を先にimportする規約にすべき。
2. **requirements にバージョン上限が無い**: `requirements-pyqt5.txt` は `PyQt5`/`pyqtgraph`/`numpy`/`pandas` を無指定で列挙。Python3.9では `numpy>=2.1` や新しめの `pyqtgraph`/`pandas` がインストール不能または非対応になり得るため、本番環境用は上限ピン(例: `numpy<2.1`, `pyqtgraph<0.14` 等の動作確認済みバージョン)が必要。
3. **`from __future__ import annotations` は全ファイルにあり**、`dict[str, float]`・`int | None` 等の新式アノテーションは注釈内に限られている(実行時評価されないためPython3.9でも安全)ことを確認した。ただし今後 `typing.get_type_hints()` やdataclassの `field` 評価を導入すると3.9で壊れるので注意。
4. **`tests/conftest.py:23-26` の `QtWidgets.QMessageBox.StandardButton.Ok`**: PyQt5でもスコープドEnumアクセスは可能なため動くが、プロジェクト規約(enum差異は `enum_value` で吸収)からは外れている。
5. **PyQt5環境での実動作テストの証跡が無い**: venvは `.venv313`(PyQt6)のみ。`requirements-pyqt5.txt` はあるが3.9+PyQt5での起動確認手段(venv・CI・チェックスクリプト)が存在しない。

---

## 4. 不足部分の重要度順リストと推奨実装方針

| 優先 | 項目 | 推奨実装方針(1-3行) |
|---|---|---|
| 1 | **リポジトリ/パッケージ構成の確定**(HEAD=`src/opvjvl`、作業ツリー=未追跡のフラット`src`という分裂状態の解消。pandas廃止修正の巻き戻りあり) | どちらのツリーを正とするか決め、HEADにのみ存在する修正(pandas廃止版csv_writer等)をフラット側へ取り込んだ上で `git add` してコミットする(現行コードが未追跡のままなのが最大のリスク)。フラット`src`を正とするなら `pyproject.toml` の `packages.find`/scripts を修正(または EQE同様に配布はPyInstaller前提とし、パッケージングを諦めて`requirements`のみに簡素化)し、`qtcompat.py`/`base_viewmodel.py` の旧`opvjvl`前提docstringを更新する。 |
| 2 | **二重結線バグの解消とMVVM依存方向の是正** | ViewModel `__init__` から `tab.viewModel = self; tab._bind_viewmodel()` を削除し、「Tabが自分でVMを生成(または注入)して1回だけ結線する」流儀に統一する。結線はTab側の責務にし、VMはViewを一切参照しない(EQEのProtocol方式に寄せるならView契約Protocolを`viewmodels`層に定義)。 |
| 3 | **モードBの `reset()`/`configure_source_voltage()` 欠落修正** | `run_dual_b_sequence` 冒頭で `smu.reset()` 後、有効チャンネルごとに `configure_source_voltage(ch, chan.compliance_current, chan.nplc)` を呼ぶ。既存テスト(`test_sequences_dual_mode_b.py`)に configure_calls の検証を追加。 |
| 4 | **中断と完了の区別** | `MeasurementWorker.finished_ok` に aborted フラグを追加(例: `finished_ok = pyqtSignal(list, str, bool)`)するか `aborted` シグナルを新設し、ViewModel/Viewで「中断しました(N点まで保存)」表示に分岐。EQE `on_meas_finished` の aborted 分岐を踏襲。 |
| 5 | **ロガー基盤 + クラッシュハンドラの導入** | EQE `utils/system/logger.py` と `main.py` の `log_uncaught_exception` をほぼ移植(PyQt6依存箇所のみ qtcompat 化)。ViewModel/Workerの `log_appended` と並行してファイルログへも出力する。 |
| 6 | **測定パラメータの永続化と設定配置** | EQE `persistence.py` 方式で `DEFAULT_SETTINGS` に掃引条件・サンプル名・保存先を追加し、測定開始時に保存/起動時に復元。保存先はEQE `paths.py` を移植してAppDataへ(ルート直下 `settings.json` からの移行処理付き)。 |
| 7 | **スリープ防止(win32)** | EQE `utils/system/win32_utils.py` をそのまま移植し、各ViewModelの `running_changed(True/False)` に連動して `prevent_sleep()` を呼ぶ。 |
| 8 | **`_close_instruments` のチャンネル汎用化** | Workerにチャンネル一覧を渡す(または `smu.channels` を参照して全チャンネル `set_output(ch, False)`)。「default固定/smua+smub固定」のハードコードを排除して1つのWorkerに統合できる。 |
| 9 | **モードBのBM9未設定警告 / バリデーション共通化** | `start_mode_b` で「発光素子チャンネルあり&bm9_port空」をエラーにする(JVLと同一文言)。各VMのインライン検証を `base_viewmodel.validate_*` 呼び出しに置換。 |
| 10 | **pandas廃止の完遂(方針が廃止なら)** | `csv_writer.py` の DataFrame 生成を `csv` 標準モジュール書き出しへ置換し、`pyproject.toml`/`requirements-*.txt` から pandas を削除。列名・ヘッダはテスト(`test_csv_writer.py`)で固定。 |
| 11 | **PyQt5実環境の検証手段** | `.venv39`(gitignore済み)を作成する手順をREADMEに明記し、`python -m pytest` と起動スモークをPyQt5側でも回す簡単なスクリプトを用意。requirementsに動作確認済みバージョンの上限を付ける。 |
| 12 | **import順の規約徹底** | 各Viewモジュールで `qtcompat` を pyqtgraph より先にimportするよう並べ替え(3ファイル)。conftestの `QMessageBox.StandardButton` も `enum_value` 経由に統一。 |
| 13 | **conftestのPlotBufferモック修正** | Viewが実際にimportしている `views.plot_buffer.PlotBuffer` をmonkeypatchするか、docstringどおりViewを `bvm.PlotBuffer` 参照に変更して整合させる。 |
| 14 | **バージョン管理・About・README・.ui残置整理** | `utils/version.py`(`__version__`)を新設しAboutに表示。ルートREADME作成。未使用 `resources/ui/main_window.ui` は削除するか「参照用」ディレクトリへ移動。 |
| 15 | **(要件次第)接触確認I-V・コンプライアンス到達通知** | EQE `IVCheckThread` 相当を `sequences.py` にジェネレータとして追加し、`abs(I)>=compliance` で `compliance_hit` を通知するシグナルをWorkerに追加。 |

---

## 5. 補足: OPVJVLがEQEより優れている点(退行させないこと)

- Qt非依存の測定シーケンス(ジェネレータ+`sleep_fn`注入)と機器レジストリ/モック群は、EQEの「QThread内ロジック直書き+DUMMYアドレス切替」より保守性・テスト性が高い。EQEへ寄せる際もこの層は維持すべき。
- `qtcompat.py` による PyQt5/6 両対応はEQE(PyQt6専用)に無い本プロジェクト固有の必須要件であり、今後追加するEQE由来コード(logger/persistence/win32_utils等)も必ず qtcompat 経由に書き換えて移植すること。
- テストスイート(モデル/VM/View/統合の4階層、モックの故障注入 `simulate_connect_failure`/`fail_after_n_points`)はEQEより体系的。

(以上)
