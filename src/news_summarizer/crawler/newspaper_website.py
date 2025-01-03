import logging
import re
import time
from datetime import datetime
from typing import List

from bs4 import BeautifulSoup
from bs4.element import Tag
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from news_summarizer.crawler.base import BaseSeleniumCrawler
from news_summarizer.domain.documents import Link

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def extract_date_from_url(url: str) -> str:
    # Regular expression to match the date in the format YYYY/MM/DD

    try:
        pattern0 = r"(\d{4}/\d{2}/\d{2})"
        pattern1 = r"(\d{2}\d{2}\d{4})"

        match = re.search(pattern0, url)

        if match:
            date_str = match.group(0)
            # Convert the date string to a datetime object
            return datetime.strptime(date_str, "%Y/%m/%d")

        match = re.search(pattern1, url)

        if match:
            date_str = match.group(0)
            # Convert the date string to a datetime object
            return datetime.strptime(date_str, "%d%m%Y")
    except Exception:
        logger.error("Error trying to parse date for %s", url)
    return None


def extract_title(url: str) -> str:
    last_segment = url.rsplit("/", 1)[-1]

    # Remove HTML-like extensions
    last_segment = re.sub(r"\.html?|\.htm|\.ghtml$", "", last_segment)

    # Replace separators (-, _, etc.) with spaces and convert to lowercase
    title = re.sub(r"[-_]", " ", last_segment)

    # Optional: Replace multiple spaces with a single space
    title = re.sub(r"\s+", " ", title).strip()

    return title


def extract_links(elements: List[Tag]):
    data = []
    for element in elements:
        url = element.get("href")

        title = element.get_text(strip=True)
        if len(title) < 5:
            title = extract_title(url)

        published_at = extract_date_from_url(url)

        link = {
            "title": title,
            "url": url,
            "published_at": published_at,
        }

        data.append(link)

    return data


def clean_html(soup):
    # Remove style elements
    for style in soup(["style"]):
        style.decompose()

    # Remove script elements
    for script in soup(["script"]):
        script.decompose()
    return soup


class G1Crawler(BaseSeleniumCrawler):
    model = Link

    def __init__(self, scroll_limit: int = 10) -> None:
        super().__init__(scroll_limit=scroll_limit)

    def scroll_page(self) -> None:
        load_mode = 0
        page_number = 0
        last_page_number = 0

        while True:
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                # time.sleep(np.random.randint(2, 5))
                WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.execute_script(
                        "return window.pageYOffset + window.innerHeight >= document.body.scrollHeight"
                    )
                )

                logger.debug("Waiting the element to be clickable.")
                load_more_link = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "div.load-more a"))
                )

                url = load_more_link.get_dom_attribute("href")
                page_number = self._extract_page_number(url)

                if page_number > last_page_number:
                    logger.debug("Page number is bigger than last page number, we are seing another page.")
                    load_mode += 1
                    last_page_number = page_number
                    if load_mode >= 6:
                        break
                logger.debug("Click on element.")
                load_more_link.click()
            except TimeoutException as te:
                logger.error("Error trying to scroll page: %s", te)
                continue

    def _extract_page_number(self, url):
        match = re.search(r"pagina-(\d+)", url)
        if match:
            return int(match.group(1))
        return None

    def accept_cookies(self):
        button = WebDriverWait(self.driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.cookie-banner-lgpd_accept-button"))
        )
        button.click()

    def search(self, link: str, **kwargs) -> None:
        try:
            self.driver.get(link)
            time.sleep(5)
            self.accept_cookies()
            time.sleep(2)
            self.scroll_page()
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            soup = clean_html(soup)
            elements = soup.find_all("a", href=True)
            hyperlinks = extract_links(elements)
            self.driver.close()

            hyperlink_list = []
            for hyperlink in hyperlinks:
                try:
                    hyperlink_list.append(
                        Link(
                            title=hyperlink["title"],
                            url=hyperlink["url"],
                            source=link,
                            published_at=hyperlink["published_at"],
                        )
                    )
                except ValueError as ve:
                    logger.error(
                        "Failed to append hyperlink with title '%s' and URL '%s'. Validation error: %s",
                        hyperlink.get("title", "N/A"),
                        hyperlink.get("url", "N/A"),
                        ve,
                    )
                    continue

            logger.info("Found %s hyperlinks on '%s'", len(hyperlink_list), link)
            self.model.bulk_insert(hyperlink_list)
        except Exception as e:
            logger.error("Error while crawling domain %s: %s", link, e)
            self.driver.close()


class BandCrawler(BaseSeleniumCrawler):
    model = Link

    def __init__(self, scroll_limit: int = 10) -> None:
        super().__init__(scroll_limit=scroll_limit)

    def scroll_page(self) -> None:
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        current_scroll = 0
        while True:
            try:
                logger.debug("Scrolling page until bottom.")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                # time.sleep(5)
                WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.execute_script(
                        "return window.pageYOffset + window.innerHeight >= document.body.scrollHeight"
                    )
                )

                logger.debug("Update the page height.")
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height or (self.scroll_limit and current_scroll >= self.scroll_limit):
                    logger.debug("The page height is the same as the last or we've reached the scroll limit.")
                    break
                last_height = new_height
                current_scroll += 1
            except TimeoutException as te:
                logger.error("Error trying to scroll page: %s", te)
                continue

    def search(self, link: str, **kwargs) -> None:
        try:
            self.driver.get(link)
            time.sleep(5)
            self.scroll_page()
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            soup = clean_html(soup)
            elements = soup.find_all("a", href=True)
            hyperlinks = extract_links(elements)

            if len(hyperlinks) == 0:
                logger.error("No links found.")

            self.driver.close()

            hyperlink_list = []
            for hyperlink in hyperlinks:
                try:
                    hyperlink_list.append(
                        Link(
                            title=hyperlink["title"],
                            url=hyperlink["url"],
                            source=link,
                            published_at=hyperlink["published_at"],
                        )
                    )
                except ValueError as ve:
                    logger.error(
                        "Failed to append hyperlink with title '%s' and URL '%s'. Validation error: %s",
                        hyperlink.get("title", "N/A"),
                        hyperlink.get("url", "N/A"),
                        ve,
                    )
                    continue

            logger.info("Found %s hyperlinks on '%s'", len(hyperlink_list), link)
            self.model.bulk_insert(hyperlink_list)
        except Exception as e:
            logger.error("Error while crawling domain %s: %s", link, e)
            self.driver.close()


class R7Crawler(BaseSeleniumCrawler):
    model = Link

    def __init__(self, scroll_limit: int = 10) -> None:
        super().__init__(scroll_limit=scroll_limit)

    def scroll_page(self) -> None:
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        current_scroll = 0
        while True:
            try:
                logger.debug("Scrolling page until bottom.")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                # time.sleep(5)
                WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.execute_script(
                        "return window.pageYOffset + window.innerHeight >= document.body.scrollHeight"
                    )
                )

                logger.debug("Update the page height.")
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height or (self.scroll_limit and current_scroll >= self.scroll_limit):
                    logger.debug("The page height is the same as the last or we've reached the scroll limit.")
                    break
                last_height = new_height
                current_scroll += 1
            except TimeoutException as te:
                logger.debug("Error trying to scroll page: %s", te)
                continue

    def search(self, link: str, **kwargs) -> None:
        try:
            logger.info("Start searching hyperlinks for link: %s", link)
            self.driver.get(link)
            time.sleep(5)
            self.scroll_page()
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            soup = clean_html(soup)
            elements = soup.find_all("a", href=True)
            hyperlinks = extract_links(elements)

            if len(hyperlinks) == 0:
                logger.error("No links found.")

            self.driver.close()

            hyperlink_list = []

            for hyperlink in hyperlinks:
                try:
                    hyperlink_list.append(
                        Link(
                            title=hyperlink["title"],
                            url=hyperlink["url"],
                            source=link,
                            published_at=hyperlink["published_at"],
                        )
                    )
                except ValueError as ve:
                    logger.error(
                        "Failed to append hyperlink with title '%s' and URL '%s'. Validation error: %s",
                        hyperlink.get("title", "N/A"),
                        hyperlink.get("url", "N/A"),
                        ve,
                    )
                    continue

            logger.info("Found %s hyperlinks on '%s'", len(hyperlink_list), link)
            self.model.bulk_insert(hyperlink_list)
        except Exception as e:
            logger.error("Error while crawling domain %s: %s", link, e)
            self.driver.close()
