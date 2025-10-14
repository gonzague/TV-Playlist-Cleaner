# Utiliser une image Python Alpine légère
FROM python:3.11-alpine

# Installer curl et autres dépendances système nécessaires
RUN apk add --no-cache \
    curl \
    ffmpeg \
    && rm -rf /var/cache/apk/*

# Installer UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances Python avec UV
RUN uv pip install --system "requests>=2.25.0" "tqdm>=4.60.0"

# Copier le code source
COPY *.py ./

# Créer un utilisateur non-root pour la sécurité
RUN adduser -D -s /bin/sh appuser && chown -R appuser:appuser /app
USER appuser

# Définir les variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Point d'entrée par défaut
CMD ["python", "cleaner.py"] 