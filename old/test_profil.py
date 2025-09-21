# Testskript: Führt einen CSV-Import durch, initialisiert Riegen-Tabellen
# und gibt Beispiel-Daten sowie eine Profil-Statistik aus.
# Hinweis: Dieses Skript ist für lokale Tests/Entwicklung gedacht.
import backend.backend as backend
import sqlite3


# Teste CSV-Import (löscht bestehende Daten und importiert neu aus backend/Mappe1.csv)
print("Starte CSV-Import...")
success = backend.setup_database_with_csv('backend/Mappe1.csv', 'backend/database/bjs.db')  # True bei Erfolg
print(f'CSV-Import erfolgreich: {success}')

# Teste RiegenManager (legt Tabellen für Riegenführer und Zuordnungen an)
print("\nErstelle RiegenManager...")
rm = backend.RiegenManager('backend/database/bjs.db')
rm.create_riegen_tables()  # idempotent

# Teste Datenbankinhalt (zeigt eine Stichprobe von 10 Schülern)
print("\nPrüfe Datenbankinhalt...")
conn = sqlite3.connect('backend/database/bjs.db')
cursor = conn.cursor()
cursor.execute('SELECT SchuelerID, Name, Geschlecht, Profil FROM Schueler LIMIT 10')
results = cursor.fetchall()
print('Beispiel-Schüler:')
for r in results:
    print(f'ID: {r[0]}, Name: {r[1]}, Geschlecht: {r[2]}, Profil: {r[3]}')

# Teste Profil-Verteilung (Anzahl pro Profil-Kennzeichen)
cursor.execute('SELECT Profil, COUNT(*) FROM Schueler GROUP BY Profil')
profil_stats = cursor.fetchall()
print('\nProfil-Verteilung:')
for stat in profil_stats:
    print(f'Profil {stat[0]}: {stat[1]} Schüler')

# Aufräumen
conn.close()
rm.close()
print("\nTest abgeschlossen!")
