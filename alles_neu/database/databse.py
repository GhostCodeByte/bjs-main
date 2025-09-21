import sqlite3
from datetime import datetime
import os

class Database:
    # Die ID kann genuzt werden wen man mehrere datenbanken gleichzeitig haben will 
    def __init__(self, id = None):

        if id == None:
            id = datetime.now().year

        self.connection = sqlite3.connect(f"bjs_database_{id}.db")
        self.cursor = self.connection.cursor()

        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        if not self.cursor.fetchall():
            self.datenbank_erstellen()

    def datenbank_erstellen():
        pass