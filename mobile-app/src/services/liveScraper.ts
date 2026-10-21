import { Platform } from 'react-native';
import { MobilePayload, ProductItem } from '../types/models';
import initialData from '../data/initialData.json';

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/125.0.0.0 Mobile Safari/537.36',
  Accept: 'application/json, text/html, */*',
};

function normalizeColor(raw: string): string {
  const s = raw.trim();
  if (s.includes('バーガンディ') || s.toLowerCase().includes('burgundy')) return 'バーガンディ';
  if (s.includes('グレイシャ') || s.toLowerCase().includes('glacier')) return 'グレイシャー';
  if (s.includes('ブラック') || s.toLowerCase().includes('black')) return 'ブラック';
  if (s.includes('シルバー') || s.toLowerCase().includes('silver')) return 'シルバー';
  return s;
}

function formatNow(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

/**
 * 初期バンドルデータを取得
 */
export function getInitialPayload(): MobilePayload {
  return initialData as unknown as MobilePayload;
}

/**
 * オンデマンドで最新買取価格を調査・更新する
 * - Web環境 / PCローカル起動時: ローカルAPIサーバー (http://localhost:8765/api/refresh) を試行
 * - ネイティブアプリ (Android .apk / iOS Expo Go): スマホから直接 買取1丁目API & 買取ルデヤ 等へアクセスして
 *   13桁JANコードおよびApple公式型番(PartNumber)完全一致でリアルタイム更新
 */
export async function fetchLatestPricesOnDemand(
  currentPayload: MobilePayload,
  onProgress?: (msg: string) => void
): Promise<{ payload: MobilePayload; source: string }> {
  // 1. まずローカルAPIサーバー (PC連動時) が応答するかチェック
  if (Platform.OS === 'web') {
    try {
      onProgress?.('ローカル調査サーバーへ接続中...');
      const resp = await fetch('http://localhost:8765/api/refresh', { method: 'GET' });
      if (resp.ok) {
        const data = (await resp.json()) as MobilePayload;
        return { payload: data, source: 'リアルタイム一括調査 (JAN・型番完全一致)' };
      }
    } catch {
      // ローカルサーバー未起動時はそのまま直接取得へ進行
    }
  }

  // 2. スマホ本体からの直接リアルタイム取得 (Android .apk / iOS Expo Go)
  const clonedItems: ProductItem[] = JSON.parse(JSON.stringify(currentPayload.items));
  let updatedCount = 0;

  // JANコードまたは型番(PartNumber)の完全一致でアイテムに店舗価格を記録するヘルパー
  const applyStorePrice = (storeName: string, price: number, jan?: string | null, textWithPart?: string) => {
    if (!price || price <= 0) return;
    const cleanJan = (jan || '').trim();
    const upperText = (textWithPart || '').toUpperCase();

    for (const item of clonedItems) {
      const janMatch = cleanJan && item.jan && item.jan === cleanJan;
      const partMatch = item.part_number && upperText.includes(item.part_number.toUpperCase());
      if (janMatch || partMatch) {
        item.store_prices[storeName] = price;
        if (cleanJan && !item.jan) {
          item.jan = cleanJan;
        }
        updatedCount++;
      }
    }
  };

  try {
    // (A) 買取1丁目 API から iPhone 18 シリーズを直接取得 (JANコード & モデル・容量・カラー一致)
    onProgress?.('買取1丁目 API から iPhone 18 最新価格を取得中...');
    const icIphoneResp = await fetch(
      'https://www.1-chome.com/api/index/findByKeyword?keyword=iPhone+18',
      { headers: HEADERS }
    );
    if (icIphoneResp.ok) {
      const icJson = await icIphoneResp.json();
      const contents = icJson?.data?.content || [];
      for (const prod of contents) {
        const title: string = prod.title || '';
        const details: any[] = prod.goodsKbDetails || [];
        const unopened = details.find((d) => (d.kbDetailName || '').includes('未開封')) || details[0];
        if (!unopened || !unopened.kbDetailPrice) continue;
        const basePrice = Number(unopened.kbDetailPrice);
        const kbId = unopened.allGoodsKbDetailId;

        const mName = title.includes('Pro Max')
          ? 'iPhone 18 Pro Max'
          : title.includes('Pro')
          ? 'iPhone 18 Pro'
          : '';
        const capMatch = title.match(/(128GB|256GB|512GB|1TB|2TB)/i);
        const cap = capMatch ? capMatch[1].toUpperCase() : '';
        if (!mName || !cap) continue;

        const colorOpts: any[] = prod.keitaiColorOptions || [];
        for (const co of colorOpts) {
          const col = normalizeColor(co.color || '');
          const coJan = (co.jan || '').trim();
          const rels: any[] = co.keitaiKbDetailColorRels || [];
          const rel = rels.find((r) => r.keitaiKbDetailId === kbId) || rels[0];
          const varPrice = rel ? Number(rel.varPrice || 0) : 0;
          const finalPrice = basePrice + varPrice;

          const target = clonedItems.find(
            (it) =>
              it.category === 'iPhone' &&
              ((coJan && it.jan === coJan) || (it.model_name === mName && it.capacity === cap && it.color === col))
          );
          if (target && finalPrice > 0) {
            target.store_prices['買取1丁目'] = finalPrice;
            if (coJan && !target.jan) target.jan = coJan;
            updatedCount++;
          }
        }
      }
    }

    // (B) 買取1丁目 API から 他Apple Store商品 (Mac / iPad / Watch / AirPods / Pencil / HomePod) を JAN・型番完全一致で取得
    const otherKeywords = [
      'Mac+mini',
      'MacBook+Air',
      'MacBook+Pro',
      'iMac',
      'iPad',
      'iPad+mini',
      'AirPods',
      'Apple+Watch',
      'Apple+Pencil',
      'HomePod',
    ];
    for (const kw of otherKeywords) {
      onProgress?.(`買取1丁目 API から ${decodeURIComponent(kw)} (JAN・型番一致) を調査中...`);
      try {
        const r = await fetch(`https://www.1-chome.com/api/index/findByKeyword?keyword=${kw}&page=1&size=50`, {
          headers: HEADERS,
        });
        if (r.ok) {
          const j = await r.json();
          const list = j?.data?.content || [];
          for (const x of list) {
            const title: string = x.title || '';
            const details: any[] = x.goodsKbDetails || [];
            const unopened =
              details.find((d) => {
                const n = d.kbDetailName || '';
                return n.includes('未開封') || n.includes('新品') || n.includes('保証未開始');
              }) || details[0];
            const basePrice = Number(unopened?.kbDetailPrice || 0);
            if (basePrice <= 0) continue;
            const kbId = unopened?.allGoodsKbDetailId;

            const colorOpts: any[] = x.keitaiColorOptions || [];
            if (colorOpts.length > 0) {
              for (const opt of colorOpts) {
                const optColor: string = opt.color || '';
                const optJan: string = opt.jan || '';
                const rels: any[] = opt.keitaiKbDetailColorRels || [];
                const rel = rels.find((relItem) => relItem.keitaiKbDetailId === kbId);
                const varPrice = rel ? Number(rel.varPrice || 0) : 0;
                applyStorePrice('買取1丁目', basePrice + varPrice, optJan, `${title} ${optColor}`);
              }
            } else {
              const topJan: string = x.jan || '';
              applyStorePrice('買取1丁目', basePrice, topJan, title);
            }
          }
        }
      } catch {
        // 個別キーワードエラーはスキップ
      }
    }

    // (C) 買取ルデヤ から iPhone 18 & 他Apple商品を JAN・型番完全一致で取得
    const rudeyaCats = [253, 254, 8, 9, 5, 71, 72, 73, 74, 4, 33, 256, 259, 223, 25, 146];
    for (const cid of rudeyaCats) {
      onProgress?.(`買取ルデヤ (カテゴリ:${cid}) JAN・型番照合中...`);
      try {
        const r = await fetch(`https://kaitori-rudeya.com/category/detail/${cid}`, {
          headers: HEADERS,
        });
        if (r.ok) {
          const html = await r.text();
          const cardRegex = /<article class="pgrid-card"[\s\S]*?<\/article>/g;
          const cards = html.match(cardRegex) || [];
          for (const card of cards) {
            const nameMatch = card.match(/class="product-card-name-link"[^>]*>([\s\S]*?)<\/a>/);
            const priceMatch = card.match(/class="product-card-price-value"[^>]*>([\s\S]*?)<\/div>/);
            if (!nameMatch || !priceMatch) continue;
            const rawTitle = nameMatch[1].replace(/<[^>]+>/g, '').trim();
            const priceDigits = priceMatch[1].replace(/[^\d]/g, '');
            if (!priceDigits) continue;
            const price = Number(priceDigits);
            const janMatch = card.match(/JAN:\s*(454999\d{7})/);
            const cardJan = janMatch ? janMatch[1] : '';
            applyStorePrice('買取ルデヤ', price, cardJan, `${rawTitle} ${card}`);
          }
        }
      } catch {
        // 個別エラーはスキップ
      }
    }
  } catch {
    // ネットワーク制限等
  }

  // 再集計
  for (const it of clonedItems) {
    const entries = Object.entries(it.store_prices).filter(([, v]) => v > 0);
    if (entries.length > 0) {
      entries.sort((a, b) => b[1] - a[1]);
      it.best_store = entries[0][0];
      it.best_price = entries[0][1];
      it.lowest_store = entries[entries.length - 1][0];
      it.lowest_price = entries[entries.length - 1][1];
      it.price_diff = it.best_price - it.lowest_price;
      if (it.official_price > 0) {
        it.profit_jpy = it.best_price - it.official_price;
        it.profit_rate = Math.round((it.best_price / it.official_price) * 1000) / 10;
      }
    }
  }

  const iphoneNoLoss = clonedItems.filter((x) => x.category === 'iPhone' && x.profit_jpy >= 0);
  const iphoneProfit1000 = clonedItems.filter((x) => x.category === 'iPhone' && x.profit_jpy >= 1000);
  const otherNoLoss = clonedItems.filter((x) => x.category !== 'iPhone' && x.profit_jpy >= 0);

  const newPayload: MobilePayload = {
    updated_at: formatNow(),
    summary: {
      total_count: clonedItems.length,
      iphone_no_loss_count: iphoneNoLoss.length,
      iphone_profit_1000_count: iphoneProfit1000.length,
      other_no_loss_count: otherNoLoss.length,
    },
    items: clonedItems,
  };

  return {
    payload: newPayload,
    source: updatedCount > 0 ? `スマホ直接リアルタイム取得 (JAN・型番完全一致)` : '最新スナップショットデータ',
  };
}
