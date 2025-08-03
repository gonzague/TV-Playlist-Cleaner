#!/bin/bash

# Script pour faciliter l'utilisation de Docker avec TV Playlist Cleaner

set -e

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour afficher les messages
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Fonction d'aide
show_help() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  build                    Construire l'image Docker"
    echo "  run [SCRIPT] [ARGS]      Exécuter un script spécifique"
    echo "  config [CATEGORY] [ARGS] Exécuter cleaner_config.py"
    echo "  tnt [ARGS]              Exécuter cleaner_tnt.py"
    echo "  advanced [ARGS]         Exécuter cleaner_advanced.py"
    echo "  shell                   Ouvrir un shell dans le conteneur"
    echo "  clean                   Nettoyer les conteneurs et images"
    echo "  help                    Afficher cette aide"
    echo ""
    echo "Examples:"
    echo "  $0 build"
    echo "  $0 run cleaner.py"
    echo "  $0 config french --direct-only"
    echo "  $0 tnt --direct-only --workers 20"
    echo "  $0 advanced --direct-only --output ma_playlist.m3u"
}

# Fonction pour construire l'image
build_image() {
    print_info "Construction de l'image Docker..."
    docker build -t tv-playlist-cleaner .
    print_success "Image construite avec succès !"
}

# Fonction pour exécuter un script
run_script() {
    local script="$1"
    shift
    local args="$@"
    
    print_info "Exécution de $script avec les arguments: $args"
    docker run --rm -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner "$script" $args
}

# Fonction pour exécuter cleaner_config.py
run_config() {
    local category="$1"
    shift
    local args="$@"
    
    if [ -z "$category" ]; then
        category="french"
    fi
    
    print_info "Exécution de cleaner_config.py avec la catégorie: $category"
    docker run --rm -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner cleaner_config.py "$category" $args
}

# Fonction pour exécuter cleaner_tnt.py
run_tnt() {
    local args="$@"
    print_info "Exécution de cleaner_tnt.py"
    docker run --rm -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner cleaner_tnt.py $args
}

# Fonction pour exécuter cleaner_advanced.py
run_advanced() {
    local args="$@"
    print_info "Exécution de cleaner_advanced.py"
    docker run --rm -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner cleaner_advanced.py $args
}

# Fonction pour ouvrir un shell
open_shell() {
    print_info "Ouverture d'un shell dans le conteneur..."
    docker run --rm -it -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner /bin/sh
}

# Fonction pour nettoyer
clean_docker() {
    print_info "Nettoyage des conteneurs et images..."
    docker container prune -f
    docker image prune -f
    print_success "Nettoyage terminé !"
}

# Créer le dossier output s'il n'existe pas
mkdir -p output

# Traitement des commandes
case "${1:-help}" in
    "build")
        build_image
        ;;
    "run")
        shift
        run_script "$@"
        ;;
    "config")
        shift
        run_config "$@"
        ;;
    "tnt")
        shift
        run_tnt "$@"
        ;;
    "advanced")
        shift
        run_advanced "$@"
        ;;
    "shell")
        open_shell
        ;;
    "clean")
        clean_docker
        ;;
    "help"|*)
        show_help
        ;;
esac 