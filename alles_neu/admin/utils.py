import pandas as pd
import numpy as np
from alles_neu.app.database.database import Database

def csv_to_list(csv_path: str) -> np.ndarray:
    """
    Extract data from a csv file and return a list
    """
    df = pd.read_csv(csv_path, delimiter=';')
    data = np.array(df)
    return data

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

def fill_riegenfuehrer(data: np.ndarray):
    pass

if __name__ == '__main__':
    fill_schueler(csv_to_list(r"alles_neu/admin/test_data.csv"))