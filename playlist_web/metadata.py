"""Deterministic channel metadata for the local playlist browser."""

import re
from functools import lru_cache

from babel import Locale
from babel.core import get_global

from .media import CachedCatalog

CATEGORY_NAMES = {
    "auto": "Automobile",
    "animation": "Animation",
    "business": "Économie",
    "classic": "Classiques",
    "comedy": "Comédie",
    "cooking": "Cuisine",
    "culture": "Culture",
    "documentary": "Documentaires",
    "education": "Éducation",
    "entertainment": "Divertissement",
    "family": "Famille",
    "general": "Généraliste",
    "interactive": "Interactif",
    "kids": "Jeunesse",
    "legislative": "Parlement",
    "lifestyle": "Art de vivre",
    "movies": "Cinéma",
    "music": "Musique",
    "news": "Information",
    "outdoor": "Plein air",
    "public": "Service public",
    "relax": "Détente",
    "religious": "Religion",
    "series": "Séries",
    "science": "Sciences",
    "shop": "Téléachat",
    "sports": "Sport",
    "travel": "Voyages",
    "weather": "Météo",
    "xxx": "Adulte",
}
CATEGORY_ALIASES = {label.casefold(): code for code, label in CATEGORY_NAMES.items()}
CATEGORY_ALIASES.update({code: code for code in CATEGORY_NAMES})
CATEGORY_ALIASES.update(
    {"infos": "news", "actualités": "news", "documentaire": "documentary"}
)

# Match complete attributes, stopping at the first comma outside quotes.
HEADER = re.compile(r'^#EXTINF:(?:[^",]|"[^"]*")*')
ATTRIBUTES = re.compile(r'\s+([\w-]+)\s*=\s*"([^"]*)"')


@lru_cache(maxsize=2)
def localized_codes(field):
    french = getattr(Locale("fr"), field)
    english = getattr(Locale("en"), field)
    aliases = {}
    labels = {}
    for code, label in french.items():
        if field == "territories" and (len(code) != 2 or code == "ZZ"):
            continue
        if code == "und":
            continue
        labels[code] = label
        for value in (code, label, english.get(code, "")):
            if value:
                aliases[value.casefold()] = code
    alias_table = "territory_aliases" if field == "territories" else "language_aliases"
    for key, replacement in get_global(alias_table).items():
        if isinstance(replacement, list):
            replacement = replacement[0] if len(replacement) == 1 else None
        if replacement in labels:
            aliases.setdefault(key.casefold(), replacement)
    return aliases, labels


def values(raw, aliases):
    if isinstance(raw, str):
        # A full country name can contain a comma.
        raw = [raw] if raw.strip().casefold() in aliases else re.split(r"[,;|]", raw)
    if not isinstance(raw, list):
        return []
    return list(
        dict.fromkeys(
            aliases[v.strip().casefold()]
            for v in raw
            if isinstance(v, str) and v.strip().casefold() in aliases
        )
    )


def enrich_entry(entry, channel, feed, header, attrs):
    groups = [v.strip() for v in attrs.get("group-title", "").split(";") if v.strip()]
    country_aliases, country_names = localized_codes("territories")
    language_aliases, language_names = localized_codes("languages")
    metadata = {"sources": {}, "groups": groups}
    additions = []
    for field, tag, official, aliases, labels in (
        (
            "countries",
            "tvg-country",
            channel.get("country"),
            country_aliases,
            country_names,
        ),
        (
            "languages",
            "tvg-language",
            feed.get("languages"),
            language_aliases,
            language_names,
        ),
        (
            "categories",
            "group-title",
            channel.get("categories"),
            CATEGORY_ALIASES,
            CATEGORY_NAMES,
        ),
    ):
        codes = values(official, aliases)
        if codes:
            metadata["sources"][field] = "iptv-org"
            if tag not in attrs:
                encoded = ";".join(codes)
                additions.append(f' {tag}="{encoded}"')
        else:
            codes = values(groups if field == "categories" else attrs.get(tag), aliases)
            if codes:
                metadata["sources"][field] = "m3u"
        metadata[field] = [labels[code] for code in codes]
    entry["metadata"] = metadata
    if additions and header:
        entry["info"] = header + "".join(additions) + entry["info"][len(header) :]


class ChannelCatalog:
    def __init__(self, directory):
        self.channels = CachedCatalog(directory, "channels")
        self.feeds = CachedCatalog(directory, "feeds")

    def enrich(self, entries):
        prepared = []
        for entry in entries:
            match = HEADER.match(entry["info"])
            header = match.group() if match else ""
            attrs = {k.lower(): v for k, v in ATTRIBUTES.findall(header)}
            channel, _, feed = attrs.get("tvg-id", "").partition("@")
            prepared.append((entry, header, attrs, channel, feed))
        channels = {}
        feeds = {}
        if any(channel for _, _, _, channel, _ in prepared):
            channels = {
                r["id"]: r
                for r in self.channels.load()
                if isinstance(r, dict) and isinstance(r.get("id"), str)
            }
        if any(channel and feed for _, _, _, channel, feed in prepared):
            feeds = {
                (r["channel"], r["id"]): r
                for r in self.feeds.load()
                if isinstance(r, dict)
                and isinstance(r.get("id"), str)
                and isinstance(r.get("channel"), str)
            }
        for entry, header, attrs, channel, feed in prepared:
            enrich_entry(
                entry,
                channels.get(channel, {}),
                feeds.get((channel, feed), {}),
                header,
                attrs,
            )
