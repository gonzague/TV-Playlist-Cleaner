#!/usr/bin/env python3
"""
Wrapper pour le nettoyeur de playlist TV avec configuration des sources
"""

import sys
import subprocess
from sources_config import get_sources_by_category, list_available_categories

def main():
    if len(sys.argv) < 2:
        print("🎯 Nettoyeur de playlist TV - Configuration des sources")
        print("=" * 50)
        print("\n📋 Catégories disponibles:")
        
        categories = list_available_categories()
        for i, category in enumerate(categories, 1):
            sources = get_sources_by_category(category)
            print(f"  {i}. {category} ({len(sources)} sources)")
        
        print(f"\n💡 Utilisation:")
        print(f"  python cleaner_config.py <catégorie> [options]")
        print(f"  python cleaner_config.py french --direct-only")
        print(f"  python cleaner_config.py english --workers 20")
        print(f"  python cleaner_config.py all --output playlist_complete.m3u")
        
        print(f"\n🔧 Options disponibles:")
        print(f"  --direct-only     : Vérification directe uniquement (plus rapide)")
        print(f"  --workers N       : Nombre de workers parallèles")
        print(f"  --output FILE     : Fichier de sortie")
        print(f"  --no-deduplication: Désactiver le dédoublonnage")
        
        return
    
    category = sys.argv[1].lower()
    sources = get_sources_by_category(category)
    
    if not sources:
        print(f"❌ Catégorie '{category}' non trouvée")
        print(f"📋 Catégories disponibles: {', '.join(list_available_categories())}")
        return
    
    print(f"🎯 Utilisation de la catégorie: {category}")
    print(f"📥 Sources: {len(sources)}")
    for i, source in enumerate(sources, 1):
        print(f"  {i}. {source}")
    
    # Construire la commande
    cmd = ["python", "cleaner_multi_source.py", "--sources"] + sources
    
    # Ajouter les options supplémentaires
    for arg in sys.argv[2:]:
        cmd.append(arg)
    
    print(f"\n🚀 Exécution de la commande:")
    print(f"  {' '.join(cmd)}")
    print()
    
    # Exécuter la commande
    try:
        result = subprocess.run(cmd)
        if result.returncode == 0:
            print(f"\n✅ Script terminé avec succès!")
        else:
            print(f"\n❌ Script terminé avec le code {result.returncode}")
    except KeyboardInterrupt:
        print(f"\n⏹️  Script interrompu par l'utilisateur")
    except Exception as e:
        print(f"\n💥 Erreur lors de l'exécution: {e}")

if __name__ == "__main__":
    main() 