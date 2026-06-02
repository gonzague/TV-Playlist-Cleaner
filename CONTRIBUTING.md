# 🤝 Guide de Contribution

Merci de votre intérêt pour contribuer au projet TV Playlist Cleaner ! Ce document vous guidera dans le processus de contribution.

## 📋 Table des Matières

- [Comment Contribuer](#comment-contribuer)
- [Configuration de l'Environnement](#configuration-de-lenvironnement)
- [Standards de Code](#standards-de-code)
- [Tests](#tests)
- [Pull Request](#pull-request)
- [Signaler un Bug](#signaler-un-bug)
- [Demander une Fonctionnalité](#demander-une-fonctionnalité)

## 🚀 Comment Contribuer

### 1. Fork le Projet

1. Allez sur [GitHub](https://github.com/yourusername/TV-playlist-cleaner)
2. Cliquez sur le bouton "Fork" en haut à droite
3. Clonez votre fork localement :
   ```bash
   git clone https://github.com/votre-username/TV-playlist-cleaner.git
   cd TV-playlist-cleaner
   ```

### 2. Créez une Branche

Créez une branche pour votre fonctionnalité ou correction :

```bash
git checkout -b feature/nouvelle-fonctionnalite
# ou
git checkout -b fix/correction-bug
```

### 3. Configurez l'Environnement

```bash
# Installez UV (si pas déjà fait)
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:
# powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Créez l'environnement virtuel et installez les dépendances de développement
uv sync --extra dev
```

### 4. Développez

- Écrivez votre code
- Ajoutez des tests si nécessaire
- Vérifiez que tout fonctionne

### 5. Testez

```bash
# Lancez les tests
uv run pytest tests/ -v

# Testez avec différentes options
uv run python cleaner_config.py french
uv run python cleaner_tnt.py
```

### 6. Commit et Push

```bash
git add .
git commit -m "feat: ajoute nouvelle fonctionnalité"
git push origin feature/nouvelle-fonctionnalite
```

### 7. Créez une Pull Request

1. Allez sur votre fork GitHub
2. Cliquez sur "Compare & pull request"
3. Remplissez le template de PR
4. Soumettez la PR

## 🛠️ Configuration de l'Environnement

### Prérequis

- Python 3.8+
- curl
- ffmpeg (optionnel, pour ffprobe)

### Installation des Dépendances

```bash
uv sync --extra dev
```

### Installation de curl

```bash
# Avec Homebrew (macOS)
brew install curl

# Avec apt (Ubuntu/Debian)
sudo apt install curl

# Windows
curl est inclus dans Windows 10 et versions ultérieures.
```

## 📝 Standards de Code

### Style de Code

- Suivez [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Utilisez des noms de variables et fonctions descriptifs
- Ajoutez des docstrings pour les fonctions principales
- Limitez les lignes à 79 caractères

### Exemple de Code

```python
def clean_playlist(url: str, output: str = "filtered.m3u") -> bool:
    """
    Nettoie et filtre une playlist M3U.
    
    Args:
        url: URL de la playlist M3U
        output: Fichier de sortie
        
    Returns:
        bool: True si succès, False sinon
    """
    try:
        # Votre code ici
        return True
    except Exception as e:
        print(f"Erreur: {e}")
        return False
```

### Messages de Commit

Utilisez le format [Conventional Commits](https://www.conventionalcommits.org/) :

```
feat: ajoute nouvelle fonctionnalité
fix: corrige un bug
docs: met à jour la documentation
style: améliore le style de code
refactor: refactorise le code
test: ajoute des tests
chore: tâches de maintenance
```

## 🧪 Tests

### Tests Manuels

```bash
# Test de base
python cleaner.py

# Test avancé
python cleaner_advanced.py

# Test TNT
uv run python cleaner_tnt.py

# Test de validation
uv run pytest tests/ -v
```

### Tests Automatisés

Si vous ajoutez des tests automatisés :

```bash
# pytest est déjà installé avec les dépendances dev
# Lancez les tests
uv run pytest tests/
```

## 🔄 Pull Request

### Template de PR

```markdown
## Description
Brève description des changements apportés.

## Type de Changement
- [ ] Bug fix
- [ ] Nouvelle fonctionnalité
- [ ] Amélioration
- [ ] Documentation
- [ ] Refactoring

## Tests
- [ ] Tests manuels effectués
- [ ] Tests automatisés ajoutés
- [ ] Aucun test nécessaire

## Checklist
- [ ] Le code suit les standards de style
- [ ] Les tests passent
- [ ] La documentation est mise à jour
- [ ] Les changements sont documentés
```

## 🐛 Signaler un Bug

### Template d'Issue

```markdown
## Description du Bug
Description claire et concise du bug.

## Étapes pour Reproduire
1. Aller à '...'
2. Cliquer sur '...'
3. Voir l'erreur

## Comportement Attendu
Description de ce qui devrait se passer.

## Comportement Actuel
Description de ce qui se passe actuellement.

## Informations Système
- OS: [ex: macOS 12.0]
- Python: [ex: 3.9.7]
- curl: [ex: 7.68.0]

## Logs
```
Pastez les logs d'erreur ici
```

## Capture d'Écran
Si applicable, ajoutez une capture d'écran.
```

## 💡 Demander une Fonctionnalité

### Template de Feature Request

```markdown
## Description de la Fonctionnalité
Description claire et concise de la fonctionnalité souhaitée.

## Problème Résolu
Description du problème que cette fonctionnalité résoudrait.

## Solution Proposée
Description de la solution souhaitée.

## Alternatives Considérées
Description des alternatives considérées.

## Informations Supplémentaires
Toute information supplémentaire, captures d'écran, etc.
```

## 📞 Contact

Si vous avez des questions ou besoin d'aide :

- Ouvrez une [issue](https://github.com/yourusername/TV-playlist-cleaner/issues)
- Consultez la [documentation](README.md)
- Vérifiez les [discussions](https://github.com/yourusername/TV-playlist-cleaner/discussions)

## 🙏 Remerciements

Merci à tous les contributeurs qui participent à l'amélioration de ce projet !

---

N'hésitez pas à contribuer, même pour de petites améliorations ! Chaque contribution compte. 🚀
