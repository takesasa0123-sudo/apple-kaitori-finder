"""
データ出力モジュール (src/exporter.py)
比較結果および取得データを Excel (.xlsx)、CSV、JSON、HTMLダッシュボードに出力します。
Chart.jsによる価格推移グラフおよび全店舗比較モーダルを内蔵しています。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config import OUTPUT_DIR, DATA_DIR
from src.models import ComparisonItem, PriceRecord

logger = logging.getLogger(__name__)


class Exporter:
    """Excel / CSV / JSON / HTML 出力クラス"""

    def __init__(self, comparison_items: List[ComparisonItem], raw_records: List[PriceRecord]):
        self.items = comparison_items
        self.records = raw_records
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def export_all(self) -> Dict[str, Path]:
        """全形式で出力"""
        excel_path = self.export_excel()
        csv_path = self.export_csv()
        json_path = self.export_json()
        html_path = self.export_html()
        return {
            "excel": excel_path,
            "csv": csv_path,
            "json": json_path,
            "html": html_path,
        }

    def export_excel(self) -> Path:
        """デザインされた Excel ワークブックを出力"""
        wb = Workbook()
        ws_compare = wb.active
        ws_compare.title = "買取価格比較一覧"

        # スタイル定義
        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_font = Font(name="Yu Gothic", size=11, bold=True, color="FFFFFF")
        best_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")  # 淡い緑
        diff_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")  # 淡い黄
        up_fill = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")    # 上昇 (薄緑)
        down_fill = PatternFill(start_color="FCE5CD", end_color="FCE5CD", fill_type="solid")  # 下落 (薄赤)

        data_font = Font(name="Yu Gothic", size=10)
        bold_font = Font(name="Yu Gothic", size=10, bold=True)
        center_align = Alignment(horizontal="center", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )

        # 動的店舗リストの抽出
        all_stores = sorted(list({rec.store for rec in self.records}))

        # ヘッダー作成
        headers = [
            "機種名",
            "容量",
            "カラー",
            "Apple型番",
            "JANコード",
            "最高買取価格 (円)",
            "前回比 (円)",
            "最高買取店",
        ]
        for s in all_stores:
            headers.append(f"{s} (円)")
        headers.extend(["店舗間差額 (円)", "Apple公式HP価格 (円)", "差益/利益額 (円)", "還元率 (%)"])

        ws_compare.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws_compare.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align

        # データ行の書き込み
        for row_idx, it in enumerate(self.items, start=2):
            change_val = it.price_change if it.price_change is not None else "-"
            row_data = [
                it.model_name,
                it.capacity,
                it.color,
                it.part_number or "-",
                it.jan or "-",
                it.best_price,
                change_val,
                it.best_store,
            ]
            for s in all_stores:
                row_data.append(it.store_prices.get(s, "-"))
            row_data.extend([
                it.price_diff,
                it.official_price or "-",
                it.profit_jpy if it.profit_jpy is not None else "-",
                f"{it.profit_rate}%" if it.profit_rate is not None else "-",
            ])
            ws_compare.append(row_data)

            # 書式と装飾
            for col_idx in range(1, len(row_data) + 1):
                cell = ws_compare.cell(row=row_idx, column=col_idx)
                cell.font = data_font
                cell.border = thin_border

                val = cell.value
                if isinstance(val, (int, float)):
                    cell.alignment = right_align
                    cell.number_format = "#,##0"
                elif col_idx in (2, 3, 4, 5, 7, 8):
                    cell.alignment = center_align
                else:
                    cell.alignment = left_align

            # 最高価格セルのハイライト (列6)
            best_price_cell = ws_compare.cell(row=row_idx, column=6)
            best_price_cell.fill = best_fill
            best_price_cell.font = bold_font

            # 前回比セルのハイライト (列7)
            change_cell = ws_compare.cell(row=row_idx, column=7)
            if isinstance(change_cell.value, (int, float)):
                if change_cell.value > 0:
                    change_cell.fill = up_fill
                    change_cell.font = bold_font
                elif change_cell.value < 0:
                    change_cell.fill = down_fill
                    change_cell.font = bold_font

            # 店舗間差額セルのハイライト
            diff_col_idx = 8 + len(all_stores) + 1
            diff_cell = ws_compare.cell(row=row_idx, column=diff_col_idx)
            if isinstance(diff_cell.value, (int, float)) and diff_cell.value > 0:
                diff_cell.fill = diff_fill
                diff_cell.font = bold_font

        # シート2: 全レコード生データ
        ws_raw = wb.create_sheet(title="店舗別生データ")
        raw_headers = [
            "取得店舗",
            "元タイトル",
            "機種名",
            "容量",
            "カラー",
            "買取価格 (円)",
            "JANコード",
            "SIMステータス",
            "状態",
            "商品URL",
            "取得日時",
        ]
        ws_raw.append(raw_headers)
        for col_idx in range(1, len(raw_headers) + 1):
            c = ws_raw.cell(row=1, column=col_idx)
            c.fill = header_fill
            c.font = header_font
            c.alignment = center_align

        for r_idx, rec in enumerate(self.records, start=2):
            ws_raw.append([
                rec.store,
                rec.raw_title,
                rec.model_name,
                rec.capacity,
                rec.color,
                rec.price,
                rec.jan or "-",
                rec.sim_status,
                rec.condition,
                rec.url or "-",
                rec.scraped_at.strftime("%Y-%m-%d %H:%M"),
            ])
            for c_idx in range(1, len(raw_headers) + 1):
                c = ws_raw.cell(row=r_idx, column=c_idx)
                c.font = data_font
                c.border = thin_border
                if isinstance(c.value, (int, float)):
                    c.alignment = right_align
                    c.number_format = "#,##0"

        # シート3: カラー別買取価格差リサーチ
        from src.comparator import analyze_color_spread
        color_groups = analyze_color_spread(self.items, self.records)

        ws_color = wb.create_sheet(title="カラー別価格差リサーチ")
        color_headers = [
            "機種名", "容量", "Apple公式HP価格 (円)",
            "最高値カラー", "最高買取価格 (円)", "最高買取店",
            "最安値カラー", "最安買取価格 (円)", "最大カラー格差 (円)",
            "カラー別価格内訳 & 基準比差額",
            "店舗別減額メモ (買取1丁目等)",
        ]
        ws_color.append(color_headers)
        for col_idx in range(1, len(color_headers) + 1):
            c = ws_color.cell(row=1, column=col_idx)
            c.fill = header_fill
            c.font = header_font
            c.alignment = center_align

        spread_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        for r_idx, g in enumerate(color_groups, start=2):
            colors_breakdown = " / ".join(
                f"{c.color}: {c.best_price:,}円 ({'基準±0' if c.diff_from_top == 0 else f'{c.diff_from_top:,}円'})"
                for c in g.colors
            )
            note = list(g.store_deductions.values())[0] if g.store_deductions else "-"
            row_data = [
                g.model_name,
                g.capacity,
                g.official_price or "-",
                g.top_color,
                g.top_price,
                g.colors[0].best_store if g.colors else "-",
                g.lowest_color,
                g.lowest_price,
                g.max_spread,
                colors_breakdown,
                note,
            ]
            ws_color.append(row_data)
            for c_idx in range(1, len(row_data) + 1):
                c = ws_color.cell(row=r_idx, column=c_idx)
                c.font = data_font
                c.border = thin_border
                if isinstance(c.value, (int, float)):
                    c.alignment = right_align
                    c.number_format = "#,##0"
                elif c_idx in (2, 4, 6, 7):
                    c.alignment = center_align
                else:
                    c.alignment = left_align

            # 最大カラー格差セルのハイライト (列9)
            diff_cell = ws_color.cell(row=r_idx, column=9)
            if g.max_spread > 0:
                diff_cell.fill = spread_fill
                diff_cell.font = bold_font

        # 列幅の自動調整
        for ws in (ws_compare, ws_raw, ws_color):
            ws.views.sheetView[0].showGridLines = True
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    val_str = str(cell.value or "")
                    length = sum(2 if ord(ch) > 127 else 1 for ch in val_str)
                    if length > max_len:
                        max_len = length
                ws.column_dimensions[col_letter].width = min(max(max_len + 3, 11), 50)

        out_path = OUTPUT_DIR / f"iphone18_kaitori_comparison_{self.timestamp}.xlsx"
        wb.save(out_path)
        logger.info("Excel出力完了: %s", out_path)
        return out_path

    def export_csv(self) -> Path:
        """Excelで文字化けしない UTF-8 with BOM のCSVを出力"""
        from src.comparator import analyze_color_spread
        color_groups = analyze_color_spread(self.items, self.records)
        color_diff_map = {}
        for g in color_groups:
            for c in g.colors:
                color_diff_map[(g.model_name, g.capacity, c.color)] = c.diff_from_top

        rows: List[Dict[str, Any]] = []
        for it in self.items:
            c_diff = color_diff_map.get((it.model_name, it.capacity, it.color), 0)
            row = {
                "機種名": it.model_name,
                "容量": it.capacity,
                "カラー": it.color,
                "Apple型番": it.part_number or "",
                "JANコード": it.jan or "",
                "最高買取価格": it.best_price,
                "カラー基準差額": c_diff,
                "前回比": it.price_change if it.price_change is not None else "",
                "最高買取店": it.best_store,
                "店舗間差額": it.price_diff,
                "Apple公式HP価格": it.official_price or "",
                "差益_利益額": it.profit_jpy if it.profit_jpy is not None else "",
                "還元率%": it.profit_rate if it.profit_rate is not None else "",
            }
            for s, p in it.store_prices.items():
                row[f"{s}_価格"] = p
            rows.append(row)

        df = pd.DataFrame(rows)
        out_path = OUTPUT_DIR / f"iphone18_kaitori_comparison_{self.timestamp}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        logger.info("CSV出力完了: %s", out_path)
        return out_path

    def export_json(self) -> Path:
        """JSONスナップショットを出力"""
        data = {
            "scraped_at": datetime.now().isoformat(),
            "total_items": len(self.items),
            "items": [
                {
                    "model_name": it.model_name,
                    "capacity": it.capacity,
                    "color": it.color,
                    "part_number": it.part_number,
                    "jan": it.jan,
                    "best_store": it.best_store,
                    "best_price": it.best_price,
                    "lowest_store": it.lowest_store,
                    "lowest_price": it.lowest_price,
                    "price_diff": it.price_diff,
                    "prev_best_price": it.prev_best_price,
                    "price_change": it.price_change,
                    "official_price": it.official_price,
                    "profit_jpy": it.profit_jpy,
                    "profit_rate": it.profit_rate,
                    "store_prices": it.store_prices,
                }
                for it in self.items
            ],
        }
        out_path = DATA_DIR / f"iphone18_snapshot_{self.timestamp}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("JSON出力完了: %s", out_path)
        return out_path

    def export_html(self) -> Path:
        """ブラウザで直接閲覧・操作できるインタラクティブHTMLダッシュボードを出力"""
        all_stores = sorted(list({rec.store for rec in self.records}))
        max_price_item = max(self.items, key=lambda x: x.best_price) if self.items else None
        max_diff_item = max(self.items, key=lambda x: x.price_diff) if self.items else None
        price_change_count = sum(1 for it in self.items if it.price_change is not None and it.price_change != 0)

        from src.comparator import analyze_color_spread
        color_groups = analyze_color_spread(self.items, self.records)
        max_color_spread = color_groups[0].max_spread if color_groups else 0
        top_color_spread_group = color_groups[0] if color_groups else None
        top_color_spread_sub = (
            f"{top_color_spread_group.model_name.replace('iPhone 18 ', '')} {top_color_spread_group.capacity} ({top_color_spread_group.top_color} vs {top_color_spread_group.lowest_color})"
            if top_color_spread_group else "同容量モデル内の格差"
        )

        color_cards_html = []
        for g in color_groups:
            pills = []
            for c in g.colors:
                diff_label = "基準 ±0円" if c.diff_from_top == 0 else f"{c.diff_from_top:,}円"
                badge_class = "color-pill-top" if c.diff_from_top == 0 else "color-pill-sub"
                crown = " 👑" if c.diff_from_top == 0 else ""
                pills.append(
                    f'<div class="color-pill {badge_class}">'
                    f'<div class="color-name">{c.color}{crown}</div>'
                    f'<div class="color-price">{c.best_price:,}円</div>'
                    f'<div class="color-diff">{diff_label}</div>'
                    f'<div class="color-store">@{c.best_store}</div>'
                    f'</div>'
                )
            pills_str = "".join(pills)
            deduction_note_html = ""
            if g.store_deductions:
                note_text = list(g.store_deductions.values())[0]
                deduction_note_html = f'<div class="color-deduction-note">🏷️ 買取1丁目減額: {note_text}</div>'

            spread_badge_html = f'<span class="badge-spread">最大格差 +{g.max_spread:,}円</span>' if g.max_spread > 0 else '<span class="badge-spread-zero">格差なし</span>'
            official_txt = f'<span class="official-price-tag">公式価格: {g.official_price:,}円</span>' if g.official_price else ''

            color_cards_html.append(
                f'<div class="color-group-card">'
                f'<div class="color-group-header">'
                f'  <div><span class="color-group-title">{g.model_name} {g.capacity}</span> {official_txt}</div>'
                f'  {spread_badge_html}'
                f'</div>'
                f'<div class="color-pills-wrap">{pills_str}</div>'
                f'{deduction_note_html}'
                f'</div>'
            )
        color_cards_rendered = "".join(color_cards_html)

        filter_banner_html = ""
        if len(self.items) < 32:
            filter_banner_html = f"""
    <div style="background:#fffbeb; border:1px solid #f59e0b; border-left:6px solid #d97706; border-radius:10px; padding:14px 20px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
        <div>
            <div style="font-weight:800; color:#92400e; font-size:1rem; display:flex; align-items:center; gap:8px;">
                <span>🎯</span> 特定端末の絞り込み表示中（表示: {len(self.items)} 機種 / 全32機種中）
            </div>
            <div style="color:#b45309; font-size:0.85rem; margin-top:4px;">
                ※ 一部の端末のみが表示されています。全機種を表示するには <code>run.bat</code> で <strong>[1] 全機種 通常実行</strong> を選択するか、<strong>[14] フィルター解除</strong> を実行してください。
            </div>
        </div>
        <div style="font-size:0.8rem; background:#fef3c7; color:#92400e; padding:4px 10px; border-radius:6px; font-weight:700;">
            絞り込み適用中
        </div>
    </div>
"""
        kpi_sub_models = "iPhone 18 Pro Max / Pro (全容量・カラー)" if len(self.items) >= 32 else f"🎯 絞り込み表示中 ({len(self.items)} / 32機種)"

        items_json = json.dumps([
            {
                "id": idx,
                "model": it.model_name,
                "capacity": it.capacity,
                "color": it.color,
                "part_number": it.part_number or "-",
                "jan": it.jan or "-",
                "best_store": it.best_store,
                "best_price": it.best_price,
                "lowest_store": it.lowest_store,
                "lowest_price": it.lowest_price,
                "prev_best_price": it.prev_best_price,
                "price_change": it.price_change,
                "trend_badge": it.trend_badge,
                "price_diff": it.price_diff,
                "official_price": it.official_price or 0,
                "profit_jpy": it.profit_jpy if it.profit_jpy is not None else 0,
                "profit_rate": it.profit_rate if it.profit_rate is not None else 0.0,
                "store_prices": it.store_prices,
                "history_points": it.history_points,
            }
            for idx, it in enumerate(self.items)
        ], ensure_ascii=False)

        stores_json = json.dumps(all_stores, ensure_ascii=False)

        html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>iPhone 18 買取価格 ダッシュボード</title>
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
            --border-color: #e2e8f0;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Yu Gothic", "Meiryo", sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            padding: 24px;
            line-height: 1.5;
        }}
        .container {{ max-width: 1440px; margin: 0 auto; }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .header h1 {{ font-size: 1.85rem; font-weight: 800; color: #1e293b; letter-spacing: -0.02em; }}
        .badge-time {{
            background: #e2e8f0;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 600;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 18px 20px;
            border: 1px solid var(--border-color);
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            transition: transform 0.15s ease;
        }}
        .kpi-card:hover {{ transform: translateY(-2px); }}
        .kpi-title {{ font-size: 0.82rem; color: var(--text-muted); font-weight: 600; margin-bottom: 6px; }}
        .kpi-val {{ font-size: 1.55rem; font-weight: 800; color: #1e293b; }}
        .kpi-sub {{ font-size: 0.78rem; color: var(--text-muted); margin-top: 4px; }}
        
        .controls {{
            background: var(--card-bg);
            padding: 16px 20px;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            margin-bottom: 20px;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .controls input, .controls select {{
            padding: 8px 14px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            font-size: 0.88rem;
            background: #fff;
            outline: none;
        }}
        .controls input:focus, .controls select:focus {{ border-color: var(--primary); }}
        .btn {{
            padding: 8px 16px;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 600;
            transition: all 0.15s;
        }}
        .btn-sort {{ background: #f1f5f9; color: #334155; }}
        .btn-sort:hover {{ background: #e2e8f0; }}
        .btn-sort.active {{ background: var(--primary); color: #fff; }}
        
        .table-wrap {{
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            overflow-x: auto;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
            white-space: nowrap;
        }}
        th, td {{
            padding: 12px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background: #f8fafc;
            color: #475569;
            font-weight: 700;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        tbody tr {{
            cursor: pointer;
            transition: background-color 0.1s;
        }}
        tbody tr:hover {{ background-color: #f1f5f9; }}
        .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
        .center {{ text-align: center; }}
        .tag-best {{
            background: #dcfce7;
            color: #15803d;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.8rem;
        }}
        .tag-diff {{
            background: #fef3c7;
            color: #b45309;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.8rem;
        }}
        .trend-up {{
            background: #dcfce7;
            color: #16a34a;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.8rem;
        }}
        .trend-down {{
            background: #fee2e2;
            color: #dc2626;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.8rem;
        }}
        .trend-same {{
            background: #f1f5f9;
            color: #64748b;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.8rem;
        }}
        .trend-new {{
            background: #e0e7ff;
            color: #4338ca;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.8rem;
        }}
        .price-highlight {{ font-weight: 800; color: #047857; font-size: 0.95rem; }}
        .btn-detail {{
            padding: 4px 10px;
            border-radius: 6px;
            background: #e2e8f0;
            color: #334155;
            border: none;
            font-size: 0.78rem;
            font-weight: 600;
            cursor: pointer;
        }}
        .btn-detail:hover {{ background: var(--primary); color: #fff; }}

        /* Modal Styles */
        .modal-overlay {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.6);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            backdrop-filter: blur(3px);
        }}
        .modal-content {{
            background: #fff;
            width: 90%;
            max-width: 900px;
            max-height: 90vh;
            border-radius: 16px;
            overflow-y: auto;
            padding: 28px;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);
            position: relative;
        }}
        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 14px;
        }}
        .modal-title {{ font-size: 1.4rem; font-weight: 800; color: #1e293b; }}
        .modal-subtitle {{ font-size: 0.88rem; color: var(--text-muted); margin-top: 4px; }}
        .modal-close {{
            background: #f1f5f9;
            border: none;
            width: 32px; height: 32px;
            border-radius: 50%;
            font-size: 1.2rem;
            cursor: pointer;
            color: #64748b;
            display: flex; align-items: center; justify-content: center;
        }}
        .modal-close:hover {{ background: #e2e8f0; color: #0f172a; }}
        .modal-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 16px;
        }}
        @media (max-width: 768px) {{
            .modal-grid {{ grid-template-columns: 1fr; }}
        }}
        .modal-card {{
            background: #f8fafc;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid var(--border-color);
        }}
        .modal-card h3 {{ font-size: 0.95rem; font-weight: 700; color: #334155; margin-bottom: 12px; }}
        .store-bar-item {{
            margin-bottom: 10px;
        }}
        .store-bar-info {{
            display: flex;
            justify-content: space-between;
            font-size: 0.82rem;
            margin-bottom: 3px;
        }}
        .store-bar-track {{
            background: #e2e8f0;
            border-radius: 6px;
            height: 10px;
            overflow: hidden;
        }}
        .store-bar-fill {{
            background: var(--primary);
            height: 100%;
            border-radius: 6px;
            transition: width 0.3s ease;
        }}
        .store-bar-fill.best {{ background: var(--accent-green); }}
        .copy-jan-btn {{
            cursor: pointer;
            padding: 2px 6px;
            background: #e2e8f0;
            border-radius: 4px;
            font-size: 0.75rem;
            margin-left: 6px;
            border: none;
        }}
        .copy-jan-btn:hover {{ background: #cbd5e1; }}

        /* Color Spread Styles */
        .color-spread-section {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border-color);
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .section-header h2 {{
            font-size: 1.15rem;
            font-weight: 800;
            color: #1e293b;
        }}
        .btn-toggle-color {{
            background: #f1f5f9;
            border: 1px solid var(--border-color);
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 0.8rem;
            cursor: pointer;
            font-weight: 600;
            color: #475569;
        }}
        .btn-toggle-color:hover {{ background: #e2e8f0; }}
        .color-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
            gap: 14px;
        }}
        .color-group-card {{
            background: #f8fafc;
            border-radius: 10px;
            padding: 14px;
            border: 1px solid var(--border-color);
        }}
        .color-group-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .color-group-title {{
            font-weight: 700;
            font-size: 0.95rem;
            color: #1e293b;
        }}
        .badge-spread {{
            background: #fee2e2;
            color: #b91c1c;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
        }}
        .badge-spread-zero {{
            background: #f1f5f9;
            color: #64748b;
            font-size: 0.75rem;
            padding: 3px 8px;
            border-radius: 6px;
        }}
        .official-price-tag {{
            font-size: 0.78rem;
            color: var(--text-muted);
            margin-left: 6px;
        }}
        .color-pills-wrap {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }}
        .color-pill {{
            background: #ffffff;
            border-radius: 8px;
            padding: 8px 10px;
            border: 1px solid var(--border-color);
        }}
        .color-pill.color-pill-top {{
            border-color: #86efac;
            background: #f0fdf4;
        }}
        .color-pill-sub {{
            background: #ffffff;
        }}
        .color-name {{
            font-size: 0.8rem;
            font-weight: 700;
            color: #334155;
            margin-bottom: 2px;
        }}
        .color-price {{
            font-size: 0.95rem;
            font-weight: 800;
            color: #0f172a;
        }}
        .color-diff {{
            font-size: 0.75rem;
            font-weight: 600;
            color: #64748b;
        }}
        .color-pill.color-pill-top .color-diff {{
            color: #16a34a;
        }}
        .color-store {{
            font-size: 0.72rem;
            color: var(--text-muted);
            margin-top: 2px;
        }}
        .color-deduction-note {{
            margin-top: 10px;
            font-size: 0.78rem;
            background: #fef3c7;
            color: #92400e;
            padding: 5px 10px;
            border-radius: 6px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h1>📱 iPhone 18 買取価格 リアルタイムダッシュボード</h1>
            <p style="color:var(--text-muted); font-size:0.9rem;">主要 {len(all_stores)} 店舗の買取価格・価格差・時系列トレンド分析</p>
        </div>
        <div class="badge-time">更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
    </div>

    {filter_banner_html}

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-title">比較対象モデル</div>
            <div class="kpi-val">{len(self.items)} <span style="font-size:1rem; font-weight:normal;">機種</span></div>
            <div class="kpi-sub">{kpi_sub_models}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">調査買取店舗数</div>
            <div class="kpi-val">{len(all_stores)} <span style="font-size:1rem; font-weight:normal;">店舗</span></div>
            <div class="kpi-sub">買取ルデヤ, 森森買取, 一丁目, wiki等</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">最高買取価格</div>
            <div class="kpi-val" style="color:#059669;">{max_price_item.best_price:,}円</div>
            <div class="kpi-sub">{max_price_item.summary_title} ({max_price_item.best_store})</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">最大店舗間価格差</div>
            <div class="kpi-val" style="color:#d97706;">+{max_diff_item.price_diff:,}円</div>
            <div class="kpi-sub">{max_diff_item.summary_title} ({max_diff_item.best_store} vs {max_diff_item.lowest_store})</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">最大カラー間価格差</div>
            <div class="kpi-val" style="color:#e11d48;">+{max_color_spread:,}円</div>
            <div class="kpi-sub">{top_color_spread_sub}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">価格変動検知数</div>
            <div class="kpi-val" style="color:#2563eb;">{price_change_count} <span style="font-size:1rem; font-weight:normal;">機種</span></div>
            <div class="kpi-sub">前回調査からの最高値変動</div>
        </div>
    </div>

    <!-- カラー別買取価格差リサーチセクション -->
    <div class="color-spread-section" id="colorSection">
        <div class="section-header">
            <div>
                <h2>🎨 カラー別買取価格差リサーチ (色の違いによる買取格差・人気色マトリクス)</h2>
                <p style="font-size:0.83rem; color:var(--text-muted); margin-top:3px;">
                    主要買取店では新色（バーガンディ等）が最高値査定され、シルバー・ブラック等は減額（-10,000円〜-23,000円）が適用されます。
                </p>
            </div>
            <button class="btn-toggle-color" onclick="toggleColorSection()" id="btnToggleColor">非表示にする</button>
        </div>
        <div class="color-grid" id="colorGrid">
            {color_cards_rendered}
        </div>
    </div>

    <div class="controls">
        <input type="text" id="searchInput" placeholder="機種名、容量、カラー、JANで検索..." style="min-width: 240px;">
        <select id="modelSelect">
            <option value="">全モデル</option>
            <option value="iPhone 18 Pro Max">iPhone 18 Pro Max</option>
            <option value="iPhone 18 Pro">iPhone 18 Pro</option>
        </select>
        <select id="capacitySelect">
            <option value="">全容量</option>
            <option value="256GB">256GB</option>
            <option value="512GB">512GB</option>
            <option value="1TB">1TB</option>
            <option value="2TB">2TB</option>
        </select>
        <select id="trendSelect">
            <option value="">全ステータス</option>
            <option value="up">価格上昇 (↗)</option>
            <option value="down">価格下落 (↘)</option>
            <option value="diff">差額あり (1,000円〜)</option>
            <option value="changed">変動あり</option>
        </select>
        <button class="btn btn-sort active" id="btnSortPrice" onclick="setSort('price')">最高価格順</button>
        <button class="btn btn-sort" id="btnSortDiff" onclick="setSort('diff')">店舗間差額順</button>
        <button class="btn btn-sort" id="btnSortRate" onclick="setSort('rate')">還元率順</button>
        <button class="btn btn-sort" id="btnSortTrend" onclick="setSort('trend')">前回比変動順</button>
    </div>

    <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>機種名</th>
                    <th class="center">容量</th>
                    <th>カラー</th>
                    <th class="num">最高買取価格</th>
                    <th class="center">最高買取店</th>
                    <th class="center">前回比</th>
                    <th class="num">店舗間差額</th>
                    <th class="num">Apple公式HP価格</th>
                    <th class="num">差益(利益)</th>
                    <th class="num">還元率</th>
                    <th class="center">JANコード</th>
                    <th class="center">詳細</th>
                </tr>
            </thead>
            <tbody id="tableBody"></tbody>
        </table>
    </div>
</div>

<!-- Modal Dialog -->
<div class="modal-overlay" id="detailModal" onclick="closeModalOnOverlay(event)">
    <div class="modal-content">
        <div class="modal-header">
            <div>
                <div class="modal-title" id="mTitle">-</div>
                <div class="modal-subtitle">
                    型番: <span id="mPart" style="font-family:monospace; font-weight:bold;">-</span>
                    <button class="copy-jan-btn" onclick="copyPart()">型番コピー</button>
                    &nbsp;|&nbsp;
                    JAN: <span id="mJan" style="font-family:monospace; font-weight:bold;">-</span>
                    <button class="copy-jan-btn" onclick="copyJan()">JANコピー</button>
                </div>
            </div>
            <button class="modal-close" onclick="closeModal()">×</button>
        </div>

        <div class="modal-grid">
            <!-- Left: Store Prices Bar Breakdown -->
            <div class="modal-card">
                <h3>🏬 店舗別 買取価格一覧 (全店舗比較)</h3>
                <div id="mStoreBars"></div>
            </div>

            <!-- Right: Price History Chart -->
            <div class="modal-card">
                <h3>📈 過去の価格推移チャート</h3>
                <div style="position: relative; height: 260px;">
                    <canvas id="mHistoryCanvas"></canvas>
                </div>
                <div id="mChartNote" style="font-size:0.75rem; color:var(--text-muted); margin-top:8px; text-align:center;"></div>
            </div>
        </div>

        <!-- Profit Summary -->
        <div style="margin-top:16px; background:#f1f5f9; border-radius:10px; padding:14px; display:flex; justify-content:space-around; flex-wrap:wrap; gap:10px; text-align:center;">
            <div>
                <div style="font-size:0.75rem; color:var(--text-muted);">Apple公式HP価格 (取得時)</div>
                <div id="mOfficial" style="font-weight:700; font-size:1rem;">-</div>
            </div>
            <div>
                <div style="font-size:0.75rem; color:var(--text-muted);">最高買取価格</div>
                <div id="mBestPrice" style="font-weight:800; font-size:1.1rem; color:#059669;">-</div>
            </div>
            <div>
                <div style="font-size:0.75rem; color:var(--text-muted);">定価差益 (利益)</div>
                <div id="mProfit" style="font-weight:700; font-size:1rem;">-</div>
            </div>
            <div>
                <div style="font-size:0.75rem; color:var(--text-muted);">還元率</div>
                <div id="mRate" style="font-weight:700; font-size:1rem;">-</div>
            </div>
            <div>
                <div style="font-size:0.75rem; color:var(--text-muted);">店舗間最大差額</div>
                <div id="mDiff" style="font-weight:700; font-size:1rem; color:#d97706;">-</div>
            </div>
        </div>
    </div>
</div>

<script>
    const rawData = {items_json};
    const allStores = {stores_json};
    let currentSort = 'price';
    let chartInstance = null;

    function renderTable() {{
        const search = document.getElementById('searchInput').value.toLowerCase();
        const modelFilter = document.getElementById('modelSelect').value;
        const capFilter = document.getElementById('capacitySelect').value;
        const trendFilter = document.getElementById('trendSelect').value;

        let filtered = rawData.filter(it => {{
            const matchSearch = !search || 
                it.model.toLowerCase().includes(search) || 
                it.capacity.toLowerCase().includes(search) || 
                it.color.toLowerCase().includes(search) || 
                (it.jan && it.jan.includes(search));
            const matchModel = !modelFilter || it.model === modelFilter;
            const matchCap = !capFilter || it.capacity === capFilter;
            
            let matchTrend = true;
            if (trendFilter === 'up') matchTrend = (it.price_change && it.price_change > 0);
            else if (trendFilter === 'down') matchTrend = (it.price_change && it.price_change < 0);
            else if (trendFilter === 'diff') matchTrend = (it.price_diff >= 1000);
            else if (trendFilter === 'changed') matchTrend = (it.price_change !== null && it.price_change !== 0);

            return matchSearch && matchModel && matchCap && matchTrend;
        }});

        if (currentSort === 'price') {{
            filtered.sort((a, b) => b.best_price - a.best_price);
        }} else if (currentSort === 'diff') {{
            filtered.sort((a, b) => b.price_diff - a.price_diff);
        }} else if (currentSort === 'rate') {{
            filtered.sort((a, b) => (b.profit_rate || 0) - (a.profit_rate || 0));
        }} else if (currentSort === 'trend') {{
            filtered.sort((a, b) => (b.price_change || 0) - (a.price_change || 0));
        }}

        const tbody = document.getElementById('tableBody');
        tbody.innerHTML = filtered.map(it => {{
            const diffTag = it.price_diff > 0 
                ? `<span class="tag-diff">+${{it.price_diff.toLocaleString()}}円</span>` 
                : `<span style="color:#94a3b8;">±0円</span>`;
            
            let trendHtml = '<span class="trend-same">±0円</span>';
            if (it.price_change === null) {{
                trendHtml = '<span class="trend-new">NEW</span>';
            }} else if (it.price_change > 0) {{
                trendHtml = `<span class="trend-up">+${{it.price_change.toLocaleString()}}円 ↗</span>`;
            }} else if (it.price_change < 0) {{
                trendHtml = `<span class="trend-down">${{it.price_change.toLocaleString()}}円 ↘</span>`;
            }}

            const profitStr = it.profit_jpy > 0 ? `+${{it.profit_jpy.toLocaleString()}}円` : (it.profit_jpy ? `${{it.profit_jpy.toLocaleString()}}円` : '-');
            const rateStr = it.profit_rate ? `${{it.profit_rate}}%` : '-';
            const officialStr = it.official_price ? `${{it.official_price.toLocaleString()}}円` : '-';

            return `
                <tr onclick="openDetail(${{it.id}})">
                    <td><strong>${{it.model}}</strong></td>
                    <td class="center"><span style="background:#f1f5f9; padding:2px 6px; border-radius:4px; font-weight:600;">${{it.capacity}}</span></td>
                    <td>${{it.color}}</td>
                    <td class="num price-highlight">${{it.best_price.toLocaleString()}}円</td>
                    <td class="center"><span class="tag-best">${{it.best_store}}</span></td>
                    <td class="center">${{trendHtml}}</td>
                    <td class="num">${{diffTag}}</td>
                    <td class="num" style="color:#64748b;">${{officialStr}}</td>
                    <td class="num" style="font-weight:600; color:${{it.profit_jpy >= 0 ? '#10b981' : '#64748b'}}">${{profitStr}}</td>
                    <td class="num" style="font-weight:700; color:${{it.profit_rate >= 100 ? '#ef4444' : '#64748b'}}">${{rateStr}}</td>
                    <td class="center" style="font-family:monospace; color:#64748b; font-size:0.8rem;">${{it.jan}}</td>
                    <td class="center"><button class="btn-detail" onclick="event.stopPropagation(); openDetail(${{it.id}})">詳細</button></td>
                </tr>
            `;
        }}).join('');
    }}

    function setSort(type) {{
        currentSort = type;
        document.querySelectorAll('.btn-sort').forEach(b => b.classList.remove('active'));
        if (type === 'price') document.getElementById('btnSortPrice').classList.add('active');
        if (type === 'diff') document.getElementById('btnSortDiff').classList.add('active');
        if (type === 'rate') document.getElementById('btnSortRate').classList.add('active');
        if (type === 'trend') document.getElementById('btnSortTrend').classList.add('active');
        renderTable();
    }}

    function openDetail(id) {{
        const item = rawData.find(x => x.id === id);
        if (!item) return;

        document.getElementById('mTitle').innerText = `${{item.model}} ${{item.capacity}} ${{item.color}}`;
        document.getElementById('mPart').innerText = item.part_number || '未登録';
        document.getElementById('mJan').innerText = item.jan || '未登録';
        document.getElementById('mOfficial').innerText = item.official_price ? item.official_price.toLocaleString() + '円' : '-';
        document.getElementById('mBestPrice').innerText = item.best_price.toLocaleString() + '円 (' + item.best_store + ')';
        document.getElementById('mProfit').innerText = (item.profit_jpy >= 0 ? '+' : '') + item.profit_jpy.toLocaleString() + '円';
        document.getElementById('mProfit').style.color = item.profit_jpy >= 0 ? '#10b981' : '#64748b';
        document.getElementById('mRate').innerText = item.profit_rate ? item.profit_rate + '%' : '-';
        document.getElementById('mDiff').innerText = '+' + item.price_diff.toLocaleString() + '円';

        // Render Store Bars
        const storeEntries = Object.entries(item.store_prices).sort((a, b) => b[1] - a[1]);
        const maxStorePrice = storeEntries.length > 0 ? storeEntries[0][1] : item.best_price;
        const minStorePrice = storeEntries.length > 0 ? storeEntries[storeEntries.length - 1][1] : 0;
        
        const barsHtml = storeEntries.map(([sName, sPrice]) => {{
            const isBest = (sName === item.best_store);
            const pct = maxStorePrice > 0 ? Math.max(20, Math.round((sPrice / maxStorePrice) * 100)) : 100;
            const diffFromMax = maxStorePrice - sPrice;
            const diffLabel = diffFromMax > 0 ? `<span style="color:#ef4444; font-size:0.75rem;">(-${{diffFromMax.toLocaleString()}}円)</span>` : `<span style="color:#10b981; font-weight:700; font-size:0.75rem;">[最高値]</span>`;
            return `
                <div class="store-bar-item">
                    <div class="store-bar-info">
                        <span><strong>${{sName}}</strong> ${{diffLabel}}</span>
                        <span style="font-weight:700;">${{sPrice.toLocaleString()}}円</span>
                    </div>
                    <div class="store-bar-track">
                        <div class="store-bar-fill ${{isBest ? 'best' : ''}}" style="width: ${{pct}}%;"></div>
                    </div>
                </div>
            `;
        }}).join('');
        document.getElementById('mStoreBars').innerHTML = barsHtml || '<p style="color:var(--text-muted);">店舗価格データがありません</p>';

        // Render Chart.js History
        renderChart(item);

        document.getElementById('detailModal').style.display = 'flex';
    }}

    function renderChart(item) {{
        const canvas = document.getElementById('mHistoryCanvas');
        const ctx = canvas.getContext('2d');
        if (chartInstance) {{
            chartInstance.destroy();
        }}

        const points = item.history_points || [];
        if (points.length === 0) {{
            // フォールバック: 現在値のみ
            points.push({{ time: '現在', best_price: item.best_price, best_store: item.best_store }});
        }}

        const labels = points.map(p => p.time);
        const data = points.map(p => p.best_price);

        chartInstance = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    label: '最高買取価格 (円)',
                    data: data,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    fill: true,
                    tension: 0.25,
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    pointBackgroundColor: '#2563eb',
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        callbacks: {{
                            label: function(ctx) {{
                                const pt = points[ctx.dataIndex];
                                return `${{ctx.parsed.y.toLocaleString()}}円 (${{pt.best_store || ''}})`;
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        ticks: {{
                            callback: function(val) {{ return val.toLocaleString() + '円'; }}
                        }}
                    }}
                }}
            }}
        }});
        document.getElementById('mChartNote').innerText = `データ点数: ${{points.length}} 件 (時系列取得データ)`;
    }}

    function closeModal() {{
        document.getElementById('detailModal').style.display = 'none';
        if (chartInstance) {{
            chartInstance.destroy();
            chartInstance = null;
        }}
    }}

    function closeModalOnOverlay(e) {{
        if (e.target.id === 'detailModal') {{
            closeModal();
        }}
    }}

    function copyPart() {{
        const part = document.getElementById('mPart').innerText;
        if (part && part !== '未登録' && part !== '-') {{
            navigator.clipboard.writeText(part).then(() => {{
                alert('Apple型番をコピーしました: ' + part);
            }}).catch(() => {{
                prompt('Apple型番:', part);
            }});
        }}
    }}

    function copyJan() {{
        const jan = document.getElementById('mJan').innerText;
        if (jan && jan !== '未登録' && jan !== '-') {{
            navigator.clipboard.writeText(jan).then(() => {{
                alert('JANコードをコピーしました: ' + jan);
            }}).catch(() => {{
                prompt('JANコード:', jan);
            }});
        }}
    }}

    document.addEventListener('keydown', (e) => {{
        if (e.key === 'Escape') closeModal();
    }});

    document.getElementById('searchInput').addEventListener('input', renderTable);
    document.getElementById('modelSelect').addEventListener('change', renderTable);
    document.getElementById('capacitySelect').addEventListener('change', renderTable);
    document.getElementById('trendSelect').addEventListener('change', renderTable);

    function toggleColorSection() {{
        const grid = document.getElementById('colorGrid');
        const btn = document.getElementById('btnToggleColor');
        if (grid.style.display === 'none') {{
            grid.style.display = 'grid';
            btn.innerText = '非表示にする';
        }} else {{
            grid.style.display = 'none';
            btn.innerText = '表示する';
        }}
    }}

    renderTable();
</script>
</body>
</html>
"""

        out_path = OUTPUT_DIR / f"iphone18_dashboard_{self.timestamp}.html"
        latest_path = OUTPUT_DIR / "latest_dashboard.html"

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info("HTMLダッシュボード出力完了: %s (最新: %s)", out_path, latest_path)
        return out_path
