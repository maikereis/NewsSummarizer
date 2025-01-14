import logging
from urllib.parse import urlparse

from .base import BaseCrawler
from .newspaper_website import BBCBrasilCrawler, BandCrawler, CNNBrasilCrawler, G1Crawler, R7Crawler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CrawlerRegistry:
    def __init__(self):
        self._crawlers = {}

    def register(self, name, crawler: BaseCrawler):
        if name in self._crawlers:
            raise ValueError("Crawler '%s' is already registered.", name)

        logger.debug("Registering %s crawler", name)
        self._crawlers[name] = crawler

    def get(self, name):
        parsed_domain = urlparse(name)
        name = self._extract_netloc(parsed_domain)

        if name not in self._crawlers:
            raise KeyError("Component '%s' not found.", name)
        return self._crawlers[name]()

    def _extract_netloc(self, domain):
        return f"{domain.scheme}://{domain.netloc}/"

    def list_crawlers(self):
        return list(self._crawlers.keys())


crawler_registry = CrawlerRegistry()

crawler_registry.register("https://g1.globo.com/", G1Crawler)
crawler_registry.register("https://bandnewstv.uol.com.br/", BandCrawler)
crawler_registry.register("https://noticias.r7.com/", R7Crawler)
crawler_registry.register("https://www.bbc.com/", BBCBrasilCrawler)
crawler_registry.register("https://www.cnnbrasil.com.br/", CNNBrasilCrawler)
