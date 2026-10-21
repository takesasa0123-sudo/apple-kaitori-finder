"""
テストスイート (tests/test_tracker.py)
モデル正規化、名寄せ統合ロジック、エクスポート処理、履歴推移・変動検知を検証します。
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.models import PriceRecord, ComparisonItem
from src.comparator import PriceComparator, filter_items
from src.exporter import Exporter
from src.scrapers.base import BaseScraper
from src.history import PriceHistoryTracker
from src.line_notifier import LineNotifier


class DummyScraper(BaseScraper):
    def scrape(self):
        return []


class TestTracker(unittest.TestCase):

    def setUp(self):
        self.scraper = DummyScraper("テスト店")

    def test_normalization(self):
        # 機種名
        self.assertEqual(
            self.scraper.normalize_model_name("Apple iPhone18 ProMax 256GB"),
            "iPhone 18 Pro Max"
        )
        self.assertEqual(
            self.scraper.normalize_model_name("iPhone 18 Pro"),
            "iPhone 18 Pro"
        )
        # 容量
        self.assertEqual(self.scraper.normalize_capacity("256GB バーガンディ"), "256GB")
        self.assertEqual(self.scraper.normalize_capacity("1TB シルバー"), "1TB")
        self.assertEqual(self.scraper.normalize_capacity("2TB ブラック"), "2TB")
        # カラー
        self.assertEqual(self.scraper.normalize_color("バーガンディ SIMフリー"), "バーガンディ")
        self.assertEqual(self.scraper.normalize_color("Glacier White"), "グレイシャー")
        # 金額
        self.assertEqual(self.scraper.clean_price("244,500円"), 244500)
        # JAN
        self.assertEqual(self.scraper.extract_jan("JAN:4549995734645"), "4549995734645")

    def test_comparator_merging_with_and_without_jan(self):
        """JANあり（ルデヤ等）とJANなし（最高値ナビ各店）が正しく1つのアイテムに統合されるか検証"""
        rec1 = PriceRecord(
            store="買取ルデヤ",
            raw_title="iPhone 18 Pro Max 256GB バーガンディ",
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            price=244500,
            jan="4549995734645",
        )
        rec2 = PriceRecord(
            store="森森買取",
            raw_title="Apple iPhone18 ProMax 256GB バーガンディ SIMフリー",
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            price=245000,
            jan="4549995734645",
        )
        rec3 = PriceRecord(
            store="買取一丁目",
            raw_title="iPhone 18 Pro Max 256GB バーガンディ",
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            price=244000,
            jan=None,  # 最高値ナビからのレコード想定
        )

        comparator = PriceComparator([rec1, rec2, rec3])
        items = comparator.compare()

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.jan, "4549995734645")  # ルデヤ・森森のJANを継承
        self.assertEqual(item.best_store, "森森買取")
        self.assertEqual(item.best_price, 245000)
        self.assertEqual(item.lowest_store, "買取一丁目")
        self.assertEqual(item.lowest_price, 244000)
        self.assertEqual(item.price_diff, 1000)
        self.assertEqual(item.store_prices["買取ルデヤ"], 244500)
        self.assertEqual(item.store_prices["森森買取"], 245000)
        self.assertEqual(item.store_prices["買取一丁目"], 244000)

    def test_history_tracker(self):
        """価格履歴と前回比（増減・トレンドバッジ）の検出を検証"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # 過去スナップショットを1つ作成
            snap1 = {
                "scraped_at": "2026-10-10T10:00:00",
                "items": [
                    {
                        "model_name": "iPhone 18 Pro Max",
                        "capacity": "256GB",
                        "color": "バーガンディ",
                        "best_price": 240000,
                        "best_store": "森森買取",
                    }
                ]
            }
            with open(tmppath / "iphone18_snapshot_20261010_100000.json", "w", encoding="utf-8") as f:
                json.dump(snap1, f)

            tracker = PriceHistoryTracker(data_dir=tmppath)
            current_item = ComparisonItem(
                model_name="iPhone 18 Pro Max",
                capacity="256GB",
                color="バーガンディ",
                best_price=245000,
                best_store="買取ルデヤ",
            )

            updated = tracker.attach_history_to_items([current_item])
            self.assertEqual(updated[0].prev_best_price, 240000)
            self.assertEqual(updated[0].price_change, 5000)
            self.assertEqual(updated[0].trend_badge, "+5,000円 ↗")

            changed = tracker.detect_price_changes(updated)
            self.assertEqual(len(changed), 1)
            self.assertEqual(changed[0]["diff"], 5000)

    def test_exporter(self):
        rec = PriceRecord(
            store="テスト店",
            raw_title="iPhone 18 Pro Max 256GB バーガンディ",
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            price=245000,
            jan="4549995734645",
        )
        comparator = PriceComparator([rec])
        items = comparator.compare()

        exporter = Exporter(items, [rec])
        paths = exporter.export_all()

        for k, p in paths.items():
            self.assertTrue(Path(p).exists(), f"{k} file does not exist")
            self.assertGreater(Path(p).stat().st_size, 0)

    def test_apple_official_scraper_and_comparator(self):
        """Apple公式HP販売価格・型番が正しくComparisonItemに反映されるか検証"""
        rec = PriceRecord(
            store="森森買取",
            raw_title="iPhone 18 Pro Max 256GB バーガンディ",
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            price=245000,
            jan="4549995734645",
        )
        catalog = {
            ("iPhone 18 Pro Max", "256GB", "バーガンディ"): {
                "price": 239800,
                "part_number": "MJX74J/A",
                "name": "iPhone 18 Pro Max 256GB Burgundy",
            }
        }
        comparator = PriceComparator([rec], official_catalog=catalog)
        items = comparator.compare()

        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it.official_price, 239800)
        self.assertEqual(it.part_number, "MJX74J/A")
        self.assertEqual(it.profit_jpy, 5200)  # 245000 - 239800
        self.assertEqual(it.profit_rate, 102.2)  # (245000 / 239800) * 100

    def test_line_notifier(self):
        """LINE公式アカウント通知モジュールの構成判定、メッセージ生成、送信処理を検証"""
        # 1. トークン設定判定
        notifier_no_token = LineNotifier(channel_access_token="")
        self.assertFalse(notifier_no_token.is_configured)
        self.assertFalse(notifier_no_token.send_morning_report([]))

        notifier_configured = LineNotifier(channel_access_token="dummy_token_123", user_id="U1234567890")
        self.assertTrue(notifier_configured.is_configured)

        # 2. メッセージ生成
        item1 = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            best_price=245000,
            best_store="森森買取",
            lowest_price=240000,
            lowest_store="買取一丁目",
            price_diff=5000,
            official_price=239800,
            profit_jpy=5200,
            profit_rate=102.2,
        )
        item2 = ComparisonItem(
            model_name="iPhone 18",
            capacity="128GB",
            color="ブラック",
            best_price=135000,
            best_store="買取ルデヤ",
            lowest_price=132000,
            lowest_store="森森買取",
            price_diff=3000,
            official_price=134800,
            profit_jpy=200,
            profit_rate=100.1,
        )
        changed = [
            {"title": "iPhone 18 Pro Max 256GB バーガンディ", "new_price": 245000, "diff": 5000, "best_store": "森森買取"}
        ]

        report_text = notifier_configured.format_morning_report(
            [item1, item2], total_stores=14, changed_items=changed
        )
        self.assertIn("【iPhone 18 買取速報】朝の最新価格レポート", report_text)
        self.assertIn("市場最高買取額", report_text)
        self.assertIn("245,000円", report_text)
        self.assertIn("還元率・差益 TOP 5", report_text)
        self.assertIn("最大店舗間差額チャンス", report_text)
        self.assertIn("前回比 価格変動検知", report_text)

        # 3. モック送信 (Push通知)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            success = notifier_configured.send_morning_report([item1], total_stores=14)
            self.assertTrue(success)
            self.assertTrue(mock_urlopen.called)
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.full_url, "https://api.line.me/v2/bot/message/push")
            self.assertIn("Bearer dummy_token_123", req.headers["Authorization"])

        # 4. モック送信 (Broadcast通知: user_id が空の場合)
        notifier_broadcast = LineNotifier(channel_access_token="dummy_token_123", user_id="")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            success = notifier_broadcast.send_morning_report([item1], total_stores=14)
            self.assertTrue(success)
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.full_url, "https://api.line.me/v2/bot/message/broadcast")

    def test_profit_only_report(self):
        """等価格以上（定価以上・還元率100%以上）限定レポートの生成および配信ロジックを検証"""
        notifier = LineNotifier(channel_access_token="dummy_token_123", user_id="U12345")

        item_profitable = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            best_price=245000,
            best_store="森森買取",
            official_price=239800,
            profit_jpy=5200,
            profit_rate=102.2,
            part_number="MJX74J/A",
            jan="4549995734645",
        )
        item_loss = ComparisonItem(
            model_name="iPhone 18",
            capacity="128GB",
            color="ブラック",
            best_price=130000,
            best_store="買取ルデヤ",
            official_price=134800,
            profit_jpy=-4800,
            profit_rate=96.4,
        )

        # 1. 等価格以上の端末が存在する場合
        report_text = notifier.format_profit_only_report([item_profitable, item_loss], total_stores=14)
        self.assertIn("【iPhone 18 等価格以上(定価以上)速報】", report_text)
        self.assertIn("1件", report_text)
        self.assertIn("iPhone 18 Pro Max 256GB", report_text)
        self.assertIn("245,000円", report_text)
        self.assertIn("+5,200円", report_text)
        self.assertIn("102.2%", report_text)
        self.assertNotIn("iPhone 18 128GB", report_text)  # 定価割れ端末は含まれない

        # 2. 等価格以上の端末が0件の場合
        report_text_zero = notifier.format_profit_only_report([item_loss], total_stores=14)
        self.assertIn("Apple公式定価と同額以上(還元率100%以上)の買取端末はありませんでした", report_text_zero)
        self.assertIn("参考: 現在の最高還元率 TOP 3", report_text_zero)
        self.assertIn("96.4%", report_text_zero)

        # 3. skip_if_no_profit=True の場合、0件なら通信せずにTrue
        with patch("urllib.request.urlopen") as mock_urlopen:
            res = notifier.send_morning_report(
                [item_loss],
                total_stores=14,
                profit_only=True,
                skip_if_no_profit=True,
            )
            self.assertTrue(res)
            self.assertFalse(mock_urlopen.called)

        # 4. profit_only=True で送信実行
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            res = notifier.send_morning_report(
                [item_profitable, item_loss],
                total_stores=14,
                profit_only=True,
            )
            self.assertTrue(res)
            self.assertTrue(mock_urlopen.called)

    def test_filter_items(self):
        """指定端末フィルタリング関数の動作検証"""
        item1 = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            best_price=245000,
            best_store="森森買取",
            part_number="MJX74J/A",
            jan="4549995734645",
        )
        item2 = ComparisonItem(
            model_name="iPhone 18 Pro",
            capacity="256GB",
            color="ブラック",
            best_price=220000,
            best_store="買取ルデヤ",
            part_number="MJRL4J/A",
            jan="4549995734249",
        )
        item3 = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="512GB",
            color="シルバー",
            best_price=280000,
            best_store="森森買取",
            part_number="MJXC4J/A",
            jan="4549995734843",
        )
        all_items = [item1, item2, item3]

        # 1. 機種名による絞り込み (Pro Max)
        res_m = filter_items(all_items, model="Pro Max")
        self.assertEqual(len(res_m), 2)
        self.assertNotIn(item2, res_m)

        # 2. 容量による絞り込み (512GB)
        res_c = filter_items(all_items, capacity="512GB")
        self.assertEqual(len(res_c), 1)
        self.assertEqual(res_c[0].capacity, "512GB")

        # 3. カラーによる絞り込み (バーガンディ)
        res_col = filter_items(all_items, color="バーガンディ")
        self.assertEqual(len(res_col), 1)
        self.assertEqual(res_col[0].color, "バーガンディ")

        # 4. キーワード複数単語指定 ("Pro Max 256GB")
        res_kw = filter_items(all_items, target="Pro Max 256GB")
        self.assertEqual(len(res_kw), 1)
        self.assertEqual(res_kw[0], item1)

        # 5. 型番やJANコードでの絞り込み
        res_part = filter_items(all_items, target="MJX74J/A")
        self.assertEqual(len(res_part), 1)
        self.assertEqual(res_part[0], item1)

        # 6. 一致なし
        res_none = filter_items(all_items, target="2TB")
        self.assertEqual(len(res_none), 0)

    def test_targeted_report(self):
        """指定端末限定レポートのフォーマットおよびLINE送信検証"""
        notifier = LineNotifier(channel_access_token="dummy_token_123", user_id="U12345")
        item = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            best_price=245000,
            best_store="森森買取",
            lowest_price=240000,
            lowest_store="買取ルデヤ",
            price_diff=5000,
            official_price=239800,
            profit_jpy=5200,
            profit_rate=102.2,
            part_number="MJX74J/A",
            jan="4549995734645",
            store_prices={"森森買取": 245000, "買取ルデヤ": 240000},
        )

        report = notifier.format_targeted_report([item], target_label="iPhone 18 Pro Max 256GB")
        self.assertIn("【iPhone 18 指定端末 買取速報】", report)
        self.assertIn("iPhone 18 Pro Max 256GB", report)
        self.assertIn("245,000円", report)
        self.assertIn("森森買取: 245,000円 ★最高値", report)
        self.assertIn("店舗差 +5,000円", report)
        self.assertIn("MJX74J/A", report)

        # 送信モックテスト
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            res = notifier.send_morning_report([item], total_stores=14, target_label="iPhone 18 Pro Max 256GB")
            self.assertTrue(res)
            self.assertTrue(mock_urlopen.called)

    def test_kaitori1chome_scraper(self):
        """買取1丁目のAPIレスポンス解析、カラー減額(varPrice)、減額メモ生成を検証"""
        from src.scrapers.kaitori1chome import Kaitori1ChomeScraper

        sample_api_data = {
            "code": 200,
            "data": {
                "content": [
                    {
                        "title": "iPhone 18 Pro Max 256GB",
                        "goodsKbDetails": [
                            {"allGoodsKbDetailId": 3987, "kbDetailName": "未開封", "kbDetailPrice": 247000}
                        ],
                        "keitaiColorOptions": [
                            {
                                "color": "ブラック",
                                "jan": "4549995734546",
                                "keitaiKbDetailColorRels": [
                                    {"keitaiKbDetailId": 3987, "varPrice": -12000}
                                ]
                            },
                            {
                                "color": "グレイシャー",
                                "jan": "4549995734690",
                                "keitaiKbDetailColorRels": [
                                    {"keitaiKbDetailId": 3987, "varPrice": -11000}
                                ]
                            },
                            {
                                "color": "シルバー",
                                "jan": "4549995734591",
                                "keitaiKbDetailColorRels": [
                                    {"keitaiKbDetailId": 3987, "varPrice": -19000}
                                ]
                            },
                            {
                                "color": "バーガンディ",
                                "jan": "4549995734645",
                                "keitaiKbDetailColorRels": [
                                    {"keitaiKbDetailId": 3987, "varPrice": 0}
                                ]
                            },
                        ]
                    }
                ]
            }
        }

        scraper = Kaitori1ChomeScraper()
        records = scraper._parse_api_response(sample_api_data)
        self.assertEqual(len(records), 4)

        # 価格マッピング検証
        price_map = {r.color: r.price for r in records}
        self.assertEqual(price_map["バーガンディ"], 247000)
        self.assertEqual(price_map["グレイシャー"], 236000)
        self.assertEqual(price_map["ブラック"], 235000)
        self.assertEqual(price_map["シルバー"], 228000)

        # 減額注記の検証
        black_rec = next(r for r in records if r.color == "ブラック")
        self.assertEqual(black_rec.jan, "4549995734546")
        self.assertIn("ブラック-12000", black_rec.color_diff_note)
        self.assertIn("シルバー-19000", black_rec.color_diff_note)

    def test_analyze_color_spread(self):
        """同一機種・同一容量内のカラー別買取価格差の集計と格差順位を検証"""
        from src.comparator import analyze_color_spread

        item_bg = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            best_price=247000,
            best_store="買取1丁目",
            official_price=239800,
            profit_rate=103.0,
        )
        item_gl = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="グレイシャー",
            best_price=236000,
            best_store="買取1丁目",
            official_price=239800,
            profit_rate=98.4,
        )
        item_bk = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="ブラック",
            best_price=235000,
            best_store="買取1丁目",
            official_price=239800,
            profit_rate=98.0,
        )
        item_sv = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="シルバー",
            best_price=228000,
            best_store="買取1丁目",
            official_price=239800,
            profit_rate=95.1,
        )

        all_items = [item_bk, item_sv, item_bg, item_gl]
        color_groups = analyze_color_spread(all_items)

        self.assertEqual(len(color_groups), 1)
        g = color_groups[0]
        self.assertEqual(g.model_name, "iPhone 18 Pro Max")
        self.assertEqual(g.capacity, "256GB")
        self.assertEqual(g.top_color, "バーガンディ")
        self.assertEqual(g.top_price, 247000)
        self.assertEqual(g.lowest_color, "シルバー")
        self.assertEqual(g.lowest_price, 228000)
        self.assertEqual(g.max_spread, 19000)

        # 差額の検証
        diff_map = {c.color: c.diff_from_top for c in g.colors}
        self.assertEqual(diff_map["バーガンディ"], 0)
        self.assertEqual(diff_map["グレイシャー"], -11000)
        self.assertEqual(diff_map["ブラック"], -12000)
        self.assertEqual(diff_map["シルバー"], -19000)

    def test_color_spread_line_report(self):
        """カラー別価格差専用LINEレポート本文の生成および送信検証"""
        notifier = LineNotifier(channel_access_token="dummy_token_123", user_id="U12345")
        item_bg = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="バーガンディ",
            best_price=247000,
            best_store="買取1丁目",
            official_price=239800,
        )
        item_sv = ComparisonItem(
            model_name="iPhone 18 Pro Max",
            capacity="256GB",
            color="シルバー",
            best_price=228000,
            best_store="買取1丁目",
            official_price=239800,
        )

        report = notifier.format_color_spread_report([item_bg, item_sv], total_stores=14)
        self.assertIn("【iPhone 18 カラー別買取価格差リサーチ】", report)
        self.assertIn("iPhone 18 Pro Max 256GB", report)
        self.assertIn("バーガンディ", report)
        self.assertIn("247,000円", report)
        self.assertIn("最大格差: 19,000円", report)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            ok = notifier.send_morning_report([item_bg, item_sv], total_stores=14, color_spread_only=True)
            self.assertTrue(ok)
            self.assertTrue(mock_urlopen.called)

    def test_all_models_bypass_and_reset(self):
        """all_modelsフラグによるフィルターバイパスおよびupdate_env_targetのリセット動作を検証"""
        from main import update_env_target
        import config

        # 1. フィルター設定
        update_env_target(target="Pro Max", model="iPhone 18 Pro Max", capacity="256GB", color="シルバー")
        self.assertEqual(config.TARGET_CAPACITY, "256GB")
        self.assertEqual(config.TARGET_COLOR, "シルバー")

        # 2. リセット実行
        update_env_target(target="", model="", capacity="", color="")
        self.assertEqual(config.TARGET_CAPACITY, "")
        self.assertEqual(config.TARGET_COLOR, "")
        self.assertEqual(config.TARGET_DEVICE, "")
        self.assertEqual(config.TARGET_MODEL, "")

    def test_mobile_app_dataset_and_html(self):
        """スマホアプリ用4機能データセット(iPhone利益1000円〜/損なし/他Apple商品/優先チェック・全機種JAN/型番整合)とHTML出力を検証"""
        from mobile_server import generate_mobile_html, MOBILE_DATA_PATH

        self.assertTrue(MOBILE_DATA_PATH.exists(), "initialData.json should exist")
        payload = json.loads(MOBILE_DATA_PATH.read_text(encoding="utf-8"))
        items = payload.get("items", [])
        self.assertGreaterEqual(len(items), 100)

        iphone_profit_1000 = [x for x in items if x["category"] == "iPhone" and x["profit_jpy"] >= 1000]
        iphone_no_loss = [x for x in items if x["category"] == "iPhone" and x["profit_jpy"] >= 0]
        other_no_loss = [x for x in items if x["category"] != "iPhone" and x["profit_jpy"] >= 0]
        other_items = [x for x in items if x["category"] != "iPhone"]

        self.assertEqual(payload["summary"]["iphone_profit_1000_count"], len(iphone_profit_1000))
        self.assertEqual(payload["summary"]["iphone_no_loss_count"], len(iphone_no_loss))
        self.assertEqual(payload["summary"]["other_no_loss_count"], len(other_no_loss))
        self.assertGreaterEqual(len(other_items), 80)

        # 全商品（iPhone・他Apple商品すべて）に13桁JANコード(454999...)とApple公式型番(PartNumber)が揃っていることを検証
        for item in items:
            self.assertTrue(
                item.get("jan", "").startswith("454999") and len(item["jan"]) == 13,
                f"Missing or invalid JAN on {item.get('model_name')} {item.get('part_number')}: {item.get('jan')}",
            )
            self.assertTrue(
                bool(item.get("part_number")),
                f"Missing part_number on {item.get('model_name')}",
            )

        html_path = generate_mobile_html(payload)
        self.assertTrue(html_path.exists())
        html_text = html_path.read_text(encoding="utf-8")
        self.assertIn("チェックした端末（最優先表示", html_text)
        self.assertIn("利益1,000円以上", html_text)
        self.assertIn("他Apple商品", html_text)


if __name__ == "__main__":
    unittest.main()



