# 🐳 Docker pour TV Playlist Cleaner

Configuration Docker légère et efficace pour exécuter TV Playlist Cleaner dans un conteneur isolé.

## 🚀 Démarrage Rapide

### 1. Construire l'image
```bash
# Utiliser le script helper
./docker-run.sh build

# Ou directement avec Docker
docker build -t tv-playlist-cleaner .
```

### 2. Exécuter le script de base
```bash
# Utiliser le script helper
./docker-run.sh run cleaner.py

# Ou directement avec Docker
docker run --rm -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner cleaner.py
```

## 📋 Utilisation avec le Script Helper

Le script `docker-run.sh` simplifie l'utilisation de Docker :

### Commandes Disponibles

```bash
# Construire l'image
./docker-run.sh build

# Exécuter un script spécifique
./docker-run.sh run cleaner.py
./docker-run.sh run cleaner_advanced.py

# Exécuter cleaner_config.py avec une catégorie
./docker-run.sh config french
./docker-run.sh config english --workers 20

# Exécuter cleaner_tnt.py
./docker-run.sh tnt --workers 20

# Exécuter cleaner_advanced.py
./docker-run.sh advanced --workers 20 --output ma_playlist.m3u

# Ouvrir un shell dans le conteneur
./docker-run.sh shell

# Nettoyer les conteneurs et images
./docker-run.sh clean

# Afficher l'aide
./docker-run.sh help
```

## 🐳 Utilisation Directe avec Docker

### Construction de l'Image
```bash
docker build -t tv-playlist-cleaner .
```

### Exécution des Scripts

#### Script de Base
```bash
docker run --rm -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner cleaner.py
```

#### Script de Configuration
```bash
docker run --rm -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner cleaner_config.py french
```

#### Script TNT
```bash
docker run --rm -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner cleaner_tnt.py
```

#### Script Avancé
```bash
docker run --rm -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner cleaner_advanced.py --workers 20
```

### Shell Interactif
```bash
docker run --rm -it -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner /bin/sh
```

## 🐙 Utilisation avec Docker Compose

### Services Disponibles

```bash
# Script de base
docker-compose run --rm tv-playlist-cleaner

# Script de configuration
docker-compose run --rm cleaner-config

# Script TNT
docker-compose run --rm cleaner-tnt

# Script avancé
docker-compose run --rm cleaner-advanced
```

### Exécution avec Arguments Personnalisés
```bash
# Override la commande par défaut
docker-compose run --rm tv-playlist-cleaner cleaner_config.py english --workers 15

# Script TNT avec options
docker-compose run --rm cleaner-tnt --workers 20 --output tnt_playlist.m3u
```

## 📁 Structure des Volumes

Les volumes Docker sont configurés pour :

- **`./:/app/data`** : Accès aux fichiers du projet
- **`./output:/app/output`** : Dossier de sortie pour les playlists générées

### Création du Dossier Output
```bash
mkdir -p output
```

## 🔧 Configuration de l'Image

### Optimisations Incluses

- **Image de base** : Python 3.11 Alpine (léger)
- **Dépendances système** : curl, ffmpeg
- **Gestionnaire de paquets** : UV (ultra-rapide)
- **Sécurité** : Utilisateur non-root
- **Performance** : Installation optimisée avec UV
- **Taille** : ~150MB (vs ~1GB pour une image standard)

### Variables d'Environnement

- `PYTHONUNBUFFERED=1` : Sortie Python non-bufferisée
- `PYTHONDONTWRITEBYTECODE=1` : Pas de fichiers .pyc

## 🛠️ Personnalisation

### Modifier le Dockerfile

```dockerfile
# Ajouter des dépendances système
RUN apk add --no-cache \
    curl \
    ffmpeg \
    git \
    && rm -rf /var/cache/apk/*

# Installer UV et les dépendances Python verrouillées
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
```

Pour ajouter des packages Python, ajoutez-les à `pyproject.toml`, régénérez
`uv.lock` avec `uv lock`, puis reconstruisez l'image.

### Créer une Image Personnalisée

```bash
# Construire avec un tag personnalisé
docker build -t tv-playlist-cleaner:custom .

# Utiliser l'image personnalisée
docker run --rm -v "$(pwd):/app/data" tv-playlist-cleaner:custom cleaner.py
```

## 🔍 Dépannage

### Problèmes Courants

#### Permission Denied
```bash
# Vérifier les permissions du dossier
ls -la

# Corriger les permissions si nécessaire
chmod 755 .
```

#### Image Non Trouvée
```bash
# Reconstruire l'image
docker build -t tv-playlist-cleaner .

# Ou supprimer et reconstruire
docker rmi tv-playlist-cleaner
docker build -t tv-playlist-cleaner .
```

#### Problèmes de Volume
```bash
# Vérifier que le dossier existe
mkdir -p output

# Vérifier les permissions
chmod 755 output
```

### Logs et Debug

```bash
# Voir les logs du conteneur
docker logs <container_id>

# Exécuter en mode verbose
docker run --rm -v "$(pwd):/app/data" tv-playlist-cleaner cleaner.py --verbose

# Shell de debug
docker run --rm -it -v "$(pwd):/app/data" tv-playlist-cleaner /bin/sh
```

## 📊 Avantages de Docker

### ✅ Avantages
- **Isolation** : Environnement propre et reproductible
- **Portabilité** : Fonctionne sur tous les systèmes
- **Simplicité** : Pas d'installation de dépendances locales
- **Versioning** : Contrôle des versions des outils
- **Sécurité** : Conteneur isolé

### ⚠️ Considérations
- **Taille** : Image de ~150MB
- **Performance** : Léger overhead
- **Réseau** : Accès réseau nécessaire pour télécharger les playlists

## 🚀 Exemples Complets

### Workflow Typique
```bash
# 1. Construire l'image
./docker-run.sh build

# 2. Générer une playlist française
./docker-run.sh config french

# 3. Vérifier le résultat
ls -la output/

# 4. Nettoyer
./docker-run.sh clean
```

### Script Automatisé
```bash
#!/bin/bash
set -e

echo "🚀 Démarrage du processus..."

# Construire l'image
./docker-run.sh build

# Générer différentes playlists
./docker-run.sh config french --output french_playlist.m3u
./docker-run.sh config english --output english_playlist.m3u
./docker-run.sh tnt --output tnt_playlist.m3u

echo "✅ Processus terminé !"
echo "📁 Playlists générées dans le dossier output/"
```

---

🎯 **Conseil** : Utilisez le script `docker-run.sh` pour une expérience simplifiée !
