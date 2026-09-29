"""
Persistance des prédictions dans SQL Server.

`sauvegarder_prediction()` réalise un UPSERT (MERGE) dans dbo.Predictions.
Toute erreur (base indisponible, pilote absent, SQLAlchemy non installé)
est attrapée et journalisée ; la fonction renvoie False sans jamais
propager d'exception à l'appelant.
"""

SERVER = 'localhost'
DATABASE = 'TGCC_Budget_V3'

_engine = None


def get_engine():
    """Retourne une connexion réutilisable à SQL Server."""
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine
        connection_string = (
            f"mssql+pyodbc://@{SERVER}/{DATABASE}"
            "?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
        )
        _engine = create_engine(connection_string)
    return _engine


def sauvegarder_prediction(id_chantier, depassement_predit, classe_predite,
                           confiance, ecart_cout_3m, ecart_planning_3m):
    """
    Enregistre (ou met à jour) une prédiction dans la table SQL Server Predictions.
    Utilise un UPSERT car ID_Chantier est clé primaire.

    Renvoie True en cas de succès, False sinon (aucune exception propagée).
    """
    try:
        from sqlalchemy import text
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("""
                MERGE Predictions AS target
                USING (SELECT :id_chantier AS ID_Chantier) AS source
                ON target.ID_Chantier = source.ID_Chantier
                WHEN MATCHED THEN
                    UPDATE SET
                        Depassement_Predit = :depassement_predit,
                        Classe_Predite = :classe_predite,
                        Confiance = :confiance,
                        Ecart_Cout_3M = :ecart_cout_3m,
                        Ecart_Planning_3M = :ecart_planning_3m
                WHEN NOT MATCHED THEN
                    INSERT (ID_Chantier, Depassement_Predit, Classe_Predite,
                            Confiance, Ecart_Cout_3M, Ecart_Planning_3M)
                    VALUES (:id_chantier, :depassement_predit, :classe_predite,
                            :confiance, :ecart_cout_3m, :ecart_planning_3m);
            """), {
                "id_chantier": id_chantier,
                "depassement_predit": round(float(depassement_predit), 4),
                "classe_predite": str(classe_predite),
                "confiance": round(float(confiance), 3),
                "ecart_cout_3m": round(float(ecart_cout_3m), 4),
                "ecart_planning_3m": round(float(ecart_planning_3m), 2),
            })
        print(f"✅ Prédiction pour {id_chantier} enregistrée dans SQL Server.")
        return True
    except Exception as e:
        print(f"⚠️ Impossible d'enregistrer dans SQL Server : {e}")
        return False
