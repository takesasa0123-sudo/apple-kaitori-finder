"""
設定管理モジュール (config.py)
iPhone 18 買取価格トラッカーの設定を統括します。
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ベースディレクトリ
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# ディレクトリの自動作成
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# スクレイピング設定
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}
REQUEST_TIMEOUT = 15  # 秒
REQUEST_DELAY_SEC = 1.0  # リクエスト間のウェイト

# Apple公式想定定価（差額・利益計算の基準用、ユーザーが調整可能）
# モデル名 + 容量 でマッピング
# Apple公式想定定価（差額・利益計算の基準用、ユーザーが調整可能）
OFFICIAL_RETAIL_PRICES: Dict[str, Dict[str, int]] = {
    "iPhone 18 Pro Max": {
        "256GB": 239800,
        "512GB": 274800,
        "1TB": 344800,
        "2TB": 449800,
    },
    "iPhone 18 Pro": {
        "256GB": 219800,
        "512GB": 254800,
        "1TB": 319800,
        "2TB": 389800,
    },
    "iPhone 18": {
        "128GB": 139800,
        "256GB": 154800,
        "512GB": 189800,
    },
    "iPhone Air": {
        "256GB": 159800,
        "512GB": 189800,
    }
}

# 買取ルデヤ設定
RUDEYA_CONFIG = {
    "base_url": "https://kaitori-rudeya.com",
    "categories": {
        "iPhone 18 Pro Max": 253,
        "iPhone 18 Pro": 254,
    },
    "include_store_bonus": True,  # 店頭持込ボーナス(+500円など)を加味するか
}

# 森森買取設定
MORIMORI_CONFIG = {
    "base_url": "https://www.morimori-kaitori.jp",
    "search_endpoint": "https://www.morimori-kaitori.jp/search?sk=iPhone18",
}

# 最高値ナビ (14店舗一括比較) 設定
SAIKOUNE_CONFIG = {
    "url": "https://www.saikoune.jp/purchase-price/iphone18",
    "enabled": True,
}

# 買取1丁目 (1-chome.com) 設定
KAITORI1CHOME_CONFIG = {
    "api_endpoint": "https://www.1-chome.com/api/index/findByKeyword",
    "keyword": "iPhone 18",
    "enabled": True,
}

# .env ファイルが存在する場合は自動読み込み
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k = _k.strip()
                    _v = _v.strip().strip('"').strip("'")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

# Discord Webhook 通知設定 (環境変数またはここに直接記述)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# LINE 公式アカウント (Messaging API) 通知設定
# LINE Developers (https://developers.line.biz/) で発行したチャネルアクセストークン（長期）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
# 特定のユーザーにのみ送る場合のユーザーID（未指定時は公式アカウントの友達へ一斉配信）
LINE_USER_ID = os.getenv("LINE_USER_ID", "")
# 毎朝の自動通知スケジュール時刻 (デフォルト: "08:00")
MORNING_SCHEDULE_TIME = os.getenv("MORNING_SCHEDULE_TIME", "08:00")

# 等価格以上（定価以上・還元率100%以上）の端末のみをLINE通知するかどうか
LINE_PROFIT_ONLY = os.getenv("LINE_PROFIT_ONLY", "false").lower() in ("true", "1", "yes")
# 通知対象とする最低還元率 (%) (デフォルト: 100.0% = 等価格以上)
LINE_MIN_PROFIT_RATE = float(os.getenv("LINE_MIN_PROFIT_RATE", "100.0"))
# 等価格以上の端末が0件の場合に通知をスキップするか (Falseの場合は0件である旨を通知)
LINE_SKIP_IF_NO_PROFIT = os.getenv("LINE_SKIP_IF_NO_PROFIT", "false").lower() in ("true", "1", "yes")

# 比較・表示設定
MIN_ACCEPTABLE_SPREAD_JPY = 1000  # 店舗間差額がこれ以上のものを注目

# 指定端末フィルター設定 (指定した端末のみを取得・表示・通知する場合)
# 未指定(空欄)の場合は全32モデルが対象となります
TARGET_DEVICE = os.getenv("TARGET_DEVICE", "")      # キーワード指定 (例: "Pro Max 256GB", "バーガンディ")
TARGET_MODEL = os.getenv("TARGET_MODEL", "")        # 機種名 (例: "iPhone 18 Pro Max", "Pro")
TARGET_CAPACITY = os.getenv("TARGET_CAPACITY", "")  # 容量 (例: "256GB", "512GB")
TARGET_COLOR = os.getenv("TARGET_COLOR", "")        # カラー (例: "バーガンディ")

