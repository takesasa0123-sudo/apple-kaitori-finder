export interface ProductItem {
  id: string;
  category: 'iPhone' | 'Mac' | 'iPad' | 'Apple Watch' | 'AirPods' | 'Accessory' | string;
  model_name: string;
  capacity: string;
  color: string;
  part_number: string;
  jan: string;
  best_store: string;
  best_price: number;
  lowest_store: string;
  lowest_price: number;
  price_diff: number;
  official_price: number;
  profit_jpy: number;
  profit_rate: number;
  store_prices: Record<string, number>;
}

export interface MobileSummary {
  total_count: number;
  iphone_no_loss_count: number;
  iphone_profit_1000_count: number;
  other_no_loss_count: number;
}

export interface MobilePayload {
  updated_at: string;
  summary: MobileSummary;
  items: ProductItem[];
}

export type FilterTabType =
  | 'iphone_profit_1000'
  | 'iphone_no_loss'
  | 'other_no_loss'
  | 'all_check';
