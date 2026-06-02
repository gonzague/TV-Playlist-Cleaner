# 📺 TV Playlist Cleaner

<img width="1200" height="800" alt="TV Playlist cleaner-min" src="https://github.com/user-attachments/assets/114cd872-2f2a-4440-89a4-38b084ea23da" />


[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)](https://github.com/gonzague/TV-Playlist-Cleaner)


Un script Python avancé pour nettoyer, filtrer et optimiser les playlists M3U en utilisant curl et ffprobe pour détecter les flux valides et sélectionner automatiquement la meilleure qualité disponible.



## 🚀 Fonctionnalités

- 📥 **Multi-sources** : Support de multiples sources M3U (iptv-org, freeiptv, etc.)
- 🔍 **Validation intelligente** : Utilise curl et ffprobe pour tester la validité des flux
- 📊 **Détection automatique** : Qualité des flux (720p, 1080p, etc.) et résolution réelle
- 🎯 **Sélection optimale** : Flux de meilleure qualité pour chaque chaîne
- 🔄 **Dédoublonnage intelligent** : Élimination automatique des doublons
- ⚡ **Traitement parallèle** : Exécution rapide avec workers configurables
- 📈 **Barre de progression** : Suivi en temps réel avec statistiques détaillées
- 🎛️ **Configuration flexible** : Catégories prédéfinies et options avancées
- 🇫🇷 **Support TNT françaises** : Script spécialisé pour les 25 chaînes principales

---

**🔗 Liens utiles :**
- **Hébergez votre VPS & code chez** [Hetzner](https://go.gonzague.me/hetzner)
- **J'ai créé  LogCentral, une plateforme de syslog cloud simple et abordable**: [jetez un oeil](https://go.gonzague.me/logcentral)
- **Mes autres réseaux sociaux & projets**: [mon bento](https://go.gonzague.me/bento)
- **Développé à l'aide de**: [Cursor](https://go.gonzague.me/cursor)

---

## ⚠️ Avertissement Important

**Ce projet est un outil de traitement de playlists M3U uniquement. Nous n'hébergeons, ne proposons, ni ne distribuons aucune playlist ou contenu vidéo. Cet outil fonctionne exclusivement avec les playlists que vous lui fournissez, certaines sont listées pour l'exemple.**

- 🔧 **Outil de traitement** : Ce script nettoie et optimise vos propres playlists M3U
- 📋 **Sources externes** : Les URLs de playlists référencées pointent vers des sources tierces
- 🚫 **Aucun contenu** : Aucun flux vidéo ou playlist n'est hébergé par ce projet
- ⚖️ **Responsabilité** : L'utilisateur est responsable de la légalité et de l'utilisation des playlists traitées

## 📊 Résultats Performants

| Métrique | Avant | Après | Amélioration |
|----------|-------|-------|--------------|
| Sources supportées | 1 | 7+ | +600% |
| Flux traités | 223 | 2,910 | +1,300% |
| Flux valides | 102 | 1,543 | +1,400% |
| Taux de succès | 46% | 53% | +15% |
| Vitesse | Basique | ~11.4 flux/s | Optimisé |

## 🛠️ Prérequis

### 1. Installer curl

curl est nécessaire pour analyser les flux vidéo. Il est généralement préinstallé sur la plupart des systèmes.

**macOS (avec Homebrew) :**
```bash
brew install curl
```

**Ubuntu/Debian :**
```bash
sudo apt install curl
```

**Windows :**
curl est inclus dans Windows 10 et versions ultérieures.

### 2. Installer UV

UV est le gestionnaire de paquets Python ultra-rapide que nous utilisons pour ce projet.

**macOS et Linux :**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows :**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Ou avec Homebrew :**
```bash
brew install uv
```

## 🚀 Installation Rapide

### Option 1 : Installation Locale

```bash
# Cloner le repository
git clone https://github.com/gonzague/TV-playlist-Cleaner.git
cd TV-playlist-cleaner

# Installer les dépendances verrouillées avec UV
uv sync

# Générer une playlist française (recommandé pour débuter)
uv run python cleaner_config.py french

```

### Option 2 : Avec Docker (Recommandé)

```bash
# Cloner le repository
git clone https://github.com/gonzague/TV-playlist-cleaner.git
cd TV-playlist-cleaner

# Construire l'image Docker
./docker-run.sh build

# Générer une playlist française
./docker-run.sh config french

```

📖 **Documentation Docker complète** : [DOCKER.md](DOCKER.md)

## 📖 Utilisation

### 🎯 Script Recommandé (Configuration par catégories)

```bash
# Voir toutes les catégories disponibles
python cleaner_config.py

# Utiliser une catégorie spécifique
python cleaner_config.py french
python cleaner_config.py english --workers 20
python cleaner_config.py all --output playlist_complete.m3u

# Catégories disponibles: all, french, english, european, news, sports, movies, kids
```

### 🇫🇷 Script TNT Françaises (Spécialisé)

```bash
# Générer une playlist avec uniquement les 25 chaînes TNT principales
python cleaner_tnt.py

# Options personnalisées
python cleaner_tnt.py --workers 20 --output tnt_playlist.m3u
```

### 🔧 Scripts Avancés

```bash
# Script multi-sources avec dédoublonnage
python cleaner_multi_source.py

# Script avancé avec options complètes
python cleaner_advanced.py --workers 20 --output ma_playlist.m3u

# Script de base
python cleaner.py
```

### 🛠️ Scripts Utilitaires

```bash
# Démonstration complète
python demo.py

# Comparaison de playlists
python compare_playlists.py playlist1.m3u playlist2.m3u


# Configuration des sources
python sources_config.py
```

## ⚙️ Options Disponibles

| Option | Description | Défaut |
|--------|-------------|--------|
| `--url` | URL de la playlist M3U | Playlist française |
| `--output` | Fichier de sortie | `filtered.m3u` |
| `--workers` | Nombre de workers parallèles | `10` |
| `--timeout` | Timeout en secondes | `15` |
| `--no-deduplication` | Désactiver le dédoublonnage | `False` |
| `--sources` | Sources personnalisées | Sources par défaut |

## 📺 Chaînes TNT Françaises

Le script `cleaner_tnt.py` est spécialement conçu pour les 25 chaînes TNT principales :

### Chaînes Cibles
1. **TF1** - Première chaîne privée française
2. **France 2** - Chaîne publique généraliste
3. **France 3** - Chaîne publique régionale
4. **France 4** - Chaîne publique jeunesse
5. **France 5** - Chaîne publique éducative
6. **M6** - Chaîne privée généraliste
7. **Arte** - Chaîne culturelle franco-allemande
8. **La Chaîne parlementaire** - Chaîne parlementaire
9. **W9** - Chaîne privée divertissement
10. **TMC** - Chaîne privée généraliste
11. **TFX** - Chaîne privée divertissement
12. **Gulli** - Chaîne jeunesse
13. **BFM TV** - Chaîne d'information continue
14. **CNEWS** - Chaîne d'information continue
15. **LCI** - Chaîne d'information continue
16. **Franceinfo** - Chaîne d'information publique
17. **CSTAR** - Chaîne privée divertissement
18. **T18** - Chaîne privée divertissement
19. **NOVO19** - Chaîne privée divertissement
20. **TF1 Séries Films** - Chaîne séries et films
21. **L'Équipe** - Chaîne sportive
22. **6Ter** - Chaîne privée divertissement
23. **RMC Story** - Chaîne d'information
24. **RMC Découverte** - Chaîne documentaire
25. **Chérie 25** - Chaîne privée divertissement

### Fonctionnalités Spéciales
- **Reconnaissance intelligente étendue** : Variations de noms (ex: "FRANCE 2", "France2", "France 2 HD")
- **Système de fallback étendu** : Jusqu'à 5 sources par chaîne
- **Détection de résolution** : Résolution réelle (1920x1080, 1280x720, etc.)
- **Sélection qualité** : Privilégie les flux HD/1080p
- **Métadonnées enrichies** : Date/heure de génération

## 📊 Exemple de Sortie

```
🔍 Vérification de curl...
📥 Téléchargement de la playlist...
🎬 2,910 flux trouvés.
⏳ Test des flux (cela peut prendre du temps)...
Test des flux: 100%|██████████████████████████| 2910/2910 [04:15<00:00, 11.4flux/s, Valides=1543, Échoués=1367]

✅ 1,543 flux valides trouvés.
❌ 1,367 flux échoués.

🔍 Analyse des échecs...
  Méthodes utilisées:
    curl: 1,367 flux
  Types d'erreurs:
    Timeout: 856 flux
    HTTP Error: 511 flux

📊 Qualités disponibles: 1080p, 720p, 576p, 480p
🔝 1,212 flux sélectionnés avec la meilleure qualité.
💾 Playlist enregistrée dans 'filtered.m3u'

📺 Exemples de flux sélectionnés:
  1. TF1 (1920x1080) (1080p) [curl]
  2. France 2 (1920x1080) (1080p) [curl]
  3. M6 (1280x720) (720p) [curl]
  4. Arte (1920x1080) (1080p) [curl]
  5. BFM TV (768x432) (432p) [curl]
  ... et 1,207 autres
```

## 🏗️ Architecture

### Scripts Principaux
- `cleaner.py` - Version de base avec curl
- `cleaner_advanced.py` - Version avancée avec options et barre de progression
- `cleaner_multi_source.py` - Version multi-sources avec dédoublonnage
- `cleaner_config.py` - Wrapper avec configuration des sources par catégories
- `cleaner_tnt.py` - Script spécialisé pour les chaînes TNT françaises

### Scripts Utilitaires
- `sources_config.py` - Configuration des sources M3U par catégories
- `tests/` - Tests unitaires 
- `compare_playlists.py` - Comparaison et analyse de playlists
- `demo.py` - Script de démonstration complète

### Sources Supportées / Testées
- **iptv-org** : Sources officielles par pays et catégories
- **freeiptv** : Source communautaire avec flux français et internationaux
- **paratv** : Source individuelle
- **Catégories** : all, french, english, european, news, sports, movies, kids

## 🔧 Fonctionnalités Techniques

### Dédoublonnage Intelligent
- Normalisation des noms de chaînes
- Suppression des indicateurs de qualité
- Détection par hash MD5 des URLs
- Conservation de la meilleure qualité

### Vérification des Flux
- **curl** : Pour les sites web et protocoles complexes
- **ffprobe** : Détection précise de la résolution et qualité
- **curl** : Pour les flux directs (.m3u8, .mp4, etc.)
- **Timeout configurable** : 15 secondes par défaut
- **Retry automatique** : 1 tentative de reconnexion

### Configuration Flexible
- **Sources par catégories** : Régions, langues, types
- **Options flexibles** : Workers, timeout, sortie
- **Gestion d'erreurs** : Téléchargement, parsing, validation

## 🐛 Dépannage

### curl non trouvé
Si vous obtenez une erreur "curl n'est pas installé", assurez-vous qu'il est dans votre PATH ou installez-le avec votre gestionnaire de paquets système.

### Flux qui échouent
Certains flux peuvent échouer pour diverses raisons :
- Flux temporairement indisponibles
- Restrictions géographiques
- Protocoles non supportés

Le script continuera avec les flux valides.

### Performance
Si le script est trop lent, vous pouvez :
- Réduire le nombre de workers : `--workers 5`
- Augmenter le timeout : `--timeout 30`
- Utiliser moins de sources avec `cleaner_config.py`

## 📈 Avantages avec ffprobe

- **Détection précise de la résolution** : ffprobe détecte la résolution réelle des flux vidéo
- **Support de protocoles** : curl supporte HTTP, HTTPS, et d'autres protocoles de streaming
- **Détection de qualité** : Extrait automatiquement les informations de qualité
- **Robustesse** : Meilleure gestion des erreurs et des timeouts
- **Performance** : Optimisé pour les flux de streaming en direct
- **Flexibilité** : Support pour la vérification directe avec ffprobe en plus de curl
- **Barre de progression** : Affichage en temps réel de l'avancement
- **Analyse détaillée** : Statistiques sur les échecs et les méthodes utilisées
- **Métadonnées enrichies** : Date/heure de génération et qualités détectées dans les fichiers M3U

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :

1. Fork le projet
2. Créer une branche pour votre fonctionnalité (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙏 Remerciements

- [curl](https://curl.se/) pour l'analyse des flux vidéo
- [iptv-org](https://iptv-org.github.io/) pour les sources de playlists et [paratv](https://github.com/Paradise-91/ParaTV)
- [ffmpeg](https://ffmpeg.org/) pour ffprobe & l'incroyable FFMPEG bien sûr.

## 📞 Support

Si vous rencontrez des problèmes ou avez des questions :

1. Consultez la section [Dépannage](#-dépannage)
2. Vérifiez les [Issues](https://github.com/yourusername/TV-playlist-cleaner/issues) existantes
3. Créez une nouvelle issue avec les détails de votre problème

---

⭐ Si ce projet vous a été utile, n'hésitez pas à lui donner une étoile ! 
