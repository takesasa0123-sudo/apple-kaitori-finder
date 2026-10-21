import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Platform,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { FilterTabType, MobilePayload, ProductItem } from './src/types/models';
import { fetchLatestPricesOnDemand, getInitialPayload } from './src/services/liveScraper';

const STORAGE_CHECKED_KEY = '@apple_kaitori_checked_ids_v1';
const STORAGE_CACHED_PAYLOAD_KEY = '@apple_kaitori_cached_payload_v1';

export default function App() {
  const [payload, setPayload] = useState<MobilePayload>(() => getInitialPayload());
  const [checkedIds, setCheckedIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<FilterTabType>('iphone_profit_1000');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [progressText, setProgressText] = useState<string>('');
  const [lastSource, setLastSource] = useState<string>('初期スナップショット');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [otherCategoryFilter, setOtherCategoryFilter] = useState<string>('ALL');
  const [showAllOther, setShowAllOther] = useState<boolean>(false);
  const [showNearBreakevenIphone, setShowNearBreakevenIphone] = useState<boolean>(false);
  const [selectedItem, setSelectedItem] = useState<ProductItem | null>(null);
  const [pinnedCollapsed, setPinnedCollapsed] = useState<boolean>(false);

  // 起動時に保存済みのチェック端末IDとキャッシュデータを復元
  useEffect(() => {
    (async () => {
      try {
        const savedChecked = await AsyncStorage.getItem(STORAGE_CHECKED_KEY);
        if (savedChecked) {
          const parsed = JSON.parse(savedChecked);
          if (Array.isArray(parsed)) {
            setCheckedIds(parsed);
          }
        } else {
          // 初回起動時は最高利益のiPhone 18 Pro Max 512GB バーガンディをサンプルとしてチェック済みに設定
          const defaultPin = ['iphone_iPhone_18_Pro_Max_512GB_バーガンディ'];
          setCheckedIds(defaultPin);
          await AsyncStorage.setItem(STORAGE_CHECKED_KEY, JSON.stringify(defaultPin));
        }

        const savedPayload = await AsyncStorage.getItem(STORAGE_CACHED_PAYLOAD_KEY);
        if (savedPayload) {
          const parsedPayload = JSON.parse(savedPayload) as MobilePayload;
          if (parsedPayload?.items?.length) {
            setPayload(parsedPayload);
          }
        }
      } catch {
        // ストレージ読込エラー時は初期値のまま動作
      }
    })();
  }, []);

  // 端末のチェック（最優先表示）切り替え
  const toggleCheckItem = async (id: string) => {
    const next = checkedIds.includes(id)
      ? checkedIds.filter((x) => x !== id)
      : [id, ...checkedIds];
    setCheckedIds(next);
    try {
      await AsyncStorage.setItem(STORAGE_CHECKED_KEY, JSON.stringify(next));
    } catch {
      // ignore
    }
  };

  // オンデマンド調査ボタン押下時
  const handleRefresh = async () => {
    if (isLoading) return;
    setIsLoading(true);
    setProgressText('買取店・Apple公式価格を調査中...');
    try {
      const { payload: updated, source } = await fetchLatestPricesOnDemand(payload, (msg) =>
        setProgressText(msg)
      );
      setPayload(updated);
      setLastSource(source);
      await AsyncStorage.setItem(STORAGE_CACHED_PAYLOAD_KEY, JSON.stringify(updated));
    } finally {
      setIsLoading(false);
      setProgressText('');
    }
  };

  // チェックした端末（最優先表示リスト）
  const checkedItems = useMemo(() => {
    const map = new Map(payload.items.map((it) => [it.id, it]));
    return checkedIds
      .map((id) => map.get(id))
      .filter((it): it is ProductItem => Boolean(it));
  }, [payload.items, checkedIds]);

  // 各タブの件数カウント
  const counts = useMemo(() => {
    const items = payload.items;
    return {
      iphoneProfit1000: items.filter((x) => x.category === 'iPhone' && x.profit_jpy >= 1000).length,
      iphoneNoLoss: items.filter((x) => x.category === 'iPhone' && x.profit_jpy >= 0).length,
      otherNoLoss: items.filter((x) => x.category !== 'iPhone' && x.profit_jpy >= 0).length,
      all: items.length,
    };
  }, [payload.items]);

  // 現在選択中のタブに応じた表示リスト
  const displayedItems = useMemo(() => {
    let list = [...payload.items];

    if (activeTab === 'iphone_profit_1000') {
      list = list.filter((x) => x.category === 'iPhone' && x.profit_jpy >= 1000);
      list.sort((a, b) => b.profit_jpy - a.profit_jpy);
    } else if (activeTab === 'iphone_no_loss') {
      const minProfit = showNearBreakevenIphone ? -5000 : 0;
      list = list.filter((x) => x.category === 'iPhone' && x.profit_jpy >= minProfit);
      list.sort((a, b) => b.profit_jpy - a.profit_jpy);
    } else if (activeTab === 'other_no_loss') {
      list = list.filter((x) => x.category !== 'iPhone');
      if (!showAllOther) {
        list = list.filter((x) => x.profit_jpy >= 0);
      }
      if (otherCategoryFilter !== 'ALL') {
        list = list.filter((x) => x.category === otherCategoryFilter);
      }
      list.sort((a, b) => b.profit_rate - a.profit_rate || b.profit_jpy - a.profit_jpy);
    } else if (activeTab === 'all_check') {
      if (otherCategoryFilter !== 'ALL') {
        list = list.filter((x) => x.category === otherCategoryFilter);
      }
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        list = list.filter((x) =>
          `${x.category} ${x.model_name} ${x.capacity} ${x.color} ${x.part_number} ${x.jan}`
            .toLowerCase()
            .includes(q)
        );
      }
      // チェック済みを先頭に、その後は利益順
      list.sort((a, b) => {
        const aChecked = checkedIds.includes(a.id) ? 1 : 0;
        const bChecked = checkedIds.includes(b.id) ? 1 : 0;
        if (aChecked !== bChecked) return bChecked - aChecked;
        return b.profit_jpy - a.profit_jpy;
      });
    }

    return list;
  }, [
    payload.items,
    activeTab,
    showNearBreakevenIphone,
    showAllOther,
    otherCategoryFilter,
    searchQuery,
    checkedIds,
  ]);

  const formatYen = (n: number) => `${n.toLocaleString()}円`;
  const formatProfit = (n: number) => (n > 0 ? `+${n.toLocaleString()}円` : `${n.toLocaleString()}円`);

  const renderCard = (item: ProductItem, isPinnedSection: boolean = false) => {
    const isChecked = checkedIds.includes(item.id);
    const isProfit1000 = item.profit_jpy >= 1000;
    const isNoLoss = item.profit_jpy >= 0;

    const profitBadgeBg = isProfit1000
      ? '#dcfce7'
      : isNoLoss
      ? '#dbeafe'
      : '#fee2e2';
    const profitTextColor = isProfit1000
      ? '#15803d'
      : isNoLoss
      ? '#1d4ed8'
      : '#b91c1c';

    return (
      <TouchableOpacity
        key={`${isPinnedSection ? 'pin_' : 'list_'}${item.id}`}
        style={[
          styles.card,
          isPinnedSection && styles.cardPinned,
          isProfit1000 && !isPinnedSection && styles.cardProfitBorder,
        ]}
        activeOpacity={0.82}
        onPress={() => setSelectedItem(item)}
      >
        <View style={styles.cardTopRow}>
          <View style={styles.categoryBadgeWrap}>
            <View style={[styles.catBadge, item.category === 'iPhone' ? styles.catIphone : styles.catOther]}>
              <Text style={styles.catBadgeText}>{item.category}</Text>
            </View>
            {item.part_number ? (
              <Text style={styles.partNumberText}>型番:{item.part_number}</Text>
            ) : null}
            {item.jan ? (
              <Text style={styles.partNumberText}>JAN:{item.jan}</Text>
            ) : null}
          </View>

          <TouchableOpacity
            style={[styles.checkBtn, isChecked && styles.checkBtnActive]}
            onPress={() => toggleCheckItem(item.id)}
          >
            <Text style={[styles.checkBtnText, isChecked && styles.checkBtnTextActive]}>
              {isChecked ? '☑️ 優先チェック中' : '⬜ チェック'}
            </Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.modelTitle}>
          {item.model_name} <Text style={styles.capacityText}>{item.capacity}</Text>
        </Text>
        <Text style={styles.colorSubText}>カラー: {item.color}</Text>

        <View style={styles.priceGrid}>
          <View style={styles.priceBox}>
            <Text style={styles.priceLabel}>最高買取価格 ({item.best_store})</Text>
            <Text style={styles.bestPriceValue}>{formatYen(item.best_price)}</Text>
          </View>

          <View style={styles.priceBox}>
            <Text style={styles.priceLabel}>Apple公式定価</Text>
            <Text style={styles.officialPriceValue}>{formatYen(item.official_price)}</Text>
          </View>

          <View style={[styles.profitBox, { backgroundColor: profitBadgeBg }]}>
            <Text style={[styles.profitLabel, { color: profitTextColor }]}>
              差益 ({item.profit_rate}%)
            </Text>
            <Text style={[styles.profitValue, { color: profitTextColor }]}>
              {formatProfit(item.profit_jpy)}
            </Text>
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#0f172a" />

      {/* ヘッダー & 任意のタイミングで調査するオンデマンドボタン */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.headerTitle}>🍎 Apple買取 利益判定</Text>
          <Text style={styles.headerSub}>
            更新: {payload.updated_at} ({lastSource})
          </Text>
        </View>

        <TouchableOpacity
          style={[styles.refreshBtn, isLoading && styles.refreshBtnDisabled]}
          onPress={handleRefresh}
          disabled={isLoading}
        >
          {isLoading ? (
            <ActivityIndicator size="small" color="#ffffff" />
          ) : (
            <Text style={styles.refreshBtnText}>🔄 今すぐ調査</Text>
          )}
        </TouchableOpacity>
      </View>

      {isLoading && progressText ? (
        <View style={styles.progressBanner}>
          <ActivityIndicator size="small" color="#b45309" />
          <Text style={styles.progressBannerText}>{progressText}</Text>
        </View>
      ) : null}

      <ScrollView style={styles.mainScroll} contentContainerStyle={styles.mainScrollContent}>
        {/* 機能4: チェックした端末を最優先で最上部に固定表示 */}
        <View style={styles.pinnedSection}>
          <View style={styles.pinnedHeader}>
            <View style={styles.pinnedTitleRow}>
              <Text style={styles.pinnedTitle}>
                📌 チェックした端末（最優先表示: {checkedItems.length}台）
              </Text>
            </View>
            {checkedItems.length > 0 ? (
              <TouchableOpacity
                style={styles.collapseBtn}
                onPress={() => setPinnedCollapsed(!pinnedCollapsed)}
              >
                <Text style={styles.collapseBtnText}>
                  {pinnedCollapsed ? '展開する ▼' : '折りたたむ ▲'}
                </Text>
              </TouchableOpacity>
            ) : null}
          </View>

          {checkedItems.length === 0 ? (
            <Text style={styles.pinnedEmptyText}>
              カードの「⬜ チェック」を押すと、ここに最優先で固定表示されます。
            </Text>
          ) : !pinnedCollapsed ? (
            <View style={styles.pinnedList}>
              {checkedItems.map((it) => renderCard(it, true))}
            </View>
          ) : null}
        </View>

        {/* 4機能切り替えタブ */}
        <View style={styles.tabsGrid}>
          <TouchableOpacity
            style={[styles.tabBtn, activeTab === 'iphone_profit_1000' && styles.tabBtnActive]}
            onPress={() => setActiveTab('iphone_profit_1000')}
          >
            <Text style={[styles.tabTitle, activeTab === 'iphone_profit_1000' && styles.tabTitleActive]}>
              🔥 利益1,000円以上
            </Text>
            <Text style={[styles.tabSub, activeTab === 'iphone_profit_1000' && styles.tabSubActive]}>
              iPhone ({counts.iphoneProfit1000}台)
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabBtn, activeTab === 'iphone_no_loss' && styles.tabBtnActive]}
            onPress={() => setActiveTab('iphone_no_loss')}
          >
            <Text style={[styles.tabTitle, activeTab === 'iphone_no_loss' && styles.tabTitleActive]}>
              ⚖️ マイナスなし
            </Text>
            <Text style={[styles.tabSub, activeTab === 'iphone_no_loss' && styles.tabSubActive]}>
              iPhone 定価以上 ({counts.iphoneNoLoss}台)
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabBtn, activeTab === 'other_no_loss' && styles.tabBtnActive]}
            onPress={() => {
              setActiveTab('other_no_loss');
              setOtherCategoryFilter('ALL');
            }}
          >
            <Text style={[styles.tabTitle, activeTab === 'other_no_loss' && styles.tabTitleActive]}>
              💻 他Apple商品
            </Text>
            <Text style={[styles.tabSub, activeTab === 'other_no_loss' && styles.tabSubActive]}>
              マイナスなし ({counts.otherNoLoss}台)
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabBtn, activeTab === 'all_check' && styles.tabBtnActive]}
            onPress={() => {
              setActiveTab('all_check');
              setOtherCategoryFilter('ALL');
            }}
          >
            <Text style={[styles.tabTitle, activeTab === 'all_check' && styles.tabTitleActive]}>
              ☑️ 端末チェック選択
            </Text>
            <Text style={[styles.tabSub, activeTab === 'all_check' && styles.tabSubActive]}>
              全 {counts.all} 機種一覧
            </Text>
          </TouchableOpacity>
        </View>

        {/* タブごとのサブフィルター・説明バー */}
        <View style={styles.sectionFilterBar}>
          {activeTab === 'iphone_profit_1000' && (
            <Text style={styles.sectionInfoText}>
              💡 Apple公式定価より 1,000円以上 高く売れるiPhone端末のみを表示しています。
            </Text>
          )}

          {activeTab === 'iphone_no_loss' && (
            <View style={styles.subControlRow}>
              <Text style={styles.sectionInfoText}>
                💡 Apple公式定価から買取がマイナスにならない（差益0円以上の）iPhone端末です。
              </Text>
              <TouchableOpacity
                style={[styles.toggleChip, showNearBreakevenIphone && styles.toggleChipActive]}
                onPress={() => setShowNearBreakevenIphone(!showNearBreakevenIphone)}
              >
                <Text
                  style={[
                    styles.toggleChipText,
                    showNearBreakevenIphone && styles.toggleChipTextActive,
                  ]}
                >
                  {showNearBreakevenIphone
                    ? '✓ 惜しい端末(-5,000円以内)も表示中'
                    : '+ 惜しい端末(-5,000円以内)も見る'}
                </Text>
              </TouchableOpacity>
            </View>
          )}

          {activeTab === 'other_no_loss' && (
            <View>
              <Text style={styles.sectionInfoText}>
                💡 Apple公式ストア現行販売品 × 買取1丁目・ルデヤの 13桁JANコード・型番(PartNumber)完全一致 で判定しています。
              </Text>
              <View style={styles.chipRow}>
                {['ALL', 'Mac', 'iPad', 'Apple Watch', 'AirPods', 'Accessory'].map((cat) => (
                  <TouchableOpacity
                    key={cat}
                    style={[
                      styles.filterChip,
                      otherCategoryFilter === cat && styles.filterChipActive,
                    ]}
                    onPress={() => setOtherCategoryFilter(cat)}
                  >
                    <Text
                      style={[
                        styles.filterChipText,
                        otherCategoryFilter === cat && styles.filterChipTextActive,
                      ]}
                    >
                      {cat === 'ALL' ? 'すべて' : cat}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              <TouchableOpacity
                style={[styles.toggleChip, showAllOther && styles.toggleChipActive, { marginTop: 8 }]}
                onPress={() => setShowAllOther(!showAllOther)}
              >
                <Text style={[styles.toggleChipText, showAllOther && styles.toggleChipTextActive]}>
                  {showAllOther
                    ? '✓ 全機種の還元率ランキングを表示中 (マイナス含む)'
                    : '🔍 全機種の還元率ランキングを表示する (高還元率順)'}
                </Text>
              </TouchableOpacity>
            </View>
          )}

          {activeTab === 'all_check' && (
            <View>
              <TextInput
                style={styles.searchInput}
                placeholder="機種名・容量・カラー・型番(MHQK4J/A)・JAN(454999...)で検索..."
                placeholderTextColor="#94a3b8"
                value={searchQuery}
                onChangeText={setSearchQuery}
              />
              <View style={styles.chipRow}>
                {['ALL', 'iPhone', 'Mac', 'iPad', 'Apple Watch', 'AirPods', 'Accessory'].map((cat) => (
                  <TouchableOpacity
                    key={cat}
                    style={[
                      styles.filterChip,
                      otherCategoryFilter === cat && styles.filterChipActive,
                    ]}
                    onPress={() => setOtherCategoryFilter(cat)}
                  >
                    <Text
                      style={[
                        styles.filterChipText,
                        otherCategoryFilter === cat && styles.filterChipTextActive,
                      ]}
                    >
                      {cat === 'ALL' ? '全カテゴリ' : cat}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}
        </View>

        {/* メインカードリスト */}
        {displayedItems.length === 0 ? (
          <View style={styles.emptyBox}>
            <Text style={styles.emptyTitle}>
              {activeTab === 'other_no_loss' && !showAllOther
                ? '現在、Apple公式定価以上（マイナスなし）の他Apple商品は 0台 です'
                : '該当する機器がありません'}
            </Text>
            <Text style={styles.emptySub}>
              {activeTab === 'other_no_loss' && !showAllOther
                ? '※買取1丁目の指定JANコード・Apple公式型番(PartNumber)完全一致で検証済み（最高還元率: iPad 11インチ 128GB の 87.6%）'
                : '条件を変更するか、「🔄 今すぐ調査」で最新価格を取得してください。'}
            </Text>
            {activeTab === 'other_no_loss' && !showAllOther ? (
              <TouchableOpacity
                style={[styles.toggleChip, styles.toggleChipActive, { marginTop: 12 }]}
                onPress={() => setShowAllOther(true)}
              >
                <Text style={[styles.toggleChipText, styles.toggleChipTextActive]}>
                  🔍 全機種の還元率・買取価格ランキングを表示する
                </Text>
              </TouchableOpacity>
            ) : null}
          </View>
        ) : (
          displayedItems.map((it) => renderCard(it, false))
        )}
      </ScrollView>

      {/* 店舗別価格 詳細モーダル */}
      <Modal
        visible={Boolean(selectedItem)}
        transparent
        animationType="slide"
        onRequestClose={() => setSelectedItem(null)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            {selectedItem && (
              <>
                <View style={styles.modalHeader}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.modalTitle}>
                      {selectedItem.model_name} {selectedItem.capacity}
                    </Text>
                    <Text style={styles.modalSub}>
                      カラー: {selectedItem.color} | 型番: {selectedItem.part_number || '-'}
                    </Text>
                    {selectedItem.jan ? (
                      <Text style={styles.modalSub}>JAN: {selectedItem.jan}</Text>
                    ) : null}
                  </View>
                  <TouchableOpacity
                    style={styles.closeBtn}
                    onPress={() => setSelectedItem(null)}
                  >
                    <Text style={styles.closeBtnText}>✕</Text>
                  </TouchableOpacity>
                </View>

                <View style={styles.modalSummaryRow}>
                  <View style={styles.modalSummaryItem}>
                    <Text style={styles.modalSummaryLabel}>最高買取価格</Text>
                    <Text style={styles.modalSummaryBest}>
                      {formatYen(selectedItem.best_price)}
                    </Text>
                  </View>
                  <View style={styles.modalSummaryItem}>
                    <Text style={styles.modalSummaryLabel}>Apple公式定価</Text>
                    <Text style={styles.modalSummaryOfficial}>
                      {formatYen(selectedItem.official_price)}
                    </Text>
                  </View>
                  <View style={styles.modalSummaryItem}>
                    <Text style={styles.modalSummaryLabel}>差益 (還元率)</Text>
                    <Text
                      style={[
                        styles.modalSummaryProfit,
                        { color: selectedItem.profit_jpy >= 0 ? '#15803d' : '#b91c1c' },
                      ]}
                    >
                      {formatProfit(selectedItem.profit_jpy)} ({selectedItem.profit_rate}%)
                    </Text>
                  </View>
                </View>

                <Text style={styles.storeListHeader}>🏬 店舗別 買取価格ランキング</Text>
                <ScrollView style={styles.storeScroll}>
                  {Object.entries(selectedItem.store_prices)
                    .sort((a, b) => b[1] - a[1])
                    .map(([store, price], idx) => (
                      <View key={store} style={styles.storeRow}>
                        <Text style={[styles.storeRank, idx === 0 && styles.storeRankTop]}>
                          {idx === 0 ? '👑 1位' : `${idx + 1}位`} {store}
                        </Text>
                        <Text style={[styles.storePrice, idx === 0 && styles.storePriceTop]}>
                          {formatYen(price)}
                        </Text>
                      </View>
                    ))}
                </ScrollView>

                <TouchableOpacity
                  style={[
                    styles.modalCheckBtn,
                    checkedIds.includes(selectedItem.id) && styles.modalCheckBtnActive,
                  ]}
                  onPress={() => toggleCheckItem(selectedItem.id)}
                >
                  <Text style={styles.modalCheckBtnText}>
                    {checkedIds.includes(selectedItem.id)
                      ? '☑️ 最優先表示から解除する'
                      : '📌 この端末をチェックして最優先表示する'}
                  </Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#f1f5f9',
    paddingTop: Platform.OS === 'android' ? StatusBar.currentHeight : 0,
  },
  header: {
    backgroundColor: '#0f172a',
    paddingHorizontal: 16,
    paddingVertical: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerLeft: {
    flex: 1,
    marginRight: 10,
  },
  headerTitle: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '800',
  },
  headerSub: {
    color: '#94a3b8',
    fontSize: 11,
    marginTop: 2,
  },
  refreshBtn: {
    backgroundColor: '#2563eb',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
    minWidth: 110,
    alignItems: 'center',
  },
  refreshBtnDisabled: {
    backgroundColor: '#64748b',
  },
  refreshBtnText: {
    color: '#ffffff',
    fontWeight: '800',
    fontSize: 13,
  },
  progressBanner: {
    backgroundColor: '#fef3c7',
    paddingVertical: 8,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#fde68a',
  },
  progressBannerText: {
    color: '#92400e',
    fontSize: 12,
    fontWeight: '700',
    marginLeft: 8,
  },
  mainScroll: {
    flex: 1,
  },
  mainScrollContent: {
    padding: 12,
    paddingBottom: 40,
  },
  pinnedSection: {
    backgroundColor: '#fffbeb',
    borderWidth: 2,
    borderColor: '#f59e0b',
    borderRadius: 14,
    padding: 12,
    marginBottom: 14,
  },
  pinnedHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  pinnedTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  pinnedTitle: {
    color: '#92400e',
    fontWeight: '800',
    fontSize: 14,
  },
  collapseBtn: {
    backgroundColor: '#fef3c7',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  collapseBtnText: {
    color: '#b45309',
    fontSize: 11,
    fontWeight: '700',
  },
  pinnedEmptyText: {
    color: '#b45309',
    fontSize: 12,
    marginTop: 6,
  },
  pinnedList: {
    marginTop: 10,
  },
  tabsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  tabBtn: {
    width: '48.8%',
    backgroundColor: '#ffffff',
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 10,
    marginBottom: 8,
    borderWidth: 1.5,
    borderColor: '#cbd5e1',
  },
  tabBtnActive: {
    backgroundColor: '#1e293b',
    borderColor: '#0f172a',
  },
  tabTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: '#1e293b',
  },
  tabTitleActive: {
    color: '#ffffff',
  },
  tabSub: {
    fontSize: 11,
    color: '#64748b',
    marginTop: 2,
    fontWeight: '600',
  },
  tabSubActive: {
    color: '#93c5fd',
  },
  sectionFilterBar: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  sectionInfoText: {
    fontSize: 12,
    color: '#334155',
    fontWeight: '600',
  },
  subControlRow: {
    gap: 8,
  },
  toggleChip: {
    marginTop: 8,
    backgroundColor: '#f1f5f9',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    alignSelf: 'flex-start',
  },
  toggleChipActive: {
    backgroundColor: '#eff6ff',
    borderColor: '#3b82f6',
  },
  toggleChipText: {
    fontSize: 12,
    color: '#475569',
    fontWeight: '700',
  },
  toggleChipTextActive: {
    color: '#1d4ed8',
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 8,
  },
  filterChip: {
    backgroundColor: '#f1f5f9',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#cbd5e1',
  },
  filterChipActive: {
    backgroundColor: '#2563eb',
    borderColor: '#2563eb',
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#475569',
  },
  filterChipTextActive: {
    color: '#ffffff',
  },
  searchInput: {
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 13,
    color: '#0f172a',
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  cardPinned: {
    backgroundColor: '#ffffff',
    borderColor: '#f59e0b',
    borderWidth: 1.5,
  },
  cardProfitBorder: {
    borderLeftWidth: 5,
    borderLeftColor: '#16a34a',
  },
  cardTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  categoryBadgeWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  catBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  catIphone: {
    backgroundColor: '#dbeafe',
  },
  catOther: {
    backgroundColor: '#f3e8ff',
  },
  catBadgeText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#1e293b',
  },
  partNumberText: {
    fontSize: 11,
    color: '#64748b',
    fontWeight: '600',
  },
  checkBtn: {
    backgroundColor: '#f1f5f9',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
  },
  checkBtnActive: {
    backgroundColor: '#fef3c7',
    borderColor: '#f59e0b',
  },
  checkBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#475569',
  },
  checkBtnTextActive: {
    color: '#b45309',
  },
  modelTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0f172a',
  },
  capacityText: {
    color: '#2563eb',
  },
  colorSubText: {
    fontSize: 12,
    color: '#475569',
    marginTop: 2,
    marginBottom: 10,
  },
  priceGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#f1f5f9',
    paddingTop: 10,
  },
  priceBox: {
    flex: 1,
  },
  priceLabel: {
    fontSize: 10,
    color: '#64748b',
    fontWeight: '600',
  },
  bestPriceValue: {
    fontSize: 16,
    fontWeight: '800',
    color: '#047857',
    marginTop: 2,
  },
  officialPriceValue: {
    fontSize: 14,
    fontWeight: '700',
    color: '#334155',
    marginTop: 2,
  },
  profitBox: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    alignItems: 'flex-end',
    minWidth: 105,
  },
  profitLabel: {
    fontSize: 10,
    fontWeight: '700',
  },
  profitValue: {
    fontSize: 15,
    fontWeight: '900',
    marginTop: 1,
  },
  emptyBox: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 24,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: '#334155',
  },
  emptySub: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 6,
    textAlign: 'center',
    lineHeight: 18,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: '#ffffff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    maxHeight: '82%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
    paddingBottom: 12,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: '#0f172a',
  },
  modalSub: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 2,
  },
  closeBtn: {
    backgroundColor: '#f1f5f9',
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeBtnText: {
    fontSize: 15,
    fontWeight: '800',
    color: '#334155',
  },
  modalSummaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: '#f8fafc',
    padding: 12,
    borderRadius: 10,
    marginTop: 12,
  },
  modalSummaryItem: {
    alignItems: 'center',
    flex: 1,
  },
  modalSummaryLabel: {
    fontSize: 10,
    color: '#64748b',
    fontWeight: '600',
  },
  modalSummaryBest: {
    fontSize: 15,
    fontWeight: '800',
    color: '#047857',
    marginTop: 2,
  },
  modalSummaryOfficial: {
    fontSize: 14,
    fontWeight: '700',
    color: '#334155',
    marginTop: 2,
  },
  modalSummaryProfit: {
    fontSize: 14,
    fontWeight: '800',
    marginTop: 2,
  },
  storeListHeader: {
    fontSize: 13,
    fontWeight: '800',
    color: '#1e293b',
    marginTop: 14,
    marginBottom: 8,
  },
  storeScroll: {
    maxHeight: 240,
  },
  storeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 9,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  storeRank: {
    fontSize: 13,
    color: '#334155',
    fontWeight: '600',
  },
  storeRankTop: {
    color: '#047857',
    fontWeight: '800',
  },
  storePrice: {
    fontSize: 14,
    color: '#0f172a',
    fontWeight: '700',
  },
  storePriceTop: {
    color: '#047857',
    fontWeight: '900',
  },
  modalCheckBtn: {
    marginTop: 14,
    backgroundColor: '#2563eb',
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  modalCheckBtnActive: {
    backgroundColor: '#d97706',
  },
  modalCheckBtnText: {
    color: '#ffffff',
    fontWeight: '800',
    fontSize: 14,
  },
});
