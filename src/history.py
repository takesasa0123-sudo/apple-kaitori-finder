"""
価格履歴・変動追跡モジュール (src/history.py)
過去のJSONスナップショットから時系列価格推移を抽出し、
前回比の価格変動（上昇/下落）を自動検出します。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from config import DATA_DIR
from src.models import ComparisonItem

logger = logging.getLogger(__name__)


class PriceHistoryTracker:
    """スナップショット履歴の読み込みと変動検出を行うクラス"""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir

    def get_snapshot_files(self) -> List[Path]:
        """保存されているスナップショットJSONを古い順（時系列順）で取得"""
        if not self.data_dir.exists():
            return []
        files = list(self.data_dir.glob("iphone18_snapshot_*.json"))
        # ファイル名 (日付文字列含む) でソート
        files.sort(key=lambda p: p.name)
        return files

    def load_previous_snapshot(self) -> Optional[Dict[str, Any]]:
        """直前の最新スナップショットを読み込む"""
        files = self.get_snapshot_files()
        if not files:
            return None
        # 最新のファイル（現在生成中のものがある場合はその直前）
        latest_file = files[-1]
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.warning("直前スナップショット読み込みエラー (%s): %s", latest_file, e)
            return None

    def build_history_timeseries(self, max_snapshots: int = 20) -> Dict[str, List[Dict[str, Any]]]:
        """
        過去の全スナップショットから各モデルの時系列価格推移データを構築
        キー: 'model_name_capacity_color'
        値: [ {'time': '10/11 11:39', 'best_price': 245000, 'best_store': '森森買取', 'store_prices': {...}}, ... ]
        """
        files = self.get_snapshot_files()
        if not files:
            return {}

        # 直近 max_snapshots 件のみ対象
        target_files = files[-max_snapshots:]
        sku_series: Dict[str, List[Dict[str, Any]]] = {}

        for fpath in target_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    snap = json.load(f)
                scraped_at_str = snap.get("scraped_at", "")
                if scraped_at_str:
                    try:
                        dt = datetime.fromisoformat(scraped_at_str)
                        time_label = dt.strftime("%m/%d %H:%M")
                    except Exception:
                        time_label = scraped_at_str[:16]
                else:
                    time_label = fpath.stem.replace("iphone18_snapshot_", "")

                for it in snap.get("items", []):
                    model = it.get("model_name", "")
                    cap = it.get("capacity", "")
                    color = it.get("color", "")
                    sku_key = f"{model}_{cap}_{color}".strip("_")
                    if not sku_key:
                        continue

                    point = {
                        "time": time_label,
                        "best_price": it.get("best_price", 0),
                        "best_store": it.get("best_store", ""),
                        "lowest_price": it.get("lowest_price", 0),
                        "lowest_store": it.get("lowest_store", ""),
                        "price_diff": it.get("price_diff", 0),
                        "store_prices": it.get("store_prices", {}),
                    }
                    if sku_key not in sku_series:
                        sku_series[sku_key] = []
                    sku_series[sku_key].append(point)
            except Exception as e:
                logger.debug("履歴パース失敗 (%s): %s", fpath, e)
                continue

        return sku_series

    def attach_history_to_items(self, current_items: List[ComparisonItem]) -> List[ComparisonItem]:
        """
        現在の ComparisonItem リストに過去の推移データおよび前回比（増減額）を付与
        """
        sku_series = self.build_history_timeseries()

        for item in current_items:
            sku_key = f"{item.model_name}_{item.capacity}_{item.color}".strip("_")
            points = sku_series.get(sku_key, [])

            # 直前のポイントを取得して前回比を計算
            if points:
                last_saved_point = points[-1]
                prev_price = last_saved_point.get("best_price")
                if prev_price and prev_price > 0:
                    item.prev_best_price = prev_price
                    item.price_change = item.best_price - prev_price

            # 現在のポイントを追加（時系列推移表示用）
            current_point = {
                "time": datetime.now().strftime("%m/%d %H:%M"),
                "best_price": item.best_price,
                "best_store": item.best_store,
                "lowest_price": item.lowest_price,
                "lowest_store": item.lowest_store,
                "price_diff": item.price_diff,
                "store_prices": item.store_prices,
            }
            # 重複を避けて推移リストを作成
            combined_points = list(points)
            if not combined_points or combined_points[-1].get("time") != current_point["time"]:
                combined_points.append(current_point)
            elif combined_points:
                combined_points[-1] = current_point

            item.history_points = combined_points

        return current_items

    def detect_price_changes(self, current_items: List[ComparisonItem]) -> List[Dict[str, Any]]:
        """
        前回調査からの変動があったアイテムのリストを抽出
        """
        changed_items = []
        for it in current_items:
            if it.price_change is not None and it.price_change != 0:
                changed_items.append({
                    "model": it.model_name,
                    "capacity": it.capacity,
                    "color": it.color,
                    "title": it.summary_title,
                    "old_price": it.prev_best_price,
                    "new_price": it.best_price,
                    "diff": it.price_change,
                    "best_store": it.best_store,
                })
        return changed_items
