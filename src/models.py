"""
データモデル定義 (src/models.py)
買取価格レコードおよび比較結果のデータ構造を定義します。
"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class PriceRecord:
    """各店舗から取得した個別商品の買取価格レコード"""
    store: str
    raw_title: str
    model_name: str
    capacity: str
    color: str
    price: int
    jan: Optional[str] = None
    sim_status: str = "SIMフリー"
    condition: str = "新品未開封"
    bonus_price: Optional[int] = None
    deposit_price: Optional[int] = None
    quick_pay_price: Optional[int] = None
    product_code: Optional[str] = None  # 店舗ごとの商品コード
    url: Optional[str] = None
    color_diff_note: Optional[str] = None  # 店舗側のカラー別減額メモ (例: ブラック-12000,グレイシャ-11000)
    scraped_at: datetime = field(default_factory=datetime.now)

    @property
    def display_key(self) -> str:
        """比較用の一意識別キー (JAN優先、なければ モデル+容量+カラー)"""
        if self.jan:
            return f"JAN_{self.jan}"
        return f"{self.model_name}_{self.capacity}_{self.color}".strip("_")


@dataclass
class ComparisonItem:
    """店舗間の価格比較結果アイテム"""
    model_name: str
    capacity: str
    color: str
    jan: Optional[str] = None
    part_number: Optional[str] = None  # Apple公式型番 (例: MJX74J/A)
    best_store: str = ""
    best_price: int = 0
    lowest_store: str = ""
    lowest_price: int = 0
    price_diff: int = 0
    official_price: Optional[int] = None  # 取得時のApple公式HP販売価格
    profit_jpy: Optional[int] = None
    profit_rate: Optional[float] = None
    store_prices: Dict[str, int] = field(default_factory=dict)
    records: List[PriceRecord] = field(default_factory=list)
    prev_best_price: Optional[int] = None
    price_change: Optional[int] = None  # 前回調査からの最高値増減額
    history_points: List[Dict] = field(default_factory=list)  # 過去の時系列価格推移データ

    @property
    def summary_title(self) -> str:
        return f"{self.model_name} {self.capacity} {self.color}".strip()

    @property
    def display_key(self) -> str:
        """一意識別キー"""
        return f"{self.model_name}_{self.capacity}_{self.color}".strip("_")

    @property
    def trend_badge(self) -> str:
        """前回比のトレンド表示用文字列"""
        if self.price_change is None:
            return "NEW"
        if self.price_change > 0:
            return f"+{self.price_change:,}円 ↗"
        elif self.price_change < 0:
            return f"{self.price_change:,}円 ↘"
        return "±0円"


@dataclass
class ColorDetail:
    """同一機種・同一容量内のカラー別詳細"""
    color: str
    best_price: int
    best_store: str
    diff_from_top: int  # 最高値カラーとの差額 (例: 0, -11000, -12000, -19000)
    official_price: Optional[int] = None
    profit_jpy: Optional[int] = None
    profit_rate: Optional[float] = None
    jan: Optional[str] = None
    part_number: Optional[str] = None
    item: Optional[ComparisonItem] = None


@dataclass
class ColorSpreadGroup:
    """機種・容量単位のカラー別価格差リサーチ集計"""
    model_name: str
    capacity: str
    official_price: Optional[int]
    top_color: str
    top_price: int
    lowest_color: str
    lowest_price: int
    max_spread: int  # 最大カラー格差 (top_price - lowest_price)
    colors: List[ColorDetail] = field(default_factory=list)
    store_deductions: Dict[str, str] = field(default_factory=dict)  # 例: {"買取1丁目": "ブラック-12000,グレイシャ-11000,シルバー-19000"}

    @property
    def group_title(self) -> str:
        return f"{self.model_name} {self.capacity}".strip()

