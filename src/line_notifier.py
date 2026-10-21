"""
LINE 公式アカウント (Messaging API) 通知モジュール (src/line_notifier.py)
毎朝の最新 iPhone 18 買取価格、還元率ランキング、価格変動情報を
LINEアカウントへ自動配信します。
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import urllib.request
import urllib.error

from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID
from src.models import ComparisonItem

logger = logging.getLogger(__name__)


class LineNotifier:
    """LINE Messaging API を用いた買取価格レポート通知クラス"""

    def __init__(
        self,
        channel_access_token: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.token = channel_access_token if channel_access_token is not None else LINE_CHANNEL_ACCESS_TOKEN
        self.user_id = user_id if user_id is not None else LINE_USER_ID
        self.last_error: str = ""

    @property
    def is_configured(self) -> bool:
        """有効なトークンが設定されているかどうかを厳密に判定"""
        if not self.token or not self.token.strip():
            return False
        token = self.token.strip()
        # プレースホルダーのままであるかチェック
        if "ここに" in token or "YOUR_" in token or "token_here" in token.lower():
            return False
        # 非ASCII文字（全角文字等）チェック
        try:
            token.encode("ascii")
        except UnicodeEncodeError:
            return False
        # LINEチャネルアクセストークン（長期）は通常100文字以上の長い文字列
        return len(token) >= 10

    def format_morning_report(
        self,
        items: List[ComparisonItem],
        total_stores: int = 14,
        changed_items: Optional[List[dict]] = None,
    ) -> str:
        """毎朝配信用メッセージテキストの組み立て"""
        if not items:
            return "📱【iPhone 18 買取速報】現在取得できる価格データがありません。"

        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        max_price_item = max(items, key=lambda x: x.best_price)
        max_diff_item = max(items, key=lambda x: x.price_diff)

        # 還元率・差益上位 5 件 (公式価格があるもの優先)
        profit_items = [it for it in items if it.profit_rate is not None]
        top_profit = sorted(profit_items, key=lambda x: -(x.profit_rate or 0))[:5]

        lines = [
            "📱【iPhone 18 買取速報】朝の最新価格レポート",
            f"📅 {now_str} (国内{total_stores}店舗調査)",
            "",
            "🏆【市場最高買取額】",
            f"• {max_price_item.summary_title}",
            f"  {max_price_item.best_price:,}円 ({max_price_item.best_store})",
            f"  店舗間差: +{max_price_item.price_diff:,}円",
            "",
            "📊【還元率・差益 TOP 5 (Apple公式価格比)】",
        ]

        for idx, it in enumerate(top_profit, start=1):
            profit_sign = "+" if (it.profit_jpy and it.profit_jpy > 0) else ""
            profit_txt = f"{profit_sign}{it.profit_jpy:,}円" if it.profit_jpy is not None else "-"
            rate_txt = f"{it.profit_rate}%" if it.profit_rate is not None else "-"
            short_name = f"{it.model_name.replace('iPhone 18 ', '')} {it.capacity}"
            lines.append(
                f"{idx}. {short_name}: {it.best_price:,}円"
                f" ({profit_txt} / {rate_txt}) @{it.best_store}"
            )

        if max_diff_item and max_diff_item.price_diff > 0:
            lines.extend([
                "",
                "⚡【最大店舗間差額チャンス】",
                f"• {max_diff_item.summary_title}: 差額 +{max_diff_item.price_diff:,}円",
                f"  最高: {max_diff_item.best_price:,}円 ({max_diff_item.best_store})",
                f"  最安: {max_diff_item.lowest_price:,}円 ({max_diff_item.lowest_store})",
            ])

        # 価格変動の掲載 (あれば)
        if changed_items:
            lines.extend(["", "📈【前回比 価格変動検知】"])
            for c in changed_items[:4]:
                diff_sym = f"+{c['diff']:,}円 ↗" if c['diff'] > 0 else f"{c['diff']:,}円 ↘"
                c_title = c['title'].replace("iPhone 18 ", "")
                lines.append(f"• {c_title}: {c['new_price']:,}円 ({diff_sym}) @{c['best_store']}")
            if len(changed_items) > 4:
                lines.append(f"  (他 {len(changed_items) - 4} 件の変動あり)")

        # カラー別価格差の注目情報
        try:
            from src.comparator import analyze_color_spread
            color_groups = analyze_color_spread(items)
            if color_groups and color_groups[0].max_spread > 0:
                top_g = color_groups[0]
                lines.extend([
                    "",
                    "🎨【カラー別価格差リサーチ速報】",
                    f"同容量でもカラーにより最大 {top_g.max_spread:,}円 の格差あり！",
                    f"• {top_g.model_name} {top_g.capacity}: 👑{top_g.top_color}({top_g.top_price:,}円)が最高値",
                    f"  最安色({top_g.lowest_color}: {top_g.lowest_price:,}円)比で +{top_g.max_spread:,}円 高額査定",
                ])
                if top_g.store_deductions:
                    note = list(top_g.store_deductions.values())[0]
                    lines.append(f"  💡 買取1丁目減額: {note}")
        except Exception as e:
            logger.debug("カラー価格差集計スキップ: %s", e)

        lines.extend([
            "",
            "※HTMLダッシュボード(latest_dashboard.html)で全店舗の詳細比較表・推移グラフをご覧いただけます。",
        ])

        return "\n".join(lines)

    def format_profit_only_report(
        self,
        items: List[ComparisonItem],
        total_stores: int = 14,
        changed_items: Optional[List[dict]] = None,
        min_profit_rate: float = 100.0,
    ) -> str:
        """等価格以上（定価以上・還元率100%以上）の端末のみを抽出した専用レポート"""
        if not items:
            return "📱【iPhone 18 等価格以上速報】現在取得できる価格データがありません。"

        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")

        # 等価格以上（還元率 >= min_profit_rate または 差益 >= 0）の端末を抽出
        profit_items = [
            it for it in items
            if (it.profit_rate is not None and it.profit_rate >= min_profit_rate)
            or (it.profit_jpy is not None and it.profit_jpy >= 0)
        ]
        # 還元率順、差益順、価格順にソート
        profit_items.sort(key=lambda x: (-(x.profit_rate or 0), -(x.profit_jpy or 0), -x.best_price))

        lines = [
            "📱【iPhone 18 等価格以上(定価以上)速報】",
            f"📅 {now_str} (国内{total_stores}店舗調査)",
            "",
        ]

        if profit_items:
            lines.extend([
                f"🔥 Apple公式定価と同額以上の端末を【{len(profit_items)}件】検知しました！",
                "（定価と同額以上で売却・ポイント還元狙いが可能なモデルです）",
                "",
            ])
            for idx, it in enumerate(profit_items, start=1):
                model_title = f"{it.model_name} {it.capacity}"
                color_txt = f"({it.color})" if it.color else ""
                profit_sign = "+" if (it.profit_jpy and it.profit_jpy > 0) else ""
                profit_txt = f"{profit_sign}{it.profit_jpy:,}円" if it.profit_jpy is not None else "±0円"
                rate_txt = f"{it.profit_rate:.1f}%" if it.profit_rate is not None else "-"

                lines.append(f"【{idx}】{model_title} {color_txt}")
                lines.append(f"  • 買取最高: {it.best_price:,}円 (@{it.best_store})")
                if it.official_price:
                    lines.append(f"  • Apple定価: {it.official_price:,}円")
                lines.append(f"  • 差益/還元: {profit_txt} (還元率 {rate_txt})")

                extra_info = []
                if it.price_change is not None and it.price_change != 0:
                    chg_sym = f"+{it.price_change:,}円 ↗" if it.price_change > 0 else f"{it.price_change:,}円 ↘"
                    extra_info.append(f"前回比 {chg_sym}")
                if it.price_diff > 0:
                    extra_info.append(f"店舗間差 +{it.price_diff:,}円")
                if extra_info:
                    lines.append(f"  • 変動/格差: {' / '.join(extra_info)}")

                code_info = []
                if it.part_number:
                    code_info.append(f"型番:{it.part_number}")
                if it.jan:
                    code_info.append(f"JAN:{it.jan}")
                if code_info:
                    lines.append(f"  • 識別情報: {' '.join(code_info)}")
                lines.append("")

        else:
            lines.extend([
                "⚠️ 本日の調査では、Apple公式定価と同額以上(還元率100%以上)の買取端末はありませんでした。",
                "",
                "📊【参考: 現在の最高還元率 TOP 3】",
            ])
            all_profit = [it for it in items if it.profit_rate is not None]
            top_available = sorted(all_profit, key=lambda x: -(x.profit_rate or 0))[:3]
            for idx, it in enumerate(top_available, start=1):
                short_name = f"{it.model_name.replace('iPhone 18 ', '')} {it.capacity}"
                color_txt = f"({it.color})" if it.color else ""
                profit_txt = f"{it.profit_jpy:,}円" if it.profit_jpy is not None else "-"
                rate_txt = f"{it.profit_rate:.1f}%" if it.profit_rate is not None else "-"
                lines.append(f"{idx}. {short_name} {color_txt}: {it.best_price:,}円 (@{it.best_store})")
                if it.official_price:
                    lines.append(f"   定価: {it.official_price:,}円 (差額: {profit_txt} / 還元率 {rate_txt})")

            lines.extend([
                "",
                "※定価以上の高額買取モデルが検知され次第、速報でお知らせします。",
            ])

        lines.extend([
            "",
            "※HTMLダッシュボード(latest_dashboard.html)で全店舗の詳細比較表をご覧いただけます。",
        ])
        return "\n".join(lines)

    def format_targeted_report(
        self,
        items: List[ComparisonItem],
        target_label: str = "",
        total_stores: int = 14,
        changed_items: Optional[List[dict]] = None,
    ) -> str:
        """指定端末限定の価格レポートテキストを作成"""
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        header = "📱【iPhone 18 指定端末 買取速報】"
        target_info = f"🎯 対象指定: {target_label}" if target_label else "🎯 指定端末レポート"

        if not items:
            return f"{header}\n📅 {now_str}\n{target_info}\n\n⚠️ 指定条件に一致する端末データが見つかりませんでした。"

        lines = [
            header,
            f"📅 {now_str} (国内{total_stores}店舗調査)",
            target_info,
            f"（該当件数: {len(items)}件）",
            "",
        ]

        # 1〜2件の場合は各店舗の価格比較詳細付きで表示
        if len(items) <= 2:
            for idx, it in enumerate(items, start=1):
                model_title = f"{it.model_name} {it.capacity}"
                color_txt = f"({it.color})" if it.color else ""
                profit_sign = "+" if (it.profit_jpy and it.profit_jpy > 0) else ""
                profit_txt = f"{profit_sign}{it.profit_jpy:,}円" if it.profit_jpy is not None else "-"
                rate_txt = f"{it.profit_rate:.1f}%" if it.profit_rate is not None else "-"

                lines.append(f"【{idx}】{model_title} {color_txt}")
                lines.append(f"  • 買取最高: {it.best_price:,}円 (@{it.best_store})")
                if it.lowest_price > 0 and it.lowest_store != it.best_store:
                    lines.append(f"  • 最安買取: {it.lowest_price:,}円 (@{it.lowest_store}) [店舗差 +{it.price_diff:,}円]")
                if it.official_price:
                    lines.append(f"  • Apple定価: {it.official_price:,}円")
                lines.append(f"  • 差益/還元: {profit_txt} (還元率 {rate_txt})")

                if it.price_change is not None and it.price_change != 0:
                    chg_sym = f"+{it.price_change:,}円 ↗" if it.price_change > 0 else f"{it.price_change:,}円 ↘"
                    lines.append(f"  • 前回比変動: {chg_sym}")

                code_info = []
                if it.part_number:
                    code_info.append(f"型番:{it.part_number}")
                if it.jan:
                    code_info.append(f"JAN:{it.jan}")
                if code_info:
                    lines.append(f"  • 識別情報: {' '.join(code_info)}")

                # 店舗別価格上位一覧
                if it.store_prices:
                    sorted_stores = sorted(it.store_prices.items(), key=lambda x: -x[1])
                    lines.append("  🏬 [店舗別 買取価格]")
                    for s_name, s_price in sorted_stores[:6]:
                        crown = " ★最高値" if s_name == it.best_store else ""
                        lines.append(f"    - {s_name}: {s_price:,}円{crown}")
                    if len(sorted_stores) > 6:
                        lines.append(f"    (他 {len(sorted_stores) - 6} 店舗)")
                lines.append("")
        else:
            # 3件以上の場合は一覧サマリー形式
            for idx, it in enumerate(items, start=1):
                model_title = f"{it.model_name.replace('iPhone 18 ', '')} {it.capacity}"
                color_txt = f"({it.color})" if it.color else ""
                profit_sign = "+" if (it.profit_jpy and it.profit_jpy > 0) else ""
                profit_txt = f"{profit_sign}{it.profit_jpy:,}円" if it.profit_jpy is not None else "-"
                rate_txt = f"{it.profit_rate:.1f}%" if it.profit_rate is not None else "-"
                diff_txt = f" (前回比 {it.trend_badge})" if it.trend_badge and it.price_change else ""

                lines.append(f"{idx}. {model_title} {color_txt}: {it.best_price:,}円 (@{it.best_store})")
                price_line = f"   最高: {it.best_price:,}円"
                if it.official_price:
                    price_line += f" / 定価: {it.official_price:,}円 (差益: {profit_txt} / {rate_txt})"
                lines.append(price_line + diff_txt)
                if it.part_number:
                    lines.append(f"   型番: {it.part_number}")

            lines.append("")

        # 複数カラーが含まれる場合はカラー別価格順位を補足
        unique_groups = {(it.model_name, it.capacity) for it in items}
        if len(items) >= 2 and len(unique_groups) == 1:
            sorted_by_p = sorted(items, key=lambda x: x.best_price, reverse=True)
            top_p = sorted_by_p[0].best_price
            lines.append("🎨 [カラー別価格順位 & 格差]")
            for rank, it in enumerate(sorted_by_p, 1):
                diff = it.best_price - top_p
                diff_str = "基準(最高値)" if diff == 0 else f"{diff:,}円"
                lines.append(f"  {rank}位 {it.color}: {it.best_price:,}円 ({diff_str})")
            lines.append("")

        lines.extend([
            "※HTMLダッシュボード(latest_dashboard.html)で全店舗の詳細比較表をご覧いただけます。",
        ])
        return "\n".join(lines)

    def format_color_spread_report(
        self,
        items: List[ComparisonItem],
        total_stores: int = 14,
    ) -> str:
        """カラー別価格差・人気色格差に特化した専用LINEレポート"""
        if not items:
            return "📱【iPhone 18 カラー別価格差速報】現在取得できるデータがありません。"

        from src.comparator import analyze_color_spread
        color_groups = analyze_color_spread(items)
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")

        lines = [
            "📱【iPhone 18 カラー別買取価格差リサーチ】",
            f"📅 {now_str} (国内{total_stores}店舗調査)",
            "",
            "🎨 色の違いによる買取価格差・人気色格差の速報です。",
            "※主要店では新色・人気色が高額査定され、他色は減額対象となります。",
            "",
        ]

        for idx, g in enumerate(color_groups[:4], 1):
            lines.append(f"🔥 [{idx}] {g.model_name} {g.capacity} (最大格差: {g.max_spread:,}円)")
            lines.append(f"  👑 最高値: {g.top_color} {g.top_price:,}円 (@{g.colors[0].best_store})")
            color_strs = []
            for c in g.colors:
                diff_str = "±0" if c.diff_from_top == 0 else f"{c.diff_from_top // 1000:+}k"
                color_strs.append(f"{c.color}({diff_str})")
            lines.append(f"  📊 内訳: {' / '.join(color_strs)}")
            if g.store_deductions:
                note = list(g.store_deductions.values())[0]
                lines.append(f"  💡 買取1丁目減額: {note}")
            lines.append("")

        lines.extend([
            "⚠️ [購入・売却時のアドバイス]",
            "同容量でもカラー選定を誤ると10,000円〜20,000円以上査定が下がります。売却前提の場合は最高値カラー(バーガンディ等)の選定が最も高還元率となります。",
            "",
            "※HTMLダッシュボードで全機種のカラー価格差マトリクスをご覧いただけます。",
        ])

        return "\n".join(lines)

    def send_morning_report(
        self,
        items: List[ComparisonItem],
        total_stores: int = 14,
        changed_items: Optional[List[dict]] = None,
        profit_only: bool = False,
        min_profit_rate: float = 100.0,
        skip_if_no_profit: bool = False,
        target_label: Optional[str] = None,
        color_spread_only: bool = False,
    ) -> bool:
        """価格レポートをLINEへ送信"""
        if not self.is_configured:
            logger.warning(
                "LINEチャネルアクセストークンが設定されていません。\n"
                "config.py の LINE_CHANNEL_ACCESS_TOKEN または環境変数に設定してください。"
            )
            return False

        if color_spread_only:
            # カラー別価格差専用レポート
            message_text = self.format_color_spread_report(items, total_stores=total_stores)
        elif target_label:
            # 指定端末専用レポート
            message_text = self.format_targeted_report(
                items,
                target_label=target_label,
                total_stores=total_stores,
                changed_items=changed_items,
            )
        elif profit_only:
            # 等価格以上の端末のみチェック
            profitable = [
                it for it in items
                if (it.profit_rate is not None and it.profit_rate >= min_profit_rate)
                or (it.profit_jpy is not None and it.profit_jpy >= 0)
            ]
            if not profitable and skip_if_no_profit:
                logger.info("等価格以上の端末が0件のため、LINE通知をスキップしました。")
                return True

            message_text = self.format_profit_only_report(
                items,
                total_stores=total_stores,
                changed_items=changed_items,
                min_profit_rate=min_profit_rate,
            )
        else:
            message_text = self.format_morning_report(
                items, total_stores=total_stores, changed_items=changed_items
            )

        return self.send_text_message(message_text)

    def send_text_message(self, text: str) -> bool:
        """LINE Messaging API経由でテキストメッセージを送信"""
        if not self.is_configured:
            self.last_error = "LINEチャネルアクセストークンが未設定またはプレースホルダーのままです。"
            return False

        # ユーザーID指定があれば Push、なければ Broadcast (友達全員)
        if self.user_id and self.user_id.strip():
            url = "https://api.line.me/v2/bot/message/push"
            payload = {
                "to": self.user_id.strip(),
                "messages": [{"type": "text", "text": text}],
            }
        else:
            url = "https://api.line.me/v2/bot/message/broadcast"
            payload = {
                "messages": [{"type": "text", "text": text}],
            }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token.strip()}",
            "User-Agent": "iPhone18-Kaitori-Tracker/1.0",
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                logger.info("LINE通知の送信に成功しました (Status: %d)", resp.status)
                self.last_error = ""
                return True
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error("LINE通知送信エラー (HTTP %d): %s", e.code, err_body)
            if e.code == 401:
                self.last_error = f"HTTP 401 認証失敗: チャネルアクセストークンが無効または失効しています ({err_body})"
            elif e.code == 400:
                self.last_error = f"HTTP 400 リクエスト不正: {err_body}"
            elif e.code == 403:
                self.last_error = f"HTTP 403 権限エラー: Messaging APIが有効化されているかご確認ください ({err_body})"
            else:
                self.last_error = f"HTTP {e.code}: {err_body}"
            return False
        except Exception as e:
            logger.error("LINE通知通信エラー: %s", e)
            self.last_error = str(e)
            return False
