"""
TGCC — Plateforme de prévision des écarts budgétaires

Application complémentaire au tableau de bord Power BI. Là où le tableau de bord
pilote le portefeuille existant, cette plateforme permet :
  - de simuler le risque d'un chantier qui n'est pas encore en base ;
  - d'explorer le portefeuille et les prédictions ;
  - d'interroger les données en langage naturel.

Lancement :  streamlit run app.py
"""

import io
import json
import os
from datetime import date, datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import streamlit as st

import donnees_source
import assistant
import db_utils

BASE = os.path.dirname(os.path.abspath(__file__))

BORDEAUX = '#6B1E2B'
ROUGE = '#6B1E2B'      # alias — plus de rouge vif, tout est bordeaux
ORANGE = '#6B1E2B'     # alias — plus d'orange, remplacé par bordeaux
NOIR = '#1A1A1A'
GRIS_TEXTE = '#4A4A4A'
GRIS_MOYEN = '#8A8A8A'
GRIS_BORDURE = '#E5E5E5'
GRIS_FOND = '#FAFAFA'

COULEUR_RISQUE = {'Faible': '#2E7D32', 'Modéré': '#E8792C',
                  'Élevé': '#C41E3A', 'Critique': '#6B1E2B'}
ICONE_RISQUE = {'Faible': '🟢', 'Modéré': '🟠', 'Élevé': '🔴', 'Critique': '⛔'}

LOGO = os.path.join(BASE, 'assets', 'logo_tgcc.png')

st.set_page_config(page_title='TGCC — Prévision budgétaire',
                   page_icon=LOGO if os.path.exists(LOGO) else '🏗️',
                   layout='wide')

st.markdown(f"""
<style>
  /* ============ MINIMALISTE — bordeaux · gris · blanc ============ */

  /* Base */
  .stApp {{
      background: #FFFFFF;
      color: {NOIR};
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif;
  }}
  .block-container {{ padding-top: 2.5rem; max-width: 1200px; }}
  h1, h2, h3, h4 {{ color: {NOIR}; font-weight: 600; letter-spacing: -0.01em; }}

  /* Bandeau — plus de gradient, juste une accroche typographique */
  .bandeau {{
      background: transparent; padding: 0 0 24px 0;
      margin-bottom: 32px; border-bottom: 1px solid {GRIS_BORDURE};
      position: relative;
  }}
  .bandeau .eyebrow {{
      color: {BORDEAUX}; font-size: 11.5px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.14em;
      margin: 0 0 10px 0;
  }}
  .bandeau h1 {{
      color: {NOIR} !important; margin: 0; font-size: 32px;
      font-weight: 700; letter-spacing: -0.02em; line-height: 1.15;
  }}
  .bandeau p {{
      color: {GRIS_MOYEN}; margin: 8px 0 0 0; font-size: 15px;
      font-weight: 400; max-width: 720px;
  }}
  .bandeau-logo {{
      position: absolute; right: 0; top: 4px;
      height: 42px;
  }}

  /* Encart — trait fin bordeaux, sans ombre */
  .encart {{
      background: {GRIS_FOND}; border-left: 2px solid {BORDEAUX};
      padding: 14px 20px; border-radius: 0;
      font-size: 14px; line-height: 1.6; color: {GRIS_TEXTE};
      margin: 16px 0;
  }}

  /* Inputs — bordures fines, focus bordeaux */
  div[data-baseweb="select"] > div,
  div[data-testid="stNumberInput"] input,
  div[data-testid="stTextInput"] input {{
      border-radius: 4px !important;
      border: 1px solid {GRIS_BORDURE} !important;
      background: #FFFFFF !important;
      box-shadow: none !important;
  }}
  div[data-baseweb="select"] > div:hover,
  div[data-testid="stNumberInput"] input:hover,
  div[data-testid="stTextInput"] input:hover {{
      border-color: {NOIR} !important;
  }}
  div[data-baseweb="select"] > div:focus-within,
  div[data-testid="stNumberInput"] input:focus,
  div[data-testid="stTextInput"] input:focus {{
      border-color: {BORDEAUX} !important;
      box-shadow: 0 0 0 3px rgba(107, 30, 43, 0.10) !important;
  }}
  label p {{
      font-weight: 500; color: {NOIR}; font-size: 13.5px !important;
      margin-bottom: 4px !important;
  }}

  /* Saisie directe — pas de +/- */
  div[data-testid="stNumberInput"] button {{ display: none !important; }}
  div[data-testid="stNumberInput"] input {{
      -moz-appearance: textfield; padding-right: 12px !important;
  }}
  div[data-testid="stNumberInput"] input::-webkit-outer-spin-button,
  div[data-testid="stNumberInput"] input::-webkit-inner-spin-button {{
      -webkit-appearance: none; margin: 0;
  }}

  /* Boutons — plat, bordeaux, sans ombre */
  .stButton > button, .stFormSubmitButton > button {{
      border-radius: 4px; font-weight: 500;
      padding: 10px 22px; transition: background 0.15s ease;
      border: 1px solid {GRIS_BORDURE};
      background: #FFFFFF; color: {NOIR};
      box-shadow: none !important;
  }}
  .stButton > button:hover, .stFormSubmitButton > button:hover {{
      border-color: {NOIR}; color: {NOIR};
  }}
  .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
      background: {BORDEAUX}; color: #FFFFFF; border: 1px solid {BORDEAUX};
  }}
  .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
      background: #4A0F1A; border-color: #4A0F1A;
  }}

  /* Metrics — pas de carte, juste typographie */
  div[data-testid="stMetric"] {{
      background: transparent; padding: 0;
      border: none; border-left: 2px solid {BORDEAUX};
      padding-left: 16px;
  }}
  div[data-testid="stMetricValue"] {{
      font-size: 30px; font-weight: 600; color: {NOIR};
      letter-spacing: -0.02em;
  }}
  div[data-testid="stMetricLabel"] {{
      font-size: 11.5px; font-weight: 500;
      text-transform: uppercase; letter-spacing: 0.1em;
      color: {GRIS_MOYEN};
  }}
  div[data-testid="stMetricDelta"] {{ font-size: 12.5px; color: {GRIS_MOYEN}; }}

  /* ============ SIDEBAR — sophistiqué ============ */
  section[data-testid="stSidebar"] {{
      background: #FFFFFF;
      border-right: 1px solid {GRIS_BORDURE};
  }}
  section[data-testid="stSidebar"] > div:first-child {{
      padding-top: 1.5rem;
  }}

  /* Bloc logo — encadré discret */
  .sb-logo-box {{
      padding: 20px 18px 22px 18px;
      margin: -8px 0 4px 0;
      border-bottom: 1px solid {GRIS_BORDURE};
      text-align: center;
  }}
  .sb-logo-box img {{ max-height: 88px; width: auto; }}
  .sb-tagline {{
      display: block; margin-top: 10px;
      font-size: 10.5px; text-transform: uppercase;
      letter-spacing: 0.18em; color: {GRIS_MOYEN};
      font-weight: 500;
  }}

  /* Labels de section */
  .sb-section {{
      font-size: 10.5px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.16em;
      color: {GRIS_MOYEN};
      margin: 22px 0 10px 4px;
  }}

  /* Radio → navigation full-width */
  section[data-testid="stSidebar"] div[role="radiogroup"] {{
      gap: 2px !important; display: flex; flex-direction: column;
  }}
  section[data-testid="stSidebar"] div[role="radiogroup"] label {{
      position: relative;
      padding: 10px 14px 10px 18px !important;
      margin: 0 !important;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.15s ease, color 0.15s ease;
      font-size: 14px !important;
      color: {GRIS_TEXTE} !important;
  }}
  /* Masquer le rond du radio */
  section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{
      display: none !important;
  }}
  section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
      background: {GRIS_FOND};
      color: {NOIR} !important;
  }}
  /* État actif via l'input checked */
  section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
      background: rgba(107, 30, 43, 0.06);
      color: {BORDEAUX} !important;
      font-weight: 600;
  }}
  section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::before {{
      content: ""; position: absolute; left: 0; top: 8px; bottom: 8px;
      width: 3px; background: {BORDEAUX}; border-radius: 0 2px 2px 0;
  }}
  section[data-testid="stSidebar"] div[role="radiogroup"] label p {{
      color: inherit !important; font-weight: inherit !important;
      font-size: 14px !important;
  }}

  /* Carte info système */
  .sb-info {{
      margin-top: 8px;
      background: {GRIS_FOND};
      border: 1px solid {GRIS_BORDURE};
      border-radius: 6px;
      padding: 12px 14px;
  }}
  .sb-info-row {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px solid {GRIS_BORDURE};
      font-size: 12.5px;
  }}
  .sb-info-row:last-child {{ border-bottom: none; }}
  .sb-info-label {{
      color: {GRIS_MOYEN}; text-transform: uppercase;
      letter-spacing: 0.06em; font-size: 10.5px; font-weight: 500;
  }}
  .sb-info-value {{
      color: {NOIR}; font-weight: 600; font-size: 13px;
      display: flex; align-items: center; gap: 6px;
  }}
  .sb-dot {{
      width: 6px; height: 6px; border-radius: 50%;
      background: {BORDEAUX}; display: inline-block;
      box-shadow: 0 0 0 3px rgba(107, 30, 43, 0.15);
  }}
  .sb-dot.warn {{
      background: {GRIS_MOYEN};
      box-shadow: 0 0 0 3px rgba(138, 138, 138, 0.18);
  }}

  /* Footer sidebar */
  .sb-footer {{
      margin-top: 32px; padding-top: 14px;
      border-top: 1px solid {GRIS_BORDURE};
      font-size: 10.5px; color: {GRIS_MOYEN};
      text-align: center; letter-spacing: 0.06em;
  }}

  /* Divider */
  hr {{ border-color: {GRIS_BORDURE} !important; margin: 24px 0 !important; }}

  /* Chat */
  div[data-testid="stChatMessage"] {{
      background: {GRIS_FOND}; border: 1px solid {GRIS_BORDURE};
      border-radius: 6px;
  }}

  /* Expander */
  div[data-testid="stExpander"] {{
      border: 1px solid {GRIS_BORDURE}; border-radius: 4px;
      background: #FFFFFF; box-shadow: none;
  }}
  div[data-testid="stExpander"] summary {{ font-weight: 500; color: {NOIR}; }}

  /* Dataframe */
  div[data-testid="stDataFrame"] {{ border: 1px solid {GRIS_BORDURE}; border-radius: 4px; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def charger_modeles():
    reg = joblib.load(os.path.join(BASE, 'modele', 'modele_regression.pkl'))
    clf = joblib.load(os.path.join(BASE, 'modele', 'modele_classification.pkl'))
    with open(os.path.join(BASE, 'modele', 'metadonnees.json'), encoding='utf-8') as f:
        meta = json.load(f)
    return reg, clf, meta


try:
    modele_reg, modele_clf, META = charger_modeles()
except FileNotFoundError:
    st.error("Modèles introuvables. Exécutez d'abord : `python train_and_save.py`")
    st.stop()

portefeuille, depenses, SOURCE = donnees_source.charger()


def mad(v):
    v = float(v)
    if abs(v) >= 1e9:
        return f"{v/1e9:.2f} Md MAD"
    if abs(v) >= 1e6:
        return f"{v/1e6:.1f} M MAD"
    return f"{v:,.0f} MAD".replace(',', ' ')


def _logo_b64():
    if not os.path.exists(LOGO):
        return None
    import base64
    with open(LOGO, 'rb') as f:
        return base64.b64encode(f.read()).decode()


def generer_pdf(donnees, prediction):
    """Génère un PDF de synthèse de la simulation. Retourne les bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.units import cm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, Image as RLImage,
                                    HRFlowable)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    bord = rl_colors.HexColor(BORDEAUX)
    gris = rl_colors.HexColor('#8A8A8A')
    gris_clair = rl_colors.HexColor('#E5E5E5')
    gris_fond = rl_colors.HexColor('#FAFAFA')
    noir = rl_colors.HexColor(NOIR)

    # Styles typographiques avec interlignage (leading) explicite
    s_eyebrow = ParagraphStyle('eyebrow', fontName='Helvetica-Bold',
                               fontSize=8.5, leading=11, textColor=bord,
                               alignment=TA_LEFT, spaceAfter=4)
    s_titre = ParagraphStyle('titre', fontName='Helvetica-Bold',
                             fontSize=22, leading=26, textColor=noir,
                             alignment=TA_LEFT, spaceAfter=2)
    s_meta = ParagraphStyle('meta', fontName='Helvetica',
                            fontSize=9.5, leading=12, textColor=gris,
                            alignment=TA_LEFT)
    s_section = ParagraphStyle('section', fontName='Helvetica-Bold',
                               fontSize=9, leading=12, textColor=bord,
                               alignment=TA_LEFT, spaceBefore=4, spaceAfter=6)

    story = []

    # ---- En-tête : logo à gauche + bloc titre à droite ----
    if os.path.exists(LOGO):
        logo = RLImage(LOGO, width=4.5*cm, height=2.8*cm, kind='proportional')
        entete = Table(
            [[logo,
              [Paragraph('SIMULATION BUDGÉTAIRE', s_eyebrow),
               Paragraph(donnees.get('nom') or 'Chantier sans nom', s_titre),
               Paragraph(f'Émis le {datetime.now().strftime("%d/%m/%Y à %H:%M")}',
                         s_meta)]]],
            colWidths=[5.4*cm, 11.6*cm])
        entete.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(entete)
    else:
        story.append(Paragraph('SIMULATION BUDGÉTAIRE', s_eyebrow))
        story.append(Paragraph(donnees.get('nom') or 'Chantier sans nom', s_titre))
        story.append(Paragraph(
            f'Émis le {datetime.now().strftime("%d/%m/%Y à %H:%M")}', s_meta))

    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=gris_clair))
    story.append(Spacer(1, 0.5*cm))

    # ---- Bloc caractéristiques ----
    story.append(Paragraph('CARACTÉRISTIQUES DU CHANTIER', s_section))

    caract = [
        ['Nom du chantier', donnees.get('nom') or '—'],
        ['Ville', donnees.get('ville') or '—'],
        ['Région', donnees['region']],
        ['Type de projet', donnees['type_projet']],
        ['Type de marché', donnees['type_marche']],
        ['Type de sol', donnees.get('type_sol') or '—'],
        ['Budget prévisionnel', mad(donnees['budget'])],
        ['Marge commerciale cible', f"{donnees.get('marge', 0):.1f} %"],
        ['Date de démarrage', donnees.get('date_debut') or '—'],
        ['Date de fin estimée', donnees.get('date_fin') or '—'],
        ['Durée prévue', f"{donnees['duree']} mois"],
        ['Superficie', f"{donnees['superficie']:,} m²".replace(',', ' ')],
        ["Nombre d'étages", str(donnees['etages'])],
        ['Fiabilité fournisseurs', f"{donnees['fiabilite']:.1f} / 5"],
    ]
    t = Table(caract, colWidths=[6*cm, 11*cm])
    t.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica', 9.5),
        ('FONT', (1, 0), (1, -1), 'Helvetica-Bold', 9.5),
        ('TEXTCOLOR', (0, 0), (0, -1), gris),
        ('TEXTCOLOR', (1, 0), (1, -1), noir),
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, gris_clair),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.8*cm))

    # ---- Bloc résultats ----
    story.append(Paragraph('RÉSULTATS DE LA SIMULATION', s_section))

    marge_pct = donnees.get('marge', 0) / 100
    surcout = prediction['surcout']
    perte_marge = surcout / donnees['budget'] if donnees['budget'] else 0
    verdict_marge = ('Projet resterait rentable'
                     if perte_marge < marge_pct
                     else 'Projet passerait en perte')

    res = [
        ['Dépassement estimé', f"{prediction['depassement']*100:.1f} %"],
        ['Niveau de risque', prediction['classe']],
        ['Confiance du modèle', f"{prediction['confiance']*100:.0f} %"],
        ['Surcoût projeté', mad(surcout)],
        ['Coût total projeté', mad(donnees['budget'] + surcout)],
        ['Impact sur la marge cible', verdict_marge],
    ]
    tr = Table(res, colWidths=[6*cm, 11*cm])
    tr.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica', 9.5),
        ('FONT', (1, 0), (1, -1), 'Helvetica-Bold', 9.5),
        ('TEXTCOLOR', (0, 0), (0, -1), gris),
        ('TEXTCOLOR', (1, 0), (1, -1), noir),
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, gris_clair),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Ligne "Coût total projeté" mise en avant
        ('BACKGROUND', (0, 4), (-1, 4), gris_fond),
        ('LINEBEFORE', (0, 4), (0, 4), 2, bord),
        ('FONT', (1, 4), (1, 4), 'Helvetica-Bold', 11),
        ('TEXTCOLOR', (1, 4), (1, 4), noir),
    ]))
    story.append(tr)

    doc.build(story)
    return buf.getvalue()


def bandeau(titre, sous_titre="", eyebrow="TGCC"):
    logo = _logo_b64()
    badge = (f'<img src="data:image/png;base64,{logo}" class="bandeau-logo"/>'
             if logo else '')
    sous = f'<p>{sous_titre}</p>' if sous_titre else ''
    st.markdown(
        f'<div class="bandeau">{badge}'
        f'<p class="eyebrow">{eyebrow}</p>'
        f'<h1>{titre}</h1>{sous}</div>',
        unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Barre latérale
# ---------------------------------------------------------------------
with st.sidebar:
    logo_b64 = _logo_b64()
    if logo_b64:
        st.markdown(
            f'<div class="sb-logo-box">'
            f'<img src="data:image/png;base64,{logo_b64}"/>'
            f'<span class="sb-tagline">Prévision budgétaire</span>'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="sb-logo-box"><h3 style="margin:0;">TGCC</h3>'
            '<span class="sb-tagline">Prévision budgétaire</span></div>',
            unsafe_allow_html=True)

    st.markdown('<div class="sb-section">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("Navigation", [
        "Simulation d'un chantier",
        "Portefeuille",
        "Assistant",
        "À propos du modèle",
    ], label_visibility='collapsed')

    st.markdown('<div class="sb-section">Système</div>', unsafe_allow_html=True)
    dot_cls = "" if SOURCE == 'SQL Server' else "warn"
    st.markdown(
        f'<div class="sb-info">'
        f'  <div class="sb-info-row">'
        f'    <span class="sb-info-label">Source</span>'
        f'    <span class="sb-info-value"><span class="sb-dot {dot_cls}"></span>{SOURCE}</span>'
        f'  </div>'
        f'  <div class="sb-info-row">'
        f'    <span class="sb-info-label">Entraînement</span>'
        f'    <span class="sb-info-value">{META["date_entrainement"]}</span>'
        f'  </div>'
        f'  <div class="sb-info-row">'
        f'    <span class="sb-info-label">Chantiers</span>'
        f'    <span class="sb-info-value">{len(portefeuille)}</span>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True)

    st.markdown(
        '<div class="sb-footer">TGCC · CONSTRUISONS ENSEMBLE</div>',
        unsafe_allow_html=True)


# =====================================================================
# PAGE 1 — SIMULATION
# =====================================================================
if page == "Simulation d'un chantier":
    bandeau("Simulation du risque de dépassement")

    # ---- Sélecteur : chantier à simuler (chargé depuis la base) ----
    noms = sorted(portefeuille.Nom_Projet.dropna().unique().tolist())

    TYPES_SOL = ['Facile', 'Moyen', 'Difficile', 'Inconnu']

    def _prefill_from_db():
        nom = st.session_state.chantier_source
        row = portefeuille[portefeuille.Nom_Projet == nom].iloc[0]

        def _clip(v, lo, hi):
            return max(lo, min(hi, v))

        st.session_state.sim_nom = str(row.Nom_Projet)
        if pd.notna(row.get('Ville')):
            st.session_state.sim_ville = str(row.Ville)
        if pd.notna(row.get('Date_Debut')):
            st.session_state.sim_date_debut = pd.to_datetime(row.Date_Debut).date()

        if row.Type_Projet in META['options']['Type_Projet']:
            st.session_state.sim_type_projet = row.Type_Projet
        if row.Type_Marche in META['options']['Type_Marche']:
            st.session_state.sim_type_marche = row.Type_Marche
        if row.Region in META['options']['Region']:
            st.session_state.sim_region = row.Region
        if pd.notna(row.Budget_Prevu_Total):
            st.session_state.sim_budget = _clip(int(row.Budget_Prevu_Total),
                                                1_000_000, 500_000_000)
        if pd.notna(row.get('Date_Debut')) and pd.notna(row.get('Date_Fin_Prevue')):
            d1 = pd.to_datetime(row.Date_Debut)
            d2 = pd.to_datetime(row.Date_Fin_Prevue)
            mois = int(round((d2 - d1).days / 30.44))
            st.session_state.sim_duree = _clip(mois, 6, 30)
        if pd.notna(row.get('Superficie_m2')):
            st.session_state.sim_superficie = _clip(int(row.Superficie_m2), 0, 200_000)
        if pd.notna(row.get('Nb_Etages')):
            st.session_state.sim_etages = _clip(int(row.Nb_Etages), 0, 25)
        if pd.notna(row.get('Ecart_Cout_3M')):
            st.session_state.sim_ecart_cout = _clip(
                float(row.Ecart_Cout_3M) * 100, -15.0, 40.0)
        if pd.notna(row.get('Ecart_Planning_3M')):
            st.session_state.sim_ecart_plan = _clip(
                float(row.Ecart_Planning_3M), -25.0, 10.0)

    # Pré-remplissage automatique au premier chargement (avant que les widgets soient rendus).
    if 'chantier_source' not in st.session_state:
        st.session_state.chantier_source = noms[0]
        _prefill_from_db()

    st.selectbox("Chantier à simuler", noms,
                 key='chantier_source', on_change=_prefill_from_db,
                 help=f"{len(noms)} chantiers disponibles dans la source « {SOURCE} »")

    st.markdown("&nbsp;", unsafe_allow_html=True)

    # ---- Champs du formulaire (clés partagées avec le callback ci-dessus) ----
    nom_chantier = st.text_input("Nom du chantier",
                                 placeholder="Ex. Résidence Al Manzah — Tranche 2",
                                 key='sim_nom')
    ville = st.text_input("Ville",
                          placeholder="Ex. Casablanca",
                          key='sim_ville')
    type_projet = st.selectbox("Type de projet", META['options']['Type_Projet'],
                               key='sim_type_projet')
    type_marche = st.selectbox("Type de marché", META['options']['Type_Marche'],
                               key='sim_type_marche')
    region = st.selectbox("Région", META['options']['Region'],
                          key='sim_region')
    type_sol = st.selectbox("Type de sol", TYPES_SOL,
                            key='sim_type_sol',
                            help="Information contextuelle — non prise en compte par le modèle actuel")
    budget = st.number_input("Budget prévisionnel (MAD)",
                             min_value=1_000_000, max_value=500_000_000,
                             value=int(META['defauts']['Budget_Prevu_Total']),
                             step=1_000_000, format="%d",
                             key='sim_budget')
    marge_cible = st.number_input("Marge commerciale cible (%)",
                                  min_value=0.0, max_value=50.0,
                                  value=8.0, step=0.5, format="%.1f",
                                  key='sim_marge',
                                  help="Marge visée sur le projet — permet de savoir si un dépassement rend le projet déficitaire")
    date_debut = st.date_input("Date de démarrage envisagée",
                               value=st.session_state.get('sim_date_debut', date.today()),
                               key='sim_date_debut',
                               format="DD/MM/YYYY")
    duree = st.number_input("Durée prévue (mois)",
                            min_value=6, max_value=30,
                            value=int(META['defauts']['Duree_Mois']),
                            step=1, format="%d",
                            key='sim_duree')
    date_fin = date_debut + timedelta(days=int(duree * 30.44))
    st.caption(f"→ Date de fin estimée : **{date_fin.strftime('%d/%m/%Y')}**")

    superficie = st.number_input("Superficie (m²)", min_value=0, max_value=200_000,
                                 value=int(META['defauts']['Superficie_m2']),
                                 step=1_000, format="%d",
                                 key='sim_superficie')
    etages = st.number_input("Nombre d'étages",
                             min_value=0, max_value=25,
                             value=int(META['defauts']['Nb_Etages']),
                             step=1, format="%d",
                             key='sim_etages')
    fiabilite = st.number_input("Fiabilité moyenne des fournisseurs",
                                min_value=1.0, max_value=5.0,
                                value=float(META['defauts']['Note_Fiabilite_Moy']),
                                step=0.1, format="%.1f",
                                help="Note de 1 (faible) à 5 (excellente)",
                                key='sim_fiabilite')
    # Les indicateurs à 3 mois sont désormais lus depuis la base (via le sélecteur
    # ci-dessus) et valent 0 en saisie manuelle.
    ecart_cout = st.session_state.get('sim_ecart_cout', 0.0) / 100
    ecart_plan = st.session_state.get('sim_ecart_plan', 0.0)

    if st.button("Estimer le risque", type='primary', use_container_width=True):
        eloignement = META['eloignement_par_region'].get(region, 0.2)
        X = pd.DataFrame([{
            'Type_Projet': type_projet, 'Type_Marche': type_marche, 'Region': region,
            'Budget_Prevu_Total': budget, 'Duree_Mois': duree,
            'Superficie_m2': superficie, 'Nb_Etages': etages,
            'Note_Fiabilite_Moy': fiabilite, 'Eloignement': eloignement,
            'Ecart_Cout_3M': ecart_cout, 'Ecart_Planning_3M': ecart_plan,
        }])[META['features']]

        depassement = float(modele_reg.predict(X)[0])
        classe = str(modele_clf.predict(X)[0])
        proba = modele_clf.predict_proba(X)[0]
        confiance = float(proba.max())
        surcout = budget * depassement

        # Persistance en base
        row_src = portefeuille[portefeuille.Nom_Projet == st.session_state.chantier_source]
        if not row_src.empty:
            ok = db_utils.sauvegarder_prediction(
                id_chantier=str(row_src.iloc[0].ID_Chantier),
                depassement_predit=depassement,
                classe_predite=classe,
                confiance=confiance,
                ecart_cout_3m=ecart_cout,
                ecart_planning_3m=ecart_plan,
            )
            if not ok:
                st.toast("Prédiction non enregistrée en base (SQL Server indisponible).", icon="⚠️")

        st.divider()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Dépassement estimé", f"{depassement*100:.1f} %")
        k2.metric("Niveau de risque", f"{ICONE_RISQUE.get(classe,'')} {classe}")
        k3.metric("Surcoût projeté", mad(surcout))
        k4.metric("Confiance du modèle", f"{confiance*100:.0f} %")

        coul = COULEUR_RISQUE.get(classe, ROUGE)
        st.markdown(
            f"""<div style="background:{GRIS_FOND};border-left:2px solid {BORDEAUX};
            padding:18px 22px;margin-top:14px;">
            <div style="font-size:11.5px;text-transform:uppercase;letter-spacing:0.1em;
            color:{GRIS_MOYEN};margin-bottom:6px;">Coût total projeté</div>
            <div style="font-size:24px;font-weight:600;color:{NOIR};letter-spacing:-0.01em;">
            {mad(budget + surcout)}</div>
            <div style="color:{GRIS_MOYEN};font-size:13px;margin-top:4px;">
            Budget initial {mad(budget)} · écart estimé {mad(surcout)}</div>
            </div>""", unsafe_allow_html=True)

        # Verdict par rapport à la marge cible
        marge_pct = marge_cible / 100
        if marge_pct > 0:
            if depassement < marge_pct:
                marge_restante = (marge_pct - depassement) * 100
                verdict_html = (f'<b style="color:{NOIR};">Projet rentable</b> — '
                                f'il resterait <b>{marge_restante:.1f} %</b> de marge '
                                f'après absorption du dépassement estimé.')
            else:
                perte = (depassement - marge_pct) * 100
                verdict_html = (f'<b style="color:{BORDEAUX};">Projet déficitaire</b> — '
                                f'le dépassement estimé consommerait toute la marge '
                                f'({marge_cible:.1f} %) et engendrerait une perte '
                                f"d'environ <b>{perte:.1f} %</b> du budget.")
            st.markdown(
                f"""<div style="background:#FFFFFF;border:1px solid {GRIS_BORDURE};
                padding:14px 20px;margin-top:10px;font-size:14px;color:{GRIS_TEXTE};
                line-height:1.5;">
                <div style="font-size:11.5px;text-transform:uppercase;letter-spacing:0.1em;
                color:{GRIS_MOYEN};margin-bottom:6px;">Impact sur la marge cible</div>
                {verdict_html}</div>""", unsafe_allow_html=True)

        g1, g2 = st.columns([1, 1])
        with g1:
            st.markdown("**Probabilité par classe de risque**")
            dp = pd.DataFrame({'Classe': modele_clf.classes_,
                               'Probabilité': proba}).set_index('Classe')
            st.bar_chart(dp, color=coul, height=240)

        with g2:
            st.markdown("**Positionnement dans le portefeuille**")
            ref = portefeuille[portefeuille.Type_Projet == type_projet]
            if len(ref) >= 3:
                rang = float((ref.Pct_Depassement < depassement).mean())
                st.markdown(f"""<div class="encart">
                    Parmi les <b>{len(ref)} chantiers</b> de type « {type_projet} »
                    du portefeuille, ce projet se situerait au-dessus de
                    <b>{rang*100:.0f} %</b> d'entre eux.<br><br>
                    Dépassement moyen observé sur ce type :
                    <b>{ref.Pct_Depassement.mean()*100:.1f} %</b>
                    </div>""", unsafe_allow_html=True)
            else:
                st.info("Trop peu de chantiers comparables dans le portefeuille.")

        st.markdown("**Variables les plus déterminantes du modèle**")
        imp = pd.DataFrame(META['importances']).set_index('variable')
        st.bar_chart(imp, color=BORDEAUX, height=260)

        st.caption(
            "L'estimation est un ordre de grandeur assorti d'une incertitude. "
            f"En validation croisée, l'erreur absolue moyenne du modèle s'établit à "
            f"{META['metriques']['mae']*100:.1f} points de pourcentage."
        )

        # --- Export PDF ---
        try:
            pdf_bytes = generer_pdf(
                donnees={
                    'nom': nom_chantier, 'ville': ville,
                    'region': region, 'type_projet': type_projet,
                    'type_marche': type_marche, 'type_sol': type_sol,
                    'budget': budget, 'marge': marge_cible,
                    'date_debut': date_debut.strftime('%d/%m/%Y'),
                    'date_fin': date_fin.strftime('%d/%m/%Y'),
                    'duree': duree, 'superficie': superficie,
                    'etages': etages, 'fiabilite': fiabilite,
                },
                prediction={
                    'depassement': depassement, 'classe': classe,
                    'confiance': confiance, 'surcout': surcout,
                },
            )
            nom_fichier = (nom_chantier or "simulation").replace(' ', '_')
            st.download_button(
                "📄 Exporter la simulation en PDF",
                data=pdf_bytes,
                file_name=f"TGCC_simulation_{nom_fichier}_{date.today().isoformat()}.pdf",
                mime='application/pdf',
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"Export PDF indisponible : {e}")


# =====================================================================
# PAGE 2 — PORTEFEUILLE
# =====================================================================
elif page == "Portefeuille":
    bandeau("Portefeuille de chantiers")

    f1, f2, f3, f4 = st.columns(4)
    regions = f1.multiselect("Région", sorted(portefeuille.Region.dropna().unique()))
    types = f2.multiselect("Type de projet", sorted(portefeuille.Type_Projet.dropna().unique()))
    statuts = f3.multiselect("Statut", sorted(portefeuille.Statut.dropna().unique()))
    risques = f4.multiselect("Niveau de risque", ['Faible', 'Modéré', 'Élevé', 'Critique'])

    d = portefeuille.copy()
    if regions:
        d = d[d.Region.isin(regions)]
    if types:
        d = d[d.Type_Projet.isin(types)]
    if statuts:
        d = d[d.Statut.isin(statuts)]
    if risques:
        d = d[d.Niveau_Risque.isin(risques)]

    if d.empty:
        st.warning("Aucun chantier ne correspond à ces filtres.")
        st.stop()

    st.divider()
    bp, dr = d.Budget_Prevu.sum(), d.Depenses_Reelles.sum()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Chantiers", len(d))
    k2.metric("Budget prévu", mad(bp))
    k3.metric("Dépenses réelles", mad(dr))
    k4.metric("Dépassement global", f"{(dr-bp)/bp*100:.1f} %")

    g1, g2 = st.columns([1, 1])
    with g1:
        st.markdown("**Répartition par niveau de risque**")
        rep = d.Niveau_Risque.value_counts().reindex(
            ['Faible', 'Modéré', 'Élevé', 'Critique']).fillna(0).astype(int)
        st.bar_chart(rep, color=ORANGE, height=260)
    with g2:
        st.markdown("**Dépassement moyen par région**")
        gr = d.groupby('Region')[['Budget_Prevu', 'Depenses_Reelles']].sum()
        gr = ((gr.Depenses_Reelles - gr.Budget_Prevu) / gr.Budget_Prevu).sort_values(ascending=False)
        st.bar_chart(gr, color=ROUGE, height=260)

    # alerte précoce
    ap = d[(d.Ecart_Cout_3M.notna()) & (d.Ecart_Cout_3M < 0.05) & (d.Depassement_Predit > 0.10)]
    if len(ap):
        st.markdown(f"""<div style="background:{GRIS_FOND};border-left:2px solid {BORDEAUX};
            padding:16px 22px;margin:14px 0;">
            <div style="font-size:11.5px;text-transform:uppercase;letter-spacing:0.1em;
            color:{BORDEAUX};font-weight:600;margin-bottom:6px;">Alerte précoce</div>
            <div style="color:{NOIR};font-weight:500;font-size:15px;">
            {len(ap)} chantiers concernés</div>
            <div style="color:{GRIS_MOYEN};font-size:13px;margin-top:4px;">
            Situation actuelle maîtrisée, mais dérive annoncée par le modèle.
            Ces projets ne seraient signalés par aucun indicateur classique.
            </div></div>""", unsafe_allow_html=True)

    st.markdown("**Détail des chantiers**")
    aff = d[['Nom_Projet', 'Ville', 'Region', 'Type_Projet', 'Statut',
             'Budget_Prevu', 'Depenses_Reelles', 'Pct_Depassement',
             'Niveau_Risque', 'Depassement_Predit', 'Classe_Predite']].copy()
    aff = aff.sort_values('Pct_Depassement', ascending=False)
    aff['Pct_Depassement'] = aff.Pct_Depassement * 100
    aff['Depassement_Predit'] = aff.Depassement_Predit * 100
    aff.columns = ['Chantier', 'Ville', 'Région', 'Type', 'Statut', 'Budget prévu',
                   'Dépenses réelles', 'Dépassement', 'Risque',
                   'Dépassement projeté', 'Classe prédite']
    st.dataframe(
        aff, use_container_width=True, hide_index=True, height=420,
        column_config={
            'Budget prévu': st.column_config.NumberColumn(format="%.0f"),
            'Dépenses réelles': st.column_config.NumberColumn(format="%.0f"),
            'Dépassement': st.column_config.NumberColumn(format="%.1f %%"),
            'Dépassement projeté': st.column_config.NumberColumn(format="%.1f %%"),
        })

    if {'Latitude', 'Longitude'}.issubset(d.columns):
        st.markdown("**Localisation**")
        carte = d[['Latitude', 'Longitude']].dropna().rename(
            columns={'Latitude': 'lat', 'Longitude': 'lon'})
        if len(carte):
            st.map(carte, size=6000, color='#C41E3A')


# =====================================================================
# PAGE 3 — ASSISTANT
# =====================================================================
elif page == "Assistant":
    bandeau("Assistant")

    if 'messages' not in st.session_state:
        st.session_state.messages = [{
            'role': 'assistant',
            'contenu': (
                "Bonjour. Je réponds aux questions portant sur les "
                f"**{len(portefeuille)} chantiers** du portefeuille et sur les "
                "prédictions du modèle.\n\n"
                "Posez-moi par exemple : *quels chantiers dépassent le plus ?*, "
                "*quelle région dérape le plus ?* ou *quels chantiers vont déraper ?*\n\n"
                "Tapez **aide** pour connaître toutes les formulations reconnues."
            ),
            'tableau': None,
        }]

    for m in st.session_state.messages:
        with st.chat_message(m['role'], avatar='🏗️' if m['role'] == 'assistant' else '👤'):
            st.markdown(m['contenu'])
            if m.get('tableau') is not None:
                st.dataframe(m['tableau'], use_container_width=True, hide_index=True)

    question = st.chat_input("Posez votre question…")

    if question:
        st.session_state.messages.append(
            {'role': 'user', 'contenu': question, 'tableau': None})
        with st.chat_message('user', avatar='👤'):
            st.markdown(question)

        with st.chat_message('assistant', avatar='🏗️'):
            with st.spinner("Analyse…"):
                texte, tableau = assistant.repondre(question, portefeuille)
            st.markdown(texte)
            if tableau is not None:
                st.dataframe(tableau, use_container_width=True, hide_index=True)

        st.session_state.messages.append(
            {'role': 'assistant', 'contenu': texte, 'tableau': tableau})

    if len(st.session_state.messages) > 1:
        if st.button("Effacer la conversation"):
            del st.session_state.messages
            st.rerun()


# =====================================================================
# PAGE 4 — À PROPOS
# =====================================================================
else:
    bandeau("À propos du modèle")

    m = META['metriques']

    st.subheader("Cadre méthodologique")
    st.markdown(f"""
Le modèle est entraîné sur les **{m['n_train']} chantiers achevés**, dont le dépassement
final est connu, puis appliqué aux **{m['n_predict']} chantiers en cours**.

Une contrainte gouverne toute la conception : **aucune variable postérieure au troisième
mois d'exécution n'entre dans le modèle**. Autoriser l'observation des mois ultérieurs
produirait d'excellents résultats apparents, mais sans valeur opérationnelle — à ce stade,
le dépassement est déjà consommé et l'alerte inutile.
""")

    st.subheader("Performances en validation croisée")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("R² (régression)", f"{m['r2']:.3f}")
    c2.metric("Erreur moyenne", f"{m['mae']*100:.1f} pts",
              delta=f"−{m['gain_vs_baseline']*100:.0f} % vs référence",
              delta_color='inverse')
    c3.metric("Exactitude (4 classes)", f"{m['accuracy']*100:.1f} %",
              delta=f"référence {m['accuracy_baseline']*100:.0f} %")
    c4.metric("Exactitude à ±1 classe", f"{m['accuracy_tolerance_1']*100:.1f} %")

    st.markdown(f"""<div class="encart">
        L'<b>exactitude à une classe près</b> est la lecture la plus pertinente sur le plan
        métier : confondre « Élevé » et « Critique » conduit à la même action corrective,
        alors que confondre « Faible » et « Critique » constituerait une erreur coûteuse.
        </div>""", unsafe_allow_html=True)

    st.subheader("Importance des variables")
    imp = pd.DataFrame(META['importances']).set_index('variable')
    st.bar_chart(imp, color=BORDEAUX, height=300)
    st.caption(
        "Le comportement des trois premiers mois est de loin le meilleur prédicteur : "
        "un chantier qui dérape tôt continue généralement de déraper. La durée arrive "
        "ensuite, ce qui est cohérent — plus un chantier est long, plus il est exposé "
        "aux aléas et à la révision des prix."
    )

    st.subheader("Limites")
    st.markdown("""
- **Les données sont simulées.** Le processus générateur reproduit une causalité plausible,
  mais ne se substitue pas à des données de production. Les performances mesurées valident
  la démarche, non le modèle en tant que tel.
- **L'effectif d'entraînement est restreint**, ce qui justifie le recours à la validation
  croisée et écarte les architectures nécessitant de grands volumes.
- **Le plafond de performance est intentionnel.** Une part de la variance provient d'aléas
  survenant après le troisième mois, structurellement imprévisibles. Un R² proche de 1
  constituerait au contraire un signal d'alerte révélant une fuite de données.
""")

    st.subheader("Fonctionnement de l'assistant")
    st.markdown("""
L'assistant repose sur un moteur d'analyse d'intention : la question est normalisée,
rapprochée d'un ensemble de motifs, puis les entités citées — région, ville, type de projet,
seuil — sont extraites. La réponse est ensuite **calculée sur les données réelles**.

Ce choix garantit que l'assistant ne peut produire aucun chiffre inventé, qu'il fonctionne
sans connexion externe, et qu'il signale explicitement les questions hors de son périmètre.
""")
