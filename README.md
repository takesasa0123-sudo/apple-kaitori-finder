# 📱 iPhone 18 買取価格 自動収集・比較・トレンド分析ツール

国内・中華系の主要買取店（**買取ルデヤ**、**森森買取**、**買取一丁目**、**買取wiki**、**買取商店**、**モバステ** 等 **全14店舗**）から、iPhone 18 シリーズ（iPhone 18 Pro Max / iPhone 18 Pro 全32モデル）の最新買取価格を自動取得し、店舗間での価格比較、最高買取店判定、想定利益（還元率）の分析、過去からの価格変動検知、および **HTMLダッシュボード / Excel / CSV / JSON レポート** の自動生成を行う総合プラットフォームです。

---

## ✨ 主な機能

1. **国内主要14店舗のリアルタイム一括収集**
   - **買取ルデヤ** (kaitori-rudeya.com)
   - **森森買取** (morimori-kaitori.jp)
   - **買取一丁目** (1-chome.com)
   - **買取wiki** (kaitori.wiki)
   - **買取商店** (kaitorishouten-co.jp)
   - **モバステ** (pastec.net)
   - **モバイル一番**
   - **携帯空間**
   - **買取楽園**
   - **ゲストモバイル**
   - **ドラゴンモバイル**
   - **買取ソムリエ**
   - **モバイルミックス**
2. **iPhone 18 全32モデルへの完全名寄せ統合**
   - 各モデル（Pro / Pro Max 各4容量 × 4色 = 計32機種）に14店舗の価格を横並びで完全統合。
   - 13桁のJANコード（例: `4549995734645`）も自動紐付け。
3. **時系列価格推移 & 前回比トレンド追跡**
   - 過去のスナップショットJSONから価格変動（`+2,000円 ↗`, `-1,000円 ↘`, `±0円`, `NEW`）を自動検知。
4. **定期自動巡回・常駐監視モード (`--watch`)**
   - 指定間隔（例: 30分）で定期的に価格を巡回・収集。
   - 価格が変動したモデルを自動検知し、赤枠ハイライト表示、Windows通知音（`--alert`）、およびDiscordへ即座に変動速報を送信。
5. **LINE公式アカウント (Messaging API) 毎朝自動通知 & 等価格以上限定配信**
   - **朝の最新価格レポート自動配信**: 毎朝の市場最高額、Apple公式定価比還元率TOP5、最大店舗間差額、および前回比の価格変動サマリー（📈/📉）をLINEアカウントへダイジェスト配信。
   - **🔥 等価格以上（定価以上・還元率100%以上）限定配信**: 買取価格がApple公式定価と同額以上の「損をしない・転売差益が出る」プレミアム端末のみを抽出してLINEへ通知。
   - **プッシュ通知 & 一斉配信両対応**: 送信先指定なし時は友だち全員へ一斉ブロードキャスト配信（無料枠内で利用可能）。
   - **Windowsタスクスケジューラ連携**: `run.bat` のメニュー `[7]` または `[8]`（あるいは `setup_morning_task.bat` / `setup_morning_profit_task.bat`）を実行するだけで、PC起動時に毎朝自動実行するように設定可能。
   - ※2025年3月末でサービス終了した「LINE Notify」ではなく、現行の「LINE Messaging API」に完全対応。
6. **インタラクティブ HTML ダッシュボード (Chart.js グラフ内蔵)**
   - ブラウザでダブルクリックして開くだけの美しいWeb画面 (`output/latest_dashboard.html`)。
   - **検索 & 絞り込み**: 機種名・容量・カラー・JANコード検索、ステータス別（価格上昇 ↗ / 価格下落 ↘ / 変動あり / 差額1,000円〜）フィルター。
   - **詳細モーダル**: テーブル行をクリックすると、**全14店舗の価格比較バー** と **過去の価格推移折れ線グラフ（Chart.js）** をポップアップ表示。
   - **JANコード ワンクリックコピー** 機能。
7. **デザインド Excel & CSV 出力**
   - **Excel (.xlsx)**: 前回比、最高買取価格、店舗間差額のカラーハイライト、14店舗横並び比較表、生データシート付き。
   - **CSV (.csv)**: Windows Excelでダブルクリックしても文字化けしない UTF-8 BOM（`utf-8-sig`）対応。
8. **Discord Webhook 通知連携**
   - 通常速報（TOP5高額モデル・最大価格差）および価格変動時のみの「🚨 変動検知アラート」に対応。
9. **🎨 カラー別価格差・人気色格差リサーチ（買取一丁目API直結連携）**
   - 同一容量でもカラー（バーガンディ、ブラック、シルバー、グレイシャー）による価格差（**最大21,000円〜23,000円**の格差）を自動算出・可視化。
   - 買取一丁目のリアルタイム減額データ（例: シルバー -19,000円、ブラック -12,000円等）をAPIから直取得。
   - HTMLダッシュボードに「🎨 カラー別価格差リサーチ」専用セクション＆第6のKPIカード、Excelに「カラー別価格差リサーチ」第3シート、CSVに「カラー基準差額」列を搭載。
   - LINE通知にもカラー別価格差の専用ダイジェスト・個別レポート機能を完備。

---

## 🚀 使い方

### 1. かんたん実行 (Windows ワンクリック)
フォルダ内の `run.bat` をダブルクリックすると対話メニューが表示されます：
- `[1]` 最新価格取得 & HTMLダッシュボードを開く (全機種 通常実行)
- `[2]` **🎯 指定した端末のみの価格を取得** (対話ウィザードで機種・容量・カラーを選択)
- `[3]` **🎨 カラー別価格差リサーチ** (色の違いによる値段差・人気色格差を表示)
- `[4]` 定期自動監視モード起動 (30分間隔で巡回・変動検知)
- `[5]` 定期自動監視モード起動 (15分間隔 & 変動時通知音つき)
- `[6]` 価格差1,000円以上の差額チャンスのみ表示
- `[7]` **LINE通知テスト送信** (朝の総合レポート)
- `[8]` **🔥 LINE通知テスト送信 (等価格以上の端末のみ)**
- `[9]` **🎯 LINE通知テスト送信 (指定した端末のみ)**
- `[10]` **🎨 LINE通知テスト送信 (カラー別価格差レポート)**
- `[11]` **毎朝自動LINE通知を登録** (総合レポート 毎朝08:00)
- `[12]` **🔥 毎朝自動LINE通知を登録 (等価格以上の端末のみ 毎朝08:00)**
- `[13]` **🎯 毎朝自動LINE通知を登録 (指定した端末のみ 毎朝08:00)**
- `[14]` **🔄 指定端末フィルターを解除・リセット** (全機種モードに戻す)
- `[15]` 毎朝自動LINE通知を解除 (Windowsタスク削除)
- `[16]` システム検証 (単体テスト実行 12項目)

### 2. 毎朝LINE通知の設定手順 (約2分)
1. [LINE Developers コンソール](https://developers.line.biz/console/) にログインし、プロバイダーおよび「Messaging API」チャネルを作成します。
2. チャネル設定画面の「Messaging API設定」タブ下部から「チャネルアクセストークン（長期）」を発行してコピーします。
3. チャネルのQRコードをスマホのLINEアプリで読み取り、友だち追加します。
4. 本プロジェクトフォルダ内の `.env.example` をコピーして `.env` にリネームし、トークンを貼り付けます：
   ```env
   LINE_CHANNEL_ACCESS_TOKEN=YOUR_LONG_LIVED_CHANNEL_ACCESS_TOKEN_HERE
   LINE_USER_ID=
   MORNING_SCHEDULE_TIME=08:00
   LINE_PROFIT_ONLY=false
   
   # 特定端末のみを常時監視・通知したい場合 (指定なしで全機種)
   TARGET_DEVICE=Pro Max 256GB
   # TARGET_MODEL=iPhone 18 Pro Max
   # TARGET_CAPACITY=256GB
   # TARGET_COLOR=バーガンディ
   ```
   *(※ `TARGET_DEVICE` などを設定すると、毎朝の自動通知やダッシュボード出力が指定端末のみに絞り込まれます。)*
5. `run.bat` を起動して `[7]`、`[8]`、`[9]`、または `[10]` を押し、LINEにテスト通知が届くか確認します。
6. `[11]`、`[12]`、または `[13]` を押してWindowsタスクスケジューラに登録すれば、以降は毎朝08:00に自動配信されます！

### 3. コマンドライン実行 (CLI)
```bash
# 通常実行 (画面表示 + 全ファイル出力)
python main.py

# 🎨 カラー別価格差リサーチを実行 (コンソール詳細表 + HTMLダッシュボード)
python main.py --color-spread

# 🎨 カラー別価格差レポートをLINEに即時通知
python main.py --line-color-spread

# 🎯 指定した端末のみ価格を取得・ダッシュボード表示
python main.py --target "Pro Max 256GB"
python main.py --model "iPhone 18 Pro" --capacity "256GB" --color "バーガンディ"

# 🎯 指定した端末のみをLINEに通知
python main.py --target "Pro Max 256GB" --line-notify

# 実行後にブラウザでHTMLダッシュボードを自動起動
python main.py --open-dashboard

# LINE通知を実行 (総合ダイジェストレポート)
python main.py --line-notify

# 🔥 等価格以上(定価以上)の端末情報のみをLINE通知
python main.py --line-notify --line-profit-only

# 最低還元率を指定して通知 (例: 102.0%以上の端末のみ)
python main.py --line-notify --line-profit-only --min-profit-rate 102.0

# 該当端末が0件の場合は送信をスキップ
python main.py --line-notify --line-profit-only --skip-if-no-profit

# 毎朝指定時刻(例: 08:00)に等価格以上の端末を自動通知する常駐モード
python main.py --morning-schedule 08:00 --line-profit-only

# 定期自動監視モード (例: 30分ごとに自動チェック & 変動時に通知音)
python main.py --watch 30 --alert --open-dashboard

# 価格差が1,000円以上の商品のみ抽出表示
python main.py --min-spread 1000

# Discordチャンネルに最新速報 / 変動アラートを通知
python main.py --notify

# ファイル出力をスキップして画面表示のみ
python main.py --no-export
```

---

## 📂 ディレクトリ構成

```
├── .env.example              # 環境変数設定テンプレート (LINE/Discord等)
├── config.py                 # 定価マッピング、対象URL、設定ローダー
├── main.py                   # メイン実行スクリプト (CLI / Rich表示 / Watchモード)
├── run.bat                   # 対話メニュー対応ワンクリック起動バッチ
├── run_morning.bat           # 毎朝配信用サイレント実行バッチ
├── setup_morning_task.bat    # Windowsタスクスケジューラ登録スクリプト
├── cancel_morning_task.bat   # Windowsタスクスケジューラ解除スクリプト
├── requirements.txt          # 必要パッケージ一覧
├── README.md                 # 本ドキュメント
├── src/
│   ├── models.py             # データモデル (PriceRecord, ComparisonItem, ColorSpreadGroup)
│   ├── comparator.py         # 32モデル完全名寄せ・価格差・利益計算・カラー格差集計
│   ├── history.py            # 時系列価格推移 & 変動検知モジュール
│   ├── exporter.py           # HTML (Chart.js) / Excel / CSV / JSON 出力モジュール
│   ├── notifier.py           # Discord Webhook 通知モジュール
│   ├── line_notifier.py      # LINE Messaging API 朝レポート通知モジュール
│   └── scrapers/
│       ├── base.py           # 基底スクレイパー (HTTP通信、WAF耐性、正規化)
│       ├── apple.py          # Apple公式HPリアルタイム販売価格スクレイパー
│       ├── kaitori1chome.py  # 買取一丁目用スクレイパー (リアルタイムカラー減額解析)
│       ├── rudeya.py         # 買取ルデヤ用スクレイパー
│       ├── morimori.py       # 森森買取用スクレイパー
│       └── saikoune.py       # 最高値ナビ (14店舗一括) スクレイパー
├── output/                   # HTMLダッシュボード / Excel / CSV レポート出力先
│   ├── latest_dashboard.html # 常に最新のHTMLダッシュボード
│   └── *.xlsx / *.csv
├── data/                     # JSON スナップショット保存先
└── tests/
    └── test_tracker.py       # 単体テストスイート (12項目)
```

---

## ⚙️ カスタマイズ設定 (`config.py` / `.env`)

- **LINE通知**: `.env` の `LINE_CHANNEL_ACCESS_TOKEN` および `LINE_USER_ID`、`MORNING_SCHEDULE_TIME` で設定します。
- **想定定価の変更**: `OFFICIAL_RETAIL_PRICES` に各モデル・容量ごとの仕入れ価格・定価を設定できます（Apple公式HPスクレイパー利用時は自動で実売価格へ更新されます）。
- **Discord通知**: `DISCORD_WEBHOOK_URL` にWebhook URLを記載するか、環境変数に設定すると利用できます。
- **店頭ボーナスの加味**: `RUDEYA_CONFIG["include_store_bonus"]` で持込増額（+500円など）を反映するか切り替え可能です。
