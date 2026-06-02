#!/usr/bin/env python3
"""
Wrapper for TV playlist cleaner with source configuration by category.

Provides an easy interface to select playlist sources by category (french, english, all, etc.)
and passes them to the multi-source cleaner.
"""

import sys
import subprocess  # nosec B404
import logging
from typing import List
from sources_config import get_sources_by_category, list_available_categories

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def show_usage() -> None:
    """Display usage information and available categories."""
    logger.info("🎯 Nettoyeur de playlist TV - Configuration des sources")
    logger.info("=" * 50)
    logger.info("\n📋 Catégories disponibles:")

    categories = list_available_categories()
    for i, category in enumerate(categories, 1):
        sources = get_sources_by_category(category)
        logger.info(f"  {i}. {category} ({len(sources)} sources)")

    logger.info(f"\n💡 Utilisation:")
    logger.info(f"  python cleaner_config.py <catégorie> [options]")
    logger.info(f"  python cleaner_config.py french")
    logger.info(f"  python cleaner_config.py english --workers 20")
    logger.info(f"  python cleaner_config.py all --output playlist_complete.m3u")

    logger.info(f"\n🔧 Options disponibles:")
    logger.info(f"  --workers N       : Nombre de workers parallèles (défaut: 10)")
    logger.info(f"  --timeout N       : Timeout en secondes (défaut: 15)")
    logger.info(f"  --output FILE     : Fichier de sortie (défaut: filtered.m3u)")
    logger.info(f"  --no-deduplication: Désactiver le dédoublonnage")
    logger.info(f"  --verbose         : Mode verbeux (debug logging)")


def validate_category(category: str, available: List[str]) -> bool:
    """
    Validate that the category is in the available categories list.

    Args:
        category: Category name to validate
        available: List of available categories

    Returns:
        True if valid, False otherwise
    """
    return category.lower() in [c.lower() for c in available]


def main() -> None:
    """Main entry point for the configuration wrapper."""
    if len(sys.argv) < 2:
        show_usage()
        return

    category = sys.argv[1].lower()

    # Validate category
    available_categories = list_available_categories()
    if not validate_category(category, available_categories):
        logger.error(f"❌ Catégorie '{category}' non trouvée")
        logger.error(f"📋 Catégories disponibles: {', '.join(available_categories)}")
        return

    sources = get_sources_by_category(category)

    if not sources:
        logger.error(f"❌ Aucune source pour la catégorie '{category}'")
        return

    logger.info(f"🎯 Utilisation de la catégorie: {category}")
    logger.info(f"📥 Sources: {len(sources)}")
    for i, source in enumerate(sources, 1):
        # Truncate long URLs for display
        display_url = source if len(source) <= 60 else source[:57] + "..."
        logger.info(f"  {i}. {display_url}")

    # Build command
    cmd = [sys.executable, "cleaner_multi_source.py", "--sources"] + sources

    # Add additional options
    for arg in sys.argv[2:]:
        cmd.append(arg)

    logger.info(f"\n🚀 Exécution de la commande:")
    logger.info(
        f"  {' '.join(cmd[:4])} ... [+{len(sources)} sources] {' '.join(sys.argv[2:])}"
    )
    logger.info("")

    # Execute command with timeout
    try:
        result = subprocess.run(cmd, timeout=3600)  # nosec B603
        if result.returncode == 0:
            logger.info(f"\n✅ Script terminé avec succès!")
        else:
            logger.error(f"\n❌ Script terminé avec le code {result.returncode}")
            sys.exit(result.returncode)
    except KeyboardInterrupt:
        logger.warning(f"\n⏹️  Script interrompu par l'utilisateur")
        sys.exit(130)  # Standard exit code for SIGINT
    except subprocess.TimeoutExpired:
        logger.error(f"\n⏱️  Timeout: Le script a dépassé la limite de temps (1 heure)")
        sys.exit(124)  # Standard timeout exit code
    except Exception as e:
        logger.error(f"\n💥 Erreur lors de l'exécution: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
