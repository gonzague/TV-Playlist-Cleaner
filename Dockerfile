# Utiliser une image Python Alpine légère
FROM python:3.11-alpine

# Installer curl et autres dépendances système nécessaires
RUN apk add --no-cache \
    curl \
    ffmpeg \
    && rm -rf /var/cache/apk/*

# Définir le répertoire de travail
WORKDIR /app

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY *.py ./

# Créer un utilisateur non-root pour la sécurité
RUN adduser -D -s /bin/sh appuser && chown -R appuser:appuser /app
USER appuser

# Définir les variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Point d'entrée par défaut
ENTRYPOINT ["python"]
CMD ["cleaner.py"] 