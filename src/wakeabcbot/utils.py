"""
Shared utility functions for Wake ABC Telegram Bot
Contains common functionality used across multiple modules
"""

import logging
import re
import time
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


_DEFAULT_CITIES = [
    "Raleigh",
    "Cary",
    "Apex",
    "Wake Forest",
    "Garner",
    "Holly Springs",
    "Morrisville",
    "Fuquay Varina",
    "Knightdale",
    "Wendell",
    "Zebulon",
    "Rolesville",
]


class WakeABCCityCache:
    """Singleton cache for Wake ABC city locations"""

    _instance = None
    _cache = None
    _timestamp = None
    _duration = 86400  # Cache for 24 hours

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_wake_cities(self) -> List[str]:
        """
        Fetch Wake ABC store locations dynamically and extract city names.
        Results are cached for 24 hours to avoid excessive API calls.
        """

        # Check if cache is still valid
        current_time = time.time()
        if (
            self._cache is not None
            and self._timestamp is not None
            and current_time - self._timestamp < self._duration
        ):
            return self._cache

        try:
            # Fetch store locations from Wake ABC API
            stores_url = "https://wakeabc.com/wp-admin/admin-ajax.php?action=store_search&lat=35.7795897&lng=-78.6381787&max_results=1000&search_radius=200"
            response = requests.get(stores_url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to fetch Wake ABC store locations: {e}")
            return _DEFAULT_CITIES

        stores_data = response.json()
        cities = set()

        for store in stores_data:
            city = store.get("city", "").strip()
            if city and city not in ["North Carolina", "NC", "United States"]:
                cities.add(city)

        # Convert to sorted list for consistent ordering
        wake_cities = sorted(list(cities))

        # Update cache
        self._cache = wake_cities
        self._timestamp = current_time

        logger.debug(f"Fetched {len(wake_cities)} Wake ABC cities: {wake_cities}")
        return wake_cities


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2"""
    if not text:
        return ""
    special_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


def extract_city_and_stock(location_str: str) -> Tuple[Optional[str], int, str]:
    """Extract city and stock quantity from location string"""
    try:
        # Parse and validate input
        address, quantity_str = _parse_location_string(location_str)
        if not address or not quantity_str:
            return None, 0, location_str

        # Extract city from address using multiple methods
        city = _extract_city_from_address(address)

        # Clean up the address for display
        clean_address = _clean_address_for_display(address, city)

        # Extract numeric stock quantity
        stock_num = _extract_stock_quantity(quantity_str)

        return city, stock_num, f"{clean_address} ({quantity_str})"
    except Exception as e:
        # Log the error for debugging but don't crash
        logger.debug(f"Error parsing location '{location_str}': {e}")
        return None, 0, location_str


def _parse_location_string(location_str: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse location string into address and quantity parts"""
    location_parts = location_str.split(" - ")
    if len(location_parts) != 2:
        return None, None
    return location_parts[0], location_parts[1]


def _extract_city_from_address(address: str) -> Optional[str]:
    """Extract city name from address using multiple methods"""
    # Method 1: Look for pattern like "Street.City, State"
    city = _extract_city_method_1(address)
    if city:
        return _clean_city_name(city)

    # Method 2: Look for pattern like "StreetCity, State" (no period)
    city = _extract_city_method_2(address)
    if city:
        return _clean_city_name(city)

    # Method 3: Fallback - just take everything before the comma
    if "," in address:
        city = address.split(",")[0].strip()
        return _clean_city_name(city)

    # Method 4: Ultimate fallback
    return _clean_city_name(address.strip())


def _extract_city_method_1(address: str) -> Optional[str]:
    """Extract city using pattern 'Street.City, State'"""
    if "." in address and "," in address:
        # Split by period and take the part after the last period
        after_period = address.split(".")[-1]
        if "," in after_period:
            return after_period.split(",")[0].strip()
    return None


def _extract_city_method_2(address: str) -> Optional[str]:
    """Extract city using pattern 'StreetCity, State' with city matching"""
    if "," not in address:
        return None

    # Use regex to find city name before ", STATE"
    match = re.search(r"([A-Za-z\s]+),\s*[A-Z]{2}", address)
    if not match:
        return None

    potential_city = match.group(1).strip()

    # Try to match against known Wake ABC cities
    city = _match_known_wake_cities(potential_city)
    if city:
        return city

    # If no known city found, try word-by-word parsing
    return _parse_city_from_words(potential_city)


def _match_known_wake_cities(potential_city: str) -> Optional[str]:
    """Match potential city against known Wake ABC cities"""
    city_cache = WakeABCCityCache()
    wake_cities = city_cache.get_wake_cities()

    # Check if any known city appears at the end of the potential_city string
    for known_city in wake_cities:
        if potential_city.endswith(known_city):
            return known_city
    return None


def _parse_city_from_words(potential_city: str) -> Optional[str]:
    """Parse city name from words by removing street elements"""
    street_suffixes = [
        "St",
        "Street",
        "Ave",
        "Avenue",
        "Rd",
        "Road",
        "Dr",
        "Drive",
        "Blvd",
        "Boulevard",
        "Ln",
        "Lane",
        "Ct",
        "Court",
        "Pl",
        "Place",
        "Cir",
        "Circle",
        "Way",
        "Pkwy",
        "Parkway",
    ]

    words = potential_city.split()
    if len(words) <= 1:
        return potential_city

    # Look for a word that could be a city name
    for i in range(len(words)):
        word = words[i]
        if (
            not word.isdigit()
            and word not in street_suffixes
            and not any(char.isdigit() for char in word)
            and len(word) > 2
        ):
            # Take this word and everything after it as the city
            return " ".join(words[i:])

    # If we couldn't parse it intelligently, just take the whole thing
    return potential_city


def _clean_city_name(city: str) -> Optional[str]:
    """Clean up the city name by removing punctuation"""
    if not city:
        return None

    city = city.strip()
    # Remove any trailing periods or other punctuation
    return city.rstrip(".,;:")


def _clean_address_for_display(address: str, city: Optional[str]) -> str:
    """Clean up the address for display by removing city and zip code"""
    if not city:
        return address

    clean_address = address

    # Remove everything from ".CityName, NC zipcode" onward
    if f".{city}, NC" in address:
        clean_address = address.split(f".{city}, NC")[0]
    # Handle case without period: "StreetCityName, NC zipcode"
    elif f"{city}, NC" in address:
        clean_address = address.split(f"{city}, NC")[0]
    # Handle case without comma: "Street.CityName"
    elif f".{city}" in address and address.endswith(city):
        clean_address = address.split(f".{city}")[0]
    # Handle case with no period or comma: "StreetCityName"
    elif address.endswith(city) and len(address) > len(city):
        potential_clean = address[: -len(city)]
        # Only clean if it ends with a space or punctuation (not a letter)
        if potential_clean and not potential_clean[-1].isalpha():
            clean_address = potential_clean.rstrip(".")
        else:
            # Find the last non-alphabetic character to split on
            for i in range(len(potential_clean) - 1, -1, -1):
                if not potential_clean[i].isalpha():
                    clean_address = potential_clean[: i + 1].rstrip(".")
                    break

    return clean_address


def _extract_stock_quantity(quantity_str: str) -> int:
    """Extract numeric stock quantity for sorting"""
    stock_num = 0
    quantity_lower = quantity_str.lower()
    if "in stock" in quantity_lower:
        # Extract number from strings like "224 in stock"
        numbers = re.findall(r"\d+", quantity_str)
        if numbers:
            stock_num = int(numbers[0])
    return stock_num
