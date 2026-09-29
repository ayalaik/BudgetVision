# Plateforme de prévision des écarts budgétaires — TGCC

Application web complémentaire au tableau de bord Power BI.

Là où le tableau de bord **pilote le portefeuille existant**, cette plateforme permet de
**simuler le risque d'un chantier qui n'est pas encore en base** — situation courante en
phase d'étude ou de réponse à un appel d'offres — et d'interroger les données en langage
naturel.

---

## Installation

### 1. Prérequis

Python 3.9 ou supérieur. Vérifier avec :

```bash
python --version
```

### 2. Installer les dépendances

Ouvrir une invite de commandes **dans le dossier de l'application**, puis :

```bash
pip install -r requirements.txt
```

> Si l'installation de `pyodbc` échoue, ce n'est pas bloquant : l'application bascule
> automatiquement sur l'instantané local. Voir la section « Modes de fonctionnement ».

### 3. Générer les modèles

```bash
python train_and_save.py
```

Cette commande crée le dossier `modele/` (modèles sérialisés + métadonnées) et le dossier
`donnees/` (instantané de secours). **À exécuter une seule fois**, ou après chaque
modification des données.

### 4. Lancer l'application

```bash
python server.py
```

Ouvrir ensuite `http://127.0.0.1:5000`. L'interface est une application web HTML/CSS/JavaScript servie par Flask ; Streamlit n'est plus nécessaire pour la lancer.

---

## Modes de fonctionnement

L'application détecte seule sa source de données. Le mode actif est affiché en bas de la
barre latérale.

| Mode | Condition | Indicateur |
|---|---|---|
| **SQL Server** | Base `TGCC_Budget_V3` accessible | 🟢 |
| **Instantané local** | Repli automatique si la base est indisponible | 🟡 |

Ce repli est délibéré : il garantit que l'application reste démontrable même sans connexion
à la base — situation qui arrive plus souvent qu'on ne le voudrait le jour d'une soutenance.

Pour pointer vers un autre serveur ou une autre base, définir avant le lancement :

```bash
set TGCC_SERVEUR=localhost
set TGCC_BASE=TGCC_Budget_V3
```

---

## Les quatre pages

### Simulation d'un chantier
Formulaire de saisie des caractéristiques d'un projet — type, marché, région, budget,
durée, fiabilité des fournisseurs. L'application retourne le dépassement estimé, le niveau
de risque, le surcoût projeté et l'indice de confiance, accompagnés du positionnement du
projet parmi les chantiers comparables du portefeuille.

Les deux derniers curseurs (écart de coût et de planning à 3 mois) sont facultatifs : ils
ne concernent que les chantiers ayant déjà démarré. Les laisser à zéro revient à simuler un
projet en phase d'étude.

### Portefeuille
Consultation filtrée des 144 chantiers avec leur situation budgétaire, leur niveau de
risque et, pour les chantiers en cours, la prédiction du modèle. Un encart signale les
chantiers en **alerte précoce**.

### Assistant
Interrogation du portefeuille en langage naturel. Quatre boutons de suggestion permettent
de démarrer rapidement — utiles en démonstration.

### À propos du modèle
Méthodologie, performances en validation croisée, importance des variables et limites
assumées. Cette page répond par avance aux questions du jury.

---

## Fonctionnement de l'assistant

L'assistant repose sur un **moteur d'analyse d'intention** et non sur un modèle de langage.
La question est normalisée, rapprochée d'un ensemble de motifs, puis les entités citées
— région, ville, type de projet, seuil numérique, nom de chantier — sont extraites du texte.
La réponse est ensuite **calculée sur les données réelles**.

Ce choix a trois conséquences :

- **Aucun chiffre ne peut être inventé** : chaque valeur restituée provient d'un calcul sur
  le jeu de données. C'est un point défendable en soutenance, là où un modèle de langage
  peut produire des chiffres plausibles mais faux.
- **Aucune dépendance externe** : ni clé d'API, ni connexion internet, ni coût. L'application
  ne peut pas tomber en panne pendant la démonstration.
- **Le périmètre est explicite** : les questions hors sujet reçoivent une réponse claire
  plutôt qu'une approximation.

La contrepartie est que les formulations très libres ne sont pas toutes couvertes. Le
fichier `assistant.py` est structuré pour qu'un modèle de langage puisse être branché en
complément, en traitant uniquement les questions non reconnues par les motifs.

### Formulations reconnues

| Catégorie | Exemple |
|---|---|
| Classement | quels sont les 5 chantiers les plus en dépassement ? |
| Comptage | combien de chantiers dépassent de plus de 15 % ? |
| Comparaison | quelle région dépasse le plus ? |
| Chantier précis | parle-moi du Barrage Collinaire Zenata |
| Prédiction | quels chantiers vont déraper ? |
| Alerte précoce | quels chantiers paraissent sains mais sont annoncés en dérive ? |
| Méthodologie | comment le niveau de risque est-il déterminé ? |
| Synthèse | synthèse des chantiers publics |

Les filtres se combinent : *les chantiers publics d'infrastructure en cours*.

---

## Structure des fichiers

```
server.py              API Flask et point d'entrée de l'interface web
frontend/              Interface HTML/CSS/JavaScript
app.py                 Ancienne interface Streamlit conservée temporairement
assistant.py           Moteur conversationnel (intentions, entités, réponses)
donnees_source.py      Accès aux données — SQL Server avec repli CSV
train_and_save.py      Entraînement et sérialisation des modèles
gen_v3.py              Génération du jeu de données (structure causale)
requirements.txt       Dépendances Python

modele/                Généré par train_and_save.py
  modele_regression.pkl
  modele_classification.pkl
  metadonnees.json

donnees/               Généré par train_and_save.py
  portefeuille.csv
  depenses.csv
```

---

## En cas de problème

**« Modèles introuvables »**
Exécuter `python train_and_save.py` avant de lancer l'application.

**L'application affiche 🟡 alors que SQL Server tourne**
Vérifier que le pilote *ODBC Driver 17 for SQL Server* est installé, et que le nom de la
base correspond bien à `TGCC_Budget_V3`. L'application reste pleinement fonctionnelle en
mode instantané.

**Le serveur Flask ne démarre pas**
Vérifier que les dépendances sont installées avec `pip install -r requirements.txt`, puis
lancer `python server.py` depuis le dossier de l'application.

**Le port 5000 est déjà utilisé**
Sous Windows PowerShell : `$env:PORT=5001; python server.py`, puis ouvrir
`http://127.0.0.1:5001`.

---

## Pour la démonstration

Un enchaînement qui fonctionne bien en une poignée de minutes :

1. **Portefeuille** — poser le décor : 144 chantiers, la répartition des risques, l'encart
   d'alerte précoce
2. **Simulation** — saisir un projet d'infrastructure public en région éloignée, montrer que
   le modèle annonce un risque critique, puis rebasculer sur un résidentiel privé pour
   montrer l'écart
3. **Assistant** — cliquer sur la suggestion « Alerte précoce », laisser le jury lire les
   six chantiers concernés, puis poser une question libre
4. **À propos** — enchaîner sur les métriques et les limites, avant même qu'on ne vous les
   demande

Le moment fort est l'alerte précoce : ces six chantiers ne seraient signalés par aucun
indicateur classique, et une intervention y reste possible.
