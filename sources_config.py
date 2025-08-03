#!/usr/bin/env python3
"""
Configuration des sources M3U pour le nettoyeur de playlist TV
"""

# Sources M3U officielles et communautaires
M3U_SOURCES = [
    # Sources officielles iptv-org
    "https://iptv-org.github.io/iptv/countries/fr.m3u",
    "https://iptv-org.github.io/iptv/countries/us.m3u",
    "https://iptv-org.github.io/iptv/countries/gb.m3u",
    "https://iptv-org.github.io/iptv/countries/de.m3u",
    "https://iptv-org.github.io/iptv/countries/es.m3u",
    "https://iptv-org.github.io/iptv/countries/it.m3u",
    # Sources communautaires
    "https://raw.githubusercontent.com/ipstreet312/freeiptv/refs/heads/master/all.m3u",
    # Sources spécialisées (à décommenter si nécessaire)
    # "https://iptv-org.github.io/iptv/categories/news.m3u",
    # "https://iptv-org.github.io/iptv/categories/sports.m3u",
    # "https://iptv-org.github.io/iptv/categories/movies.m3u",
    # "https://iptv-org.github.io/iptv/categories/kids.m3u",
]

# Sources par région/langue
FRENCH_SOURCES = [
    "https://iptv-org.github.io/iptv/countries/fr.m3u",
    "https://raw.githubusercontent.com/ipstreet312/freeiptv/refs/heads/master/all.m3u",
    "https://raw.githubusercontent.com/Paradise-91/ParaTV/refs/heads/main/playlists/paratv/main/paratv-highest.m3us",
]

ENGLISH_SOURCES = [
    "https://iptv-org.github.io/iptv/countries/us.m3u",
    "https://iptv-org.github.io/iptv/countries/gb.m3u",
    "https://iptv-org.github.io/iptv/countries/ca.m3u",
    "https://iptv-org.github.io/iptv/countries/au.m3u",
]

EUROPEAN_SOURCES = [
    "https://iptv-org.github.io/iptv/countries/fr.m3u",
    "https://iptv-org.github.io/iptv/countries/de.m3u",
    "https://iptv-org.github.io/iptv/countries/es.m3u",
    "https://iptv-org.github.io/iptv/countries/it.m3u",
    "https://iptv-org.github.io/iptv/countries/nl.m3u",
    "https://iptv-org.github.io/iptv/countries/be.m3u",
    "https://iptv-org.github.io/iptv/countries/ch.m3u",
]

# Sources par catégorie
NEWS_SOURCES = [
    "https://iptv-org.github.io/iptv/categories/news.m3u",
]

SPORTS_SOURCES = [
    "https://iptv-org.github.io/iptv/categories/sports.m3u",
]

MOVIES_SOURCES = [
    "https://iptv-org.github.io/iptv/categories/movies.m3u",
]

KIDS_SOURCES = [
    "https://iptv-org.github.io/iptv/categories/kids.m3u",
]


def get_sources_by_category(category):
    """Retourne les sources selon la catégorie demandée."""
    categories = {
        "all": M3U_SOURCES,
        "french": FRENCH_SOURCES,
        "english": ENGLISH_SOURCES,
        "european": EUROPEAN_SOURCES,
        "news": NEWS_SOURCES,
        "sports": SPORTS_SOURCES,
        "movies": MOVIES_SOURCES,
        "kids": KIDS_SOURCES,
    }
    return categories.get(category.lower(), M3U_SOURCES)


def list_available_categories():
    """Liste toutes les catégories disponibles."""
    return ["all", "french", "english", "european", "news", "sports", "movies", "kids"]


if __name__ == "__main__":
    print("📋 Sources M3U disponibles:")
    print("=" * 40)

    categories = list_available_categories()
    for category in categories:
        sources = get_sources_by_category(category)
        print(f"\n🎯 {category.upper()}:")
        for i, source in enumerate(sources, 1):
            print(f"  {i}. {source}")

    print(f"\n💡 Utilisation:")
    print(f"  python cleaner_multi_source.py --sources {' '.join(FRENCH_SOURCES)}")
    print(f"  python cleaner_multi_source.py --sources {' '.join(ENGLISH_SOURCES)}")
