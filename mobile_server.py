"""
スマホアプリ用 データ生成 & オンデマンド調査 API サーバー (mobile_server.py)

機能:
1. iPhone 18 シリーズ (全32モデル) + 他のApple Store製品 (Mac / iPad / Watch / AirPods 等 32モデル)
   の最新買取価格とApple公式価格を一括収集・突合し:
   - React Native (Expo) 用データ: mobile-app/src/data/initialData.json
   - JSON API 用データ: output/mobile_latest_data.json
   - スマホ・PC共通モバイルアプリ画面: output/mobile_app.html
   を自動生成・更新します。
2. ローカルHTTP APIサーバー (ポート8765) としても動作し、スマホやPCからの
   「🔄 今すぐ調査」ボタン (/api/refresh) でリアルタイム再調査を実行します。
"""

import argparse
import json
import logging
import os
import re
import socket
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from config import BASE_DIR, OUTPUT_DIR
from src.comparator import PriceComparator
from src.scrapers import (
    AppleOfficialScraper,
    AppleOtherScraper,
    Kaitori1ChomeScraper,
    RudeyaScraper,
    MorimoriScraper,
    SaikouneScraper,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

MOBILE_DATA_PATH = BASE_DIR / "mobile-app" / "src" / "data" / "initialData.json"
OUTPUT_MOBILE_JSON = OUTPUT_DIR / "mobile_latest_data.json"
OUTPUT_MOBILE_HTML = OUTPUT_DIR / "mobile_app.html"


def get_local_ip() -> str:
    """同一Wi-Fi内のスマホからアクセスするためのローカルIPを取得"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_mobile_html(payload: Dict[str, Any]) -> Path:
    """スマホ (iPhone / Android) および PC でネイティブアプリ同様に動作するモバイルアプリHTMLを生成"""
    json_str = json.dumps(payload, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Apple買取判定">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#0f172a">
    <title>Apple買取 利益判定アプリ (iPhone & Android)</title>
    <style>
        :root {{
            --bg: #f1f5f9;
            --card: #ffffff;
            --navy: #0f172a;
            --blue: #2563eb;
            --green: #15803d;
            --green-bg: #dcfce7;
            --amber: #d97706;
            --amber-bg: #fffbeb;
            --red: #b91c1c;
            --red-bg: #fee2e2;
            --text: #0f172a;
            --muted: #64748b;
            --border: #e2e8f0;
        }}
        * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Hiragino Sans", "Noto Sans JP", sans-serif;
            background: #cbd5e1;
            color: var(--text);
            display: flex;
            justify-content: center;
            min-height: 100vh;
        }}
        .app-shell {{
            width: 100%;
            max-width: 520px;
            background: var(--bg);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 0 30px rgba(0,0,0,0.18);
            position: relative;
        }}
        .app-header {{
            background: var(--navy);
            color: #fff;
            padding: 14px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 50;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}
        .header-title {{ font-size: 1.08rem; font-weight: 800; letter-spacing: -0.01em; }}
        .header-sub {{ font-size: 0.7rem; color: #94a3b8; margin-top: 3px; }}
        .btn-share {{
            background: #334155;
            color: #fff;
            border: none;
            border-radius: 10px;
            padding: 10px 12px;
            font-size: 0.82rem;
            font-weight: 800;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 4px;
            white-space: nowrap;
            box-shadow: 0 2px 6px rgba(51,65,85,0.4);
            transition: transform 0.1s;
        }}
        .btn-share:active {{ transform: scale(0.96); }}
        .btn-refresh {{
            background: var(--blue);
            color: #fff;
            border: none;
            border-radius: 10px;
            padding: 10px 14px;
            font-size: 0.82rem;
            font-weight: 800;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
            box-shadow: 0 2px 6px rgba(37,99,235,0.4);
            transition: transform 0.1s;
        }}
        .btn-refresh:active {{ transform: scale(0.96); }}
        .btn-refresh:disabled {{ background: #64748b; cursor: wait; }}
        .status-toast {{
            background: #fef3c7;
            color: #92400e;
            padding: 8px 14px;
            font-size: 0.78rem;
            font-weight: 700;
            border-bottom: 1px solid #fde68a;
            display: none;
            align-items: center;
            gap: 8px;
        }}
        .content {{ padding: 12px; flex: 1; padding-bottom: 40px; }}

        /* 機能4: チェックした端末の最優先表示エリア */
        .pinned-box {{
            background: var(--amber-bg);
            border: 2px solid #f59e0b;
            border-radius: 14px;
            padding: 12px;
            margin-bottom: 14px;
        }}
        .pinned-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .pinned-title {{
            font-size: 0.88rem;
            font-weight: 800;
            color: #92400e;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .btn-collapse {{
            background: #fef3c7;
            border: 1px solid #fbbf24;
            color: #b45309;
            font-size: 0.72rem;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
            cursor: pointer;
        }}
        .pinned-empty {{
            font-size: 0.76rem;
            color: #b45309;
            margin-top: 6px;
        }}
        .pinned-list {{ margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }}

        /* 4大機能タブ */
        .tabs-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-bottom: 12px;
        }}
        .tab-btn {{
            background: #fff;
            border: 1.5px solid #cbd5e1;
            border-radius: 12px;
            padding: 10px 12px;
            text-align: left;
            cursor: pointer;
            transition: all 0.15s;
        }}
        .tab-btn.active {{
            background: #1e293b;
            border-color: #0f172a;
            box-shadow: 0 3px 8px rgba(15,23,42,0.18);
        }}
        .tab-main {{
            font-size: 0.84rem;
            font-weight: 800;
            color: #1e293b;
            display: block;
        }}
        .tab-btn.active .tab-main {{ color: #fff; }}
        .tab-sub {{
            font-size: 0.72rem;
            color: #64748b;
            font-weight: 600;
            margin-top: 2px;
            display: block;
        }}
        .tab-btn.active .tab-sub {{ color: #93c5fd; }}

        /* フィルター説明＆チップ */
        .filter-panel {{
            background: #fff;
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 12px;
            border: 1px solid var(--border);
        }}
        .filter-desc {{
            font-size: 0.78rem;
            color: #334155;
            font-weight: 600;
            margin: 0;
        }}
        .chip-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 8px;
        }}
        .chip {{
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            color: #475569;
            padding: 5px 12px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            cursor: pointer;
        }}
        .chip.active {{
            background: var(--blue);
            border-color: var(--blue);
            color: #fff;
        }}
        .toggle-btn {{
            margin-top: 8px;
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            color: #475569;
            padding: 7px 12px;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: 700;
            cursor: pointer;
            display: inline-block;
        }}
        .toggle-btn.active {{
            background: #eff6ff;
            border-color: #3b82f6;
            color: #1d4ed8;
        }}
        .search-box {{
            width: 100%;
            padding: 9px 12px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            font-size: 0.85rem;
            outline: none;
            background: #f8fafc;
        }}
        .search-box:focus {{ border-color: var(--blue); background: #fff; }}

        /* 商品カード */
        .card-list {{ display: flex; flex-direction: column; gap: 10px; }}
        .item-card {{
            background: #fff;
            border-radius: 12px;
            padding: 13px 14px;
            border: 1px solid var(--border);
            cursor: pointer;
            transition: transform 0.1s;
        }}
        .item-card:active {{ transform: scale(0.99); }}
        .item-card.pinned-card {{ border: 1.5px solid #f59e0b; }}
        .item-card.profit-1000 {{ border-left: 5px solid #16a34a; }}
        .card-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }}
        .badge-group {{ display: flex; align-items: center; gap: 6px; }}
        .cat-pill {{
            font-size: 0.68rem;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 6px;
            background: #dbeafe;
            color: #1e3a8a;
        }}
        .cat-pill.other {{ background: #f3e8ff; color: #581c87; }}
        .part-no {{ font-size: 0.72rem; color: var(--muted); font-family: monospace; font-weight: 600; }}
        .btn-check {{
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            color: #475569;
            padding: 5px 10px;
            border-radius: 8px;
            font-size: 0.73rem;
            font-weight: 800;
            cursor: pointer;
        }}
        .btn-check.checked {{
            background: #fef3c7;
            border-color: #f59e0b;
            color: #b45309;
        }}
        .item-title {{ font-size: 0.98rem; font-weight: 800; color: var(--text); }}
        .item-cap {{ color: var(--blue); }}
        .item-color {{ font-size: 0.76rem; color: #475569; margin-top: 2px; margin-bottom: 10px; }}
        .price-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid #f1f5f9;
            padding-top: 9px;
        }}
        .p-col {{ flex: 1; }}
        .p-label {{ font-size: 0.66rem; color: var(--muted); font-weight: 600; }}
        .p-best {{ font-size: 1rem; font-weight: 900; color: #047857; margin-top: 1px; }}
        .p-official {{ font-size: 0.88rem; font-weight: 700; color: #334155; margin-top: 1px; }}
        .profit-pill {{
            padding: 6px 10px;
            border-radius: 8px;
            text-align: right;
            min-width: 105px;
        }}
        .profit-pill.plus1000 {{ background: #dcfce7; color: #15803d; }}
        .profit-pill.noloss {{ background: #dbeafe; color: #1d4ed8; }}
        .profit-pill.minus {{ background: #fee2e2; color: #b91c1c; }}
        .profit-rate {{ font-size: 0.65rem; font-weight: 700; }}
        .profit-val {{ font-size: 0.95rem; font-weight: 900; }}

        /* モーダル */
        .modal-bg {{
            position: fixed;
            inset: 0;
            background: rgba(15,23,42,0.6);
            display: none;
            align-items: flex-end;
            justify-content: center;
            z-index: 100;
        }}
        .modal-sheet {{
            background: #fff;
            width: 100%;
            max-width: 520px;
            border-radius: 20px 20px 0 0;
            padding: 20px;
            max-height: 85vh;
            overflow-y: auto;
        }}
        .store-item {{
            display: flex;
            justify-content: space-between;
            padding: 9px 10px;
            border-bottom: 1px solid #f1f5f9;
            font-size: 0.85rem;
        }}
        .store-item.top {{ color: #047857; font-weight: 800; background: #f0fdf4; border-radius: 6px; }}
    </style>
</head>
<body>
<div class="app-shell">
    <div class="app-header">
        <div>
            <div class="header-title">🍎 Apple買取 利益判定</div>
            <div class="header-sub" id="updatedAtText">更新: {payload['updated_at']}</div>
        </div>
        <div style="display:flex;gap:6px;align-items:center;">
            <button class="btn-share" id="shareBtn" onclick="openShareModal()" title="他の人に教えるWebアドレスを表示">
                🔗 共有
            </button>
            <button class="btn-refresh" id="refreshBtn" onclick="refreshPrices()">
                🔄 今すぐ調査
            </button>
        </div>
    </div>

    <div class="status-toast" id="statusToast"></div>

    <div class="content">
        <!-- 1. チェックした端末 (最優先表示エリア) -->
        <div class="pinned-box">
            <div class="pinned-header">
                <div class="pinned-title">
                    📌 チェックした端末（最優先表示: <span id="pinnedCount">0</span>台）
                </div>
                <button class="btn-collapse" id="collapseBtn" onclick="toggleCollapsePinned()">折りたたむ ▲</button>
            </div>
            <div id="pinnedContainer" class="pinned-list"></div>
        </div>

        <!-- 2. 4機能切り替えタブ -->
        <div class="tabs-grid">
            <button class="tab-btn active" id="tab_iphone_profit_1000" onclick="switchTab('iphone_profit_1000')">
                <span class="tab-main">🔥 利益1,000円以上</span>
                <span class="tab-sub" id="sub_iphone_profit_1000">iPhone (0台)</span>
            </button>
            <button class="tab-btn" id="tab_iphone_no_loss" onclick="switchTab('iphone_no_loss')">
                <span class="tab-main">⚖️ マイナスなし</span>
                <span class="tab-sub" id="sub_iphone_no_loss">iPhone 定価以上 (0台)</span>
            </button>
            <button class="tab-btn" id="tab_other_no_loss" onclick="switchTab('other_no_loss')">
                <span class="tab-main">💻 他Apple商品</span>
                <span class="tab-sub" id="sub_other_no_loss">マイナスなし (0台)</span>
            </button>
            <button class="tab-btn" id="tab_all_check" onclick="switchTab('all_check')">
                <span class="tab-main">☑️ 端末チェック選択</span>
                <span class="tab-sub" id="sub_all_check">全機種一覧</span>
            </button>
        </div>

        <!-- 3. サブフィルターパネル -->
        <div class="filter-panel" id="filterPanel"></div>

        <!-- 4. メインリスト -->
        <div class="card-list" id="mainCardList"></div>
    </div>
</div>

<!-- 店舗別詳細モーダル -->
<div class="modal-bg" id="detailModal" onclick="if(event.target===this)closeModal()">
    <div class="modal-sheet" id="modalContent"></div>
</div>

<!-- 共有用アドレスモーダル -->
<div class="modal-bg" id="shareModal" onclick="if(event.target===this)closeShareModal()">
    <div class="modal-sheet" style="padding:20px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <div style="font-size:1.05rem;font-weight:800;">🔗 他の人に教えるWebアドレス</div>
            <button onclick="closeShareModal()" style="border:none;background:#f1f5f9;width:32px;height:32px;border-radius:16px;font-weight:800;cursor:pointer;">✕</button>
        </div>
        <p style="font-size:0.75rem;color:#64748b;margin:0 0 12px 0;">相手の環境に合わせて以下のURLをコピーしてLINEやメールで送ってください。</p>

        <div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:10px;padding:12px;margin-bottom:12px;">
            <div style="font-size:0.8rem;font-weight:800;color:#1e40af;margin-bottom:4px;">🌍 【1】外出先・LINE等用 (誰でも開ける公開URL)</div>
            <div style="display:flex;gap:6px;">
                <input id="inputSharePublic" readonly style="flex:1;padding:8px 10px;font-size:0.75rem;border:1px solid #cbd5e1;border-radius:6px;background:#fff;" value="読み込み中..." />
                <button onclick="copyShareText('inputSharePublic')" style="background:#2563eb;color:#fff;border:none;border-radius:6px;padding:0 12px;font-size:0.75rem;font-weight:700;cursor:pointer;">コピー</button>
            </div>
            <div style="font-size:0.68rem;color:#64748b;margin-top:4px;">※ 4G/5G回線のスマホや、離れた場所にいる人でもアクセス可能です。</div>
        </div>

        <div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:10px;padding:12px;margin-bottom:14px;">
            <div style="font-size:0.8rem;font-weight:800;color:#047857;margin-bottom:4px;">📶 【2】同じWi-Fi用 (社内・自宅ネットワーク)</div>
            <div style="display:flex;gap:6px;">
                <input id="inputShareLan" readonly style="flex:1;padding:8px 10px;font-size:0.75rem;border:1px solid #cbd5e1;border-radius:6px;background:#fff;" value="読み込み中..." />
                <button onclick="copyShareText('inputShareLan')" style="background:#10b981;color:#fff;border:none;border-radius:6px;padding:0 12px;font-size:0.75rem;font-weight:700;cursor:pointer;">コピー</button>
            </div>
            <div style="font-size:0.68rem;color:#64748b;margin-top:4px;">※ このPCと同じWi-Fiルーターに接続しているスマホ・PC用です。</div>
        </div>

        <button onclick="closeShareModal()" style="width:100%;padding:10px;background:#0f172a;color:#fff;border:none;border-radius:8px;font-weight:700;cursor:pointer;">閉じる</button>
    </div>
</div>

<script>
const STORAGE_KEY = 'apple_kaitori_checked_ids_v1';
let appData = {json_str};
let checkedIds = [];
let activeTab = 'iphone_profit_1000';
let otherCat = 'ALL';
let showAllOther = false;
let showNearIphone = false;
let searchQuery = '';
let pinnedCollapsed = false;

function initApp() {{
    try {{
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {{
            checkedIds = JSON.parse(saved);
        }} else {{
            checkedIds = ['iphone_iPhone_18_Pro_Max_512GB_バーガンディ'];
            localStorage.setItem(STORAGE_KEY, JSON.stringify(checkedIds));
        }}
    }} catch (e) {{
        checkedIds = [];
    }}
    renderAll();
}}

function toggleCheck(e, id) {{
    if (e) e.stopPropagation();
    const idx = checkedIds.indexOf(id);
    if (idx >= 0) {{
        checkedIds.splice(idx, 1);
    }} else {{
        checkedIds.unshift(id);
    }}
    try {{
        localStorage.setItem(STORAGE_KEY, JSON.stringify(checkedIds));
    }} catch (err) {{}}
    renderAll();
}}

function toggleCollapsePinned() {{
    pinnedCollapsed = !pinnedCollapsed;
    renderAll();
}}

function switchTab(tab) {{
    activeTab = tab;
    otherCat = 'ALL';
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const el = document.getElementById('tab_' + tab);
    if (el) el.classList.add('active');
    renderAll();
}}

function formatYen(n) {{
    return Number(n || 0).toLocaleString() + '円';
}}

function formatProfit(n) {{
    const v = Number(n || 0);
    return (v > 0 ? '+' : '') + v.toLocaleString() + '円';
}}

function createCardHtml(item, isPinned) {{
    const isChecked = checkedIds.includes(item.id);
    const profitClass = item.profit_jpy >= 1000 ? 'plus1000' : (item.profit_jpy >= 0 ? 'noloss' : 'minus');
    const cardExtra = isPinned ? 'pinned-card' : (item.profit_jpy >= 1000 ? 'profit-1000' : '');
    const catClass = item.category === 'iPhone' ? '' : 'other';

    return `
    <div class="item-card ${{cardExtra}}" onclick="openModal('${{item.id}}')">
        <div class="card-top">
            <div class="badge-group">
                <span class="cat-pill ${{catClass}}">${{item.category}}</span>
                ${{item.part_number ? `<span class="part-no">型番:${{item.part_number}}</span>` : ''}}
                ${{item.jan ? `<span class="part-no" style="background:#f1f5f9;padding:1px 6px;border-radius:4px;">JAN:${{item.jan}}</span>` : ''}}
            </div>
            <button class="btn-check ${{isChecked ? 'checked' : ''}}" onclick="toggleCheck(event, '${{item.id}}')">
                ${{isChecked ? '☑️ 優先チェック中' : '⬜ チェック'}}
            </button>
        </div>
        <div class="item-title">${{item.model_name}} <span class="item-cap">${{item.capacity}}</span></div>
        <div class="item-color">カラー: ${{item.color}}</div>
        <div class="price-row">
            <div class="p-col">
                <div class="p-label">最高買取 (${{item.best_store}})</div>
                <div class="p-best">${{formatYen(item.best_price)}}</div>
            </div>
            <div class="p-col">
                <div class="p-label">Apple公式定価</div>
                <div class="p-official">${{formatYen(item.official_price)}}</div>
            </div>
            <div class="profit-pill ${{profitClass}}">
                <div class="profit-rate">差益 (${{item.profit_rate}}%)</div>
                <div class="profit-val">${{formatProfit(item.profit_jpy)}}</div>
            </div>
        </div>
    </div>`;
}}

function renderAll() {{
    const items = appData.items || [];
    document.getElementById('updatedAtText').textContent = '更新: ' + (appData.updated_at || '-');

    // カウント更新
    const cProfit1000 = items.filter(x => x.category === 'iPhone' && x.profit_jpy >= 1000).length;
    const cNoLoss = items.filter(x => x.category === 'iPhone' && x.profit_jpy >= 0).length;
    const cOtherNoLoss = items.filter(x => x.category !== 'iPhone' && x.profit_jpy >= 0).length;

    document.getElementById('sub_iphone_profit_1000').textContent = `iPhone (${{cProfit1000}}台)`;
    document.getElementById('sub_iphone_no_loss').textContent = `iPhone 定価以上 (${{cNoLoss}}台)`;
    document.getElementById('sub_other_no_loss').textContent = `マイナスなし (${{cOtherNoLoss}}台)`;
    document.getElementById('sub_all_check').textContent = `全 ${{items.length}} 機種一覧`;

    // 1. ピン留め（最優先表示）
    const itemMap = new Map(items.map(i => [i.id, i]));
    const pinnedItems = checkedIds.map(id => itemMap.get(id)).filter(Boolean);
    document.getElementById('pinnedCount').textContent = pinnedItems.length;
    const collapseBtn = document.getElementById('collapseBtn');
    const pinnedContainer = document.getElementById('pinnedContainer');

    if (pinnedItems.length === 0) {{
        collapseBtn.style.display = 'none';
        pinnedContainer.innerHTML = `<div class="pinned-empty">カードの「⬜ チェック」を押すと、ここに最優先で固定表示されます。</div>`;
    }} else {{
        collapseBtn.style.display = 'inline-block';
        collapseBtn.textContent = pinnedCollapsed ? '展開する ▼' : '折りたたむ ▲';
        pinnedContainer.innerHTML = pinnedCollapsed ? '' : pinnedItems.map(i => createCardHtml(i, true)).join('');
    }}

    // 2. サブフィルター描画
    const fp = document.getElementById('filterPanel');
    if (activeTab === 'iphone_profit_1000') {{
        fp.innerHTML = `<p class="filter-desc">💡 Apple公式定価より <strong>1,000円以上</strong> 高く売れるiPhone端末のみを表示しています（JAN・型番完全一致）。</p>`;
    }} else if (activeTab === 'iphone_no_loss') {{
        fp.innerHTML = `
            <p class="filter-desc">💡 Apple公式定価から買取がマイナスにならない（差益0円以上の）iPhone端末です。</p>
            <button class="toggle-btn ${{showNearIphone ? 'active' : ''}}" onclick="showNearIphone=!showNearIphone;renderAll()">
                ${{showNearIphone ? '✓ 惜しい端末(-5,000円以内)も表示中' : '+ 惜しい端末(-5,000円以内)も見る'}}
            </button>
        `;
    }} else if (activeTab === 'other_no_loss') {{
        const cats = ['ALL', 'Mac', 'iPad', 'Apple Watch', 'AirPods', 'Accessory'];
        const chips = cats.map(c => `<button class="chip ${{otherCat===c?'active':''}}" onclick="otherCat='${{c}}';renderAll()">${{c==='ALL'?'すべて':c}}</button>`).join('');
        fp.innerHTML = `
            <p class="filter-desc">💡 Apple公式ストア現行販売品 × 買取1丁目・ルデヤの <strong>13桁JANコード・型番(PartNumber)完全一致</strong> で判定しています。</p>
            <div class="chip-row">${{chips}}</div>
            <button class="toggle-btn ${{showAllOther ? 'active' : ''}}" onclick="showAllOther=!showAllOther;renderAll()">
                ${{showAllOther ? '✓ 全機種の還元率ランキングを表示中 (マイナス含む)' : '🔍 全機種の還元率ランキングを表示する (高還元率順)'}}
            </button>
        `;
    }} else if (activeTab === 'all_check') {{
        const cats = ['ALL', 'iPhone', 'Mac', 'iPad', 'Apple Watch', 'AirPods', 'Accessory'];
        const chips = cats.map(c => `<button class="chip ${{otherCat===c?'active':''}}" onclick="otherCat='${{c}}';renderAll()">${{c==='ALL'?'全カテゴリ':c}}</button>`).join('');
        fp.innerHTML = `
            <input class="search-box" placeholder="機種名・容量・カラー・型番(MHQK4J/A)・JAN(454999...)で検索..." value="${{searchQuery}}" oninput="searchQuery=this.value;renderListOnly()" />
            <div class="chip-row">${{chips}}</div>
        `;
    }}

    renderListOnly();
}}

function renderListOnly() {{
    const items = appData.items || [];
    let list = [...items];

    if (activeTab === 'iphone_profit_1000') {{
        list = list.filter(x => x.category === 'iPhone' && x.profit_jpy >= 1000);
        list.sort((a, b) => b.profit_jpy - a.profit_jpy);
    }} else if (activeTab === 'iphone_no_loss') {{
        const minP = showNearIphone ? -5000 : 0;
        list = list.filter(x => x.category === 'iPhone' && x.profit_jpy >= minP);
        list.sort((a, b) => b.profit_jpy - a.profit_jpy);
    }} else if (activeTab === 'other_no_loss') {{
        list = list.filter(x => x.category !== 'iPhone');
        if (!showAllOther) list = list.filter(x => x.profit_jpy >= 0);
        if (otherCat !== 'ALL') list = list.filter(x => x.category === otherCat);
        list.sort((a, b) => b.profit_rate - a.profit_rate || b.profit_jpy - a.profit_jpy);
    }} else if (activeTab === 'all_check') {{
        if (otherCat !== 'ALL') list = list.filter(x => x.category === otherCat);
        if (searchQuery.trim()) {{
            const q = searchQuery.trim().toLowerCase();
            list = list.filter(x => `${{x.category}} ${{x.model_name}} ${{x.capacity}} ${{x.color}} ${{x.part_number}} ${{x.jan}}`.toLowerCase().includes(q));
        }}
        list.sort((a, b) => {{
            const ac = checkedIds.includes(a.id) ? 1 : 0;
            const bc = checkedIds.includes(b.id) ? 1 : 0;
            if (ac !== bc) return bc - ac;
            return b.profit_jpy - a.profit_jpy;
        }});
    }}

    const container = document.getElementById('mainCardList');
    if (list.length === 0) {{
        if (activeTab === 'other_no_loss' && !showAllOther) {{
            container.innerHTML = `
            <div style="background:#fff;padding:24px;border-radius:12px;text-align:center;color:#475569;font-size:0.85rem;border:1px solid #cbd5e1;">
                <div style="font-weight:800;font-size:0.95rem;color:#0f172a;margin-bottom:6px;">現在、Apple公式定価以上（マイナスなし）の他Apple商品は 0台 です</div>
                <div style="margin-bottom:14px;color:#64748b;">※買取1丁目の指定JANコード・Apple公式型番(PartNumber)完全一致で検証済み（最高還元率: iPad 11インチ 128GB の 87.6%）</div>
                <button class="toggle-btn active" onclick="showAllOther=true;renderAll()" style="padding:10px 16px;font-size:0.82rem;">
                    🔍 全機種の還元率・買取価格ランキングを表示する
                </button>
            </div>`;
        }} else {{
            container.innerHTML = `<div style="background:#fff;padding:24px;border-radius:12px;text-align:center;color:#64748b;font-size:0.85rem;">該当する機器がありません。上のフィルタボタンで表示範囲を広げることができます。</div>`;
        }}
    }} else {{
        container.innerHTML = list.map(i => createCardHtml(i, false)).join('');
    }}
}}

function openModal(id) {{
    const item = (appData.items || []).find(x => x.id === id);
    if (!item) return;
    const isChecked = checkedIds.includes(item.id);
    const stores = Object.entries(item.store_prices || {{}}).sort((a, b) => b[1] - a[1]);
    const storesHtml = stores.map(([s, p], idx) => `
        <div class="store-item ${{idx===0?'top':''}}">
            <span>${{idx===0?'👑 1位':(idx+1)+'位'}} ${{s}}</span>
            <span>${{formatYen(p)}}</span>
        </div>
    `).join('');

    const mc = document.getElementById('modalContent');
    mc.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid #e2e8f0;padding-bottom:12px;">
            <div>
                <div style="font-size:1.05rem;font-weight:800;">${{item.model_name}} ${{item.capacity}}</div>
                <div style="font-size:0.78rem;color:#64748b;margin-top:3px;">カラー: ${{item.color}} | 型番: ${{item.part_number || '-'}} ${{item.jan ? '| JAN: '+item.jan : ''}}</div>
            </div>
            <button onclick="closeModal()" style="border:none;background:#f1f5f9;width:32px;height:32px;border-radius:16px;font-weight:800;cursor:pointer;">✕</button>
        </div>
        <div style="display:flex;justify-content:space-around;background:#f8fafc;padding:12px;border-radius:10px;margin:12px 0;text-align:center;">
            <div>
                <div style="font-size:0.68rem;color:#64748b;">最高買取価格</div>
                <div style="font-size:0.98rem;font-weight:800;color:#047857;">${{formatYen(item.best_price)}}</div>
            </div>
            <div>
                <div style="font-size:0.68rem;color:#64748b;">Apple公式定価</div>
                <div style="font-size:0.92rem;font-weight:700;">${{formatYen(item.official_price)}}</div>
            </div>
            <div>
                <div style="font-size:0.68rem;color:#64748b;">差益 (${{item.profit_rate}}%)</div>
                <div style="font-size:0.95rem;font-weight:800;color:${{item.profit_jpy>=0?'#15803d':'#b91c1c'}};">${{formatProfit(item.profit_jpy)}}</div>
            </div>
        </div>
        <div style="font-size:0.82rem;font-weight:800;margin-bottom:6px;">🏬 店舗別 買取価格ランキング</div>
        <div style="max-height:240px;overflow-y:auto;">${{storesHtml}}</div>
        <button onclick="toggleCheck(null, '${{item.id}}');closeModal();" style="margin-top:14px;width:100%;padding:12px;border:none;border-radius:10px;background:${{isChecked?'#d97706':'#2563eb'}};color:#fff;font-weight:800;font-size:0.88rem;cursor:pointer;">
            ${{isChecked ? '☑️ 最優先表示から解除する' : '📌 この端末をチェックして最優先表示する'}}
        </button>
    `;
    document.getElementById('detailModal').style.display = 'flex';
}}

function closeModal() {{
    document.getElementById('detailModal').style.display = 'none';
}}

async function openShareModal() {{
    const modal = document.getElementById('shareModal');
    if (!modal) return;
    modal.style.display = 'flex';
    try {{
        const apiUrl = window.location.protocol.startsWith('http')
            ? '/api/share-urls'
            : 'http://localhost:8765/api/share-urls';
        const res = await fetch(apiUrl);
        if (res.ok) {{
            const data = await res.json();
            document.getElementById('inputSharePublic').value = data.public_url || '(サーバー起動時に自動発行されます)';
            document.getElementById('inputShareLan').value = data.lan_url || 'http://' + window.location.hostname + ':8765/';
        }} else {{
            document.getElementById('inputSharePublic').value = window.location.href;
            document.getElementById('inputShareLan').value = window.location.origin + '/';
        }}
    }} catch (e) {{
        document.getElementById('inputSharePublic').value = window.location.href;
        document.getElementById('inputShareLan').value = 'http://localhost:8765/';
    }}
}}

function closeShareModal() {{
    const modal = document.getElementById('shareModal');
    if (modal) modal.style.display = 'none';
}}

function copyShareText(id) {{
    const input = document.getElementById(id);
    if (!input) return;
    input.select();
    input.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(input.value).then(() => {{
        alert('URLをコピーしました！\\n' + input.value);
    }}).catch(() => {{
        prompt('以下のURLをコピーしてください:', input.value);
    }});
}}

async function refreshPrices() {{
    const btn = document.getElementById('refreshBtn');
    const toast = document.getElementById('statusToast');
    btn.disabled = true;
    btn.textContent = '⏳ 調査中...';
    toast.style.display = 'flex';
    toast.textContent = '🔄 買取各店およびApple公式ストアから最新価格をリアルタイム調査しています...';

    try {{
        const apiUrl = window.location.protocol.startsWith('http')
            ? '/api/refresh'
            : 'http://localhost:8765/api/refresh';
        const resp = await fetch(apiUrl);
        if (resp.ok) {{
            appData = await resp.json();
            renderAll();
            toast.textContent = '✅ 最新価格の調査・更新が完了しました！ (' + appData.updated_at + ')';
            setTimeout(() => {{ toast.style.display = 'none'; }}, 3500);
        }} else {{
            throw new Error('Server error');
        }}
    }} catch (e) {{
        toast.textContent = 'ℹ️ オフラインまたはサーバー未起動のため、現在の最新スナップショットを表示しています（run_mobile_app.bat 起動でリアルタイム再調査可能）。';
        setTimeout(() => {{ toast.style.display = 'none'; }}, 4500);
    }} finally {{
        btn.disabled = false;
        btn.textContent = '🔄 今すぐ調査';
    }}
}}

initApp();

// ブラウザのアドレスを開いた時・再読み込み(リロード)した時に自動で最新価格を再調査
if (window.location.protocol.startsWith('http')) {{
    setTimeout(() => {{
        refreshPrices();
    }}, 600);
}}
</script>
</body>
</html>"""

    OUTPUT_MOBILE_HTML.write_text(html, encoding="utf-8")
    logger.info("モバイルアプリHTML出力完了: %s", OUTPUT_MOBILE_HTML)
    return OUTPUT_MOBILE_HTML


def collect_all_mobile_data() -> Dict[str, Any]:
    """iPhone 全機種 + 他Apple Store商品の最新データを一括収集してモバイル用JSON構造を返す"""
    logger.info("=== スマホアプリ用 最新価格データの収集を開始します ===")

    # 1. Apple公式HPからiPhone 18シリーズのリアルタイム定価を取得
    apple_scraper = AppleOfficialScraper()
    apple_catalog = {}
    try:
        apple_catalog = apple_scraper.get_official_catalog()
    except Exception as e:
        logger.warning("Apple公式HP取得警告: %s", e)

    # 2. 主要買取店からiPhone 18シリーズを一括取得
    scrapers = [
        Kaitori1ChomeScraper(),
        RudeyaScraper(),
        MorimoriScraper(),
        SaikouneScraper(),
    ]
    all_records = []
    for sc in scrapers:
        try:
            recs = sc.scrape()
            all_records.extend(recs)
        except Exception as e:
            logger.warning("%s 取得エラー: %s", sc.store_name, e)

    comparator = PriceComparator(all_records, official_catalog=apple_catalog)
    iphone_items = comparator.compare()

    unified_items: List[Dict[str, Any]] = []
    for it in iphone_items:
        item_id = f"iphone_{it.model_name}_{it.capacity}_{it.color}".replace(" ", "_")
        unified_items.append({
            "id": item_id,
            "category": "iPhone",
            "model_name": it.model_name,
            "capacity": it.capacity,
            "color": it.color,
            "part_number": it.part_number or "",
            "jan": it.jan or "",
            "best_store": it.best_store,
            "best_price": it.best_price,
            "lowest_store": it.lowest_store,
            "lowest_price": it.lowest_price,
            "price_diff": it.price_diff,
            "official_price": it.official_price or 0,
            "profit_jpy": it.profit_jpy if it.profit_jpy is not None else -999999,
            "profit_rate": it.profit_rate if it.profit_rate is not None else 0.0,
            "store_prices": it.store_prices,
        })

    # 3. 他のApple Store商品 (Mac / iPad / Apple Watch / AirPods / Apple Pencil) を取得
    other_scraper = AppleOtherScraper()
    try:
        other_items = other_scraper.scrape_and_compare()
        unified_items.extend(other_items)
    except Exception as e:
        logger.warning("他Apple商品の取得エラー: %s", e)

    # 統計サマリー計算
    iphone_no_loss = [x for x in unified_items if x["category"] == "iPhone" and x["profit_jpy"] >= 0]
    iphone_profit_1000 = [x for x in unified_items if x["category"] == "iPhone" and x["profit_jpy"] >= 1000]
    other_no_loss = [x for x in unified_items if x["category"] != "iPhone" and x["profit_jpy"] >= 0]

    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_count": len(unified_items),
            "iphone_no_loss_count": len(iphone_no_loss),
            "iphone_profit_1000_count": len(iphone_profit_1000),
            "other_no_loss_count": len(other_no_loss),
        },
        "items": unified_items,
    }

    # ファイル保存
    MOBILE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    MOBILE_DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MOBILE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    generate_mobile_html(payload)

    logger.info(
        "モバイルデータ更新完了: 全%d件 (iPhone利益1000円以上:%d件 / iPhone損なし:%d件 / 他Apple商品損なし:%d件)",
        len(unified_items),
        len(iphone_profit_1000),
        len(iphone_no_loss),
        len(other_no_loss),
    )
    return payload


class MobileAPIHandler(SimpleHTTPRequestHandler):
    """CORS対応のモバイル用オンデマンド調査APIハンドラー"""

    PUBLIC_URL: str = ""
    LAN_URL: str = ""
    LOCAL_URL: str = ""

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/healthz" or self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        if self.path == "/" or self.path.startswith("/index") or self.path.startswith("/mobile"):
            if not OUTPUT_MOBILE_HTML.exists():
                collect_all_mobile_data()
            body = OUTPUT_MOBILE_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/share-urls"):
            host = self.headers.get("Host", "")
            proto = self.headers.get("X-Forwarded-Proto", "https" if ("onrender.com" in host or "railway.app" in host) else "http")
            detected_url = f"{proto}://{host}/" if host else ""
            pub_url = MobileAPIHandler.PUBLIC_URL or detected_url
            info = {
                "public_url": pub_url,
                "lan_url": MobileAPIHandler.LAN_URL or pub_url,
                "local_url": MobileAPIHandler.LOCAL_URL or pub_url,
            }
            body = json.dumps(info, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/refresh"):
            data = collect_all_mobile_data()
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/latest"):
            if OUTPUT_MOBILE_JSON.exists():
                body = OUTPUT_MOBILE_JSON.read_bytes()
            else:
                data = collect_all_mobile_data()
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()


def start_public_tunnel(port: int) -> Tuple[Optional[subprocess.Popen], Optional[str]]:
    """Windows標準のSSH(localhost.run)を使ってインストール不要で外部公開URL(https://*.lhr.life)を発行"""
    try:
        proc = subprocess.Popen(
            [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ServerAliveInterval=30",
                "-R", f"80:localhost:{port}",
                "nokey@localhost.run",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        found_url: List[str] = []

        def _reader():
            if not proc.stdout:
                return
            for line in proc.stdout:
                m = re.search(r"https://[a-z0-9\-]+\.lhr\.life", line)
                if m and not found_url:
                    found_url.append(m.group(0))

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        for _ in range(25):
            if found_url:
                return proc, found_url[0]
            time.sleep(0.2)
        return proc, None
    except Exception:
        return None, None


def background_periodic_refresh(interval_sec: int = 3600):
    """クラウドサーバー稼働中に定期的に最新価格を自動更新 (デフォルト: 1時間毎)"""
    while True:
        time.sleep(interval_sec)
        try:
            logger.info("定期自動更新: 最新価格データを収集中...")
            collect_all_mobile_data()
        except Exception as e:
            logger.warning("定期自動更新エラー: %s", e)


def main():
    parser = argparse.ArgumentParser(description="スマホアプリ用データ生成 & APIサーバー")
    parser.add_argument("--serve", action="store_true", help="ローカルAPIサーバー(ポート8765)を起動")
    parser.add_argument("--cloud", action="store_true", help="Render/Railway等のクラウドモードで起動")
    parser.add_argument("--open", action="store_true", help="モバイルアプリ画面をブラウザで開く")
    parser.add_argument("--port", type=int, default=0, help="サーバリッスンポート (未指定時は環境変数PORTまたは8765)")
    args = parser.parse_args()

    # クラウド環境(Render, Railway, Heroku等)の自動検知
    is_cloud = (
        args.cloud
        or "RENDER" in os.environ
        or "RAILWAY_ENVIRONMENT" in os.environ
        or ("PORT" in os.environ and not args.serve)
    )
    port = args.port if args.port > 0 else int(os.environ.get("PORT", 8765))

    if is_cloud:
        # クラウドモード: Render等のポートバインド期限に即応するため、即座にサーバーを起動
        logger.info(f"=== クラウドモード (Render/Railway) で起動します (Port: {port}) ===")
        if not OUTPUT_MOBILE_HTML.exists() or not OUTPUT_MOBILE_JSON.exists():
            threading.Thread(target=collect_all_mobile_data, daemon=True).start()
        else:
            logger.info("既存の最新スナップショットデータを利用して即時稼働します。")

        # バックグラウンド定期自動更新スレッド開始 (1時間おき)
        threading.Thread(target=background_periodic_refresh, args=(3600,), daemon=True).start()

        server = ThreadingHTTPServer(("0.0.0.0", port), MobileAPIHandler)
        logger.info(f"クラウドサーバーがポート {port} で稼働開始しました。")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("サーバーを停止しました。")
        return

    # 通常のローカルPCモード
    collect_all_mobile_data()

    if args.open and not args.serve:
        webbrowser.open(OUTPUT_MOBILE_HTML.as_uri())

    if args.serve:
        local_ip = get_local_ip()
        url_local = f"http://localhost:{port}/"
        url_lan = f"http://{local_ip}:{port}/"
        tunnel_proc, url_public = start_public_tunnel(port)

        MobileAPIHandler.PUBLIC_URL = url_public or ""
        MobileAPIHandler.LAN_URL = url_lan
        MobileAPIHandler.LOCAL_URL = url_local

        # 共有URLをメモ帳ですぐ確認できるよう「共有用アドレス.txt」ファイルにも自動保存
        share_file_content = (
            "====================================================================\n"
            "  Apple買取 利益判定 スマホアプリ 共有用Webアドレス一覧\n"
            "====================================================================\n\n"
            "【1】外出先・LINE等で他の人に送る場合 (4G/5G回線・誰でも開ける公開URL):\n"
            f"   {url_public if url_public else '(URL発行待ち または オフライン)'}\n\n"
            "【2】同じWi-Fi（自宅・オフィス内）の人に教える場合:\n"
            f"   {url_lan}\n\n"
            "【3】このPC自身で開く場合:\n"
            f"   {url_local}\n\n"
            "--------------------------------------------------------------------\n"
            "※ 上記URLはPCでアプリサーバーを起動している間、スマホやPCから開けます。\n"
            "※ スマホ(iPhone Safari / Android Chrome)で開いて「ホーム画面に追加」\n"
            "   を押すと、本物のアプリ同様に全画面で常時ご利用いただけます。\n"
            "====================================================================\n"
        )
        try:
            (BASE_DIR / "共有用アドレス.txt").write_text(share_file_content, encoding="utf-8")
            (OUTPUT_DIR / "共有用アドレス.txt").write_text(share_file_content, encoding="utf-8")
        except Exception:
            pass

        print("\n" + "=" * 68)
        print("  📱 Apple買取 利益判定 スマホアプリサーバーが起動しました！")
        print("=" * 68)
        print(f"  [1] このPCで開く場合                 : {url_local}")
        print(f"  [2] 同じWi-Fi内の人に伝えるURL       : {url_lan}")
        if url_public:
            print(f"  [3] 外出先・LINE等で他の人に伝えるURL: {url_public}")
        print("-" * 68)
        print("  ※ 共有用アドレスは「共有用アドレス.txt」にも保存されています。")
        print("  ※ iPhone(Safari) / Android(Chrome) で上記[2]または[3]のURLを開き、")
        print("     「ホーム画面に追加」を押すとアプリとしてインストールできます。")
        print("  ※ 終了するには Ctrl + C を押してください。")
        print("=" * 68 + "\n")
        if args.open:
            webbrowser.open(url_local)
        server = ThreadingHTTPServer(("0.0.0.0", port), MobileAPIHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("サーバーを停止しました。")
        finally:
            if tunnel_proc:
                tunnel_proc.terminate()


if __name__ == "__main__":
    main()
