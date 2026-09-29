"""
Couche d'accès aux données.

Deux modes de fonctionnement :
  1. SQL SERVER  — mode nominal, lit directement la base TGCC_Budget_V3
  2. INSTANTANÉ  — repli automatique sur les fichiers CSV du dossier `donnees/`

Le repli garantit que l'application reste fonctionnelle même sans connexion à la
base : indispensable pour une démonstration en conditions réelles.
"""

import os
import pandas as pd


_CACHE = {}


def _cache_once(key, loader):
    if key not in _CACHE:
        _CACHE[key] = loader()
    return _CACHE[key]

SERVEUR = os.environ.get('TGCC_SERVEUR', 'localhost')
BASE = os.environ.get('TGCC_BASE', 'TGCC_Budget_V3')

BINS = [-float('inf'), 0.05, 0.10, 0.20, float('inf')]
LABELS = ["Faible", "Modéré", "Élevé", "Critique"]


def _chaine_connexion():
    return (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SERVEUR};DATABASE={BASE};"
        f"Trusted_Connection=yes;TrustServerCertificate=yes;"
    )


def _depuis_sql():
    """Tente la lecture depuis SQL Server. Lève une exception si indisponible."""
    import pyodbc
    cnx = pyodbc.connect(_chaine_connexion(), timeout=5)

    portefeuille = pd.read_sql("""
        SELECT
            c.ID_Chantier, c.Nom_Projet, c.Maitre_Ouvrage, c.Ville, c.Region,
            c.Latitude, c.Longitude, c.Type_Projet, c.Type_Marche,
            c.Superficie_m2, c.Nb_Etages, c.Chef_Chantier,
            c.Date_Debut, c.Date_Fin_Prevue, c.Statut, c.Budget_Prevu_Total,
            SUM(t.Montant_Prevu)  AS Budget_Prevu,
            SUM(t.Montant_Reel)   AS Depenses_Reelles,
            COUNT(*)              AS Nb_Transactions
        FROM dbo.Chantiers c
        JOIN dbo.Transactions t ON t.ID_Chantier = c.ID_Chantier
        GROUP BY c.ID_Chantier, c.Nom_Projet, c.Maitre_Ouvrage, c.Ville, c.Region,
                 c.Latitude, c.Longitude, c.Type_Projet, c.Type_Marche,
                 c.Superficie_m2, c.Nb_Etages, c.Chef_Chantier,
                 c.Date_Debut, c.Date_Fin_Prevue, c.Statut, c.Budget_Prevu_Total
    """, cnx)

    predictions = pd.read_sql("""
        SELECT ID_Chantier, Depassement_Predit, Classe_Predite,
               Confiance, Ecart_Cout_3M, Ecart_Planning_3M
        FROM dbo.Predictions
    """, cnx)

    depenses = pd.read_sql("""
        SELECT t.ID_Chantier,
               FORMAT(t.Date_Transaction, 'yyyy-MM') AS Mois,
               cat.Nom_Categorie AS Categorie,
               SUM(t.Montant_Prevu) AS Montant_Prevu,
               SUM(t.Montant_Reel)  AS Montant_Reel
        FROM dbo.Transactions t
        JOIN dbo.Categories_Depense cat ON cat.ID_Categorie = t.ID_Categorie
        GROUP BY t.ID_Chantier, FORMAT(t.Date_Transaction, 'yyyy-MM'), cat.Nom_Categorie
    """, cnx)
    cnx.close()

    portefeuille = portefeuille.merge(predictions, on='ID_Chantier', how='left')
    return portefeuille, depenses


def _depuis_instantane():
    """Lit l'instantané CSV livré avec l'application."""
    base = os.path.dirname(os.path.abspath(__file__))
    portefeuille = pd.read_csv(os.path.join(base, 'donnees', 'portefeuille.csv'), sep=';')
    depenses = pd.read_csv(os.path.join(base, 'donnees', 'depenses.csv'), sep=';')
    return portefeuille, depenses


def charger():
    """
    Retourne (portefeuille, depenses, source).
    `source` vaut 'SQL Server' ou 'Instantané local'.
    """
    try:
        p, d = _cache_once('sql', _depuis_sql)
        source = 'SQL Server'
    except Exception:
        p, d = _cache_once('instantane', _depuis_instantane)
        source = 'Instantané local'

    p = p.copy()
    p['Ecart'] = p['Depenses_Reelles'] - p['Budget_Prevu']
    p['Pct_Depassement'] = p['Ecart'] / p['Budget_Prevu']
    p['Niveau_Risque'] = pd.cut(p['Pct_Depassement'], bins=BINS, labels=LABELS).astype(str)
    return p, d, source
