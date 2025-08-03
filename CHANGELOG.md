# 📝 Changelog

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [Unreleased]

### Added
- Support multi-sources avec dédoublonnage intelligent
- Barre de progression en temps réel
- Configuration flexible par catégories
- Script spécialisé TNT françaises
- Détection précise de résolution avec ffprobe
- Métadonnées enrichies dans les fichiers M3U
- Système de fallback étendu (jusqu'à 5 sources par chaîne)

### Changed
- Amélioration significative des performances (+1,300% de flux traités)
- Optimisation de la détection de qualité
- Interface utilisateur améliorée avec statistiques détaillées

### Fixed
- Correction des problèmes de timeout
- Amélioration de la gestion d'erreurs
- Optimisation de la reconnaissance des noms de chaînes

## [1.0.0] - 2024-01-XX

### Added
- Script de base `cleaner.py` avec curl
- Support des playlists M3U
- Validation des flux vidéo
- Détection automatique de qualité
- Traitement parallèle
- Script avancé `cleaner_advanced.py`
- Script multi-sources `cleaner_multi_source.py`
- Script de configuration `cleaner_config.py`
- Script TNT `cleaner_tnt.py`
- Scripts utilitaires (test, comparaison, démo)
- Documentation complète

### Features
- Téléchargement automatique des playlists
- Test de validité des flux avec curl et ffprobe
- Sélection de la meilleure qualité disponible
- Génération de playlists filtrées
- Support de multiples sources (iptv-org, freeiptv)
- Dédoublonnage intelligent
- Configuration par catégories (french, english, european, etc.)
- Script spécialisé pour les chaînes TNT françaises
- Détection de résolution avec ffprobe
- Barre de progression en temps réel
- Statistiques détaillées des échecs
- Métadonnées enrichies

### Technical
- Python 3.8+ support
- curl integration
- ffprobe integration
- Parallel processing
- Error handling
- Timeout management
- URL validation
- Quality detection
- Resolution detection
- M3U parsing and generation

---

## Types de Changements

- **Added** : Nouvelles fonctionnalités
- **Changed** : Changements dans les fonctionnalités existantes
- **Deprecated** : Fonctionnalités qui seront supprimées
- **Removed** : Fonctionnalités supprimées
- **Fixed** : Corrections de bugs
- **Security** : Corrections de vulnérabilités 