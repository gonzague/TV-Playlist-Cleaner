"""Metadata lookup and M3U fallback, including ambiguous channel editions."""

from unittest.mock import Mock

import pytest

pytest.importorskip("flask")
from playlist_web.metadata import ChannelCatalog  # noqa: E402


@pytest.fixture
def catalog(tmp_path):
    catalog = ChannelCatalog(tmp_path)
    catalog.channels.load = Mock(
        return_value=[
            {"id": "News.be", "country": "BE", "categories": ["news", "culture"]}
        ]
    )
    catalog.feeds.load = Mock(
        return_value=[
            {"channel": "News.be", "id": "Main", "languages": ["fra", "nld"]},
            {"channel": "Other.be", "id": "English", "languages": ["eng"]},
        ]
    )
    return catalog


def test_exact_feed_and_personal_groups(catalog):
    entry = {
        "info": '#EXTINF:-1 tvg-id="News.be@Main" group-title="Mes favoris, TV" tvg-country="FR",News, live'
    }
    catalog.enrich([entry])
    assert entry["metadata"] == {
        "countries": ["Belgique"],
        "languages": ["français", "néerlandais"],
        "categories": ["Information", "Culture"],
        "groups": ["Mes favoris, TV"],
        "sources": dict.fromkeys(("countries", "languages", "categories"), "iptv-org"),
    }
    assert entry["info"].endswith('tvg-country="FR" tvg-language="fr;nl",News, live')
    assert 'group-title="Mes favoris, TV"' in entry["info"]


@pytest.mark.parametrize("tvg_id", ["News.be@English", "News.be"])
def test_language_requires_exact_feed(catalog, tvg_id):
    entry = {"info": f'#EXTINF:-1 tvg-id="{tvg_id}",News'}
    catalog.enrich([entry])
    assert entry["metadata"]["countries"] == ["Belgique"]
    assert entry["metadata"]["languages"] == []
    assert "languages" not in entry["metadata"]["sources"]
    if "@" not in tvg_id:
        catalog.feeds.load.assert_not_called()


def test_imported_fields_without_id_need_no_catalog(catalog):
    info = '#EXTINF:-1 TVG-COUNTRY="BEL;France" tvg-language="fra|French|Dutch" group-title="News;Favoris",Test tvg-id="News.be@Main"'
    entry = {"info": info}
    catalog.enrich([entry])
    assert entry["info"] == info
    assert entry["metadata"] == {
        "countries": ["Belgique", "France"],
        "languages": ["français", "néerlandais"],
        "categories": ["Information"],
        "groups": ["News", "Favoris"],
        "sources": dict.fromkeys(("countries", "languages", "categories"), "m3u"),
    }
    catalog.channels.load.assert_not_called()
    catalog.feeds.load.assert_not_called()


def test_missing_catalog_and_unknown_values(catalog):
    catalog.feeds.load.return_value = []
    entry = {"info": '#EXTINF:-1 tvg-id="News.be@Main" tvg-language="fre",News'}
    other = {
        "info": '#EXTINF:-1 tvg-id="Absent.be@Main" tvg-country="ZZ" tvg-language="und" group-title="Mes favoris",News'
    }
    catalog.enrich([entry, other])
    assert entry["metadata"]["sources"] == {
        "countries": "iptv-org",
        "categories": "iptv-org",
        "languages": "m3u",
    }
    assert other["metadata"] == {
        "countries": [],
        "categories": [],
        "languages": [],
        "sources": {},
        "groups": ["Mes favoris"],
    }
