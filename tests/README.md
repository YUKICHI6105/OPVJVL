# テストの検証範囲

追加前に、対象の振る舞いを担当する既存テストを確認する。

| 検証すること | 主なテスト |
| --- | --- |
| 電圧列、折り返し点、繰り返し、往路点数 | `test_models/test_hysteresis_voltage_list.py` |
| CSV方向列の空データ・往路中断・折り返し・完走 | `test_models/test_hysteresis_csv.py`（共通writer） |
| 各モードからCSVへの条件伝達、別名保存、完了後のボタン復帰 | `test_integration/test_hysteresis_csv_save.py` |
| BM9ありのJVL保存とモードAのsmub採用 | `test_integration/test_end_to_end_mock_measurement.py` |
| チャネル別中断・再測定・接触確認の併用 | `test_integration/test_hysteresis_csv_save.py` |
| アラームの各モードからの呼び出し | `test_views/test_completion_feedback.py` |
| アラーム無効化・音源保持・試聴・設定保存 | `test_views/test_alarm_settings.py`、`test_utils/test_alarm_library.py` |
| グラフの表示切替と実データの変換 | `test_views/test_plot_buffer.py`、`test_views/test_data_viewer.py` |
| 機器の排他と安全な出力停止 | `test_views/test_exclusive_locks.py`、`test_models/test_sequences_*.py`、`test_workers/` |

2026-11の整理では、共通writerの境界値と全モードの直積をやめ、モード別の
引数伝達は統合テストに任せた。往路点数は同じ入力を生成する電圧列テストへ移した。
ウィジェットの存在・固定された配置順だけを確認するテストは外し、入力値の反映や
保存結果などの振る舞いを検証するテストを残した。

GUIテストで輝度軸を作る場合は、既存のfixtureに倣ってViewBoxのリンクを解除してから
破棄する。省略すると、破棄済みQtオブジェクトへのアクセスでクラッシュすることがある。
