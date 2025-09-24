import pandas as pd
import numpy as np
import os
from alles_neu.admin.admin_database import Database
from datetime import datetime


def fill_schueler(data: np.ndarray):
    db = Database()
    for element in data:
        stufe = element[1][:-1]
        klasse = element[1][-1:]
        db.add_schueler(
            name=element[2],
            vorname=element[3],
            geschlecht=element[0].lower(),
            klasse=stufe,
            klassenbuchstabe=klasse,
            geburtsjahr=int(element[4]),
            profil=element[5]
        )

def create_riege(rf_id, stufe, klassenendungen, geschlechter, profil):
    print('adding')
    db = Database()
    id = db.add_riegenfuehrer(
        rf_id,
        geschlechter,
        profil,
        stufe,
        klassenendungen
    )
    for kl_end in klassenendungen:
        for geschlecht in geschlechter:
            db.add_riegenfuehrer_to_schueler(
                id,
                kl_end,
                stufe,
                geschlecht,
                profil
            )

def create_db_from_csv(csv_path):
    try:
        os.remove(f"alles_neu/admin/bjs_database_{datetime.now().year}.db")
    except Exception:
        print(f"Failed to delete database: alles_neu/admin/bjs_database_{datetime.now().year}.db")
    df = pd.read_csv(csv_path, delimiter=';')
    data = np.array(df)
    fill_schueler(data)
