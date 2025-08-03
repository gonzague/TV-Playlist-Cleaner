#!/usr/bin/env python3
"""
Test rapide pour vérifier le fonctionnement de base
"""

import sys
import os
import tempfile
import subprocess

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test des imports de base"""
    print("🔍 Test des imports...")
    try:
        import cleaner
        import requests
        import tqdm
        print("✅ Imports réussis")
        return True
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        return False

def test_basic_functions():
    """Test des fonctions de base"""
    print("🔍 Test des fonctions de base...")
    try:
        from cleaner import parse_m3u, extract_resolution_from_quality
        
        # Test parse_m3u
        m3u_content = """#EXTM3U
#EXTINF:-1 tvg-name="TF1",TF1
http://example.com/tf1.m3u8"""
        
        entries = parse_m3u(m3u_content)
        if len(entries) == 1 and entries[0]['name'] == 'TF1':
            print("✅ parse_m3u fonctionne")
        else:
            print("❌ parse_m3u échoue")
            return False
        
        # Test extract_resolution_from_quality
        result = extract_resolution_from_quality("1080p")
        if result['width'] == 1920 and result['height'] == 1080:
            print("✅ extract_resolution_from_quality fonctionne")
        else:
            print("❌ extract_resolution_from_quality échoue")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Erreur dans les fonctions de base: {e}")
        return False

def test_curl_availability():
    """Test de la disponibilité de curl"""
    print("🔍 Test de curl...")
    try:
        result = subprocess.run(
            ['curl', '--version'], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print("✅ curl est disponible")
            return True
        else:
            print("❌ curl n'est pas disponible")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ curl n'est pas installé")
        return False

def test_playlist_download():
    """Test de téléchargement de playlist"""
    print("🔍 Test de téléchargement...")
    try:
        from cleaner import download_playlist
        # Test avec une URL qui existe
        content = download_playlist("https://iptv-org.github.io/iptv/countries/fr.m3u")
        if "#EXTM3U" in content:
            print("✅ Téléchargement de playlist réussi")
            return True
        else:
            print("❌ Contenu de playlist invalide")
            return False
    except Exception as e:
        print(f"❌ Erreur de téléchargement: {e}")
        return False

def test_file_operations():
    """Test des opérations de fichiers"""
    print("🔍 Test des opérations de fichiers...")
    try:
        from cleaner import write_playlist
        entries = [
            {'name': 'Test', 'info': '#EXTINF:-1,Test', 'url': 'http://example.com/test.m3u8'}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.m3u') as tmp_file:
            tmp_filename = tmp_file.name
        
        try:
            write_playlist(entries, tmp_filename)
            
            with open(tmp_filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "#EXTM3U" in content and "Test" in content:
                print("✅ Écriture de playlist réussie")
                return True
            else:
                print("❌ Contenu de fichier invalide")
                return False
        finally:
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)
    except Exception as e:
        print(f"❌ Erreur d'opération de fichier: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🚀 Test rapide de TV Playlist Cleaner")
    print("=" * 40)
    
    tests = [
        ("Imports", test_imports),
        ("Fonctions de base", test_basic_functions),
        ("Disponibilité curl", test_curl_availability),
        ("Téléchargement", test_playlist_download),
        ("Opérations de fichiers", test_file_operations),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} a échoué")
    
    print("\n" + "=" * 40)
    print(f"📊 Résultats: {passed}/{total} tests réussis")
    
    if passed == total:
        print("🎉 Tous les tests sont passés !")
        return 0
    else:
        print("⚠️  Certains tests ont échoué")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 