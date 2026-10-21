"""
森森買取 スクレイパー (src/scrapers/morimori.py)
森森買取公式サイトから iPhone 18 関連の買取価格を取得します。
"""

import re
import logging
from typing import List
from bs4 import BeautifulSoup

from config import MORIMORI_CONFIG
from src.models import PriceRecord
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class MorimoriScraper(BaseScraper):
    """森森買取 (morimori-kaitori.jp) のスクレイパー"""

    def __init__(self):
        super().__init__(store_name="森森買取")
        self.base_url = MORIMORI_CONFIG.get("base_url", "https://www.morimori-kaitori.jp")
        self.search_endpoint = MORIMORI_CONFIG.get(
            "search_endpoint", "https://www.morimori-kaitori.jp/search?sk=iPhone18"
        )

    def scrape(self) -> List[PriceRecord]:
        """検索結果ページから全商品の買取価格を取得"""
        logger.info("[%s] スクレイピング開始: %s", self.store_name, self.search_endpoint)
        results: List[PriceRecord] = []
        try:
            html = self.fetch_html(self.search_endpoint)
            results = self._parse_search_page(html)
            logger.info("[%s] 合計 %d 件の買取レコードを取得完了", self.store_name, len(results))
        except Exception as e:
            logger.error("[%s] スクレイピング失敗: %s", self.store_name, e)

        return results

    def _parse_search_page(self, html: str) -> List[PriceRecord]:
        """検索結果ページの .mm1551-prow 要素を解析"""
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select(".mm1551-prow")
        records: List[PriceRecord] = []

        for row in rows:
            try:
                # 価格情報 (data属性から直接取得)
                price_attr = row.get("data-cond-new-price")
                base_price = self.clean_price(price_attr) if price_attr else 0

                dep_attr = row.get("data-cond-new-deposit")
                deposit_price = self.clean_price(dep_attr) if dep_attr else None

                fri_attr = row.get("data-cond-new-fri")
                quick_pay_price = self.clean_price(fri_attr) if fri_attr else None

                if base_price <= 0:
                    continue

                # タイトルとリンク
                name_el = row.select_one(".mm1551-prow__name a")
                raw_title = name_el.get_text(separator=" ", strip=True) if name_el else ""
                href = name_el.get("href", "") if name_el else ""
                full_url = href if href.startswith("http") else f"{self.base_url}{href}"

                # JANコード取得
                meta_el = row.select_one(".mm1551-prow__meta")
                meta_text = meta_el.get_text(strip=True) if meta_el else ""
                jan = self.extract_jan(meta_text) or self.extract_jan(raw_title)

                # モデル名、容量、カラーの正規化
                model_name = self.normalize_model_name(raw_title)
                capacity = self.normalize_capacity(raw_title)
                color = self.normalize_color(raw_title)

                record = PriceRecord(
                    store=self.store_name,
                    raw_title=raw_title,
                    model_name=model_name,
                    capacity=capacity,
                    color=color,
                    price=base_price,
                    jan=jan,
                    sim_status="SIMフリー" if "SIMフリー" in raw_title else "キャリア版",
                    condition="新品未開封",
                    deposit_price=deposit_price,
                    quick_pay_price=quick_pay_price,
                    url=full_url,
                )
                records.append(record)

            except Exception as e:
                logger.warning("[%s] 行解析エラー: %s", self.store_name, e)

        return records
