"""
iPhone 18 買取価格トラッカー メイン実行スクリプト (main.py)
買取ルデヤ・森森買取・最高値ナビ(14店舗)から最新買取価格をスクレイピングし、
店舗間価格比較、利益計算、時系列推移追跡、Excel/CSV/HTMLダッシュボード出力を行います。
定期監視モード (--watch) を備え、価格変動を自動検出します。
"""

import sys
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# WindowsコンソールでのUTF-8出力対応
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import webbrowser

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from src.models import PriceRecord, ComparisonItem, ColorSpreadGroup
from src.scrapers.kaitori1chome import Kaitori1ChomeScraper
from src.scrapers.rudeya import RudeyaScraper
from src.scrapers.morimori import MorimoriScraper
from src.scrapers.saikoune import SaikouneScraper
from src.scrapers.apple import AppleOfficialScraper
from src.comparator import PriceComparator, filter_items, analyze_color_spread
from src.history import PriceHistoryTracker
from src.exporter import Exporter
from src.notifier import DiscordNotifier
from src.line_notifier import LineNotifier
import config
from config import MORNING_SCHEDULE_TIME

console = Console(force_terminal=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("main")


def update_env_token(token: str) -> None:
    """ .env の LINE_CHANNEL_ACCESS_TOKEN を安全に更新 """
    env_path = Path(__file__).parent / ".env"
    token = token.strip()
    if not env_path.exists():
        content = (
            f"# LINE公式アカウント (Messaging API) 設定\n"
            f"LINE_CHANNEL_ACCESS_TOKEN={token}\n"
            f"LINE_USER_ID=\n"
            f"MORNING_SCHEDULE_TIME=08:00\n"
        )
        env_path.write_text(content, encoding="utf-8")
    else:
        lines = env_path.read_text(encoding="utf-8").splitlines()
        new_lines = []
        replaced = False
        for line in lines:
            if line.strip().startswith("LINE_CHANNEL_ACCESS_TOKEN="):
                new_lines.append(f"LINE_CHANNEL_ACCESS_TOKEN={token}")
                replaced = True
            else:
                new_lines.append(line)
        if not replaced:
            new_lines.append(f"LINE_CHANNEL_ACCESS_TOKEN={token}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    config.LINE_CHANNEL_ACCESS_TOKEN = token
    import os
    os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = token


def update_env_target(target: str = "", model: str = "", capacity: str = "", color: str = "") -> None:
    """ .env の TARGET_* 設定を安全に更新 """
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    keys_to_set = {
        "TARGET_DEVICE": target,
        "TARGET_MODEL": model,
        "TARGET_CAPACITY": capacity,
        "TARGET_COLOR": color,
    }
    found_keys = set()
    for line in lines:
        matched = False
        for k, v in keys_to_set.items():
            if line.strip().startswith(f"{k}="):
                new_lines.append(f"{k}={v}")
                found_keys.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    for k, v in keys_to_set.items():
        if k not in found_keys:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    config.TARGET_DEVICE = target
    config.TARGET_MODEL = model
    config.TARGET_CAPACITY = capacity
    config.TARGET_COLOR = color
    import os
    os.environ["TARGET_DEVICE"] = target
    os.environ["TARGET_MODEL"] = model
    os.environ["TARGET_CAPACITY"] = capacity
    os.environ["TARGET_COLOR"] = color


def prompt_target_device():
    """端末選択の対話ウィザード"""
    console.print("\n[bold cyan]=== 🎯 取得したい端末を選択してください ===[/bold cyan]")
    console.print("  [1] iPhone 18 Pro Max")
    console.print("  [2] iPhone 18 Pro")
    console.print("  [3] iPhone 18")
    console.print("  [4] すべての機種 (容量やカラー・キーワードで絞り込み)")
    console.print("  [5] キーワードを自由入力 (例: 'Pro Max 256GB', 'バーガンディ', 'MJX74J/A')")

    try:
        m_choice = console.input("[yellow]機種番号を選択 [1-5, デフォルト: 1]: [/yellow]").strip()
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)

    model = ""
    target_kw = ""
    if not m_choice or m_choice == "1":
        model = "iPhone 18 Pro Max"
    elif m_choice == "2":
        model = "iPhone 18 Pro"
    elif m_choice == "3":
        model = "iPhone 18"
    elif m_choice == "5":
        try:
            target_kw = console.input("[yellow]検索キーワードを入力: [/yellow]").strip()
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)
        return target_kw, "", "", ""

    # 容量選択
    console.print("\n[bold cyan]=== 容量を選択してください ===[/bold cyan]")
    console.print("  [1] すべての容量")
    console.print("  [2] 256GB")
    console.print("  [3] 512GB")
    console.print("  [4] 1TB")
    console.print("  [5] 2TB")
    console.print("  [6] 128GB")
    try:
        c_choice = console.input("[yellow]容量番号を選択 [1-6, デフォルト: 1]: [/yellow]").strip()
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)
    cap_map = {"2": "256GB", "3": "512GB", "4": "1TB", "5": "2TB", "6": "128GB"}
    capacity = cap_map.get(c_choice, "")

    # カラー選択
    try:
        color = console.input("\n[yellow]カラー名 (例: バーガンディ, シルバー, ブラック。空Enterですべて): [/yellow]").strip()
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)

    return target_kw, model, capacity, color



def print_banner():
    banner = Text("=== iPhone 18 買取価格 自動収集・比較・トレンド分析ツール ===", style="bold cyan")
    console.print(Panel(banner, subtitle="国内主要14店舗 リアルタイム価格トラッカー & 変動検知システム", expand=False))


def display_comparison_table(items: List[ComparisonItem]):
    """Richを使った見やすいコンソールテーブル表示"""
    table = Table(
        title=f"[ iPhone 18 シリーズ 買取価格 比較表 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ]",
        header_style="bold magenta",
        show_lines=True,
    )

    table.add_column("機種名", style="cyan", no_wrap=True)
    table.add_column("容量", style="yellow", justify="center")
    table.add_column("カラー", style="white")
    table.add_column("最高買取店", style="bold green", justify="center")
    table.add_column("最高価格", style="bold green", justify="right")
    table.add_column("前回比", justify="center")
    table.add_column("ルデヤ", style="bright_blue", justify="right")
    table.add_column("森森買取", style="bright_cyan", justify="right")
    table.add_column("価格差", style="bold yellow", justify="right")
    table.add_column("Apple公式価格", style="dim", justify="right")
    table.add_column("差益(利益)", style="bold magenta", justify="right")
    table.add_column("還元率", style="bold red", justify="right")

    for it in items:
        rudeya_price = f"{it.store_prices.get('買取ルデヤ', 0):,}" if "買取ルデヤ" in it.store_prices else "-"
        morimori_price = f"{it.store_prices.get('森森買取', 0):,}" if "森森買取" in it.store_prices else "-"
        diff_str = f"+{it.price_diff:,}円" if it.price_diff > 0 else "±0円"
        official_str = f"{it.official_price:,}円" if it.official_price else "-"

        # 前回比トレンド
        if it.price_change is None:
            trend_text = Text("NEW", style="bold blue")
        elif it.price_change > 0:
            trend_text = Text(f"+{it.price_change:,} ↗", style="bold green")
        elif it.price_change < 0:
            trend_text = Text(f"{it.price_change:,} ↘", style="bold red")
        else:
            trend_text = Text("±0", style="dim")

        if it.profit_jpy is not None:
            profit_str = f"+{it.profit_jpy:,}円" if it.profit_jpy >= 0 else f"{it.profit_jpy:,}円"
        else:
            profit_str = "-"

        rate_str = f"{it.profit_rate}%" if it.profit_rate is not None else "-"

        # スタイルの調整
        diff_style = "bold yellow" if it.price_diff > 0 else "dim"
        profit_style = "bold green" if (it.profit_jpy and it.profit_jpy > 0) else "white"

        table.add_row(
            it.model_name,
            it.capacity,
            it.color,
            it.best_store,
            f"{it.best_price:,}円",
            trend_text,
            rudeya_price,
            morimori_price,
            Text(diff_str, style=diff_style),
            official_str,
            Text(profit_str, style=profit_style),
            rate_str,
        )

    console.print(table)


def display_summary(items: List[ComparisonItem], changed_items: List[dict]):
    """サマリー指標および変動アラートの表示"""
    total = len(items)
    if total == 0:
        return

    # 最高値店舗内訳
    store_counts = {}
    for it in items:
        store_counts[it.best_store] = store_counts.get(it.best_store, 0) + 1
    store_summary = " | ".join(f"{s}: {c}件" for s, c in sorted(store_counts.items(), key=lambda x: -x[1])[:3])

    max_diff_item = max(items, key=lambda x: x.price_diff) if items else None
    max_price_item = max(items, key=lambda x: x.best_price) if items else None

    summary_text = (
        f"・[bold]比較対象モデル数:[/bold] {total} 機種 (Pro Max / Pro)\n"
        f"・[bold]最高値店舗の内訳:[/bold] {store_summary}\n"
        f"・[bold]最高買取価格:[/bold] {max_price_item.summary_title} -> "
        f"[bold green]{max_price_item.best_price:,}円[/bold green] ({max_price_item.best_store})\n"
    )
    if max_diff_item and max_diff_item.price_diff > 0:
        summary_text += (
            f"・[bold]最大価格差 (差額チャンス):[/bold] {max_diff_item.summary_title} -> "
            f"[bold yellow]+{max_diff_item.price_diff:,}円[/bold yellow] "
            f"({max_diff_item.best_store} {max_diff_item.best_price:,}円 vs "
            f"{max_diff_item.lowest_store} {max_diff_item.lowest_price:,}円)\n"
        )

    console.print(Panel(summary_text, title="[ 市場サマリー & チャンス分析 ]", border_style="green"))

    # 価格変動アラート表示
    if changed_items:
        change_text = ""
        for c in changed_items:
            diff_symbol = f"+{c['diff']:,}円 ↗" if c['diff'] > 0 else f"{c['diff']:,}円 ↘"
            color_style = "bold green" if c['diff'] > 0 else "bold red"
            change_text += f"• [bold]{c['title']}[/bold]: {c['old_price']:,}円 -> [{color_style}]{c['new_price']:,}円 ({diff_symbol})[/{color_style}] ({c['best_store']})\n"
        console.print(Panel(change_text.strip(), title=f"🚨 [ 価格変動を検知しました ({len(changed_items)}件) ]", border_style="red"))


def display_color_spread_table(color_groups: List[ColorSpreadGroup]):
    """カラー別価格差リサーチテーブルのRich表示"""
    table = Table(
        title="🎨 【カラー別買取価格差リサーチ】色の違いによる買取格差・人気色マトリクス",
        box=box.ROUNDED,
        header_style="bold magenta",
        title_style="bold yellow",
    )
    table.add_column("機種名", style="bold white", width=18)
    table.add_column("容量", justify="center", style="cyan", width=8)
    table.add_column("最高値カラー (基準色)", style="bold green", width=24)
    table.add_column("カラー別価格差 (基準比)", width=42)
    table.add_column("最大カラー格差", justify="right", style="bold red", width=18)
    table.add_column("主要店減額メモ (買取1丁目等)", style="dim", width=34)

    for g in color_groups:
        top_store = f" (@{g.colors[0].best_store})" if g.colors else ""
        top_str = f"🥇 {g.top_color} {g.top_price:,}円{top_store}"

        diff_lines = []
        for c in g.colors:
            if c.diff_from_top == 0:
                diff_lines.append(f"[bold green]{c.color}: {c.best_price:,}円 (基準 ±0円)[/bold green]")
            else:
                diff_lines.append(f"[yellow]{c.color}: {c.best_price:,}円 ({c.diff_from_top:,}円)[/yellow]")
        diff_str = "\n".join(diff_lines)

        spread_str = f"[bold red]+{g.max_spread:,}円 格差[/bold red]" if g.max_spread > 0 else "[dim]格差なし[/dim]"
        note = list(g.store_deductions.values())[0] if g.store_deductions else "-"

        table.add_row(
            g.model_name.replace("iPhone 18 ", ""),
            g.capacity,
            top_str,
            diff_str,
            spread_str,
            note,
        )

    console.print(table)


def play_chime():
    """Windows通知音を鳴らす"""
    if sys.platform == "win32":
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass


def execute_cycle(args, is_first: bool = True) -> Optional[dict]:
    """1サイクルのデータ収集・突合・エクスポートを実行"""
    console.print(f"\n[bold cyan]>>> 買取価格データの収集を開始します... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})[/bold cyan]")

    # 1. Apple公式HPよりリアルタイム販売価格・型番を取得
    apple_scraper = AppleOfficialScraper()
    apple_catalog = {}
    try:
        apple_catalog = apple_scraper.get_official_catalog()
        console.print(f"[OK] [cyan]{apple_scraper.store_name}[/cyan]: {len(apple_catalog)} 件の最新公式販売価格・型番を取得")
    except Exception as e:
        console.print(f"[WARN] [yellow]{apple_scraper.store_name} 取得警告 (設定値へフォールバック)[/yellow]: {e}")

    scrapers = [
        Kaitori1ChomeScraper(),
        RudeyaScraper(),
        MorimoriScraper(),
        SaikouneScraper(),
    ]

    all_records: List[PriceRecord] = []
    with console.status("[bold green]主要買取店から最新価格を収集中...[/bold green]"):
        for scraper in scrapers:
            try:
                records = scraper.scrape()
                all_records.extend(records)
                console.print(f"[OK] [cyan]{scraper.store_name}[/cyan]: {len(records)} 件取得")
            except Exception as e:
                console.print(f"[ERR] [red]{scraper.store_name} エラー[/red]: {e}")

    if not all_records:
        console.print("[bold red]買取データの取得に失敗しました。[/bold red]")
        return None

    # 2. 突合 & 比較 (取得時公式販売価格を使用)
    comparator = PriceComparator(all_records, official_catalog=apple_catalog)
    items = comparator.compare()

    # 3. 過去履歴との比較 & トレンド付与
    history_tracker = PriceHistoryTracker()
    items = history_tracker.attach_history_to_items(items)
    changed_items = history_tracker.detect_price_changes(items)

    # 4. 指定端末によるフィルタリング
    if getattr(args, "all_models", False):
        target_kw = ""
        target_m = ""
        target_c = ""
        target_col = ""
    else:
        target_kw = getattr(args, "target", "") or config.TARGET_DEVICE
        target_m = getattr(args, "model", "") or config.TARGET_MODEL
        target_c = getattr(args, "capacity", "") or config.TARGET_CAPACITY
        target_col = getattr(args, "color", "") or config.TARGET_COLOR

    target_label = ""
    if target_kw or target_m or target_c or target_col:
        parts = [p for p in [target_m, target_c, target_col, target_kw] if p]
        target_label = " ".join(parts)
        console.print(f"\n[bold yellow]🎯 指定端末で抽出中: {target_label} ({len(items)}件中)[/bold yellow]")
        console.print("[dim]※ 全機種を取得したい場合は 'run.bat' で [1] (全機種 通常実行) を選択するか、[14] でフィルターを解除してください。[/dim]")
        items = filter_items(items, target=target_kw, model=target_m, capacity=target_c, color=target_col)
        if not items:
            console.print(f"[bold red]指定条件 '{target_label}' に一致する端末データが見つかりませんでした。[/bold red]")
            return None
        console.print(f"[bold green]指定端末に一致: {len(items)} 件の価格データを取得[/bold green]")
        # 該当アイテムの生レコードのみに絞り込む (Exporter用)
        extracted_recs = [r for it in items for r in it.records]
        if extracted_recs:
            all_records = extracted_recs
        else:
            item_keys = {it.display_key for it in items}
            all_records = [r for r in all_records if r.display_key in item_keys]
        # changed_items も該当端末のみに絞り込む
        if changed_items:
            item_titles = {it.summary_title for it in items}
            changed_items = [c for c in changed_items if any(t in c.get("title", "") for t in item_titles)]

    # 5. カラー別価格差リサーチ集計
    color_groups = analyze_color_spread(items, all_records)
    if color_groups and color_groups[0].max_spread > 0:
        top_g = color_groups[0]
        console.print(
            f"\n[bold yellow]🎨【カラー別価格差リサーチ速報】同容量でもカラーにより最大 [bold red]{top_g.max_spread:,}円[/bold red] の格差を検知！ "
            f"({top_g.model_name.replace('iPhone 18 ', '')} {top_g.capacity}: 🥇{top_g.top_color} 最高値)[/bold yellow]"
        )

    # 6. 差額フィルタリング
    display_items = items
    if args.min_spread > 0:
        display_items = [it for it in items if it.price_diff >= args.min_spread]

    # 7. コンソール表示
    display_summary(display_items, changed_items)
    if getattr(args, "color_spread", False):
        display_color_spread_table(color_groups)
    display_comparison_table(display_items)

    # 8. 音声アラート
    if changed_items and args.alert:
        play_chime()

    # 9. エクスポート
    paths = None
    if not args.no_export:
        exporter = Exporter(items, all_records)
        paths = exporter.export_all()
        console.print("\n[bold green][ファイル出力完了][/bold green]")
        console.print(f"・HTMLダッシュボード: {paths['html']}")
        console.print(f"・Excelレポート:      {paths['excel']}")
        console.print(f"・CSVデータ:          {paths['csv']}")
        console.print(f"・JSONスナップショット: {paths['json']}")

    total_stores = len({r.store for r in all_records})

    # Discord通知
    if args.notify:
        notifier = DiscordNotifier()
        if changed_items:
            notifier.send_price_change_alert(changed_items)
        else:
            notifier.send_update(items, total_stores=total_stores)

    # LINE公式アカウント通知
    if getattr(args, "line_notify", False):
        line_notifier = LineNotifier()
        if line_notifier.is_configured:
            profit_only = getattr(args, "line_profit_only", False) or config.LINE_PROFIT_ONLY
            color_spread_only = getattr(args, "line_color_spread", False)
            min_rate = getattr(args, "min_profit_rate", None)
            if min_rate is None:
                min_rate = config.LINE_MIN_PROFIT_RATE
            skip_if_none = getattr(args, "skip_if_no_profit", False) or config.LINE_SKIP_IF_NO_PROFIT

            if color_spread_only:
                mode_label = "カラー別価格差レポート"
            elif target_label:
                mode_label = f"指定端末({target_label})レポート"
            elif profit_only:
                mode_label = "等価格以上(定価以上)限定レポート"
            else:
                mode_label = "朝の最新買取レポート"

            console.print(f"\n[cyan]LINE公式アカウント経由で{mode_label}を送信中...[/cyan]")
            ok = line_notifier.send_morning_report(
                items,
                total_stores=total_stores,
                changed_items=changed_items,
                profit_only=profit_only,
                min_profit_rate=min_rate,
                skip_if_no_profit=skip_if_none,
                target_label=target_label,
                color_spread_only=color_spread_only,
            )
            if ok:
                console.print(f"[bold green][LINE通知成功] LINEアカウントへ{mode_label}を配信しました[/bold green]")
                console.print("[dim]※ スマホに届かない場合は、LINE公式アカウントを友だち追加しているかご確認ください。[/dim]")
            else:
                console.print(f"[bold red][LINE通知失敗] 送信に失敗しました: {line_notifier.last_error}[/bold red]")
                console.print("[yellow]ヒント: LINE Developers の「チャネルアクセストークン（長期）」が正しいかご確認ください。[/yellow]")
        else:
            console.print(
                "\n[bold red]【LINE通知未送信】LINEチャネルアクセストークンが未設定または無効です。[/bold red]\n"
                f"[yellow]現在の設定値: {repr(line_notifier.token)}\n"
                "  .env ファイルを開き、LINE_CHANNEL_ACCESS_TOKEN に実際のトークンを設定して保存してください。[/yellow]"
            )

    # 初回のみダッシュボードを自動起動
    if is_first and args.open_dashboard and paths:
        console.print("\n[cyan]ブラウザでダッシュボードを開いています...[/cyan]")
        webbrowser.open(paths["html"].as_uri())

    return paths


def show_menu(args):
    """Rich対話メニューの表示"""
    console.print()

    # .env の指定端末フィルター設定を検知して表示
    current_filters = [
        f"モデル={config.TARGET_MODEL}" if config.TARGET_MODEL else "",
        f"容量={config.TARGET_CAPACITY}" if config.TARGET_CAPACITY else "",
        f"カラー={config.TARGET_COLOR}" if config.TARGET_COLOR else "",
        f"キーワード={config.TARGET_DEVICE}" if config.TARGET_DEVICE else "",
    ]
    active_filter_str = ", ".join(f for f in current_filters if f)
    if active_filter_str:
        console.print(Panel(
            f"[bold yellow]⚠️ 注意: .env に指定端末フィルターが設定されています: [{active_filter_str}][/bold yellow]\n"
            f"[dim]※ [1] を選択した場合はフィルターを無視して全32機種を通常取得します。\n"
            f"※ フィルター設定をクリアしたい場合は [14] (指定端末リセット) を選択してください。[/dim]",
            border_style="yellow",
            title="[ フィルター設定検知 ]"
        ))

    menu_text = (
        "[bold cyan][1][/bold cyan] 最新買取価格を取得 ＆ HTMLダッシュボードを開く [bold green](全機種 通常実行)[/bold green]\n"
        "[bold cyan][2][/bold cyan] [bold yellow]🎯 指定した端末のみの価格を取得[/bold yellow] (機種・容量・カラーを選択して取得)\n"
        "[bold cyan][3][/bold cyan] [bold magenta]🎨 カラー別価格差リサーチ[/bold magenta] (色の違いによる値段差・人気色格差を表示)\n"
        "[bold cyan][4][/bold cyan] 定期自動監視モード起動 (30分間隔で巡回・変動検知)\n"
        "[bold cyan][5][/bold cyan] 定期自動監視モード起動 (15分間隔 ＆ 変動時通知音つき)\n"
        "[bold cyan][6][/bold cyan] 価格差1,000円以上の差額チャンスのみ表示\n"
        "[bold cyan][7][/bold cyan] [bold green]LINE通知テスト送信[/bold green] (朝の総合レポート)\n"
        "[bold cyan][8][/bold cyan] [bold magenta]🔥 LINE通知テスト送信 (等価格以上の端末のみ)[/bold magenta]\n"
        "[bold cyan][9][/bold cyan] [bold yellow]🎯 LINE通知テスト送信 (指定した端末のみ)[/bold yellow]\n"
        "[bold cyan][10][/bold cyan] [bold magenta]🎨 LINE通知テスト送信 (カラー別価格差レポート)[/bold magenta]\n"
        "[bold cyan][11][/bold cyan] [bold yellow]毎朝自動LINE通知を登録[/bold yellow] (総合レポート 毎朝08:00)\n"
        "[bold cyan][12][/bold cyan] [bold magenta]🔥 毎朝自動LINE通知を登録 (等価格以上の端末のみ 毎朝08:00)[/bold magenta]\n"
        "[bold cyan][13][/bold cyan] [bold yellow]🎯 毎朝自動LINE通知を登録 (指定した端末のみ 毎朝08:00)[/bold yellow]\n"
        "[bold cyan][14][/bold cyan] [bold green]🔄 指定端末フィルターを解除・リセット[/bold green] (全機種モードに戻す)\n"
        "[bold cyan][15][/bold cyan] 毎朝自動LINE通知を解除 (Windowsタスク削除)\n"
        "[bold cyan][16][/bold cyan] システム検証 (単体テスト実行)\n"
        "[bold cyan][0][/bold cyan] 終了"
    )
    console.print(Panel(menu_text, title="[ 実行モードを選択してください ]", border_style="cyan"))

    try:
        choice = console.input("[bold yellow]番号を入力してEnter [デフォルト: 1]: [/bold yellow]").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n終了します。")
        sys.exit(0)

    if not choice or choice == "1":
        args.all_models = True
        args.open_dashboard = True
    elif choice == "2":
        # 🎯 指定した端末のみの価格を取得
        target_kw, model, capacity, color = prompt_target_device()
        args.target = target_kw
        args.model = model
        args.capacity = capacity
        args.color = color
        args.open_dashboard = True
    elif choice == "3":
        # 🎨 カラー別価格差リサーチ
        args.color_spread = True
        args.all_models = True
        args.open_dashboard = True
    elif choice == "4":
        args.watch = 30
        args.alert = True
        args.open_dashboard = True
    elif choice == "5":
        args.watch = 15
        args.alert = True
        args.open_dashboard = True
    elif choice == "6":
        args.min_spread = 1000
        args.open_dashboard = True
    elif choice == "7":
        line_notifier = LineNotifier()
        if not line_notifier.is_configured:
            console.print("\n[bold red]❌ LINEアクセストークンが未設定、またはプレースホルダーのままです[/bold red]")
            try:
                entered = console.input("\n[bold yellow]トークンをここに貼り付けてEnter (中断する場合はそのままEnter): [/bold yellow]").strip()
            except (KeyboardInterrupt, EOFError):
                sys.exit(0)

            if entered:
                update_env_token(entered)
                line_notifier = LineNotifier(channel_access_token=entered)
                console.print("[bold green]✅ .env にトークンを保存しました！[/bold green]\n")
            else:
                sys.exit(0)

        # 簡易即時テスト送信
        console.print("\n[cyan]LINE公式アカウントへ接続テストメッセージを送信中...[/cyan]")
        test_msg = (
            "📱【iPhone 18 買取トラッカー】\n"
            "LINE連携テストに成功しました！🎉\n"
            "毎朝このLINEアカウントへ最新の買取価格レポートが自動配信されます。\n"
            f"送信時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if line_notifier.send_text_message(test_msg):
            console.print("[bold green]🎉 テストメッセージの送信に成功しました！[/bold green]")
            try:
                do_full = console.input("[yellow]全店舗の価格をスクレイピングして完全レポートも今すぐ送信しますか？ [y/N]: [/yellow]").strip().lower()
            except (KeyboardInterrupt, EOFError):
                sys.exit(0)
            if do_full in ("y", "yes"):
                args.line_notify = True
                args.open_dashboard = True
            else:
                sys.exit(0)
        else:
            console.print(f"\n[bold red]❌ 送信に失敗しました: {line_notifier.last_error}[/bold red]")
            sys.exit(0)
    elif choice == "8":
        # 等価格以上の端末のみLINEテスト送信
        console.print("\n[bold magenta]全店舗の買取価格を取得し、Apple公式定価と同額以上(還元率100%以上)の端末のみをLINEに送信します...[/bold magenta]")
        args.line_notify = True
        args.line_profit_only = True
        args.open_dashboard = True
    elif choice == "9":
        # 🎯 指定した端末のみLINEテスト送信
        target_kw, model, capacity, color = prompt_target_device()
        args.target = target_kw
        args.model = model
        args.capacity = capacity
        args.color = color
        args.line_notify = True
        args.open_dashboard = True
    elif choice == "10":
        # 🎨 カラー別価格差レポートをLINEテスト送信
        console.print("\n[bold magenta]全店舗の買取価格を取得し、色の違いによる価格差・人気色格差レポートをLINEに送信します...[/bold magenta]")
        args.line_notify = True
        args.line_color_spread = True
        args.open_dashboard = True
    elif choice == "11":
        import subprocess
        console.print("\n[bold cyan]毎朝自動LINE通知タスク(総合レポート)をWindowsタスクスケジューラに登録します...[/bold cyan]")
        setup_bat = Path(__file__).parent / "setup_morning_task.bat"
        if setup_bat.exists():
            subprocess.run(["cmd.exe", "/c", str(setup_bat), MORNING_SCHEDULE_TIME], check=False)
        else:
            console.print("[red]setup_morning_task.bat が見つかりません。[/red]")
        sys.exit(0)
    elif choice == "12":
        import subprocess
        console.print("\n[bold magenta]毎朝自動LINE通知タスク(等価格以上限定)をWindowsタスクスケジューラに登録します...[/bold magenta]")
        setup_profit_bat = Path(__file__).parent / "setup_morning_profit_task.bat"
        if setup_profit_bat.exists():
            subprocess.run(["cmd.exe", "/c", str(setup_profit_bat), MORNING_SCHEDULE_TIME], check=False)
        else:
            console.print("[red]setup_morning_profit_task.bat が見つかりません。[/red]")
        sys.exit(0)
    elif choice == "13":
        # 🎯 指定した端末のみ毎朝自動LINE通知を登録
        target_kw, model, capacity, color = prompt_target_device()
        update_env_target(target=target_kw, model=model, capacity=capacity, color=color)
        console.print("[bold green]✅ .env に指定端末設定を保存しました。[/bold green]")
        import subprocess
        console.print("\n[bold cyan]毎朝自動LINE通知タスク(指定端末限定)をWindowsタスクスケジューラに登録します...[/bold cyan]")
        setup_bat = Path(__file__).parent / "setup_morning_task.bat"
        if setup_bat.exists():
            subprocess.run(["cmd.exe", "/c", str(setup_bat), MORNING_SCHEDULE_TIME], check=False)
        else:
            console.print("[red]setup_morning_task.bat が見つかりません。[/red]")
        sys.exit(0)
    elif choice == "14":
        # 🎯 指定端末フィルターの解除・リセット (全機種モードに戻す)
        update_env_target(target="", model="", capacity="", color="")
        console.print("\n[bold green]✅ 指定端末フィルターを解除しました！全32機種モードに戻りました。[/bold green]")
        console.print("[cyan]最新の全機種価格を取得してHTMLダッシュボードを開きます...[/cyan]")
        args.all_models = True
        args.open_dashboard = True
    elif choice == "15":
        import subprocess
        console.print("\n[bold yellow]毎朝自動LINE通知タスクを解除します...[/bold yellow]")
        cancel_bat = Path(__file__).parent / "cancel_morning_task.bat"
        if cancel_bat.exists():
            subprocess.run(["cmd.exe", "/c", str(cancel_bat)], check=False)
        else:
            console.print("[red]cancel_morning_task.bat が見つかりません。[/red]")
        sys.exit(0)
    elif choice == "16":
        console.print("\n[bold cyan]単体テストを実行しています...[/bold cyan]")
        import unittest
        loader = unittest.TestLoader()
        suite = loader.discover("tests")
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
        sys.exit(0)
    elif choice == "0":
        console.print("終了します。")
        sys.exit(0)
    else:
        console.print(f"[yellow]無効な番号 '{choice}' です。デフォルト (1) で実行します。[/yellow]")
        args.open_dashboard = True


def main():
    parser = argparse.ArgumentParser(description="iPhone 18 買取価格 自動収集・比較・トレンド分析ツール")
    parser.add_argument("--menu", action="store_true", help="起動後に対話型選択メニューを表示")
    parser.add_argument("--no-export", action="store_true", help="ファイルへの出力をスキップ")
    parser.add_argument("--all-models", "--all", action="store_true", help=".envの設定を無視して全機種(32モデル)を取得")
    parser.add_argument("--min-spread", type=int, default=0, help="指定金額以上の価格差があるもののみ表示")
    parser.add_argument("--color-spread", "--color-diff", action="store_true", help="カラー別買取価格差・人気色格差リサーチテーブルを表示")
    parser.add_argument("--notify", action="store_true", help="Discord Webhookへ通知を送信")
    parser.add_argument("--line-notify", action="store_true", help="LINE公式アカウント経由で最新買取価格レポートを通知")
    parser.add_argument("--line-profit-only", "--profit-only", action="store_true", help="LINE通知時にApple公式定価と同額以上(還元率100%%以上)の端末情報のみを配信")
    parser.add_argument("--line-color-spread", action="store_true", help="LINE通知時にカラー別価格差レポートを送信")
    parser.add_argument("--min-profit-rate", type=float, default=None, help="通知対象とする最低還元率(%%) (デフォルト: 100.0)")
    parser.add_argument("--skip-if-no-profit", action="store_true", help="等価格以上の端末が0件の場合にLINE通知をスキップ")
    parser.add_argument("--target", "-t", type=str, default="", help="指定端末の絞り込みキーワード (例: 'Pro Max 256GB', 'バーガンディ')")
    parser.add_argument("--model", "-m", type=str, default="", help="対象機種名 (例: 'iPhone 18 Pro Max', 'Pro')")
    parser.add_argument("--capacity", "-c", type=str, default="", help="対象容量 (例: '256GB', '512GB')")
    parser.add_argument("--color", type=str, default="", help="対象カラー (例: 'バーガンディ', 'ブラック')")
    parser.add_argument("--morning-schedule", type=str, default="", help="毎朝指定時刻(例: 08:00)に自動巡回＆LINE通知する常駐モード")
    parser.add_argument("--open-dashboard", action="store_true", help="実行後にブラウザでHTMLダッシュボードを開く")
    parser.add_argument("--watch", type=int, default=0, help="定期自動巡回の監視間隔（分）。指定すると常駐監視モードで起動")
    parser.add_argument("--alert", action="store_true", help="価格変動検知時に通知音を鳴らす")
    args = parser.parse_args()

    print_banner()

    if args.menu:
        show_menu(args)

    # 毎朝指定時刻の自動通知常駐モード
    if args.morning_schedule:
        schedule_time = args.morning_schedule.strip() or MORNING_SCHEDULE_TIME
        console.print(f"[bold yellow]毎朝自動通知常駐モードを開始します (配信時刻: {schedule_time})[/bold yellow]")
        console.print("[dim]※ 毎朝指定時刻に自動スクレイピングとLINE通知を行います。終了するには Ctrl + C を押してください。[/dim]")

        last_executed_date = None
        args.line_notify = True
        try:
            while True:
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                today_str = now.strftime("%Y-%m-%d")

                if current_time == schedule_time and last_executed_date != today_str:
                    console.print(f"\n[bold green]>>> 朝の自動通知スケジュール時刻になりました ({schedule_time})[/bold green]")
                    execute_cycle(args, is_first=False)
                    last_executed_date = today_str
                    time.sleep(65)  # 1分経過するまで待機して同分内の重複起動を防止
                else:
                    time.sleep(15)  # 15秒ごとに時刻チェック
        except KeyboardInterrupt:
            console.print("\n[bold yellow]毎朝自動通知常駐モードを終了しました。[/bold yellow]")
            sys.exit(0)

    elif args.watch and args.watch > 0:
        console.print(f"[bold yellow]常駐監視モードを開始します (巡回間隔: {args.watch} 分)[/bold yellow]")
        console.print("[dim]※ 終了するには Ctrl + C を押してください。[/dim]")

        cycle = 1
        try:
            while True:
                console.print(f"\n{'='*60}")
                console.print(f"[bold cyan]▶ 第 {cycle} 回 巡回チェック[/bold cyan]")
                execute_cycle(args, is_first=(cycle == 1))
                cycle += 1

                sleep_seconds = args.watch * 60
                console.print(f"\n[cyan]次回巡回まで {args.watch} 分間待機します... (Ctrl+C で中断)[/cyan]")
                time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]定期監視を終了しました。[/bold yellow]")
            sys.exit(0)
    else:
        execute_cycle(args, is_first=True)


if __name__ == "__main__":
    main()
