import pandas as pd
import numpy as np
from alles_neu.database.database import Database

def csv_to_list(csv_path: str) -> np.ndarray:
    """
    Extract data from a csv file and return a list
    """
    df = pd.read_csv(csv_path, delimiter=';')
    data = np.array(df)
    return data

def fill_db_from_array(data):
    db = Database()
    db.add_riegenfuehrer('test')
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


if __name__ == '__main__':
    fill_db_from_array(csv_to_list(r"old\app\backend\Mappe1.csv"))