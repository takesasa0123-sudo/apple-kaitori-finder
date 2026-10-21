"""
買取ルデヤ スクレイパー (src/scrapers/rudeya.py)
買取ルデヤ公式サイトから iPhone 18 関連の買取価格を取得します。
"""

import re
import logging
from typing import List
from bs4 import BeautifulSoup

from config import RUDEYA_CONFIG
from src.models import PriceRecord
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class RudeyaScraper(BaseScraper):
    """買取ルデヤ (kaitori-rudeya.com) のスクレイパー"""

    def __init__(self):
        super().__init__(store_name="買取ルデヤ")
        self.base_url = RUDEYA_CONFIG.get("base_url", "https://kaitori-rudeya.com")
        self.categories = RUDEYA_CONFIG.get("categories", {})
        self.include_store_bonus = RUDEYA_CONFIG.get("include_store_bonus", True)

    def scrape(self) -> List[PriceRecord]:
        """カテゴリページからiPhone 18シリーズの買取価格を取得"""
        results: List[PriceRecord] = []
        seen_keys = set()

        for category_name, cat_id in self.categories.items():
            url = f"{self.base_url}/category/detail/{cat_id}"
            logger.info("[%s] カテゴリ取得開始: %s (ID: %s)", self.store_name, category_name, cat_id)
            try:
                html = self.fetch_html(url)
                records = self._parse_category_page(html, url)
                for rec in records:
                    key = rec.display_key
                    if key not in seen_keys:
                        seen_keys.add(key)
                        results.append(rec)
            except Exception as e:
                logger.error("[%s] カテゴリ %s の取得失敗: %s", self.store_name, category_name, e)

        logger.info("[%s] 合計 %d 件の買取レコードを取得完了", self.store_name, len(results))
        return results

    def _parse_category_page(self, html: str, page_url: str) -> List[PriceRecord]:
        """ルデヤのカテゴリページ (article.pgrid-card) を解析"""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("article.pgrid-card")
        records: List[PriceRecord] = []

        for card in cards:
            try:
                name_link = card.select_one("a.product-card-name-link")
                if not name_link:
                    continue
                raw_title = name_link.get_text(strip=True)
                href = name_link.get("href", "")
                full_url = href if href.startswith("http") else f"{self.base_url}{href}"

                # JANコード取得
                jan_el = card.select_one(".product-card-jan-text")
                jan_text = jan_el.get_text(strip=True) if jan_el else ""
                jan = self.extract_jan(jan_text) or self.extract_jan(raw_title)

                # 価格取得
                price_el = card.select_one(".product-card-price-value")
                price_text = price_el.get_text(strip=True) if price_el else ""
                base_price = self.clean_price(price_text)
                if base_price <= 0:
                    continue

                # 店頭/郵送ボーナス取得
                memo_el = card.select_one(".product-card-memo")
                memo_text = memo_el.get_text(strip=True) if memo_el else ""
                bonus_val = 0
                bonus_match = re.search(r"\+(\d[\d,]*)\s*円", memo_text)
                if bonus_match:
                    bonus_val = self.clean_price(bonus_match.group(1))

                effective_price = base_price + bonus_val if (self.include_store_bonus and bonus_val > 0) else base_price

                # モデル名、容量、カラーの正規化
                model_name = self.normalize_model_name(raw_title)
                capacity = self.normalize_capacity(raw_title)
                color = self.normalize_color(raw_title)

                # 商品コード (MJX74J/A 等)
                code_match = re.search(r"\b([A-Z0-9]{5}J/A)\b", raw_title)
                product_code = code_match.group(1) if code_match else None

                record = PriceRecord(
                    store=self.store_name,
                    raw_title=raw_title,
                    model_name=model_name,
                    capacity=capacity,
                    color=color,
                    price=effective_price,
                    jan=jan,
                    sim_status="SIMフリー" if "SIMフリー" in raw_title else "キャリア版",
                    condition="新品未開封",
                    bonus_price=base_price + bonus_val if bonus_val else None,
                    product_code=product_code,
                    url=full_url,
                )
                records.append(record)

            except Exception as e:
                logger.warning("[%s] カード解析エラー: %s", self.store_name, e)

        return records
