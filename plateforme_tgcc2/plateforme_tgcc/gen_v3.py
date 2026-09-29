"""
Generation des donnees TGCC v3 - structure CAUSALE realiste.

Difference fondamentale avec les versions precedentes :
la derive budgetaire n'est PAS un multiplicateur fixe connu des le mois 1.
Elle se CONSTRUIT mois apres mois sous l'effet de :
  - facteurs structurels observables (type de projet, marche public, taille,
    region, fiabilite des fournisseurs, duree)
  - une derive qui s'auto-entretient (un chantier qui derape continue de deraper)
  - des chocs aleatoires non predictibles (aleas geotechniques, litiges,
    ruptures d'approvisionnement, intemperies)

Consequence : un modele entraine sur les 3 premiers mois peut expliquer une
PARTIE du depassement final, jamais la totalite. C'est ce qui rend l'exercice
de prediction methodologiquement defendable.
"""

import random
import numpy as np
from datetime import date, timedelta
from collections import defaultdict

random.seed(42)
np.random.seed(42)

# =====================================================================
# REFERENTIELS
# =====================================================================
VILLES = [
    # (ville, region, lat, lon, eloignement_logistique)
    ("Casablanca", "Casablanca-Settat", 33.5731, -7.5898, 0.0),
    ("Mohammedia", "Casablanca-Settat", 33.6866, -7.3830, 0.0),
    ("El Jadida", "Casablanca-Settat", 33.2549, -8.5061, 0.1),
    ("Settat", "Casablanca-Settat", 33.0010, -7.6166, 0.1),
    ("Berrechid", "Casablanca-Settat", 33.2655, -7.5877, 0.1),
    ("Rabat", "Rabat-Sale-Kenitra", 34.0209, -6.8416, 0.0),
    ("Sale", "Rabat-Sale-Kenitra", 34.0531, -6.7985, 0.0),
    ("Kenitra", "Rabat-Sale-Kenitra", 34.2610, -6.5802, 0.1),
    ("Temara", "Rabat-Sale-Kenitra", 33.9287, -6.9067, 0.0),
    ("Tanger", "Tanger-Tetouan-Al Hoceima", 35.7595, -5.8340, 0.1),
    ("Tetouan", "Tanger-Tetouan-Al Hoceima", 35.5785, -5.3684, 0.2),
    ("Al Hoceima", "Tanger-Tetouan-Al Hoceima", 35.2517, -3.9372, 0.4),
    ("Marrakech", "Marrakech-Safi", 31.6295, -7.9811, 0.1),
    ("Safi", "Marrakech-Safi", 32.2994, -9.2372, 0.3),
    ("Essaouira", "Marrakech-Safi", 31.5085, -9.7595, 0.3),
    ("Fes", "Fes-Meknes", 34.0331, -5.0003, 0.2),
    ("Meknes", "Fes-Meknes", 33.8935, -5.5473, 0.2),
    ("Agadir", "Souss-Massa", 30.4278, -9.5981, 0.2),
    ("Taroudant", "Souss-Massa", 30.4703, -8.8770, 0.4),
    ("Oujda", "L'Oriental", 34.6814, -1.9086, 0.4),
    ("Nador", "L'Oriental", 35.1681, -2.9287, 0.4),
    ("Beni Mellal", "Beni Mellal-Khenifra", 32.3373, -6.3498, 0.3),
    ("Khouribga", "Beni Mellal-Khenifra", 32.8811, -6.9063, 0.3),
    ("Laayoune", "Laayoune-Sakia El Hamra", 27.1253, -13.1625, 0.8),
    ("Dakhla", "Dakhla-Oued Ed-Dahab", 23.7185, -15.9370, 1.0),
    ("Errachidia", "Draa-Tafilalet", 31.9314, -4.4245, 0.6),
    ("Ouarzazate", "Draa-Tafilalet", 30.9335, -6.9370, 0.6),
]

# type_projet -> (risque_structurel, poids_beton, nb_etages_max, surface_moy)
TYPES_PROJET = {
    "Infrastructure": (0.075, 0.26, 0,  0),
    "Sante":          (0.060, 0.16, 6,  22000),
    "Tour de bureaux":(0.050, 0.20, 22, 30000),
    "Hotellerie":     (0.042, 0.15, 6,  38000),
    "Industriel":     (0.028, 0.18, 2,  52000),
    "Educatif":       (0.018, 0.15, 4,  25000),
    "Commercial":     (0.022, 0.16, 4,  31000),
    "Sportif":        (0.030, 0.17, 2,  19000),
    "Residentiel":    (0.010, 0.17, 9,  24000),
}

PREFIXES = {
    "Infrastructure": ["Rocade", "Pont", "Echangeur", "Voie Express", "Port Sec",
                       "Extension Tramway", "Station Epuration", "Barrage Collinaire"],
    "Sante": ["Hopital Regional", "Centre Hospitalier", "Clinique", "CHU"],
    "Tour de bureaux": ["Tour", "Business Center", "Immeuble Siege", "Twin Center"],
    "Hotellerie": ["Complexe Hotelier", "Resort", "Riad Hotel", "Village Vacances"],
    "Industriel": ["Zone Industrielle", "Plateforme Logistique", "Usine",
                   "Entrepot Frigorifique", "Zone Logistique"],
    "Educatif": ["Ecole Superieure", "Campus Universitaire", "Lycee Technique",
                 "Residence Universitaire", "Groupe Scolaire"],
    "Commercial": ["Centre Commercial", "Marche de Gros", "Galerie Marchande", "Retail Park"],
    "Sportif": ["Complexe Sportif", "Centre Aquatique", "Stade Municipal", "Salle Omnisports"],
    "Residentiel": ["Residence", "Lotissement", "Cite", "Villas", "Programme Habitat"],
}
SUFFIXES = ["Al Manar", "Al Wahda", "Al Massira", "Al Andalous", "Al Qods", "Al Fath",
            "Al Amal", "Nour", "Atlas", "Les Jardins", "Le Parc", "Riviera", "Al Boustane",
            "Saiss", "Anfa", "Zenata", "Sud", "Nord", "Centre", "Al Mostakbal", "Nakhil"]

CHEFS = ["Karim Benjelloun","Salma Idrissi","Youssef Amrani","Nadia Chraibi","Omar Bennani",
         "Hicham Alaoui","Amine Tazi","Fatima Zahra Rais","Rachid El Fassi","Laila Mekouar",
         "Mehdi Sekkat","Sanaa Berrada","Zineb Ouahbi","Adil Naciri","Imane Belghiti",
         "Anas Fikri","Btissam Zerouali","Hamza Belkadi","Ghita Lahlou","Younes Karimi",
         "Nawal Sbai","Mounir Haddadi","Kenza Bouzidi","Tarik Ouazzani","Meryem Kadiri",
         "Ismail Bennis","Souad Amrani","Khalid Serhani","Rim Filali","Othmane Berrada"]

MO_PRIVE = ["Groupe Chaabi Immobilier","Prestigia Immobilier","Groupe Alliances",
            "Palmeraie Developpement","Atlas Invest Group","Anfa Realties SA",
            "Addoha Promotion","Yamed Capital","Marjane Holding","CGI Maroc"]
MO_PUBLIC = ["Ministere de l'Equipement","Ministere de la Sante","Al Omrane",
             "Ministere Enseignement Superieur","Conseil Regional","Commune Urbaine",
             "ANP Maroc","ONCF","Ministere de l'Habitat"]

CATS = [
    (1, "Beton",             0.17), (2, "Acier",             0.13),
    (3, "Main d'oeuvre",     0.23), (4, "Sous-traitance",    0.15),
    (5, "Electricite",       0.07), (6, "Location d'engins", 0.08),
    (7, "Carburant",         0.05), (8, "Transport",         0.05),
    (9, "Securite",          0.04), (10,"Divers",            0.03),
]

FO = [
 ("FR001","Ciments du Maroc Distribution","Beton","Casablanca","0522-11-22-33",5),
 ("FR002","Betons Prets Atlas","Beton","Rabat","0537-45-12-90",4),
 ("FR003","Holcim Beton Services","Beton","Marrakech","0524-33-88-21",5),
 ("FR004","Beton Express Sud","Beton","Agadir","0528-71-40-33",2),
 ("FR005","Sonasid Aciers","Acier","Casablanca","0522-44-55-66",5),
 ("FR006","Armatures du Nord SARL","Acier","Tanger","0539-77-12-45",4),
 ("FR007","Longometal Maroc","Acier","Casablanca","0522-90-31-77",3),
 ("FR008","Acier Trading Oriental","Acier","Oujda","0536-52-18-04",2),
 ("FR009","Interim BTP Maroc","Main d'oeuvre","Casablanca","0537-12-34-56",4),
 ("FR010","Groupement Ouvriers Qualifies","Main d'oeuvre","Rabat","0522-98-76-54",3),
 ("FR011","Atlas Main d'Oeuvre SARL","Main d'oeuvre","Marrakech","0524-19-28-37",4),
 ("FR012","Manpower Chantiers Nord","Main d'oeuvre","Tanger","0539-63-90-12",2),
 ("FR013","Etancheite Pro SARL","Sous-traitance","Casablanca","0539-22-33-44",4),
 ("FR014","Plomberie & VRD Services","Sous-traitance","Rabat","0537-66-11-99",3),
 ("FR015","Menuiserie Alu Sud","Sous-traitance","Agadir","0528-84-15-62",4),
 ("FR016","Second Oeuvre Atlas","Sous-traitance","Fes","0535-27-61-38",2),
 ("FR017","Electricite Generale du BTP","Electricite","Casablanca","0524-55-66-77",5),
 ("FR018","Nexans Maroc Cables","Electricite","Mohammedia","0523-31-40-58",5),
 ("FR019","Elec Chantier Oriental","Electricite","Nador","0536-19-72-45",2),
 ("FR020","Location Grues Atlas","Location d'engins","Casablanca","0522-71-63-04",4),
 ("FR021","Engins TP Location","Location d'engins","Fes","0535-60-27-83",3),
 ("FR022","Manutention Chantier Nord","Location d'engins","Tanger","0539-15-74-20",4),
 ("FR023","Petrom Distribution Pro","Carburant","Casablanca","0522-38-91-16",5),
 ("FR024","Afriquia Gaz Chantiers","Carburant","Agadir","0528-47-02-95",4),
 ("FR025","Transport Lourd Maghreb","Transport","Casablanca","0522-26-58-71",3),
 ("FR026","Logistique Chantiers Sud","Transport","Marrakech","0524-08-63-49",4),
 ("FR027","Transit Sahara Logistics","Transport","Laayoune","0528-93-11-07",2),
 ("FR028","Securite Chantier Maroc","Securite","Rabat","0537-93-24-10",5),
 ("FR029","EPI Protection Pro","Securite","Casablanca","0522-52-17-86",4),
 ("FR030","Fournitures Generales BTP","Divers","Casablanca","0522-64-39-27",3),
]
FO_BY_CAT = defaultdict(list)
for f in FO:
    FO_BY_CAT[f[2]].append((f[0], f[5]))

STATUTS_PAIEMENT = ["Paye","Paye","Paye","En attente","En retard"]
MODES_PAIEMENT = ["Virement","Virement","Cheque","Traite","Especes"]
MOIS_NOM = ["Janvier","Fevrier","Mars","Avril","Mai","Juin","Juillet","Aout",
            "Septembre","Octobre","Novembre","Decembre"]
JOUR_SEM = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

# =====================================================================
# GENERATION DES CHANTIERS
# =====================================================================
N_TERMINES = 112   
N_EN_COURS = 32    

chantiers, transactions, avancement, effectifs = [], [], [], []
features_ml = []
facture_n = 0
noms_utilises = set()

def add_month(y, m, k):
    total = (y * 12 + (m - 1)) + k
    return total // 12, total % 12 + 1

for idx in range(1, N_TERMINES + N_EN_COURS + 1):
    cid = f"CH{idx:04d}"
    est_termine = idx <= N_TERMINES

    typ = random.choice(list(TYPES_PROJET.keys()))
    risque_type, poids_beton, etages_max, surf_moy = TYPES_PROJET[typ]
    ville, region, lat, lon, eloignement = random.choice(VILLES)
    marche = "Public" if random.random() < 0.42 else "Prive"
    mo = random.choice(MO_PUBLIC if marche == "Public" else MO_PRIVE)

    for _ in range(50):
        nom = f"{random.choice(PREFIXES[typ])} {random.choice(SUFFIXES)}"
        if nom not in noms_utilises:
            noms_utilises.add(nom); break
    else:
        nom = f"{random.choice(PREFIXES[typ])} {random.choice(SUFFIXES)} {idx}"

    budget = round(np.random.lognormal(mean=17.3, sigma=0.85))
    budget = int(min(max(budget, 4_500_000), 165_000_000))
    duree = int(np.clip(round(8 + np.log10(budget / 1e6) * 6 + random.gauss(0, 2)), 8, 26))

    superficie = 0 if typ == "Infrastructure" else int(surf_moy * random.uniform(0.5, 1.7))
    etages = 0 if etages_max == 0 else random.randint(1, etages_max)

    # fournisseurs attitres du chantier -> determine la fiabilite moyenne
    fourn_chantier = {c[1]: random.choice(FO_BY_CAT[c[1]]) for c in CATS}
    note_moy = float(np.mean([v[1] for v in fourn_chantier.values()]))

    # fenetre temporelle
    if est_termine:
        y0 = random.choice([2023, 2023, 2024])
        m0 = random.randint(1, 12 if y0 == 2023 else 6)
        duree = min(duree, (2024 - y0) * 12 + (12 - m0) + 1)
        duree = max(duree, 8)
    else:
        y0, m0 = 2025, random.randint(1, 5)
        duree = min(duree, 12 - m0 + 1)
        duree = max(duree, 6)

    d_debut = date(y0, m0, 1)
    yf, mf = add_month(y0, m0, duree - 1)
    d_fin = date(yf, mf, 28)

    # -----------------------------------------------------------------
    # MODELE CAUSAL DU RISQUE
    # -----------------------------------------------------------------
    # 1) composante STRUCTURELLE observable (le modele ML peut l'apprendre)
    risque_structurel = (
        risque_type
        + (0.030 if marche == "Public" else 0.0)
        + 0.022 * (np.log10(budget / 1e6) - 1.0)
        + 0.045 * eloignement
        + 0.020 * (3.5 - note_moy)
        + 0.0020 * (duree - 14)
    )
    # 2) composante LATENTE non observable (qualite reelle du pilotage, terrain...)
    latent = random.gauss(0.0, 0.028)
    # 3) efficacite de base : une partie des chantiers finit sous budget
    propension = risque_structurel + latent - 0.030

    # -----------------------------------------------------------------
    # DEROULEMENT MOIS PAR MOIS
    # -----------------------------------------------------------------
    budget_mensuel = budget / duree
    derive_cum = 0.0          # derive accumulee (s'auto-entretient)
    retard_cum = 0.0          # retard de planning accumule (en points de %)
    tot_prevu = tot_reel = 0.0
    prevu_3m = reel_3m = 0.0
    retard_3m = None
    chocs_subis = 0

    for m in range(duree):
        y, mo_num = add_month(y0, m0, m)
        prog = 0.55 + 0.9 * (m / max(duree - 1, 1))

        # la derive du mois : tendance de fond + inertie + choc eventuel
        # le profil de risque n'est PAS fige : il evolue en cours de chantier
        # (rotation d'equipe, defaillance d'un fournisseur, modification du
        # programme, revision des prix). Marche aleatoire -> le risque observe
        # au mois 3 n'est qu'une ESTIMATION du risque futur, pas une certitude.
        propension += random.gauss(0.0, 0.009)
        incr = propension * random.uniform(0.16, 0.34)
        # inertie legere : un chantier qui derape a tendance a continuer
        incr += derive_cum * 0.020
        # choc aleatoire NON PREDICTIBLE : survient majoritairement APRES le
        # 3e mois, donc invisible dans les features d'entree du modele.
        # C'est ce mecanisme qui plafonne volontairement la performance ML.
        p_choc = 0.030 if m < 3 else 0.085
        if random.random() < p_choc:
            chocs_subis += 1
            incr += abs(random.gauss(0.022, 0.020))
        # intemperies : surcout en hiver sur les chantiers exposes
        if mo_num in (12, 1, 2) and typ in ("Infrastructure", "Industriel"):
            incr += random.uniform(0.0, 0.010)
        derive_cum = float(np.clip(derive_cum + incr, -0.09, 0.42))

        # retard de planning correle a la derive de cout
        retard_mois = derive_cum * random.uniform(15, 30) + random.gauss(0, 1.2)
        retard_cum = max(0.0, retard_cum * 0.75 + max(0.0, retard_mois) * 0.25)

        mult_mois = 1.0 + derive_cum + random.gauss(0, 0.012)

        # ---- transactions du mois (une ligne par categorie)
        for cat_id, cat_nom, poids in CATS:
            if random.random() > 0.94:
                continue
            p = poids if cat_nom != "Beton" else poids_beton
            prevu = round(budget_mensuel * p * prog, 2)
            reel = round(prevu * mult_mois * random.uniform(0.95, 1.05), 2)
            facture_n += 1
            transactions.append((
                cid, fourn_chantier[cat_nom][0], cat_id,
                date(y, mo_num, random.randint(1, 28)),
                f"FA-{y}-{facture_n:06d}", prevu, reel,
                random.choice(STATUTS_PAIEMENT), random.choice(MODES_PAIEMENT),
            ))
            tot_prevu += prevu; tot_reel += reel
            if m < 3:
                prevu_3m += prevu; reel_3m += reel

        # ---- avancement
        av_prevu = round(min(100.0, (m + 1) / duree * 100), 1)
        av_reel = round(max(0.0, min(100.0, av_prevu - retard_cum)), 1)
        if av_prevu - av_reel > 8:
            com = "Retard constate - action corrective requise"
        elif av_reel >= av_prevu - 1:
            com = "Avancement conforme au planning"
        else:
            com = random.choice(["RAS", "Livraison materiaux a temps", "Leger retard rattrapable"])
        phase = "Gros oeuvre" if av_prevu < 45 else ("Second oeuvre" if av_prevu < 80 else "Finitions")
        avancement.append((cid, date(y, mo_num, 1), phase, av_prevu, av_reel, com))
        if m == 2:
            retard_3m = round(av_reel - av_prevu, 2)

        # ---- effectifs
        base = max(10, int(budget / 1_300_000))
        nb_ouv = int(base * random.uniform(0.75, 1.25))
        nb_ing = max(1, int(nb_ouv / random.uniform(9, 14)))
        effectifs.append((cid, date(y, mo_num, 1), nb_ouv, nb_ing,
                          round(nb_ouv * random.uniform(150, 190), 1),
                          random.randint(0, max(1, nb_ouv // 12))))

    statut = "Termine" if est_termine else "En cours"
    chantiers.append((cid, nom, mo, f"Zone {random.randint(1,9)}, {ville}", ville, region,
                      lat, lon, typ, marche, superficie, etages, random.choice(CHEFS),
                      d_debut, d_fin, statut, budget))

    depassement_final = (tot_reel - tot_prevu) / tot_prevu
    features_ml.append({
        "ID_Chantier": cid, "Nom_Projet": nom, "est_termine": est_termine,
        # --- features connues des le mois 3 ---
        "Type_Projet": typ, "Type_Marche": marche, "Region": region,
        "Budget_Prevu_Total": budget, "Duree_Mois": duree,
        "Superficie_m2": superficie, "Nb_Etages": etages,
        "Note_Fiabilite_Moy": round(note_moy, 2),
        "Eloignement": eloignement,
        "Ecart_Cout_3M": round((reel_3m - prevu_3m) / prevu_3m, 4) if prevu_3m else 0.0,
        "Ecart_Planning_3M": retard_3m if retard_3m is not None else 0.0,
        # --- cible (connue uniquement pour les chantiers termines) ---
        "Depassement_Final": round(depassement_final, 4),
        "Chocs": chocs_subis,
    })


calendrier = []
d = date(2023, 1, 1)
while d <= date(2025, 12, 31):
    t = (d.month - 1) // 3 + 1
    calendrier.append((d, d.year, d.month, MOIS_NOM[d.month - 1], f"T{t}",
                       d.day, JOUR_SEM[d.weekday()], d.isocalendar()[1],
                       1 if d.day == 1 else 0))
    d += timedelta(days=1)

if __name__ == "__main__":
    import pandas as pd
    df = pd.DataFrame(features_ml)
    print(f"chantiers    : {len(chantiers)}  (termines {df.est_termine.sum()}, en cours {(~df.est_termine).sum()})")
    print(f"transactions : {len(transactions)}")
    print(f"avancement   : {len(avancement)}")
    print(f"effectifs    : {len(effectifs)}")
    print(f"calendrier   : {len(calendrier)}")
    t = df[df.est_termine]
    print(f"\ndepassement final (termines) : moy {t.Depassement_Final.mean():.1%}  "
          f"min {t.Depassement_Final.min():.1%}  max {t.Depassement_Final.max():.1%}")
    bins = [-1, 0.05, 0.10, 0.20, 99]
    lab = ["Faible", "Modere", "Eleve", "Critique"]
    print(pd.cut(t.Depassement_Final, bins=bins, labels=lab).value_counts().reindex(lab))
    print(f"\ncorrelation Ecart_Cout_3M / Depassement_Final : {t.Ecart_Cout_3M.corr(t.Depassement_Final):.3f}")
    print(f"correlation Ecart_Planning_3M / Depassement_Final : {t.Ecart_Planning_3M.corr(t.Depassement_Final):.3f}")
