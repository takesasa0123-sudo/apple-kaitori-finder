"""
買取1丁目 スクレイパー (src/scrapers/kaitori1chome.py)
買取1丁目 (1-chome.com) の公式APIから iPhone 18 シリーズの買取価格、
カラー別減額調整値 (varPrice)、およびJANコードをリアルタイム取得します。
"""

import json
import logging
import urllib.parse
from typing import List, Optional

from config import DEFAULT_HEADERS, REQUEST_TIMEOUT
from src.models import PriceRecord
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class Kaitori1ChomeScraper(BaseScraper):
    """買取1丁目 (1-chome.com) のスクレイパー"""

    def __init__(self):
        super().__init__(store_name="買取1丁目")
        self.api_endpoint = "https://www.1-chome.com/api/index/findByKeyword"
        self.keyword = "iPhone 18"

    def scrape(self) -> List[PriceRecord]:
        """買取1丁目APIから全商品の買取価格とカラー別差額を取得"""
        logger.info("[%s] スクレイピング開始 (API: %s)", self.store_name, self.api_endpoint)
        results: List[PriceRecord] = []
        try:
            params = {
                "keyword": self.keyword,
                "page": 1,
                "size": 50,
            }
            query_url = f"{self.api_endpoint}?{urllib.parse.urlencode(params)}"
            html_or_json = self.fetch_html(query_url)
            data = json.loads(html_or_json)
            results = self._parse_api_response(data)
            logger.info("[%s] 合計 %d 件の買取レコードを取得完了", self.store_name, len(results))
        except Exception as e:
            logger.error("[%s] スクレイピング失敗: %s", self.store_name, e)

        return results

    def _parse_api_response(self, data: dict) -> List[PriceRecord]:
        """APIレスポンスから各機種・カラー別の PriceRecord を生成"""
        records: List[PriceRecord] = []
        content = data.get("data", {}).get("content", [])

        for item in content:
            raw_title = item.get("title", "") or item.get("goodsName", "")
            if not raw_title:
                continue

            model_name = self.normalize_model_name(raw_title)
            capacity = self.normalize_capacity(raw_title)
            if not model_name or not capacity:
                continue

            # 未開封条件の価格とdetailIdを特定
            kb_details = item.get("goodsKbDetails", [])
            unopened_detail = next(
                (d for d in kb_details if "未開封" in d.get("kbDetailName", "")),
                None,
            )
            if not unopened_detail and kb_details:
                unopened_detail = kb_details[0]

            if not unopened_detail:
                continue

            base_price = unopened_detail.get("kbDetailPrice", 0)
            detail_id = unopened_detail.get("allGoodsKbDetailId")
            if base_price <= 0:
                continue

            # カラー別減額テキストの構築 (例: "ブラック-12000,グレイシャ-11000,シルバー-19000")
            color_opts = item.get("keitaiColorOptions", [])
            deduction_parts = []
            for opt in color_opts:
                c_name = opt.get("color", "").strip()
                v_price = 0
                for rel in opt.get("keitaiKbDetailColorRels", []):
                    if rel.get("keitaiKbDetailId") == detail_id:
                        v_price = rel.get("varPrice") or 0
                        break
                if v_price < 0:
                    deduction_parts.append(f"{c_name}{v_price}")

            color_diff_note = ",".join(deduction_parts) if deduction_parts else None

            # 各カラーのレコードを生成
            for opt in color_opts:
                raw_color = opt.get("color", "").strip()
                canonical_color = self.normalize_color(raw_color) or raw_color
                jan = opt.get("jan", "").strip() or None

                var_price = 0
                for rel in opt.get("keitaiKbDetailColorRels", []):
                    if rel.get("keitaiKbDetailId") == detail_id:
                        var_price = rel.get("varPrice") or 0
                        break

                final_price = base_price + var_price
                if final_price <= 0:
                    continue

                full_title = f"{model_name} {capacity} {canonical_color}"
                rec = PriceRecord(
                    store=self.store_name,
                    raw_title=full_title,
                    model_name=model_name,
                    capacity=capacity,
                    color=canonical_color,
                    price=final_price,
                    jan=jan,
                    sim_status="SIMフリー",
                    condition="新品未開封",
                    url="https://www.1-chome.com",
                    color_diff_note=color_diff_note,
                )
                records.append(rec)

        return records
