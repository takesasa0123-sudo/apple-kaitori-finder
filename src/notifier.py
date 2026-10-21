"""
Discord 通知モジュール (src/notifier.py)
Discord Webhook へのリアルタイム買取速報通知を行います。
"""

import json
import logging
from datetime import datetime
from typing import List, Optional
import urllib.request

from config import DISCORD_WEBHOOK_URL
from src.models import ComparisonItem

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Discord Webhook 通知送信クラス"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or DISCORD_WEBHOOK_URL

    def send_update(self, items: List[ComparisonItem], total_stores: int = 14) -> bool:
        """買取速報を Discord Embed として送信"""
        if not self.webhook_url:
            logger.info("Discord Webhook URL が設定されていないため、通知をスキップします。")
            return False

        if not items:
            return False

        # サマリー集計
        max_price_item = max(items, key=lambda x: x.best_price)
        max_diff_item = max(items, key=lambda x: x.price_diff)

        # トップ5のモデルリスト
        top_items = sorted(items, key=lambda x: -x.best_price)[:5]
        top_fields = []
        for it in top_items:
            profit_str = f" (定価比 +{it.profit_jpy:,}円 / {it.profit_rate}%)" if it.profit_jpy is not None else ""
            diff_str = f" [店舗間差: +{it.price_diff:,}円]" if it.price_diff > 0 else ""
            top_fields.append(
                f"• **{it.summary_title}**: **{it.best_price:,}円** @ {it.best_store}{diff_str}{profit_str}"
            )

        embed = {
            "title": "📱 iPhone 18 買取価格 最新速報",
            "description": f"国内・主要 **{total_stores}店舗** の最新買取価格を調査・突合しました。",
            "color": 0x1E88E5,  # ブルー
            "fields": [
                {
                    "name": "🏆 最高買取額",
                    "value": f"**{max_price_item.summary_title}**\n**{max_price_item.best_price:,}円** ({max_price_item.best_store})",
                    "inline": True,
                },
                {
                    "name": "⚡ 最大店舗間価格差",
                    "value": f"**{max_diff_item.summary_title}**\n**+{max_diff_item.price_diff:,}円** ({max_diff_item.best_store} vs {max_diff_item.lowest_store})",
                    "inline": True,
                },
                {
                    "name": "📊 高額買取モデル TOP 5",
                    "value": "\n".join(top_fields),
                    "inline": False,
                },
            ],
            "footer": {
                "text": f"iPhone 18 買取価格トラッカー • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            },
        }

        payload = {
            "username": "iPhone18 買取トラッカー",
            "embeds": [embed],
        }

        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info("Discord 通知を送信しました (Status: %d)", resp.status)
                return True
        except Exception as e:
            logger.error("Discord 通知送信失敗: %s", e)
            return False

    def send_price_change_alert(self, changed_items: List[dict]) -> bool:
        """価格変動検知時のアラートを送信"""
        if not self.webhook_url or not changed_items:
            return False

        change_lines = []
        for c in changed_items[:10]:
            diff_str = f"+{c['diff']:,}円 ↗" if c['diff'] > 0 else f"{c['diff']:,}円 ↘"
            change_lines.append(
                f"• **{c['title']}**: {c['old_price']:,}円 ➔ **{c['new_price']:,}円** ({diff_str}) @ {c['best_store']}"
            )

        embed = {
            "title": "🚨 【価格変動検知】iPhone 18 買取価格の変動速報",
            "description": f"前回の調査から **{len(changed_items)} 機種** で買取最高価格の変動を検知しました！",
            "color": 0xFF5722,  # オレンジ/レッド
            "fields": [
                {
                    "name": "📈 変動モデル一覧",
                    "value": "\n".join(change_lines) if change_lines else "なし",
                    "inline": False,
                }
            ],
            "footer": {
                "text": f"iPhone 18 定期監視システム • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            },
        }

        payload = {
            "username": "iPhone18 変動アラート",
            "embeds": [embed],
        }

        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info("Discord 変動アラートを送信しました (Status: %d)", resp.status)
                return True
        except Exception as e:
            logger.error("Discord 変動アラート送信失敗: %s", e)
            return False
