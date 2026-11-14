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

### Interface web locale

```bash
uv sync --extra web
uv run --extra web tv-playlist-web
```

Ouvrir **http://127.0.0.1:8765** dans un navigateur. L'interface accepte une URL,
un fichier `.m3u` / `.m3u8` ou une catégorie de sources, dont iptv-org France.
Elle utilise le même moteur que les scripts en ligne de commande : curl ou
ffprobe, sélection de la qualité, en-têtes VLC/Kodi, nouvelles tentatives et cache.

- Progression réelle, annulation et reprise de l'affichage après rechargement.
- Grille de chaînes avec logos, qualité et statut ; clic sur une carte pour lire,
  accès au clavier (Entrée/Espace), recherche, filtres et pagination.
- Lecteur vidéo intégré sur les flux valides (HLS, MP4 et formats natifs du navigateur),
  changement de chaîne, arrêt et téléchargement individuel pour VLC.
- Filtres combinables par pays d’émission, langue et catégorie. La fiche de la chaîne
  fournit pays et catégories, l’édition exacte (`tvg-id="Chaîne@Édition"`) fournit
  les langues. À défaut, les attributs M3U reconnus sont utilisés. Les groupes
  personnels restent visibles dans le détail des métadonnées. Le rapport JSON indique
  la provenance par champ et les exports M3U complètent les attributs absents.
  Les catalogues sont mis en cache 24 heures et réutilisés en cas de panne.
- Logos `tvg-logo` de la playlist ; complément via [iptv-org](https://github.com/iptv-org/api#logos)
  par identifiant `tvg-id` exact (chaîne et feed), avec cache local de 24 heures.
  Les logos retrouvés sont également ajoutés au M3U exporté.
- Téléchargement de la playlist, du rapport JSON et du rapport CSV.
- Réglages du parallélisme, du timeout, des tentatives et du cache.

L'interface écoute uniquement sur la machine locale. Elle ne nécessite ni compte,
ni compilation JavaScript. Le catalogue iptv-org est facultatif : si son accès échoue,
le cache existant et les logos de la playlist restent utilisables. Les requêtes vers les sources et
les flux partent de la machine où le serveur Python tourne. Installer FFmpeg pour
le mode d'analyse complète ; si seul curl est disponible, le mode rapide est proposé.

Le lecteur contacte directement le diffuseur pour les flux ordinaires. Quand une
playlist fournit des en-têtes VLC/Kodi, le serveur local les applique à la lecture
du média, aux variantes HLS, aux segments et aux clés de la même origine. Le relais
prend en charge `User-Agent`, `Referer`, `Origin`, `Cookie`, `Authorization`,
`Accept`, `Accept-Language` et les en-têtes `X-*`. Les lectures de fichiers gèrent
les requêtes partielles (HTTP Range). Un changement de domaine, de port ou de
protocole dans le flux relayé nécessite généralement VLC. Les chaînes BFM qui déclarent
uniquement un `User-Agent` peuvent suivre les redirections HTTPS de leur CDN SFR. Le téléchargement individuel conserve
les réglages d’origine. La compatibilité du codec et les droits d’accès du diffuseur
restent nécessaires. Les logos sont chargés depuis leur hébergeur.

**Diffuser sur un téléviseur.** Depuis la carte d’une chaîne, cliquez sur
**Chromecast** pour rechercher les récepteurs vidéo du réseau local, puis sur le
nom du récepteur. La vidéo locale se met en pause quand le Chromecast confirme la
lecture. Dans Safari, **AirPlay** ouvre le sélecteur Apple. Pour un flux à en-têtes,
un premier clic prépare le média et un second ouvre le sélecteur. Le Mac et le
récepteur doivent pouvoir communiquer. Pour ces flux, le serveur ouvre sur
l’interface IPv4 locale un port dédié au média, avec une URL temporaire qui expire
après 15 minutes d’inactivité. L’interface de gestion reste sur la boucle locale.

HLS.js **1.7.4** est distribué localement avec sa licence Apache-2.0 dans
`playlist_web/static/vendor` (source : paquet npm `hls.js@1.7.4`, fichiers
`dist/hls.min.js` et `LICENSE`). Aucun script n'est chargé depuis un CDN à l'exécution.

```bash
# Changer le port ou le répertoire des résultats
uv run --extra web tv-playlist-web --port 8766 --data-dir ./resultats-web
```

Les données sont enregistrées par défaut dans `~/.cache/tv-playlist-cleaner/web`.
L’accueil reprend automatiquement la dernière analyse du serveur. Le menu
**Historique des nettoyages** donne accès aux dix derniers résultats terminés,
y compris après redémarrage. **Lien vers ce résultat** permet de rouvrir une
analyse précise dans un autre navigateur sur la même machine. Une seule analyse
s’exécute à la fois. La version web limite une analyse à
50 Mo par playlist et 10 000 entrées ; les scripts CLI restent disponibles pour
les traitements plus volumineux. L'annulation attend la fin des requêtes déjà
engagées (jusqu'au timeout courant), puis empêche le lancement des suivantes.
Arrêter le serveur avec `Ctrl+C` dans le terminal qui l'a lancé.

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

# Traiter un fichier local avec analyse de la résolution réelle (nécessite FFmpeg)
python cleaner.py --input ma_playlist.m3u --validator ffprobe --output nettoyee.m3u

# Tester rapidement la disponibilité HTTP d'une playlist distante
python cleaner.py --url https://example.com/playlist.m3u --workers 20 --timeout 10
```

Le script principal (`cleaner.py`, également accessible avec `tv-playlist-cleaner`)
accepte `--url` ou `--input`, ainsi que `--output`, `--workers` (1 à 50),
`--timeout` (1 à 60 secondes), `--validator` et `--verbose`.
Sans argument, il conserve sa source française et sa vérification avec curl.
Il renvoie le code `0` lorsqu'une playlist est écrite, `1` en cas d'échec ou
d'absence de flux valide et `2` pour des arguments incorrects.

Le mode curl vérifie la disponibilité HTTP avec une requête HEAD et suit jusqu'à
cinq redirections HTTP(S), conformément aux [options de curl](https://curl.se/docs/manpage.html).
Il ne prouve pas que le média est lisible ; les serveurs refusant HEAD peuvent
être rejetés. Utiliser `--validator ffprobe` pour analyser le média et mesurer
la résolution. Les en-têtes VLC/Kodi pris en charge sont appliqués aux deux
validateurs et les directives restent conservées dans le fichier de sortie.

Les lecteurs M3U acceptent désormais les lignes vides et les directives entre
`#EXTINF` et l'URL, les fichiers UTF-8 avec BOM et les virgules dans les attributs
entre guillemets. Les noms d'origine sont conservés à l'export. L'écriture est
atomique : une erreur d'écriture laisse la playlist précédente intacte.

### Rapports, nouvelles tentatives et cache

Ces options sont disponibles dans `cleaner.py`, `cleaner_advanced.py`,
`cleaner_multi_source.py` et `cleaner_tnt.py`, ainsi que via `cleaner_config.py`.

```bash
uv run tv-playlist-cleaner --input ma_playlist.m3u --validator ffprobe \
  --output nettoyee.m3u \
  --report-json rapport.json --report-csv rapport.csv \
  --retries 2 --retry-delay 0.5 \
  --cache verification-cache.json --cache-ttl 3600
```

| Option | Fonction | Défaut |
|--------|----------|--------|
| `--report-json FILE` | Rapport structuré avec bilan et résultat de chaque entrée | Désactivé |
| `--report-csv FILE` | Une ligne par entrée, utilisable dans un tableur | Désactivé |
| `--retries N` | Nouvelles tentatives après une erreur temporaire, de 0 à 5 | `2` |
| `--retry-delay SECONDS` | Délai initial, doublé entre tentatives, plafonné à 30 s | `0.5` |
| `--cache FILE` | Cache persistant des vérifications réussies | Désactivé |
| `--cache-ttl SECONDS` | Durée de validité du cache ; `0` force une nouvelle vérification | `3600` |

Les nouvelles tentatives concernent les téléchargements de playlists et les
vérifications de flux : timeouts, problèmes réseau temporaires et erreurs HTTP
408, 425, 429, 500, 502, 503 et 504. Les erreurs permanentes telles que 403 et
404 ne sont pas relancées. Avec `--retries 2`, un flux peut donc être testé
trois fois ; le timeout s'applique à chaque tentative.

Les rapports distinguent `selected` (conservé), `invalid` (échec de validation)
et `discarded` (doublon ou qualité inférieure). Ils indiquent la qualité,
l'erreur, le validateur, le nombre de tentatives, l'utilisation du cache et la
réutilisation d'un résultat pour une entrée identique. Le JSON précise aussi si
la playlist a pu être écrite. Une entrée par flux est conservée dans les rapports,
y compris pour les doublons. Les rapports sont produits après la validation,
même si tous les flux échouent ; un échec de chargement de la source reste signalé
dans le journal. Les variantes TNT rapportent uniquement les chaînes retenues
par leur filtre TNT. Les fichiers contiennent les URL d'origine : les conserver
localement si elles incluent des identifiants d'accès.

Le cache distingue URL, en-têtes HTTP effectifs, validateur et timeout. Il ne
stocke ni URL ni en-têtes en clair, et ne mémorise pas les échecs. Les entrées
expirées sont ignorées ; un cache corrompu entraîne une nouvelle vérification.
Les résultats identiques sont également réutilisés au sein d'une même exécution.
Le cache est limité aux 10 000 vérifications les plus récentes. L'écriture des
rapports et du cache est atomique. Utiliser un fichier de cache distinct par tâche
si plusieurs exécutions tournent simultanément : le dernier enregistrement prévaut.

### En-têtes VLC et Kodi

Exemple d'entrée nécessitant un User-Agent et un Referer :

```m3u
#EXTINF:-1,Ma chaîne
#EXTVLCOPT:http-user-agent=MonLecteur/1.0
#EXTVLCOPT:http-referrer=https://example.com/player
#KODIPROP:inputstream.adaptive.common_headers=Origin=https%3A%2F%2Fexample.com&Cookie=session%3Dexemple
https://example.com/stream.m3u8
```

Les options VLC `http-user-agent`, `http-referrer` / `http-referer`, `http-origin`
et `http-cookie` sont reconnues. Les propriétés Kodi `common_headers`,
`stream_headers` et `manifest_headers` acceptent des paires `Nom=Valeur` séparées
par `&`, avec valeurs encodées comme dans une URL, selon la
[documentation InputStream Adaptive](https://github.com/xbmc/inputstream.adaptive/wiki/Integration#inputstreamadaptivecommon_headers).
La syntaxe historique `URL|User-Agent=...&Referer=...` est aussi acceptée par le
nettoyeur ; préférer les directives explicites pour les lecteurs récents.

La priorité est VLC, puis Kodi commun, flux, manifeste et enfin suffixe d'URL.
curl et ffprobe reçoivent un jeu d'en-têtes commun à leurs requêtes : si Kodi
déclare des valeurs différentes pour un même en-tête entre manifeste et segments,
la validation échoue avec un message explicite. La configuration DRM et les
requêtes de licence ne sont pas traitées. Les noms d'en-tête invalides et les
caractères de contrôle sont rejetés avant toute requête.

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

### Couverture dans GitHub Actions

La CI installe FFmpeg pour exécuter les tests multimédias et archive les rapports
`coverage.xml` et HTML dans l’artefact **coverage-report** du workflow.
L’envoi externe à Codecov est optionnel : après activation du dépôt dans Codecov,
définir la variable GitHub Actions `CODECOV_ENABLED` à `true`. Un seul job
(Python 3.11) envoie le rapport, avec l’authentification OIDC de GitHub.
Un échec de cet envoi activé est signalé comme un échec du workflow.
