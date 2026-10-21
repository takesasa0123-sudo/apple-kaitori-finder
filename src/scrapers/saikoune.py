"""
最高値ナビ スクレイパー (src/scrapers/saikoune.py)
最高値ナビ (saikoune.jp) から主要14買取店の iPhone 18 買取価格マトリクスを一括取得します。
"""

import re
import logging
from typing import List
from bs4 import BeautifulSoup

from config import SAIKOUNE_CONFIG
from src.models import PriceRecord
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class SaikouneScraper(BaseScraper):
    """最高値ナビ (saikoune.jp) のマルチ店舗スクレイパー"""

    def __init__(self):
        super().__init__(store_name="最高値ナビ(14店舗一括)")
        self.url = SAIKOUNE_CONFIG.get("url", "https://www.saikoune.jp/purchase-price/iphone18")

    def scrape(self) -> List[PriceRecord]:
        """最高値ナビの価格表から全店舗の買取価格を取得"""
        logger.info("[%s] スクレイピング開始: %s", self.store_name, self.url)
        results: List[PriceRecord] = []
        try:
            html = self.fetch_html(self.url)
            results = self._parse_matrix_page(html)
            logger.info("[%s] 合計 %d 件の買取レコードを取得完了", self.store_name, len(results))
        except Exception as e:
            logger.error("[%s] スクレイピング失敗: %s", self.store_name, e)

        return results

    def _parse_matrix_page(self, html: str) -> List[PriceRecord]:
        """価格表テーブルを解析して店舗別 PriceRecord を生成"""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            logger.warning("[%s] テーブルが見つかりませんでした", self.store_name)
            return []

        rows = table.find_all("tr")
        if not rows:
            return []

        # ヘッダーから店舗名と列インデックスを取得
        headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
        store_cols = [(idx, name) for idx, name in enumerate(headers) if idx >= 5 and name]

        records: List[PriceRecord] = []

        for row in rows[1:]:
            cols = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
            if len(cols) < 5:
                continue

            m_type = cols[0]  # Max, Pro
            model_name = "iPhone 18 Pro Max" if "Max" in m_type else "iPhone 18 Pro"
            cap_raw = cols[1]
            capacity = f"{cap_raw}GB" if cap_raw.isdigit() else cap_raw
            color = self.normalize_color(cols[2])

            raw_title = f"{model_name} {capacity} {color}"

            # 店舗別価格列の処理
            for idx, store_name in store_cols:
                if idx < len(cols):
                    val_str = cols[idx]
                    cleaned_price = self.clean_price(val_str)
                    if cleaned_price > 0:
                        rec = PriceRecord(
                            store=store_name,
                            raw_title=raw_title,
                            model_name=model_name,
                            capacity=capacity,
                            color=color,
                            price=cleaned_price,
                            sim_status="SIMフリー",
                            condition="新品未開封",
                            url=self.url,
                        )
                        records.append(rec)

        return records
