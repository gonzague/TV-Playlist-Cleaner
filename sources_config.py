#!/usr/bin/env python3
"""
Configuration of M3U sources for TV playlist cleaner.

Provides curated lists of IPTV sources organized by region, language, and category.
All sources point to external public repositories.
"""

from typing import List, Dict

# Official and community M3U sources
M3U_SOURCES: List[str] = [
    # Official iptv-org sources
    "https://iptv-org.github.io/iptv/countries/fr.m3u",
    "https://iptv-org.github.io/iptv/countries/us.m3u",
    "https://iptv-org.github.io/iptv/countries/gb.m3u",
    "https://iptv-org.github.io/iptv/countries/de.m3u",
    "https://iptv-org.github.io/iptv/countries/es.m3u",
    "https://iptv-org.github.io/iptv/countries/it.m3u",
    # Community sources
    "https://raw.githubusercontent.com/ipstreet312/freeiptv/refs/heads/master/all.m3u",
]

# Sources by region/language
FRENCH_SOURCES: List[str] = [
    "https://iptv-org.github.io/iptv/countries/fr.m3u",
    "https://raw.githubusercontent.com/ipstreet312/freeiptv/refs/heads/master/all.m3u",
    # Fixed typo: .m3us -> .m3u
    "https://raw.githubusercontent.com/Paradise-91/ParaTV/refs/heads/main/playlists/paratv/main/paratv-highest.m3u",
]

ENGLISH_SOURCES: List[str] = [
    "https://iptv-org.github.io/iptv/countries/us.m3u",
    "https://iptv-org.github.io/iptv/countries/gb.m3u",
    "https://iptv-org.github.io/iptv/countries/ca.m3u",
    "https://iptv-org.github.io/iptv/countries/au.m3u",
]

EUROPEAN_SOURCES: List[str] = [
    "https://iptv-org.github.io/iptv/countries/fr.m3u",
    "https://iptv-org.github.io/iptv/countries/de.m3u",
    "https://iptv-org.github.io/iptv/countries/es.m3u",
    "https://iptv-org.github.io/iptv/countries/it.m3u",
    "https://iptv-org.github.io/iptv/countries/nl.m3u",
    "https://iptv-org.github.io/iptv/countries/be.m3u",
    "https://iptv-org.github.io/iptv/countries/ch.m3u",
]

# Sources by category
NEWS_SOURCES: List[str] = [
    "https://iptv-org.github.io/iptv/categories/news.m3u",
]

SPORTS_SOURCES: List[str] = [
    "https://iptv-org.github.io/iptv/categories/sports.m3u",
]

MOVIES_SOURCES: List[str] = [
    "https://iptv-org.github.io/iptv/categories/movies.m3u",
]

KIDS_SOURCES: List[str] = [
    "https://iptv-org.github.io/iptv/categories/kids.m3u",
]

# Category mapping
CATEGORY_MAP: Dict[str, List[str]] = {
    "all": M3U_SOURCES,
    "french": FRENCH_SOURCES,
    "english": ENGLISH_SOURCES,
    "european": EUROPEAN_SOURCES,
    "news": NEWS_SOURCES,
    "sports": SPORTS_SOURCES,
    "movies": MOVIES_SOURCES,
    "kids": KIDS_SOURCES,
}


def get_sources_by_category(category: str) -> List[str]:
    """
    Return sources for the requested category.

    Args:
        category: Category name (case-insensitive)

    Returns:
        List of M3U source URLs for the category

    Example:
        >>> sources = get_sources_by_category("french")
        >>> len(sources) >= 2
        True
    """
    return CATEGORY_MAP.get(category.lower(), M3U_SOURCES)


def list_available_categories() -> List[str]:
    """
    List all available categories.

    Returns:
        List of category names

    Example:
        >>> categories = list_available_categories()
        >>> "french" in categories
        True
        >>> "english" in categories
        True
    """
    return list(CATEGORY_MAP.keys())


def get_category_info(category: str) -> Dict[str, any]:
    """
    Get detailed information about a category.

    Args:
        category: Category name

    Returns:
        Dictionary with category information (name, sources count, URLs)
    """
    sources = get_sources_by_category(category)
    return {
        "name": category,
        "count": len(sources),
        "sources": sources
    }


def validate_sources() -> Dict[str, bool]:
    """
    Validate all source URLs for basic correctness.

    Returns:
        Dictionary mapping URLs to validation status

    Note:
        This only checks URL format, not availability.
    """
    from playlist_utils import validate_url

    validation_results = {}
    all_sources = set()

    # Collect all unique sources
    for sources in CATEGORY_MAP.values():
        all_sources.update(sources)

    # Validate each source
    for source in all_sources:
        validation_results[source] = validate_url(source)

    return validation_results


def main() -> None:
    """Display all available sources organized by category."""
    import logging

    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)

    logger.info("📋 Sources M3U disponibles:")
    logger.info("=" * 40)

    categories = list_available_categories()
    for category in categories:
        sources = get_sources_by_category(category)
        logger.info(f"\n🎯 {category.upper()} ({len(sources)} sources):")
        for i, source in enumerate(sources, 1):
            # Truncate long URLs for display
            display_url = source if len(source) <= 80 else source[:77] + "..."
            logger.info(f"  {i}. {display_url}")

    logger.info(f"\n💡 Utilisation:")
    logger.info(f"  python cleaner_config.py french")
    logger.info(f"  python cleaner_config.py english --workers 20")
    logger.info(f"  python cleaner_config.py all --output complete.m3u")

    logger.info(f"\n🔍 Validation des sources:")
    validation = validate_sources()
    valid_count = sum(1 for v in validation.values() if v)
    total_count = len(validation)
    logger.info(f"  ✅ {valid_count}/{total_count} sources valides")

    if valid_count < total_count:
        logger.warning(f"\n⚠️  Sources invalides:")
        for url, is_valid in validation.items():
            if not is_valid:
                logger.warning(f"  ✗ {url}")


if __name__ == "__main__":
    main()
