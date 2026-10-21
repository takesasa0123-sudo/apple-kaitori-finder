"""
価格比較・利益分析エンジン (src/comparator.py)
複数店舗の買取価格をJANコードおよびモデル属性で突合し、
最高値店舗・価格差・想定利益率を算出します。
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

from config import OFFICIAL_RETAIL_PRICES
from src.models import PriceRecord, ComparisonItem, ColorDetail, ColorSpreadGroup

logger = logging.getLogger(__name__)


class PriceComparator:
    """複数店舗の買取価格を比較・集計するエンジン"""

    def __init__(
        self,
        records: List[PriceRecord],
        official_catalog: Optional[Dict[Tuple[str, str, str], Dict[str, Any]]] = None,
    ):
        self.records = records
        self.official_catalog = official_catalog or {}

    def compare(self) -> List[ComparisonItem]:
        """全レコードを突合・比較して ComparisonItem のリストを生成"""
        # 1. JANコードまたは (モデル, 容量, カラー) でグルーピング
        grouped: Dict[str, List[PriceRecord]] = defaultdict(list)

        for rec in self.records:
            key = self._get_canonical_key(rec)
            grouped[key].append(rec)

        results: List[ComparisonItem] = []

        for key, recs in grouped.items():
            if not recs:
                continue

            # 代表情報
            first = recs[0]
            model_name = first.model_name
            capacity = first.capacity
            color = first.color
            jan = next((r.jan for r in recs if r.jan), None)

            # 店舗別価格辞書
            store_prices: Dict[str, int] = {}
            for r in recs:
                # 同一店舗で複数ある場合は最高値を採用
                if r.store not in store_prices or r.price > store_prices[r.store]:
                    store_prices[r.store] = r.price

            if not store_prices:
                continue

            # 最高価格・最安価格の算出
            best_store, best_price = max(store_prices.items(), key=lambda x: x[1])
            lowest_store, lowest_price = min(store_prices.items(), key=lambda x: x[1])
            price_diff = best_price - lowest_price

            # Apple公式最新販売価格および型番の取得 (取得時公式HP価格を最優先)
            official_price = None
            part_number = None

            cat_info = self.official_catalog.get((model_name, capacity, color))
            if cat_info:
                official_price = cat_info.get("price")
                part_number = cat_info.get("part_number")

            if not official_price:
                # 予備: config設定からの想定定価
                official_price = self._get_official_price(model_name, capacity)

            if not part_number:
                part_number = next((r.product_code for r in recs if r.product_code), None)

            profit_jpy = None
            profit_rate = None
            if official_price and official_price > 0:
                profit_jpy = best_price - official_price
                profit_rate = round((best_price / official_price) * 100, 1)

            item = ComparisonItem(
                model_name=model_name,
                capacity=capacity,
                color=color,
                jan=jan,
                part_number=part_number,
                best_store=best_store,
                best_price=best_price,
                lowest_store=lowest_store,
                lowest_price=lowest_price,
                price_diff=price_diff,
                official_price=official_price,
                profit_jpy=profit_jpy,
                profit_rate=profit_rate,
                store_prices=store_prices,
                records=recs,
            )
            results.append(item)

        # ソート順: モデル名順 -> 容量(GB/TB)大きい順 -> 最高価格降順
        results.sort(key=lambda x: (x.model_name, self._capacity_sort_key(x.capacity), -x.best_price))
        return results

    @staticmethod
    def _get_canonical_key(rec: PriceRecord) -> str:
        """名寄せ用の統一キー（モデル名_容量_カラーで全店舗を名寄せ）"""
        return f"{rec.model_name}_{rec.capacity}_{rec.color}".strip("_")

    @staticmethod
    def _capacity_sort_key(cap: str) -> int:
        """容量ソート用キー (2TB > 1TB > 512GB > 256GB > 128GB)"""
        if "2TB" in cap:
            return -2000
        if "1TB" in cap:
            return -1000
        if "512" in cap:
            return -512
        if "256" in cap:
            return -256
        if "128" in cap:
            return -128
        return 0

    @staticmethod
    def _get_official_price(model_name: str, capacity: str) -> Optional[int]:
        """設定から公式想定定価を検索"""
        for m_key, caps in OFFICIAL_RETAIL_PRICES.items():
            if m_key.lower() in model_name.lower():
                for c_key, price in caps.items():
                    if c_key.lower() == capacity.lower():
                        return price
        return None


def filter_items(
    items: List[ComparisonItem],
    target: str = "",
    model: str = "",
    capacity: str = "",
    color: str = "",
) -> List[ComparisonItem]:
    """指定された端末条件（キーワード、機種名、容量、カラー）でアイテムを絞り込む"""
    filtered: List[ComparisonItem] = []
    target_lower = target.strip().lower() if target else ""
    target_words = target_lower.split() if target_lower else []

    for it in items:
        # 1. 機種名チェック (例: "Pro Max", "Pro", "iPhone 18")
        if model:
            clean_m = model.strip().lower().replace("iphone", "").replace("18", "").replace(" ", "")
            item_m = it.model_name.lower().replace("iphone", "").replace("18", "").replace(" ", "")
            if clean_m and clean_m not in item_m:
                continue

        # 2. 容量チェック (例: "256GB", "256")
        if capacity:
            clean_c = capacity.strip().upper().replace(" ", "")
            item_c = it.capacity.strip().upper().replace(" ", "")
            if clean_c != item_c and clean_c not in item_c:
                continue

        # 3. カラーチェック (例: "バーガンディ", "ブラック")
        if color:
            clean_col = color.strip().lower()
            if clean_col not in it.color.lower():
                continue

        # 4. 自由キーワードチェック (スペース区切りの全単語が含まれるか)
        if target_words:
            search_str = f"{it.model_name} {it.capacity} {it.color} {it.jan or ''} {it.part_number or ''}".lower()
            if not all(w in search_str for w in target_words):
                continue

        filtered.append(it)

    return filtered


def analyze_color_spread(
    items: List[ComparisonItem],
    records: Optional[List[PriceRecord]] = None,
) -> List[ColorSpreadGroup]:
    """同一機種・同一容量内のカラー別買取価格差をリサーチ・分析し、格差順に集計"""
    groups_map: Dict[Tuple[str, str], List[ComparisonItem]] = defaultdict(list)
    for it in items:
        groups_map[(it.model_name, it.capacity)].append(it)

    spread_groups: List[ColorSpreadGroup] = []

    for (m_name, cap), group_items in groups_map.items():
        if not group_items:
            continue

        # 最高買取額順にソート
        sorted_items = sorted(group_items, key=lambda x: x.best_price, reverse=True)
        top_item = sorted_items[0]
        top_color = top_item.color
        top_price = top_item.best_price

        lowest_item = sorted_items[-1]
        lowest_color = lowest_item.color
        lowest_price = lowest_item.best_price

        max_spread = top_price - lowest_price
        official_price = top_item.official_price

        # 店舗別の減額メモ (例: 買取1丁目の "ブラック-12000,グレイシャ-11000,シルバー-19000")
        store_deductions = {}
        for it in group_items:
            for rec in it.records:
                if rec.color_diff_note and rec.store not in store_deductions:
                    store_deductions[rec.store] = rec.color_diff_note

        if records:
            for rec in records:
                if rec.model_name == m_name and rec.capacity == cap and rec.color_diff_note:
                    if rec.store not in store_deductions:
                        store_deductions[rec.store] = rec.color_diff_note

        # 各カラーの詳細リストを構築
        color_details: List[ColorDetail] = []
        for it in sorted_items:
            diff = it.best_price - top_price  # 0 または マイナス値
            cd = ColorDetail(
                color=it.color,
                best_price=it.best_price,
                best_store=it.best_store,
                diff_from_top=diff,
                official_price=it.official_price,
                profit_jpy=it.profit_jpy,
                profit_rate=it.profit_rate,
                jan=it.jan,
                part_number=it.part_number,
                item=it,
            )
            color_details.append(cd)

        csg = ColorSpreadGroup(
            model_name=m_name,
            capacity=cap,
            official_price=official_price,
            top_color=top_color,
            top_price=top_price,
            lowest_color=lowest_color,
            lowest_price=lowest_price,
            max_spread=max_spread,
            colors=color_details,
            store_deductions=store_deductions,
        )
        spread_groups.append(csg)

    # ソート順: 最大カラー格差降順 -> モデル名順 -> 容量降順
    spread_groups.sort(
        key=lambda x: (
            -x.max_spread,
            x.model_name,
            PriceComparator._capacity_sort_key(x.capacity),
        )
    )
    return spread_groups

