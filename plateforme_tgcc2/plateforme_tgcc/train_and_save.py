"""
Entraîne les modèles de prédiction et les sérialise pour l'application Streamlit.

Produit dans le dossier `modele/` :
  - modele_regression.pkl    : estimation du pourcentage de dépassement
  - modele_classification.pkl: estimation de la classe de risque
  - metadonnees.json         : options des listes déroulantes, métriques, date d'entraînement

Produit dans le dossier `donnees/` un instantané exploitable hors connexion à
SQL Server, afin que l'application reste démontrable même si la base est
indisponible (situation classique le jour d'une soutenance).
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import cross_val_score, cross_val_predict, KFold, StratifiedKFold
from sklearn.metrics import mean_absolute_error, r2_score, accuracy_score

from gen_v3 import features_ml, chantiers, transactions

RANDOM_STATE = 42
os.makedirs('modele', exist_ok=True)
os.makedirs('donnees', exist_ok=True)

FEATURES_CAT = ["Type_Projet", "Type_Marche", "Region"]
FEATURES_NUM = ["Budget_Prevu_Total", "Duree_Mois", "Superficie_m2", "Nb_Etages",
                "Note_Fiabilite_Moy", "Eloignement", "Ecart_Cout_3M", "Ecart_Planning_3M"]
FEATURES = FEATURES_CAT + FEATURES_NUM

BINS = [-np.inf, 0.05, 0.10, 0.20, np.inf]
LABELS = ["Faible", "Modéré", "Élevé", "Critique"]

df = pd.DataFrame(features_ml)
train = df[df.est_termine].copy()
predire = df[~df.est_termine].copy()

train["Classe"] = pd.cut(train["Depassement_Final"], bins=BINS, labels=LABELS)

X, y_reg = train[FEATURES], train["Depassement_Final"]
y_clf = train["Classe"].astype(str)

pre = ColumnTransformer([
    ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), FEATURES_CAT),
    ("num", StandardScaler(), FEATURES_NUM),
])

# ---------------------------------------------------------------------
# Entraînement
# ---------------------------------------------------------------------
pipe_reg = Pipeline([("pre", pre),
                     ("mdl", RandomForestRegressor(n_estimators=400, min_samples_leaf=3,
                                                   random_state=RANDOM_STATE))])
pipe_clf = Pipeline([("pre", pre),
                     ("mdl", RandomForestClassifier(n_estimators=400, min_samples_leaf=2,
                                                    random_state=RANDOM_STATE))])

cv = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
cv_s = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

pred_cv = cross_val_predict(pipe_reg, X, y_reg, cv=cv)
r2 = r2_score(y_reg, pred_cv)
mae = mean_absolute_error(y_reg, pred_cv)
mae_base = mean_absolute_error(y_reg, np.full(len(y_reg), y_reg.mean()))

pred_clf_cv = cross_val_predict(pipe_clf, X, y_clf, cv=cv_s)
acc = accuracy_score(y_clf, pred_clf_cv)
acc_base = y_clf.value_counts().max() / len(y_clf)
ordre = {l: i for i, l in enumerate(LABELS)}
tol1 = float(np.mean(np.abs([ordre[a] - ordre[b] for a, b in zip(y_clf, pred_clf_cv)]) <= 1))

pipe_reg.fit(X, y_reg)
pipe_clf.fit(X, y_clf)

joblib.dump(pipe_reg, 'modele/modele_regression.pkl')
joblib.dump(pipe_clf, 'modele/modele_classification.pkl')

# ---------------------------------------------------------------------
# Importance des variables
# ---------------------------------------------------------------------
noms = pipe_reg.named_steps['pre'].get_feature_names_out()
imp = pd.Series(pipe_reg.named_steps['mdl'].feature_importances_, index=noms)
imp = imp.sort_values(ascending=False)

LIB = {
    'Ecart_Cout_3M': "Écart de coût à 3 mois",
    'Ecart_Planning_3M': "Écart de planning à 3 mois",
    'Budget_Prevu_Total': "Budget prévisionnel",
    'Duree_Mois': "Durée du chantier",
    'Superficie_m2': "Superficie",
    'Nb_Etages': "Nombre d'étages",
    'Note_Fiabilite_Moy': "Fiabilité des fournisseurs",
    'Eloignement': "Éloignement logistique",
}

meta = {
    'date_entrainement': datetime.now().strftime('%d/%m/%Y à %H:%M'),
    'features_cat': FEATURES_CAT,
    'features_num': FEATURES_NUM,
    'features': FEATURES,
    'labels': LABELS,
    'bins': [-1e9, 0.05, 0.10, 0.20, 1e9],
    'options': {
        'Type_Projet': sorted(df.Type_Projet.unique().tolist()),
        'Type_Marche': sorted(df.Type_Marche.unique().tolist()),
        'Region': sorted(df.Region.unique().tolist()),
    },
    'defauts': {
        'Budget_Prevu_Total': int(df.Budget_Prevu_Total.median()),
        'Duree_Mois': int(df.Duree_Mois.median()),
        'Superficie_m2': int(df.Superficie_m2.median()),
        'Nb_Etages': int(df.Nb_Etages.median()),
        'Note_Fiabilite_Moy': round(float(df.Note_Fiabilite_Moy.median()), 2),
        'Eloignement': 0.0,
    },
    'eloignement_par_region': (
        df.groupby('Region')['Eloignement'].median().round(2).to_dict()
    ),
    'metriques': {
        'n_train': int(len(train)), 'n_predict': int(len(predire)),
        'r2': round(float(r2), 3),
        'mae': round(float(mae), 4),
        'mae_baseline': round(float(mae_base), 4),
        'gain_vs_baseline': round(float(1 - mae / mae_base), 3),
        'accuracy': round(float(acc), 3),
        'accuracy_baseline': round(float(acc_base), 3),
        'accuracy_tolerance_1': round(tol1, 3),
    },
    'importances': [
        {'variable': LIB.get(n.split('__')[-1], n.split('__')[-1]),
         'poids': round(float(v), 4)}
        for n, v in imp.head(8).items()
    ],
}
with open('modele/metadonnees.json', 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------
# Instantané de données (mode hors connexion)
# ---------------------------------------------------------------------
COLS_CH = ['ID_Chantier','Nom_Projet','Maitre_Ouvrage','Adresse','Ville','Region',
           'Latitude','Longitude','Type_Projet','Type_Marche','Superficie_m2',
           'Nb_Etages','Chef_Chantier','Date_Debut','Date_Fin_Prevue','Statut',
           'Budget_Prevu_Total']
ch = pd.DataFrame(chantiers, columns=COLS_CH)

tr = pd.DataFrame(transactions, columns=['ID_Chantier','ID_Fournisseur','ID_Categorie',
                                         'Date','Facture','Montant_Prevu','Montant_Reel',
                                         'Statut_Paiement','Mode_Paiement'])
agg = tr.groupby('ID_Chantier').agg(
    Budget_Prevu=('Montant_Prevu', 'sum'),
    Depenses_Reelles=('Montant_Reel', 'sum'),
    Nb_Transactions=('Facture', 'count')
).reset_index()
agg['Ecart'] = agg.Depenses_Reelles - agg.Budget_Prevu
agg['Pct_Depassement'] = agg.Ecart / agg.Budget_Prevu

portefeuille = ch.merge(agg, on='ID_Chantier', how='left')
portefeuille['Niveau_Risque'] = pd.cut(portefeuille.Pct_Depassement,
                                       bins=BINS, labels=LABELS).astype(str)

# prédictions sur les chantiers en cours
Xp = predire[FEATURES]
predire = predire.copy()
predire['Depassement_Predit'] = pipe_reg.predict(Xp).round(4)
predire['Classe_Predite'] = pipe_clf.predict(Xp)
predire['Confiance'] = pipe_clf.predict_proba(Xp).max(axis=1).round(3)

portefeuille = portefeuille.merge(
    predire[['ID_Chantier','Ecart_Cout_3M','Ecart_Planning_3M',
             'Depassement_Predit','Classe_Predite','Confiance']],
    on='ID_Chantier', how='left')

portefeuille.to_csv('donnees/portefeuille.csv', index=False, sep=';', encoding='utf-8-sig')

# dépenses mensuelles par catégorie (pour les graphiques de l'application)
CATS = {1:'Béton',2:'Acier',3:"Main d'œuvre",4:'Sous-traitance',5:'Électricité',
        6:"Location d'engins",7:'Carburant',8:'Transport',9:'Sécurité',10:'Divers'}
tr['Categorie'] = tr.ID_Categorie.map(CATS)
tr['Mois'] = pd.to_datetime(tr.Date).dt.to_period('M').astype(str)
tr.groupby(['ID_Chantier','Mois','Categorie'])[['Montant_Prevu','Montant_Reel']] \
  .sum().reset_index() \
  .to_csv('donnees/depenses.csv', index=False, sep=';', encoding='utf-8-sig')

# ---------------------------------------------------------------------
# Persistance dans SQL Server
# ---------------------------------------------------------------------
try:
    import db_utils
    engine = db_utils.get_engine()

    predire[['ID_Chantier', 'Depassement_Predit', 'Classe_Predite',
             'Confiance', 'Ecart_Cout_3M', 'Ecart_Planning_3M']].to_sql(
        'Predictions', engine, if_exists='replace', index=False)
    print(f"✅ {len(predire)} prédictions écrites dans SQL Server (table Predictions).")

    top = imp.head(8)
    importance_df = pd.DataFrame({
        'Variable': [LIB.get(n.split('__')[-1], n.split('__')[-1]) for n in top.index],
        'Poids': [round(float(v), 4) for v in top.values],
        'Rang': list(range(1, len(top) + 1)),
    })
    importance_df.to_sql('Importance_Variables', engine,
                         if_exists='replace', index=False)
    print(f"✅ {len(importance_df)} variables écrites dans SQL Server (table Importance_Variables).")

except Exception as e:
    print(f"⚠️ Écriture SQL Server ignorée : {e}")

print(f"Modèles sérialisés dans modele/")
print(f"  R2 = {r2:.3f} | MAE = {mae:.4f} | Accuracy = {acc:.3f} | ±1 classe = {tol1:.3f}")
print(f"Instantané : {len(portefeuille)} chantiers, dont {predire.shape[0]} en cours")
print(f"Top variables : {', '.join(m['variable'] for m in meta['importances'][:3])}")
