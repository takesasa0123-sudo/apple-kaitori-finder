"""スクレイパーパッケージ"""
from .base import BaseScraper
from .apple import AppleOfficialScraper
from .apple_other import AppleOtherScraper
from .rudeya import RudeyaScraper
from .morimori import MorimoriScraper
from .saikoune import SaikouneScraper
from .kaitori1chome import Kaitori1ChomeScraper

__all__ = [
    "BaseScraper",
    "AppleOfficialScraper",
    "AppleOtherScraper",
    "RudeyaScraper",
    "MorimoriScraper",
    "SaikouneScraper",
    "Kaitori1ChomeScraper",
]


