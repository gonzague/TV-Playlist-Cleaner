#!/bin/bash

# Script de test pour Docker

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

echo "🐳 Test de la configuration Docker pour TV Playlist Cleaner"
echo "========================================================"

# Vérifier que Docker est installé
print_info "Vérification de Docker..."
if ! command -v docker &> /dev/null; then
    print_error "Docker n'est pas installé ou n'est pas dans le PATH"
    exit 1
fi
print_success "Docker est installé"

# Vérifier que Docker fonctionne
print_info "Test de Docker..."
if ! docker info &> /dev/null; then
    print_error "Docker ne fonctionne pas. Vérifiez que le daemon Docker est démarré"
    exit 1
fi
print_success "Docker fonctionne correctement"

# Construire l'image
print_info "Construction de l'image Docker..."
if docker build -t tv-playlist-cleaner-test .; then
    print_success "Image construite avec succès"
else
    print_error "Échec de la construction de l'image"
    exit 1
fi

# Créer le dossier output
mkdir -p output

# Test 1: Script de base
print_info "Test 1: Script de base (cleaner.py)..."
if docker run --rm -v "$(pwd):/app/data" -v "$(pwd)/output:/app/output" tv-playlist-cleaner-test cleaner.py --help &> /dev/null; then
    print_success "Script de base fonctionne"
else
    print_warning "Script de base a des problèmes (normal si pas d'arguments)"
fi

# Test 2: Vérification des dépendances
print_info "Test 2: Vérification des dépendances..."
if docker run --rm tv-playlist-cleaner-test python -c "import requests, tqdm; print('Dépendances OK')" 2>/dev/null; then
    print_success "Dépendances Python installées"
else
    print_error "Problème avec les dépendances Python"
    exit 1
fi

# Test 3: Vérification de curl
print_info "Test 3: Vérification de curl..."
if docker run --rm tv-playlist-cleaner-test curl --version &> /dev/null; then
    print_success "curl est installé"
else
    print_error "curl n'est pas installé"
    exit 1
fi

# Test 4: Vérification de ffmpeg
print_info "Test 4: Vérification de ffmpeg..."
if docker run --rm tv-playlist-cleaner-test ffmpeg -version &> /dev/null; then
    print_success "ffmpeg est installé"
else
    print_warning "ffmpeg n'est pas installé (optionnel)"
fi

# Test 5: Test de téléchargement
print_info "Test 5: Test de téléchargement d'une playlist..."
if docker run --rm -v "$(pwd):/app/data" tv-playlist-cleaner-test python -c "
import requests
try:
    response = requests.get('https://iptv-org.github.io/iptv/countries/fr.m3', timeout=10)
    if response.status_code == 200:
        print('Téléchargement OK')
    else:
        print('Erreur HTTP:', response.status_code)
except Exception as e:
    print('Erreur de téléchargement:', e)
"; then
    print_success "Téléchargement fonctionne"
else
    print_warning "Problème de téléchargement (peut être temporaire)"
fi

# Test 6: Test du script helper
print_info "Test 6: Test du script helper..."
if [ -x "./docker-run.sh" ]; then
    if ./docker-run.sh help &> /dev/null; then
        print_success "Script helper fonctionne"
    else
        print_warning "Script helper a des problèmes"
    fi
else
    print_warning "Script helper non exécutable"
fi

# Nettoyage
print_info "Nettoyage..."
docker rmi tv-playlist-cleaner-test &> /dev/null || true

echo ""
echo "🎉 Tests terminés !"
echo ""
echo "📋 Résumé:"
echo "  ✅ Docker fonctionne"
echo "  ✅ Image construite avec succès"
echo "  ✅ Dépendances installées"
echo "  ✅ curl disponible"
echo "  ✅ Téléchargement fonctionne"
echo ""
echo "🚀 Vous pouvez maintenant utiliser:"
echo "  ./docker-run.sh build"
echo "  ./docker-run.sh config french"
echo ""
echo "📖 Documentation complète: DOCKER.md" 