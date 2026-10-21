"""
Apple公式オンラインストア スクレイパー (src/scrapers/apple.py)
Apple日本公式サイト (apple.com/jp) から、iPhone 18 シリーズの
取得時最新公式HP販売価格（税込定価）および型番(PartNumber)をリアルタイム取得します。
"""

import json
import logging
import re
from typing import Dict, List, Tuple, Any, Optional
from bs4 import BeautifulSoup

from config import DEFAULT_HEADERS
from src.models import PriceRecord
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AppleOfficialScraper(BaseScraper):
    """Apple日本公式オンラインストアの最新販売価格スクレイパー"""

    def __init__(self):
        super().__init__(store_name="Apple公式オンラインストア")
        self.url = "https://www.apple.com/jp/shop/buy-iphone/iphone-18-pro"

    def get_official_catalog(self) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
        """
        Apple公式サイトから全32モデルの (モデル名, 容量, カラー) -> 公式情報 を取得
        戻り値の形式:
        {
            ("iPhone 18 Pro Max", "256GB", "バーガンディ"): {
                "price": 239800,
                "part_number": "MJX74J/A",
                "name": "iPhone 18 Pro Max 256GB Burgundy",
                "url": "https://www.apple.com/jp/shop/buy-iphone/iphone-18-pro"
            },
            ...
        }
        """
        logger.info("[%s] Apple公式HPより最新販売価格を取得中: %s", self.store_name, self.url)
        catalog: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        try:
            html = self.fetch_html(self.url)
            soup = BeautifulSoup(html, "html.parser")
            metrics_script = soup.find("script", id="metrics")
            if not metrics_script or not metrics_script.string:
                logger.warning("[%s] metrics スクリプトが見つかりませんでした", self.store_name)
                return catalog

            data = json.loads(metrics_script.string)
            products = data.get("data", {}).get("products", [])

            for p in products:
                raw_name = p.get("name", "")
                part_number = p.get("partNumber", "")
                full_price = p.get("price", {}).get("fullPrice")
                if full_price is None:
                    continue

                int_price = int(round(float(full_price)))
                model_name = self.normalize_model_name(raw_name)
                capacity = self.normalize_capacity(raw_name)
                color = self.normalize_color(raw_name)

                if model_name and capacity and color:
                    key = (model_name, capacity, color)
                    catalog[key] = {
                        "price": int_price,
                        "part_number": part_number,
                        "name": raw_name,
                        "url": self.url,
                    }

            logger.info("[%s] Apple公式HPから %d 件の公式販売価格・型番を取得完了", self.store_name, len(catalog))
        except Exception as e:
            logger.error("[%s] Apple公式HPの取得エラー: %s", self.store_name, e)

        return catalog

    def scrape(self) -> List[PriceRecord]:
        """BaseScraper 実装: Apple公式ストアとしての PriceRecord リストを返す"""
        catalog = self.get_official_catalog()
        records: List[PriceRecord] = []
        for (m, c, col), info in catalog.items():
            rec = PriceRecord(
                store=self.store_name,
                raw_title=info["name"],
                model_name=m,
                capacity=c,
                color=col,
                price=info["price"],
                product_code=info["part_number"],
                url=info["url"],
            )
            records.append(rec)
        return records
