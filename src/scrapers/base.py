"""
基底スクレイパーモジュール (src/scrapers/base.py)
各店舗共通のHTTP通信、リトライ、文字列正規化処理を提供します。
"""

import re
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional
import urllib.request
import urllib.parse

from config import DEFAULT_HEADERS, REQUEST_TIMEOUT, REQUEST_DELAY_SEC
from src.models import PriceRecord

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """買取店スクレイパーの共通基底クラス"""

    def __init__(self, store_name: str):
        self.store_name = store_name

    def fetch_html(self, url: str, params: Optional[dict] = None, max_retries: int = 3) -> str:
        """指定URLのHTMLを取得（自動リトライ付き・WAF耐性のあるurllib使用）"""
        target_url = url
        if params:
            query_str = urllib.parse.urlencode(params)
            target_url = f"{url}?{query_str}" if "?" not in url else f"{url}&{query_str}"

        for attempt in range(1, max_retries + 1):
            try:
                time.sleep(REQUEST_DELAY_SEC)
                req = urllib.request.Request(target_url, headers=DEFAULT_HEADERS)
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                    raw_data = response.read()
                    charset = response.headers.get_content_charset() or "utf-8"
                    try:
                        return raw_data.decode(charset)
                    except UnicodeDecodeError:
                        return raw_data.decode("utf-8", errors="ignore")

            except Exception as e:
                logger.warning(
                    "[%s] 通信エラー (試行 %d/%d): %s -> %s",
                    self.store_name,
                    attempt,
                    max_retries,
                    target_url,
                    e,
                )
            time.sleep(1.5 * attempt)

        raise RuntimeError(f"[{self.store_name}] URLの取得に失敗しました: {target_url}")

    @abstractmethod
    def scrape(self) -> List[PriceRecord]:
        """全対象商品の買取価格を取得して返す"""
        pass

    @staticmethod
    def clean_price(text: str) -> int:
        """価格文字列から数値を抽出 (例: '244,000円' -> 244000)"""
        if not text:
            return 0
        cleaned = re.sub(r"[^\d]", "", str(text))
        return int(cleaned) if cleaned else 0

    @staticmethod
    def extract_jan(text: str) -> Optional[str]:
        """テキストからJANコード (13桁または8桁の数字) を抽出"""
        if not text:
            return None
        match = re.search(r"\b(4[59]\d{11}|\d{13})\b", text)
        if match:
            return match.group(1)
        match_label = re.search(r"JAN[:\s]*(\d{8,13})", text, re.IGNORECASE)
        if match_label:
            return match_label.group(1)
        return None

    @staticmethod
    def normalize_capacity(text: str) -> str:
        """容量の正規化 (例: '256G', '256gb', '256GB' -> '256GB')"""
        if not text:
            return ""
        match = re.search(r"(128|256|512)\s*GB?", text, re.IGNORECASE)
        if match:
            return f"{match.group(1)}GB"
        match_tb = re.search(r"([12])\s*TB?", text, re.IGNORECASE)
        if match_tb:
            return f"{match_tb.group(1)}TB"
        return ""

    @staticmethod
    def normalize_color(text: str) -> str:
        """カラー名の正規化"""
        if not text:
            return ""
        # 代表的なiPhone 18カラー
        color_candidates = [
            ("バーガンディ", ["バーガンディ", "Burgundy", "ワイン"]),
            ("ブラック", ["ブラック", "Black", "スペースブラック"]),
            ("グレイシャー", ["グレイシャー", "グレイシャ", "Glacier", "アイス"]),
            ("シルバー", ["シルバー", "Silver", "ホワイト"]),
            ("ゴールド", ["ゴールド", "Gold"]),
            ("ブルー", ["ブルー", "Blue"]),
            ("ピンク", ["ピンク", "Pink"]),
            ("ナチュラル", ["ナチュラル", "Natural"]),
        ]
        for canonical, aliases in color_candidates:
            for alias in aliases:
                if alias.lower() in text.lower():
                    return canonical
        return ""

    @staticmethod
    def normalize_model_name(text: str) -> str:
        """機種名の正規化"""
        if not text:
            return ""
        clean = text.replace("Apple", "").replace("アップル", "").strip()
        if re.search(r"iPhone\s*18\s*Pro\s*Max", clean, re.IGNORECASE):
            return "iPhone 18 Pro Max"
        if re.search(r"iPhone\s*18\s*Pro", clean, re.IGNORECASE):
            return "iPhone 18 Pro"
        if re.search(r"iPhone\s*18\s*Plus", clean, re.IGNORECASE):
            return "iPhone 18 Plus"
        if re.search(r"iPhone\s*18", clean, re.IGNORECASE):
            return "iPhone 18"
        if re.search(r"iPhone\s*Air", clean, re.IGNORECASE):
            return "iPhone Air"
        return clean
