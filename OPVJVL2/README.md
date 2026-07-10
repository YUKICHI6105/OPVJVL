# JVL Measurement GUI

OPV(有機太陽電池)特性評価用の J-V-L(電流密度-電圧-輝度)測定 統合GUI。
Keithley 2612B と TOPCON BM9 輝度計を PyQt6 の GUI から操作する。

## 構成

```
instruments.py           Keithley2612B(PyVISA+TSP)、BM9のドライバクラス
measurement_worker.py     測定ループを実行するQThreadワーカー
main_gui.py                PyQt6メインウィンドウ(エントリーポイント)
requirements.txt
```

## 元コードからの変更点

- `keithley2600` パッケージへの依存を廃止し、**PyVISA + TSPコマンド**で
  Keithley 2612Bを直接制御するようにした(`instruments.Keithley2612B`)。
  - TSP(Test Script Processor)は Keithley 26xx 独自の Lua ベースコマンド体系で、
    元の `keithley2600` パッケージも内部的にはこの方式を使っている。
  - `smua.source.levelv = 1.0` のようなコマンドを `write()` で直接送信し、
    測定値は `print(smua.measure.i())` を送って `read()` で受け取る方式。
- `InstrumentsControl.py` の `BM9` クラスを整理し、接続エラーを
  `InstrumentError` として明示的に扱うようにした。
- 測定ロジック(`OPV_measurement.py` / `_ver2.py`)を1つの
  `MeasurementWorker` に統合し、`channel_mode` で
  - `"single"`: smuaのみで掃引・測定(元の `OPV_measurement.py` 相当)
  - `"dual"`: smua掃引・smub=0V固定で電流測定(元の `_ver2.py` 相当)
  を切り替えられるようにした。
- 輝度測定(BM9)はGUI上のチェックボックスでON/OFFできる。

## 積分時間(NPLC)について【要確認】

元コードの `integration_time = 0.5` を `k.set_integration_time()` に渡していましたが、
`keithley2600` パッケージのこのメソッドは実際には **NPLC**(Number of Power Line Cycles、
電源周波数の何周期分積分するか。0.001〜25の範囲、日本の50/60Hzなら1NPLC=1/50秒 または 1/60秒)
を指定する仕様です。「秒」ではありません。

このGUI・ワーカーでは元の値をそのまま **NPLC値** として引き継いでいます
(`nplc = 0.5` の場合、50Hz環境で10ms相当)。もし元々「0.5秒待ちたい」という意図だった場合は、
`delay_time` 側の待機時間と混同している可能性があるため、実際の積分時間の意図を確認してください。

## 実行方法

```bash
pip install -r requirements.txt
python main_gui.py
```

### VISAバックエンドについて

- Windowsで NI-VISA / Keysight VISA(`visa64.dll`)が導入済みの環境では、
  `Keithley2612B(resource, visa_library="C:\\WINDOWS\\system32\\visa64.dll")`
  のようにDLLパスを指定してください(GUI側では現状 `@ivi` 固定にしているため、
  別のVISAライブラリを使う場合は `main_gui.py` の `MeasurementConfig` 生成部分に
  `visa_library` 入力欄を追加する想定です)。
- ベンダーVISAを入れたくない場合は `pyvisa-py` のみで動作します
  (USB計測器の場合はさらに `pyusb` + `libusb` が必要になることがあります)。

## 未対応・今後の拡張候補

- USB6001(NI-DAQ)の統合は今回のスコープ外(必要になれば `instruments.py` に
  `USB6001` クラスを追加し、`MeasurementConfig` / `MeasurementWorker` に
  DAQ関連の設定を足す形で拡張可能)。
- SCPI互換モードへの切り替え(TSPの代わりに `:SOUR:VOLT` 等)。
- 測定中のCSV逐次書き込み(現状は測定完了後に一括保存)。
- Jsc/Voc/FF/効率などの太陽電池パラメータの自動算出・表示。
