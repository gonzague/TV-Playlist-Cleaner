#!/usr/bin/env python3
"""
Setup script for TV Playlist Cleaner
"""

from setuptools import setup, find_packages
import os


# Lire le contenu du README
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()


# Lire les requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [
            line.strip() for line in fh if line.strip() and not line.startswith("#")
        ]


setup(
    name="tv-playlist-cleaner",
    version="1.0.0",
    author="TV Playlist Cleaner Team",
    author_email="contact@example.com",
    description="Un script Python avancé pour nettoyer, filtrer et optimiser les playlists M3U",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/TV-playlist-cleaner",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Video",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "flake8>=3.8",
            "black>=21.0",
            "bandit>=1.6",
        ],
    },
    entry_points={
        "console_scripts": [
            "tv-playlist-cleaner=cleaner:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="iptv, m3u, playlist, stream, video, tv",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/TV-playlist-cleaner/issues",
        "Source": "https://github.com/yourusername/TV-playlist-cleaner",
        "Documentation": "https://github.com/yourusername/TV-playlist-cleaner#readme",
    },
)
