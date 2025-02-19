from abc import ABC, abstractmethod

from news_summarizer.domain.base import NoSQLBaseDocument
from news_summarizer.webdriver import ShutilBrowserLocator, WebDriverFactory


class BaseScraper(ABC):
    model: type[NoSQLBaseDocument]

    @abstractmethod
    def extract(self, link: str, **kwargs) -> None:
        raise NotImplementedError


class BaseSeleniumScraper(BaseScraper, ABC):
    def __init__(self) -> None:
        self.driver = WebDriverFactory(ShutilBrowserLocator()).get_webdriver()
        self.soup = None
