"""
Apple Store 他商品 (Mac / iPad / Apple Watch / AirPods / Apple Pencil / HomePod) 買取価格スクレイパー
(src/scrapers/apple_other.py)

【JANコード・型番(PartNumber)完全一致方式】
- Apple公式オンラインストア (apple.com/jp) は日本の13桁JANコードをHTML上に掲載せず、
  全商品を一意の「Apple公式型番 (PartNumber: MxxxxJ/A 等)」で管理しています。
- 一方、買取1丁目 API (item["jan"] および item["keitaiColorOptions"][i]["jan"]) や
  買取ルデヤ HTML には、「Apple公式型番 (MxxxxJ/A)」と「13桁JANコード (454999...)」の
  両方が1対1で登録されています。
- 本モジュールでは：
  1. Apple公式サイト (apple.com/jp) から現行販売モデルの「型番 (PartNumber)」と「最新税込定価」を取得
  2. 買取1丁目 API の keitaiColorOptions（カラー別の個別JAN・個別型番・減額 varPrice）および
     買取ルデヤの個別JAN・型番を展開
  3. 「13桁JANコード」および「Apple公式型番 (PartNumber)」の完全一致で突合することで、
     買取1丁目の指定機器と100%整合した価格比較を実現します。
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any
import urllib.request
from bs4 import BeautifulSoup

from config import DEFAULT_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

PART_NUMBER_REGEX = re.compile(r"\b(M[A-Z0-9]{3,5}(?:J|X|ZA|ZP|AM)/A)\b")
JAN_REGEX = re.compile(r"\b(454999\d{7})\b")


# Apple公式オンラインストア（日本: apple.com/jp）現行販売モデル × 買取1丁目指定JAN・型番マスターカタログ
# ※ Apple公式ストアで販売終了した旧モデル（Mac mini M4 MU9D3J/A 等）は除外し、
#    現在 Apple公式ストアで新品購入可能な現行モデルのみを厳密に収録しています。
APPLE_OTHER_OFFICIAL_CATALOG: List[Dict[str, Any]] = [
    # ==================== Mac mini (2026 M6 / M5 Pro) ====================
    {
        "category": "Mac",
        "model_name": "Mac mini (M6)",
        "capacity": "16GB/256GB",
        "color": "シルバー",
        "part_number": "MHQK4J/A",
        "jan": "4549995675993",
        "official_price": 149800,
    },
    {
        "category": "Mac",
        "model_name": "Mac mini (M6)",
        "capacity": "16GB/512GB",
        "color": "シルバー",
        "part_number": "MHQL4J/A",
        "jan": "4549995676006",
        "official_price": 185800,
    },
    {
        "category": "Mac",
        "model_name": "Mac mini (M6)",
        "capacity": "24GB/512GB",
        "color": "シルバー",
        "part_number": "MHQM4J/A",
        "jan": "4549995676013",
        "official_price": 221800,
    },
    {
        "category": "Mac",
        "model_name": "Mac mini (M5 Pro)",
        "capacity": "24GB/512GB",
        "color": "シルバー",
        "part_number": "MHQN4J/A",
        "jan": "4549995676020",
        "official_price": 299800,
    },
    # ==================== MacBook Air 13.6インチ (M5) ====================
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "16GB/512GB",
        "color": "シルバー",
        "part_number": "MDH74J/A",
        "jan": "4549995656664",
        "official_price": 224800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "16GB/512GB",
        "color": "スターライト",
        "part_number": "MDHA4J/A",
        "jan": "4549995656725",
        "official_price": 224800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "16GB/512GB",
        "color": "ミッドナイト",
        "part_number": "MDHE4J/A",
        "jan": "4549995656787",
        "official_price": 224800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "16GB/512GB",
        "color": "スカイブルー",
        "part_number": "MDHH4J/A",
        "jan": "4549995656848",
        "official_price": 224800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "16GB/1TB",
        "color": "シルバー",
        "part_number": "MDH84J/A",
        "jan": "4549995656688",
        "official_price": 278800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "16GB/1TB",
        "color": "スターライト",
        "part_number": "MDHC4J/A",
        "jan": "4549995656749",
        "official_price": 278800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "16GB/1TB",
        "color": "ミッドナイト",
        "part_number": "MDHF4J/A",
        "jan": "4549995656800",
        "official_price": 278800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "16GB/1TB",
        "color": "スカイブルー",
        "part_number": "MDHJ4J/A",
        "jan": "4549995656862",
        "official_price": 278800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "24GB/1TB",
        "color": "シルバー",
        "part_number": "MDH94J/A",
        "jan": "4549995656701",
        "official_price": 314800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "24GB/1TB",
        "color": "スターライト",
        "part_number": "MDHD4J/A",
        "jan": "4549995656763",
        "official_price": 314800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "24GB/1TB",
        "color": "ミッドナイト",
        "part_number": "MDHG4J/A",
        "jan": "4549995656824",
        "official_price": 314800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 13.6インチ (M5)",
        "capacity": "24GB/1TB",
        "color": "スカイブルー",
        "part_number": "MDHK4J/A",
        "jan": "4549995656886",
        "official_price": 314800,
    },
    # ==================== MacBook Air 15.3インチ (M5) ====================
    {
        "category": "Mac",
        "model_name": "MacBook Air 15.3インチ (M5)",
        "capacity": "16GB/512GB",
        "color": "シルバー",
        "part_number": "MDV94J/A",
        "jan": "4549995656985",
        "official_price": 264800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 15.3インチ (M5)",
        "capacity": "16GB/512GB",
        "color": "スターライト",
        "part_number": "MDVD4J/A",
        "jan": "4549995657043",
        "official_price": 264800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 15.3インチ (M5)",
        "capacity": "16GB/512GB",
        "color": "ミッドナイト",
        "part_number": "MDVH4J/A",
        "jan": "4549995657104",
        "official_price": 264800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 15.3インチ (M5)",
        "capacity": "16GB/512GB",
        "color": "スカイブルー",
        "part_number": "MDVQ4J/A",
        "jan": "4549995657166",
        "official_price": 264800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 15.3インチ (M5)",
        "capacity": "16GB/1TB",
        "color": "シルバー",
        "part_number": "MDVA4J/A",
        "jan": "4549995657005",
        "official_price": 318800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Air 15.3インチ (M5)",
        "capacity": "24GB/1TB",
        "color": "シルバー",
        "part_number": "MDVC4J/A",
        "jan": "4549995657029",
        "official_price": 354800,
    },
    # ==================== MacBook Pro 14.2 / 16.2インチ (M5 / M5 Pro / M5 Max) ====================
    {
        "category": "Mac",
        "model_name": "MacBook Pro 14.2インチ (M5)",
        "capacity": "16GB/1TB",
        "color": "スペースブラック",
        "part_number": "MDE14J/A",
        "jan": "4549995628180",
        "official_price": 339800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Pro 14.2インチ (M5)",
        "capacity": "16GB/1TB",
        "color": "シルバー",
        "part_number": "MDE54J/A",
        "jan": "4549995628241",
        "official_price": 339800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Pro 14.2インチ (M5)",
        "capacity": "24GB/1TB",
        "color": "スペースブラック",
        "part_number": "MDE34J/A",
        "jan": "4549995628203",
        "official_price": 375800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Pro 14.2インチ (M5)",
        "capacity": "24GB/1TB",
        "color": "シルバー",
        "part_number": "MDE64J/A",
        "jan": "4549995628265",
        "official_price": 375800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Pro 14.2インチ (M5 Pro)",
        "capacity": "24GB/1TB",
        "color": "シルバー",
        "part_number": "MGDN4J/A",
        "jan": "4549995658255",
        "official_price": 429800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Pro 14.2インチ (M5 Pro)",
        "capacity": "24GB/1TB",
        "color": "スペースブラック",
        "part_number": "MGDR4J/A",
        "jan": "4549995658316",
        "official_price": 429800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Pro 14.2インチ (M5 Max)",
        "capacity": "36GB/2TB",
        "color": "シルバー",
        "part_number": "MGDQ4J/A",
        "jan": "4549995658293",
        "official_price": 699800,
    },
    {
        "category": "Mac",
        "model_name": "MacBook Pro 14.2インチ (M5 Max)",
        "capacity": "36GB/2TB",
        "color": "スペースブラック",
        "part_number": "MGDU4J/A",
        "jan": "4549995658354",
        "official_price": 699800,
    },
    # ==================== iMac 24インチ (M4) ====================
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 2port)",
        "capacity": "16GB/256GB",
        "color": "シルバー",
        "part_number": "MWUC3J/A",
        "jan": "4549995507065",
        "official_price": 249800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 2port)",
        "capacity": "16GB/256GB",
        "color": "グリーン",
        "part_number": "MWUE3J/A",
        "jan": "4549995507089",
        "official_price": 249800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 2port)",
        "capacity": "16GB/256GB",
        "color": "ブルー",
        "part_number": "MWUF3J/A",
        "jan": "4549995507096",
        "official_price": 249800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 2port)",
        "capacity": "16GB/256GB",
        "color": "ピンク",
        "part_number": "MWUG3J/A",
        "jan": "4549995507102",
        "official_price": 249800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 4port)",
        "capacity": "16GB/256GB",
        "color": "シルバー",
        "part_number": "MWUU3J/A",
        "jan": "4549995507133",
        "official_price": 289800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 4port)",
        "capacity": "16GB/256GB",
        "color": "グリーン",
        "part_number": "MWUY3J/A",
        "jan": "4549995507171",
        "official_price": 289800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 4port)",
        "capacity": "16GB/256GB",
        "color": "ブルー",
        "part_number": "MWV13J/A",
        "jan": "4549995507195",
        "official_price": 289800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 4port)",
        "capacity": "16GB/256GB",
        "color": "ピンク",
        "part_number": "MWV43J/A",
        "jan": "4549995507218",
        "official_price": 289800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 4port)",
        "capacity": "16GB/512GB",
        "color": "シルバー",
        "part_number": "MWUV3J/A",
        "jan": "4549995507140",
        "official_price": 325800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 4port)",
        "capacity": "16GB/512GB",
        "color": "グリーン",
        "part_number": "MWV03J/A",
        "jan": "4549995507188",
        "official_price": 325800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 4port)",
        "capacity": "16GB/512GB",
        "color": "ブルー",
        "part_number": "MWV33J/A",
        "jan": "4549995507201",
        "official_price": 325800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 4port)",
        "capacity": "24GB/512GB",
        "color": "グリーン",
        "part_number": "MD2Q4J/A",
        "jan": "4549995559798",
        "official_price": 361800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 4port)",
        "capacity": "24GB/512GB",
        "color": "ブルー",
        "part_number": "MD2T4J/A",
        "jan": "4549995559804",
        "official_price": 361800,
    },
    {
        "category": "Mac",
        "model_name": "iMac 24インチ (M4 4port)",
        "capacity": "24GB/512GB",
        "color": "ピンク",
        "part_number": "MD2U4J/A",
        "jan": "4549995559811",
        "official_price": 361800,
    },
    # ==================== iPad 11インチ (Wi-Fi) ====================
    {
        "category": "iPad",
        "model_name": "iPad 11インチ (Wi-Fi)",
        "capacity": "128GB",
        "color": "シルバー",
        "part_number": "MD3Y4J/A",
        "jan": "4549995560077",
        "official_price": 74800,
    },
    {
        "category": "iPad",
        "model_name": "iPad 11インチ (Wi-Fi)",
        "capacity": "128GB",
        "color": "ブルー",
        "part_number": "MD4A4J/A",
        "jan": "4549995560084",
        "official_price": 74800,
    },
    {
        "category": "iPad",
        "model_name": "iPad 11インチ (Wi-Fi)",
        "capacity": "128GB",
        "color": "イエロー",
        "part_number": "MD4D4J/A",
        "jan": "4549995560091",
        "official_price": 74800,
    },
    {
        "category": "iPad",
        "model_name": "iPad 11インチ (Wi-Fi)",
        "capacity": "128GB",
        "color": "ピンク",
        "part_number": "MD4E4J/A",
        "jan": "4549995560107",
        "official_price": 74800,
    },
    {
        "category": "iPad",
        "model_name": "iPad 11インチ (Wi-Fi)",
        "capacity": "256GB",
        "color": "シルバー",
        "part_number": "MD4G4J/A",
        "jan": "4549995560114",
        "official_price": 91800,
    },
    {
        "category": "iPad",
        "model_name": "iPad 11インチ (Wi-Fi)",
        "capacity": "256GB",
        "color": "ブルー",
        "part_number": "MD4H4J/A",
        "jan": "4549995560121",
        "official_price": 91800,
    },
    {
        "category": "iPad",
        "model_name": "iPad 11インチ (Wi-Fi)",
        "capacity": "256GB",
        "color": "イエロー",
        "part_number": "MD4J4J/A",
        "jan": "4549995560138",
        "official_price": 91800,
    },
    {
        "category": "iPad",
        "model_name": "iPad 11インチ (Wi-Fi)",
        "capacity": "256GB",
        "color": "ピンク",
        "part_number": "MD4P4J/A",
        "jan": "4549995560145",
        "official_price": 91800,
    },
    # ==================== iPad Air 11インチ / 13インチ (M4 Wi-Fi) ====================
    {
        "category": "iPad",
        "model_name": "iPad Air 11インチ (M4 Wi-Fi)",
        "capacity": "128GB",
        "color": "スペースグレイ",
        "part_number": "MH304J/A",
        "jan": "4549995661996",
        "official_price": 129800,
    },
    {
        "category": "iPad",
        "model_name": "iPad Air 11インチ (M4 Wi-Fi)",
        "capacity": "128GB",
        "color": "ブルー",
        "part_number": "MH314J/A",
        "jan": "4549995662009",
        "official_price": 129800,
    },
    {
        "category": "iPad",
        "model_name": "iPad Air 11インチ (M4 Wi-Fi)",
        "capacity": "128GB",
        "color": "スターライト",
        "part_number": "MH334J/A",
        "jan": "4549995662016",
        "official_price": 129800,
    },
    {
        "category": "iPad",
        "model_name": "iPad Air 11インチ (M4 Wi-Fi)",
        "capacity": "128GB",
        "color": "パープル",
        "part_number": "MH344J/A",
        "jan": "4549995662023",
        "official_price": 129800,
    },
    {
        "category": "iPad",
        "model_name": "iPad Air 11インチ (M4 Wi-Fi)",
        "capacity": "256GB",
        "color": "スペースグレイ",
        "part_number": "MH354J/A",
        "jan": "4549995662030",
        "official_price": 146800,
    },
    {
        "category": "iPad",
        "model_name": "iPad Air 11インチ (M4 Wi-Fi)",
        "capacity": "256GB",
        "color": "ブルー",
        "part_number": "MH364J/A",
        "jan": "4549995662047",
        "official_price": 146800,
    },
    {
        "category": "iPad",
        "model_name": "iPad Air 11インチ (M4 Wi-Fi)",
        "capacity": "256GB",
        "color": "スターライト",
        "part_number": "MH374J/A",
        "jan": "4549995662054",
        "official_price": 146800,
    },
    {
        "category": "iPad",
        "model_name": "iPad Air 11インチ (M4 Wi-Fi)",
        "capacity": "256GB",
        "color": "パープル",
        "part_number": "MH394J/A",
        "jan": "4549995662061",
        "official_price": 146800,
    },
    # ==================== iPad Pro 11インチ / 13インチ (M5 Wi-Fi) ====================
    {
        "category": "iPad",
        "model_name": "iPad Pro 11インチ (M5 Wi-Fi)",
        "capacity": "256GB",
        "color": "スペースブラック",
        "part_number": "MDWK4J/A",
        "jan": "4549995616606",
        "official_price": 209800,
    },
    {
        "category": "iPad",
        "model_name": "iPad Pro 11インチ (M5 Wi-Fi)",
        "capacity": "256GB",
        "color": "シルバー",
        "part_number": "MDWL4J/A",
        "jan": "4549995616613",
        "official_price": 209800,
    },
    {
        "category": "iPad",
        "model_name": "iPad Pro 11インチ (M5 Wi-Fi)",
        "capacity": "512GB",
        "color": "スペースブラック",
        "part_number": "MDWM4J/A",
        "jan": "4549995616620",
        "official_price": 244800,
    },
    {
        "category": "iPad",
        "model_name": "iPad Pro 11インチ (M5 Wi-Fi)",
        "capacity": "512GB",
        "color": "シルバー",
        "part_number": "MDWN4J/A",
        "jan": "4549995616637",
        "official_price": 244800,
    },
    # ==================== iPad mini (A17 Pro Wi-Fi) ====================
    {
        "category": "iPad",
        "model_name": "iPad mini (A17 Pro Wi-Fi)",
        "capacity": "128GB",
        "color": "スペースグレイ",
        "part_number": "MXN63J/A",
        "jan": "4549995526486",
        "official_price": 99800,
    },
    {
        "category": "iPad",
        "model_name": "iPad mini (A17 Pro Wi-Fi)",
        "capacity": "128GB",
        "color": "ブルー",
        "part_number": "MXN73J/A",
        "jan": "4549995526493",
        "official_price": 99800,
    },
    {
        "category": "iPad",
        "model_name": "iPad mini (A17 Pro Wi-Fi)",
        "capacity": "128GB",
        "color": "スターライト",
        "part_number": "MXN83J/A",
        "jan": "4549995526509",
        "official_price": 99800,
    },
    {
        "category": "iPad",
        "model_name": "iPad mini (A17 Pro Wi-Fi)",
        "capacity": "128GB",
        "color": "パープル",
        "part_number": "MXN93J/A",
        "jan": "4549995526516",
        "official_price": 99800,
    },
    {
        "category": "iPad",
        "model_name": "iPad mini (A17 Pro Wi-Fi)",
        "capacity": "256GB",
        "color": "スペースグレイ",
        "part_number": "MXNA3J/A",
        "jan": "4549995526523",
        "official_price": 116800,
    },
    {
        "category": "iPad",
        "model_name": "iPad mini (A17 Pro Wi-Fi)",
        "capacity": "256GB",
        "color": "ブルー",
        "part_number": "MXNC3J/A",
        "jan": "4549995526530",
        "official_price": 116800,
    },
    {
        "category": "iPad",
        "model_name": "iPad mini (A17 Pro Wi-Fi)",
        "capacity": "256GB",
        "color": "スターライト",
        "part_number": "MXND3J/A",
        "jan": "4549995526547",
        "official_price": 116800,
    },
    {
        "category": "iPad",
        "model_name": "iPad mini (A17 Pro Wi-Fi)",
        "capacity": "256GB",
        "color": "パープル",
        "part_number": "MXNE3J/A",
        "jan": "4549995526554",
        "official_price": 116800,
    },
    # ==================== AirPods シリーズ ====================
    {
        "category": "AirPods",
        "model_name": "AirPods Pro (第3世代)",
        "capacity": "USB-C",
        "color": "ホワイト",
        "part_number": "MFHP4J/A",
        "jan": "4549995635232",
        "official_price": 42800,
    },
    {
        "category": "AirPods",
        "model_name": "AirPods 5 (ワイヤレス充電ケース付)",
        "capacity": "ワイヤレス充電",
        "color": "ホワイト",
        "part_number": "MKFT4J/A",
        "jan": "4549995725025",
        "official_price": 27800,
    },
    {
        "category": "AirPods",
        "model_name": "AirPods 5",
        "capacity": "標準ケース",
        "color": "ホワイト",
        "part_number": "MKFW4J/A",
        "jan": "4549995725049",
        "official_price": 23800,
    },
    {
        "category": "AirPods",
        "model_name": "AirPods Max 2 (USB-C)",
        "capacity": "標準",
        "color": "ミッドナイト",
        "part_number": "MHWK4ZA/A",
        "jan": "4549995687149",
        "official_price": 89800,
    },
    {
        "category": "AirPods",
        "model_name": "AirPods Max 2 (USB-C)",
        "capacity": "標準",
        "color": "スターライト",
        "part_number": "MHWL4ZA/A",
        "jan": "4549995687156",
        "official_price": 89800,
    },
    # ==================== Apple Watch シリーズ ====================
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Series 12 (GPS)",
        "capacity": "42mm",
        "color": "ダークブロンズ (S/M)",
        "part_number": "MJEF4X/A",
        "jan": "4549995737097",
        "official_price": 71800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Series 12 (GPS)",
        "capacity": "42mm",
        "color": "ライトゴールド (S/M)",
        "part_number": "MJED4X/A",
        "jan": "4549995737073",
        "official_price": 71800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Series 12 (GPS)",
        "capacity": "42mm",
        "color": "ブラック (S/M)",
        "part_number": "MJEA4X/A",
        "jan": "4549995737059",
        "official_price": 71800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Series 12 (GPS)",
        "capacity": "42mm",
        "color": "スペースグレイ (S/M)",
        "part_number": "MJE74X/A",
        "jan": "4549995737035",
        "official_price": 71800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Series 12 (GPS)",
        "capacity": "46mm",
        "color": "ダークブロンズ (S/M)",
        "part_number": "MJEQ4X/A",
        "jan": "4549995737172",
        "official_price": 80800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Series 12 (GPS)",
        "capacity": "46mm",
        "color": "ライトゴールド (S/M)",
        "part_number": "MJEP4X/A",
        "jan": "4549995737165",
        "official_price": 80800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Series 12 (GPS)",
        "capacity": "46mm",
        "color": "ブラック (S/M)",
        "part_number": "MJEK4X/A",
        "jan": "4549995737134",
        "official_price": 80800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Series 12 (GPS)",
        "capacity": "46mm",
        "color": "スペースグレイ (S/M)",
        "part_number": "MJEH4X/A",
        "jan": "4549995737110",
        "official_price": 80800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Ultra 4 (GPS+Cell)",
        "capacity": "49mm",
        "color": "ブラックチタニウム",
        "part_number": "MJAY4X/A",
        "jan": "4549995738032",
        "official_price": 142800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Ultra 4 (GPS+Cell)",
        "capacity": "49mm",
        "color": "ブラック (トレイル S/M)",
        "part_number": "MJC34X/A",
        "jan": "4549995738070",
        "official_price": 142800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch Ultra 4 (GPS+Cell)",
        "capacity": "49mm",
        "color": "ナチュラル (トレイル S/M)",
        "part_number": "MJAJ4X/A",
        "jan": "4549995737981",
        "official_price": 142800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch SE 3 (GPS)",
        "capacity": "40mm",
        "color": "スターライト (S/M)",
        "part_number": "MEH34J/A",
        "jan": "4549995615388",
        "official_price": 41800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch SE 3 (GPS)",
        "capacity": "40mm",
        "color": "ミッドナイト (M/L)",
        "part_number": "MEHC4J/A",
        "jan": "4549995615425",
        "official_price": 41800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch SE 3 (GPS)",
        "capacity": "40mm",
        "color": "スターライト/サンド (S/M)",
        "part_number": "MJKR4J/A",
        "jan": "4549995707823",
        "official_price": 41800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch SE 3 (GPS)",
        "capacity": "44mm",
        "color": "スターライト (S/M)",
        "part_number": "MEHG4J/A",
        "jan": "4549995615449",
        "official_price": 46800,
    },
    {
        "category": "Apple Watch",
        "model_name": "Apple Watch SE 3 (GPS)",
        "capacity": "44mm",
        "color": "ミッドナイト (S/M)",
        "part_number": "MEHN4J/A",
        "jan": "4549995615470",
        "official_price": 46800,
    },
    # ==================== Apple Pencil / HomePod / AirTag ====================
    {
        "category": "Accessory",
        "model_name": "Apple Pencil Pro",
        "capacity": "標準",
        "color": "ホワイト",
        "part_number": "MX2D3ZA/A",
        "jan": "4549995504460",
        "official_price": 23800,
    },
    {
        "category": "Accessory",
        "model_name": "Apple Pencil (USB-C)",
        "capacity": "USB-C",
        "color": "ホワイト",
        "part_number": "MUWA3ZA/A",
        "jan": "4549995454017",
        "official_price": 14800,
    },
    {
        "category": "Accessory",
        "model_name": "HomePod (第2世代)",
        "capacity": "標準",
        "color": "ミッドナイト",
        "part_number": "MDEW4J/A",
        "jan": "4549995566161",
        "official_price": 59800,
    },
    {
        "category": "Accessory",
        "model_name": "HomePod (第2世代)",
        "capacity": "標準",
        "color": "ホワイト",
        "part_number": "MDEY4J/A",
        "jan": "4549995566178",
        "official_price": 59800,
    },
]


class AppleOtherScraper:
    """
    iPhone以外のApple Store製品（Mac/iPad/Watch/AirPods/Pencil/HomePod）の買取価格を
    13桁JANコードおよびApple公式型番（PartNumber）完全一致で複数店舗から収集・比較
    """

    def __init__(self):
        self.ic_keywords = [
            "Mac+mini",
            "MacBook+Air",
            "MacBook+Pro",
            "iMac",
            "iPad",
            "iPad+mini",
            "AirPods",
            "Apple+Watch",
            "Apple+Pencil",
            "HomePod",
        ]
        # 8=MacBook, 9=Macデスクトップ, 5/71/72/73=iPad系, 74/4/33=AirPods系, 256/259/223=Watch系, 25=Pencil, 146=HomePod
        self.rudeya_cats = [8, 9, 5, 71, 72, 73, 74, 4, 33, 256, 259, 223, 25, 146]
        self.apple_official_metrics_urls = [
            "https://www.apple.com/jp/shop/buy-ipad/ipad-pro",
            "https://www.apple.com/jp/shop/buy-ipad/ipad-air",
            "https://www.apple.com/jp/shop/buy-ipad/ipad",
            "https://www.apple.com/jp/shop/buy-ipad/ipad-mini",
            "https://www.apple.com/jp/shop/buy-airpods/airpods-5",
            "https://www.apple.com/jp/shop/buy-airpods/airpods-max-2",
            "https://www.apple.com/jp/shop/product/MX2D3ZA/A",
            "https://www.apple.com/jp/shop/product/MUWA3ZA/A",
            "https://www.apple.com/jp/shop/buy-homepod/homepod",
        ]

    def fetch_json(self, url: str) -> dict:
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", "ignore"))

    def fetch_html(self, url: str) -> str:
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", "ignore")

    def fetch_live_apple_official_prices(self) -> Dict[str, int]:
        """Apple公式サイト (apple.com/jp) の metrics JSON から型番 (PartNumber) 別の最新税込定価を取得"""
        live_prices: Dict[str, int] = {}
        for url in self.apple_official_metrics_urls:
            try:
                html = self.fetch_html(url)
                m = re.search(r'<script[^>]*id="metrics"[^>]*>(.*?)</script>', html, re.S)
                if not m:
                    continue
                data = json.loads(m.group(1))
                for p in data.get("data", {}).get("products", []):
                    pn = (p.get("partNumber") or "").strip().upper()
                    fp = p.get("price", {}).get("fullPrice")
                    if pn and fp is not None:
                        live_prices[pn] = int(round(float(fp)))
            except Exception as e:
                logger.debug("[AppleOtherScraper] Apple公式価格確認スキップ (%s): %s", url, e)
        return live_prices

    def scrape_and_compare(self) -> List[Dict[str, Any]]:
        """
        買取1丁目 API と 買取ルデヤから JANコード・型番 (PartNumber) 付きで買取価格を取得し、
        Apple公式定価と 1対1 完全一致で比較した辞書リストを返す
        """
        # (jan -> {store -> price}), (part_number -> {store -> price}), (part_number -> jan)
        prices_by_jan: Dict[str, Dict[str, int]] = {}
        prices_by_part: Dict[str, Dict[str, int]] = {}
        discovered_jan_by_part: Dict[str, str] = {}

        def record_store_price(store: str, price: int, jan: str = "", part: str = "") -> None:
            if price <= 0:
                return
            clean_jan = jan.strip()
            clean_part = part.strip().upper()
            if clean_jan and clean_part:
                discovered_jan_by_part[clean_part] = clean_jan
            if clean_jan:
                cur = prices_by_jan.setdefault(clean_jan, {}).get(store, 0)
                if price > cur:
                    prices_by_jan[clean_jan][store] = price
            if clean_part:
                cur = prices_by_part.setdefault(clean_part, {}).get(store, 0)
                if price > cur:
                    prices_by_part[clean_part][store] = price

        # 1. 買取1丁目 API (単一商品の jan + 複数カラー商品 keitaiColorOptions の個別 jan / 型番 / varPrice を完全展開)
        seen_goods_ids = set()
        for kw in self.ic_keywords:
            url = f"https://www.1-chome.com/api/index/findByKeyword?keyword={kw}&page=1&size=50"
            try:
                data = self.fetch_json(url)
                items = data.get("data", {}).get("content", [])
                for x in items:
                    gid = x.get("goodsId")
                    if gid in seen_goods_ids:
                        continue
                    seen_goods_ids.add(gid)

                    title = (x.get("title") or "").strip()
                    details = x.get("goodsKbDetails") or []
                    unopened = next(
                        (
                            d
                            for d in details
                            if any(
                                k in (d.get("kbDetailName") or "")
                                for k in ["未開封", "新品", "保証未開始"]
                            )
                        ),
                        details[0] if details else {},
                    )
                    base_price = int(unopened.get("kbDetailPrice") or 0)
                    if base_price <= 0:
                        continue
                    detail_id = unopened.get("allGoodsKbDetailId")

                    color_opts = x.get("keitaiColorOptions") or []
                    if color_opts:
                        for opt in color_opts:
                            opt_color = (opt.get("color") or "").strip()
                            opt_jan = (opt.get("jan") or "").strip()
                            var_price = 0
                            for rel in opt.get("keitaiKbDetailColorRels") or []:
                                if rel.get("keitaiKbDetailId") == detail_id:
                                    var_price = int(rel.get("varPrice") or 0)
                                    break
                            final_price = base_price + var_price
                            part_m = PART_NUMBER_REGEX.search(f"{opt_color} {title}".upper())
                            opt_part = part_m.group(1) if part_m else ""
                            record_store_price("買取1丁目", final_price, jan=opt_jan, part=opt_part)
                    else:
                        top_jan = (x.get("jan") or "").strip()
                        if not top_jan:
                            jm = JAN_REGEX.search(title)
                            if jm:
                                top_jan = jm.group(1)
                        part_m = PART_NUMBER_REGEX.search(title.upper())
                        top_part = part_m.group(1) if part_m else ""
                        record_store_price("買取1丁目", base_price, jan=top_jan, part=top_part)
            except Exception as e:
                logger.warning("[AppleOtherScraper] 買取1丁目 (%s) エラー: %s", kw, e)

        # 2. 買取ルデヤ (各商品カード内の JAN: 454999... と 型番 [MxxxxJ/A] を厳密抽出)
        for cid in self.rudeya_cats:
            url = f"https://kaitori-rudeya.com/category/detail/{cid}"
            try:
                html = self.fetch_html(url)
                soup = BeautifulSoup(html, "html.parser")
                for card in soup.select("article.pgrid-card"):
                    name_el = card.select_one("a.product-card-name-link")
                    price_el = card.select_one(".product-card-price-value")
                    if not name_el or not price_el:
                        continue
                    title = name_el.get_text(strip=True)
                    p_str = re.sub(r"[^\d]", "", price_el.get_text(strip=True))
                    if not p_str:
                        continue
                    price = int(p_str)
                    if price <= 0:
                        continue

                    card_text = " ".join(card.stripped_strings)
                    jan_m = JAN_REGEX.search(card_text)
                    card_jan = jan_m.group(1) if jan_m else ""
                    part_m = PART_NUMBER_REGEX.search(f"{title} {card_text}".upper())
                    card_part = part_m.group(1) if part_m else ""
                    record_store_price("買取ルデヤ", price, jan=card_jan, part=card_part)
            except Exception as e:
                logger.warning("[AppleOtherScraper] 買取ルデヤ (cat=%s) エラー: %s", cid, e)

        # 3. Apple公式サイトからリアルタイム定価の更新を確認
        live_official_prices = self.fetch_live_apple_official_prices()

        # 4. JANコード および 型番 (PartNumber) の完全一致で突合
        results: List[Dict[str, Any]] = []
        for cat_item in APPLE_OTHER_OFFICIAL_CATALOG:
            part = cat_item["part_number"].strip().upper()
            jan = (cat_item.get("jan") or discovered_jan_by_part.get(part, "")).strip()

            store_prices: Dict[str, int] = {}
            if jan and jan in prices_by_jan:
                for s_name, p_val in prices_by_jan[jan].items():
                    store_prices[s_name] = max(store_prices.get(s_name, 0), p_val)
            if part and part in prices_by_part:
                for s_name, p_val in prices_by_part[part].items():
                    store_prices[s_name] = max(store_prices.get(s_name, 0), p_val)

            if not store_prices:
                continue

            best_store, best_price = max(store_prices.items(), key=lambda x: x[1])
            lowest_store, lowest_price = min(store_prices.items(), key=lambda x: x[1])
            official_price = live_official_prices.get(part, cat_item["official_price"])
            profit_jpy = best_price - official_price
            profit_rate = round((best_price / official_price) * 100, 1)

            results.append({
                "id": f"other_{part}",
                "category": cat_item["category"],
                "model_name": cat_item["model_name"],
                "capacity": cat_item["capacity"],
                "color": cat_item["color"],
                "part_number": part,
                "jan": jan,
                "best_store": best_store,
                "best_price": best_price,
                "lowest_store": lowest_store,
                "lowest_price": lowest_price,
                "price_diff": best_price - lowest_price,
                "official_price": official_price,
                "profit_jpy": profit_jpy,
                "profit_rate": profit_rate,
                "store_prices": store_prices,
            })

        results.sort(key=lambda x: (-x["profit_jpy"], -x["profit_rate"]))
        return results
