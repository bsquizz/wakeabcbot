"""
Inventory scraper module for Wake ABC Telegram Bot
Handles web scraping and searching of the Wake ABC inventory website
"""

import logging
from dataclasses import dataclass
from typing import List

import requests
from bs4 import BeautifulSoup

from .config import Config
from .utils import WakeABCCityCache, escape_markdown, extract_city_and_stock

logger = logging.getLogger(__name__)


@dataclass
class InventoryItem:
    """Data class for inventory items"""

    name: str
    code: str = None
    size: str = None
    price: str = None
    availability: str = None
    locations: List[str] = None

    def __post_init__(self):
        if self.locations is None:
            self.locations = []


class WakeABCInventoryScraper:
    """
    A scraper for the Wake ABC Inventory website.
    It uses requests to perform POST requests and BeautifulSoup4 to parse HTML.
    """

    def __init__(self):
        """Initialize the scraper with a requests session"""
        self.session = requests.Session()
        self.search_url = Config.WAKE_ABC_SEARCH_URL
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        # Initialize city cache
        self.city_cache = WakeABCCityCache()

    def search_inventory(
        self, query: str, max_results: int = 10
    ) -> List[InventoryItem]:
        """
        Search the Wake ABC inventory for products

        Args:
            query: Search term (e.g., "bourbon", "whiskey")
            max_results: Maximum number of results to return

        Returns:
            List of InventoryItem objects
        """
        # Validate input
        if not self._validate_search_query(query):
            return []

        query = query.strip()
        logger.info(f"Searching inventory for: '{query}'")

        # Make HTTP request
        response = self._make_search_request(query)
        if not response:
            return []

        # Parse HTML response
        soup = self._parse_search_response(response)
        if not soup:
            return []

        # Extract products from HTML
        product_divs = self._extract_products_from_html(soup, query)
        if not product_divs:
            return []

        # Process each product
        items = []
        for product_div in product_divs[:max_results]:
            item = self._extract_product_info(product_div)
            if item:
                items.append(item)

        logger.info(f"Found {len(items)} items for query '{query}'")
        return items

    def _validate_search_query(self, query: str) -> bool:
        """Validate the search query"""
        if not query or not query.strip():
            logger.warning("Empty search query provided")
            return False
        return True

    def _make_search_request(self, query: str):
        """Make HTTP request to search endpoint"""
        search_url = "https://wakeabc.com/search-results"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        }
        data = {"productSearch": query}

        # Handle network requests with targeted exception handling
        try:
            response = requests.post(search_url, data=data, headers=headers, timeout=30)
            response.raise_for_status()

            # Debug: log response status and content length
            logger.debug(
                f"Response status: {response.status_code}, Content length: {len(response.text)}"
            )
            return response
        except requests.RequestException as e:
            logger.error(f"Network error while searching inventory: {e}")
            return None

    def _parse_search_response(self, response):
        """Parse HTML response and return BeautifulSoup object"""
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            return soup
        except Exception as e:
            logger.error(f"Error parsing HTML response: {e}")
            return None

    def _extract_products_from_html(self, soup, query: str):
        """Extract product divs from search results"""
        # Find the search results container
        results_div = soup.find("div", id="productSearchResults")
        if not results_div:
            logger.warning("Could not find productSearchResults div")
            # Try to find it with different selectors
            results_div = soup.find("div", {"id": "productSearchResults"})
            if not results_div:
                logger.warning(
                    "Still could not find productSearchResults div, checking page content"
                )
                if "productSearchResults" in soup.get_text():
                    logger.info(
                        "productSearchResults found in HTML but not parsed correctly"
                    )
                else:
                    logger.warning("productSearchResults not found in HTML at all")
                return None

        # Check for no results message
        no_results_text = results_div.get_text()
        if "Sorry, your search did not return any results" in no_results_text:
            logger.info(f"No results found for query '{query}'")
            return None

        # Find all product entries
        product_divs = results_div.find_all("div", class_="wake-product")
        if not product_divs:
            logger.warning("No product divs found in search results")
            return None

        return product_divs

    def _extract_product_info(self, product_div) -> InventoryItem:
        """Extract all information from a single product div"""
        # Extract basic product data
        name, code, price, size = self._extract_basic_product_data(product_div)

        # Extract location and availability data
        availability, locations = self._extract_product_locations(product_div)

        # Create inventory item
        return InventoryItem(
            name=name,
            code=code,
            size=size,
            price=price,
            availability=availability,
            locations=locations,
        )

    def _extract_basic_product_data(self, product_div) -> tuple:
        """Extract name, PLU code, price, and size from product div"""
        # Extract product name
        name_elem = product_div.find("h4")
        name = name_elem.get_text().strip() if name_elem else "Unknown Product"

        # Extract PLU code
        plu_elem = product_div.find("small")
        code = ""
        if plu_elem:
            plu_text = plu_elem.get_text()
            if "PLU:" in plu_text:
                code = plu_text.replace("PLU:", "").strip()

        # Extract price and size
        price_elem = product_div.find("span", class_="price")
        size_elem = product_div.find("span", class_="size")

        price = price_elem.get_text().strip() if price_elem else "Price N/A"
        size = size_elem.get_text().strip() if size_elem else "Size N/A"

        return name, code, price, size

    def _extract_product_locations(self, product_div) -> tuple:
        """Extract availability status and location list from product div"""
        locations = []
        availability = "Unknown"

        # Check for out of stock message
        out_of_stock = product_div.find("p", class_="out-of-stock")
        if out_of_stock:
            availability = "Out of Stock"
        else:
            # Find inventory locations
            inventory_div = product_div.find("div", class_="inventory-collapse")
            if inventory_div:
                location_items = inventory_div.find_all("li")
                for item in location_items:
                    address_span = item.find("span", class_="address")
                    quantity_span = item.find("span", class_="quantity")

                    if address_span and quantity_span:
                        # Handle <br /> tags in address
                        address_html = str(address_span)
                        address = (
                            BeautifulSoup(address_html, "html.parser")
                            .get_text()
                            .strip()
                        )
                        address = address.replace("\n", " ").replace("  ", " ")
                        quantity = quantity_span.get_text().strip()
                        locations.append(f"{address} - {quantity}")

                if locations:
                    availability = "In Stock"
                else:
                    availability = "Unknown Stock"

        return availability, locations

    def format_item_for_display(self, item: InventoryItem) -> str:
        """Format an inventory item for display in Telegram"""
        lines = []

        # Add basic item information
        lines.extend(self._format_basic_info(item))

        # Add availability status
        lines.extend(self._format_availability(item))

        # Add location information
        lines.extend(self._format_locations(item))

        return "\n".join(lines)

    def _format_basic_info(self, item: InventoryItem) -> List[str]:
        """Format basic item information (name, code, size, price)"""
        lines = []

        name = escape_markdown(item.name)
        lines.append(f"🍾 *{name}*")

        if item.code:
            code = escape_markdown(item.code)
            lines.append(f"📋 PLU: `{code}`")

        if item.size:
            size = escape_markdown(item.size)
            lines.append(f"📏 Size: {size}")

        if item.price:
            price = escape_markdown(item.price)
            lines.append(f"💰 Price: *{price}*")

        return lines

    def _format_availability(self, item: InventoryItem) -> List[str]:
        """Format availability status with appropriate emoji"""
        lines = []

        if item.availability:
            availability = escape_markdown(item.availability)
            if "in stock" in item.availability.lower():
                lines.append(f"✅ Status: {availability}")
            elif "out of stock" in item.availability.lower():
                lines.append(f"❌ Status: {availability}")
            else:
                lines.append(f"⚠️ Status: {availability}")

        return lines

    def _format_locations(self, item: InventoryItem) -> List[str]:
        """Format location information"""
        lines = []

        if not item.locations:
            return lines

        if len(item.locations) == 1:
            lines.extend(self._format_single_location(item.locations[0]))
        else:
            city_groups = self._group_locations_by_city(item.locations)
            if city_groups:
                lines.extend(self._format_multiple_locations(city_groups))

        return lines

    def _format_single_location(self, location: str) -> List[str]:
        """Format a single location"""
        lines = []

        city, stock_num, formatted_location = extract_city_and_stock(location)
        if city:
            formatted_location = escape_markdown(formatted_location)
            lines.append(f"📍 Location: {formatted_location}")
        else:
            location_escaped = escape_markdown(location)
            lines.append(f"📍 Location: {location_escaped}")

        return lines

    def _group_locations_by_city(self, locations: List[str]) -> dict:
        """Group locations by city and extract stock numbers"""
        city_groups = {}

        for location in locations:
            city, stock_num, formatted_location = extract_city_and_stock(location)
            if city:
                if city not in city_groups:
                    city_groups[city] = []
                city_groups[city].append((stock_num, formatted_location))
            else:
                # Handle locations that couldn't be parsed
                if "Other" not in city_groups:
                    city_groups["Other"] = []
                city_groups["Other"].append((0, location))

        return city_groups

    def _format_multiple_locations(self, city_groups: dict) -> List[str]:
        """Format multiple locations grouped by city with limits"""
        lines = ["📍 Locations:"]

        # Sort cities by total stock (sum of all stores in that city)
        city_totals = {
            city: sum(stock for stock, _ in stores)
            for city, stores in city_groups.items()
        }
        sorted_cities = sorted(
            city_groups.keys(), key=lambda c: city_totals[c], reverse=True
        )

        cities_shown = 0
        locations_shown = 0
        max_cities = 4  # Show up to 4 cities
        max_locations_per_city = 5  # Show up to 5 locations per city

        for city in sorted_cities:
            if cities_shown >= max_cities:
                break

            stores = city_groups[city]
            # Sort stores within city by stock quantity (highest first)
            stores.sort(key=lambda x: x[0], reverse=True)

            city_escaped = escape_markdown(city)
            lines.append(f"  *• {city_escaped}*")

            stores_shown_in_city = 0
            for stock_num, formatted_location in stores:
                if (
                    stores_shown_in_city >= max_locations_per_city
                    or locations_shown >= 15
                ):
                    remaining_in_city = len(stores) - stores_shown_in_city
                    if remaining_in_city > 0:
                        lines.append(
                            f"    _\\.\\.\\. and {remaining_in_city} more store{'s' if remaining_in_city != 1 else ''}_"
                        )
                    break

                location_escaped = escape_markdown(formatted_location)
                lines.append(f"    \\- {location_escaped}")
                stores_shown_in_city += 1
                locations_shown += 1

            cities_shown += 1

        # Show remaining cities count if any
        remaining_cities = len(sorted_cities) - cities_shown
        if remaining_cities > 0:
            total_remaining_locations = sum(
                len(city_groups[city]) for city in sorted_cities[cities_shown:]
            )
            lines.append(
                f"  _\\.\\.\\. and {remaining_cities} more cit{'ies' if remaining_cities != 1 else 'y'} \\({total_remaining_locations} locations\\)_"
            )

        return lines

    def check_keyword_availability(self, keyword: str) -> List[InventoryItem]:
        """Check if items matching a keyword are available"""
        try:
            items = self.search_inventory(keyword, max_results=20)
        except Exception as e:
            logger.error(f"Error checking keyword availability for '{keyword}': {e}")
            return []

        # Filter for available items only
        available_items = [
            item
            for item in items
            if item.availability
            and (
                "available" in item.availability.lower()
                or "in stock" in item.availability.lower()
            )
        ]

        return available_items
