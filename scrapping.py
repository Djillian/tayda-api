# built-in librairies
from typing import ClassVar, Optional, List
from dataclasses import dataclass
import re

# additional librairies
import requests
import bs4
from mouser import api

# project files
from pricing import Offer


@dataclass
class Product:
    sku: str
    name: str
    description: str
    offers_list: List[Offer]

    @property
    def formatted_name(self):
        return f"{self.sku} | {self.name}"

    def __str__(self):
        offers_str = '\n'.join(map(str, self.offers_list))
        return f"{self.formatted_name}\n{offers_str}"


@dataclass
class Provider:
    _current_url: Optional[str] = None
    _current_request: Optional[requests.models.Response] = None
    _current_page: Optional[bs4.BeautifulSoup] = None

    def init(self, url):
        self._current_url = url
        self._current_request = self.get_request()
        self._current_page = self.get_page()

    def get_request(self) -> requests.models.Response:
        return requests.get(self._current_url)

    def get_page(self) -> bs4.BeautifulSoup:
        return bs4.BeautifulSoup(self._current_request.content, 'html.parser')


@dataclass
class TaydaProductProvider(Provider):
    _URL: ClassVar[str] = "https://www.taydaelectronics.com/" \
                         "catalogsearch/result/"
    _NAME_TAG: ClassVar[str] = ".product-info-main  .page-title"
    _DESCRIPTION_TAG: ClassVar[str] = '.wrapper-details .value'
    _PRICE_TAG: ClassVar[str] = '.product-info-main .price-box .price'
    _PRICE_LIST_TAG: ClassVar[str] = ".product-info-main ul.prices-tier li.item"

    @property
    def name(self) -> str:
        return self._current_page.select_one(self._NAME_TAG).text.strip()

    @property
    def description(self) -> str:
        return self._current_page.select_one(self._DESCRIPTION_TAG).text.strip()

    @property
    def offers_list(self) -> List[Offer]:
        offers_list = list()

        # The initial price is considered as an offer for 1 item
        default_price_str = self._current_page.select_one(self._PRICE_TAG).text
        default_price = float(default_price_str.strip('$'))
        offers_list.append(
            Offer(quantity=1, price_usd_ht=default_price))

        # We go through all the proposed special offers and process them
        html_offers_list = self._current_page.select(self._PRICE_LIST_TAG)
        for html_offer in html_offers_list:
            # Isolates the first decimal number in the html
            # eg. the number of items
            quantity = re.findall(r'\d+', html_offer.text)[0]
            price_str = html_offer.select_one('.price').text
            price = float(price_str.strip('$'))

            offers_list.append(
                Offer(quantity=quantity, price_usd_ht=price))

        return offers_list

    def get(self, sku: str) -> Product:
        self.init(f'{self._URL}?q={sku}')
        return Product(sku=sku, name=self.name, description=self.description, offers_list=self.offers_list)


class MouserProductProvider:
    _provider: ClassVar[api.MouserPartSearchRequest] = None
    _response: ClassVar[object] = None

    _ARG_ACTION: ClassVar[str] = 'partnumber'

    _MANUFACTURER_TAG: ClassVar[str] = "Manufacturer"
    _MANUFACTURER_PART_NUMBER: ClassVar[str] = "ManufacturerPartNumber"

    _DESCRIPTION_TAG: ClassVar[str] = 'Description'

    _PRICE_TAG: ClassVar[str] = 'Price'
    _PRICE_LIST_TAG: ClassVar[str] = "PriceBreaks"
    _QUANTITY_TAG: ClassVar[str] = "Quantity"

    @property
    def name(self) -> str:
        return f'{self._response[self._MANUFACTURER_TAG]} {self._response[self._MANUFACTURER_PART_NUMBER]}'

    @property
    def description(self) -> str:
        return self._response[self._DESCRIPTION_TAG]

    @property
    def offers_list(self) -> List[Offer]:
        offers_list = list()
        for mouser_offer in self._response[self._PRICE_LIST_TAG]:
            quantity = mouser_offer[self._QUANTITY_TAG]
            price = float(mouser_offer[self._PRICE_TAG].strip(' ???').replace(',', '.'))
            offers_list.append(Offer(quantity=quantity, price_usd_ht=price))
        return offers_list

    def init(self, sku):
        self._provider = api.MouserPartSearchRequest(self._ARG_ACTION)
        if not self._provider.part_search(sku):
            return None
        self._response = self._provider.get_clean_response()

    def get(self, sku: str) -> Product:
        self.init(sku)
        return Product(sku=sku, name=self.name, description=self.description, offers_list=self.offers_list)
