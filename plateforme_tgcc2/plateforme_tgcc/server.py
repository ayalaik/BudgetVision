import json
import os
from datetime import date, datetime

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

import donnees_source

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="frontend", static_url_path="/static")

MODELE_REG = joblib.load(os.path.join(BASE, "modele", "modele_regression.pkl"))
MODELE_CLF = joblib.load(os.path.join(BASE, "modele", "modele_classification.pkl"))
with open(os.path.join(BASE, "modele", "metadonnees.json"), encoding="utf-8") as fichier:
    META = json.load(fichier)

PORTEFEUILLE, DEPENSES, SOURCE = donnees_source.charger()
RISQUES = ["Faible", "Modéré", "Élevé", "Critique"]


def _json_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    return value


def _records(dataframe):
    return [{key: _json_value(value) for key, value in row.items()}
            for row in dataframe.to_dict(orient="records")]


def _mad(value):
    value = float(value)
    if abs(value) >= 1e9:
        return f"{value / 1e9:.2f} Md MAD"
    if abs(value) >= 1e6:
        return f"{value / 1e6:.1f} M MAD"
    return f"{value:,.0f} MAD".replace(",", " ")


def _portfolio_payload(filters=None):
    filters = filters or {}
    data = PORTEFEUILLE.copy()
    for column in ("Region", "Type_Projet", "Statut", "Niveau_Risque"):
        values = filters.get(column, [])
        if values:
            data = data[data[column].isin(values)]

    budget = float(data.Budget_Prevu.sum()) if len(data) else 0
    expenses = float(data.Depenses_Reelles.sum()) if len(data) else 0
    risk_counts = data.Niveau_Risque.value_counts().reindex(RISQUES).fillna(0)
    by_region = data.groupby("Region")[['Budget_Prevu', 'Depenses_Reelles']].sum()
    by_region["pct"] = (by_region.Depenses_Reelles - by_region.Budget_Prevu) / by_region.Budget_Prevu
    early = data[(data.Ecart_Cout_3M.notna()) & (data.Ecart_Cout_3M < 0.05)
                 & (data.Depassement_Predit > 0.10)]
    columns = ['ID_Chantier', 'Nom_Projet', 'Ville', 'Region', 'Type_Projet', 'Statut',
               'Budget_Prevu', 'Depenses_Reelles', 'Pct_Depassement', 'Niveau_Risque',
               'Depassement_Predit', 'Classe_Predite', 'Confiance']
    return {
        "items": _records(data[columns].sort_values("Pct_Depassement", ascending=False)),
        "summary": {"count": len(data), "budget": budget, "expenses": expenses,
                    "pct": (expenses - budget) / budget if budget else 0},
        "risk_counts": {risk: int(risk_counts[risk]) for risk in RISQUES},
        "regions": [{"name": str(index), "pct": _json_value(row.pct)}
                    for index, row in by_region.sort_values("pct", ascending=False).iterrows()],
        "early_alerts": _records(early[['Nom_Projet', 'Ville', 'Ecart_Cout_3M',
                                         'Depassement_Predit', 'Confiance']]),
    }


@app.get("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.get("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(os.path.join(BASE, "assets"), filename)


@app.get("/api/bootstrap")
def bootstrap():
    return jsonify({
        "source": SOURCE,
        "training_date": META["date_entrainement"],
        "count": len(PORTEFEUILLE),
        "options": META["options"],
        "defaults": META["defauts"],
        "portfolio": _portfolio_payload(),
        "meta": {"metrics": META["metriques"], "importances": META["importances"]},
    })


@app.get("/api/portfolio")
def portfolio():
    return jsonify(_portfolio_payload(request.args.to_dict(flat=False)))


@app.post("/api/simulate")
def simulate():
    payload = request.get_json(silent=True) or {}
    try:
        region = payload["region"]
        values = {
            "Type_Projet": payload["type_projet"],
            "Type_Marche": payload["type_marche"],
            "Region": region,
            "Budget_Prevu_Total": float(payload["budget"]),
            "Duree_Mois": int(payload["duree"]),
            "Superficie_m2": float(payload["superficie"]),
            "Nb_Etages": int(payload["etages"]),
            "Note_Fiabilite_Moy": float(payload["fiabilite"]),
            "Eloignement": META["eloignement_par_region"].get(region, 0.2),
            "Ecart_Cout_3M": float(payload.get("ecart_cout", 0)) / 100,
            "Ecart_Planning_3M": float(payload.get("ecart_plan", 0)),
        }
        features = pd.DataFrame([values])[META["features"]]
        depassement = float(MODELE_REG.predict(features)[0])
        classe = str(MODELE_CLF.predict(features)[0])
        confiance = float(MODELE_CLF.predict_proba(features)[0].max())
        budget = values["Budget_Prevu_Total"]
        comparable = PORTEFEUILLE[PORTEFEUILLE.Type_Projet == values["Type_Projet"]]
        result = {
            "depassement": depassement, "classe": classe, "confiance": confiance,
            "surcout": budget * depassement, "total": budget * (1 + depassement),
            "comparable_count": len(comparable),
            "comparable_rank": float((comparable.Pct_Depassement < depassement).mean()) if len(comparable) else None,
            "comparable_average": float(comparable.Pct_Depassement.mean()) if len(comparable) else None,
            "probabilities": [{"label": label, "value": float(value)}
                              for label, value in zip(MODELE_CLF.classes_, MODELE_CLF.predict_proba(features)[0])],
            "importances": META["importances"],
        }
        return jsonify(result)
    except (KeyError, TypeError, ValueError) as error:
        return jsonify({"error": f"Données de simulation invalides : {error}"}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
