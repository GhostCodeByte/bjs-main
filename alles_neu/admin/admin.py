"""
BJS Admin Tool (Kivy GUI)

Erweiterte Version mit:
- UX-Verbesserungen und Fehleranzeigen
- Eingabevalidierung
- Fortschritts- und Log-Output
- CSV-Schema-Dokumentation
"""

import os
import re
import threading
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen, ScreenManager

try:
    from kivymd.app import MDApp
    from kivymd.uix.menu import MDDropdownMenu

    HAS_KIVYMD = True
except ImportError:
    HAS_KIVYMD = False
    MDApp = App

from alles_neu.admin.admin_database import Database
from alles_neu.admin.utils import create_db_from_csv, create_riege

# CSV-Schema Dokumentation
CSV_SCHEMA_INFO = """
CSV-Format für Schüler-Import:

Spalten (Reihenfolge wichtig):
1. Geschlecht    - 'm' oder 'w'
2. Klasse        - z.B. '5a', '6b', '10c'
3. Name          - Nachname
4. Vorname       - Vorname
5. Geburtsjahr   - 4-stellig, z.B. '2012'
6. Profil        - 'True' oder 'False' (Sportprofil)

Trennzeichen: Semikolon (;)
Encoding: UTF-8

Beispiel:
Geschlecht;Klasse;Name;Vorname;Geburtsjahr;Profil
m;5a;Mustermann;Max;2012;False
w;5a;Musterfrau;Maria;2012;True
m;6b;Schmidt;Paul;2011;False
"""


class LogPopup(Popup):
    """Popup für Log-Ausgaben und Fortschritt."""

    log_text = StringProperty("")
    progress_value = 0
    is_running = BooleanProperty(False)

    def __init__(self, title="Fortschritt", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.size_hint = (0.9, 0.8)
        self.auto_dismiss = False

        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # Log-Bereich
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.textinput import TextInput

        self.log_input = TextInput(
            text="",
            readonly=True,
            font_size="14sp",
            background_color=(0.1, 0.1, 0.1, 1),
            foreground_color=(0.9, 0.9, 0.9, 1),
            size_hint_y=0.85,
        )
        layout.add_widget(self.log_input)

        # Progress Bar
        self.progress_bar = ProgressBar(max=100, value=0, size_hint_y=0.05)
        layout.add_widget(self.progress_bar)

        # Status Label
        self.status_label = Label(
            text="Bereit...", size_hint_y=0.05, color=(0.7, 0.7, 0.7, 1)
        )
        layout.add_widget(self.status_label)

        # Close Button
        from kivy.uix.button import Button

        self.close_btn = Button(
            text="Schließen",
            size_hint_y=0.05,
            disabled=True,
            background_color=(0.3, 0.3, 0.3, 1),
        )
        self.close_btn.bind(on_release=self.dismiss)
        layout.add_widget(self.close_btn)

        self.content = layout

    @mainthread
    def add_log(self, message: str, level: str = "info"):
        """Fügt eine Log-Nachricht hinzu."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        icons = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}
        icon = icons.get(level, "•")

        self.log_input.text += f"[{timestamp}] {icon} {message}\n"
        # Scroll to bottom
        self.log_input.cursor = (0, len(self.log_input.text))

    @mainthread
    def set_progress(self, value: int, status: str = None):
        """Setzt den Fortschritt."""
        self.progress_bar.value = value
        if status:
            self.status_label.text = status

    @mainthread
    def finish(self, success: bool = True):
        """Markiert den Vorgang als abgeschlossen."""
        self.is_running = False
        self.close_btn.disabled = False
        self.close_btn.background_color = (
            (0.2, 0.6, 0.2, 1) if success else (0.6, 0.2, 0.2, 1)
        )
        self.progress_bar.value = 100
        self.status_label.text = "Abgeschlossen" if success else "Fehlgeschlagen"


class ValidationError(Exception):
    """Fehler bei der Eingabevalidierung."""

    pass


class Home(Screen):
    """Startseite des Admin-Tools."""

    pass


class Riegeneinteilung(Screen):
    """Screen für die Riegen-Erstellung."""

    def validate_inputs(self) -> tuple:
        """
        Validiert alle Eingaben.

        Returns:
            Tuple mit (name, stufe, klassenendung, geschlecht, profil)

        Raises:
            ValidationError bei ungültigen Eingaben
        """
        app = App.get_running_app()
        screen = app.root.get_screen("riegeneinteilung")

        # Name validieren
        name = screen.ids.riegenfuehrer_text_input.text.strip()
        if not name:
            raise ValidationError("Riegenführer-Name ist erforderlich")
        if len(name) < 3:
            raise ValidationError("Name muss mindestens 3 Zeichen haben")
        if not re.match(r"^[A-Za-zäöüÄÖÜß]+$", name):
            raise ValidationError(
                "Name darf nur Buchstaben enthalten (keine Leerzeichen)"
            )

        # Klassenendungen validieren
        klassen_raw = screen.ids.klassen_text_input.text.strip()
        if not klassen_raw:
            raise ValidationError("Klassenendungen sind erforderlich (z.B. a,b,c)")
        klassenendung = klassen_raw.replace(",", "").replace(" ", "")
        if not re.match(r"^[a-zA-Z]+$", klassenendung):
            raise ValidationError(
                "Klassenendungen dürfen nur Buchstaben sein (z.B. a,b,c)"
            )

        # Stufe validieren
        stufe_text = screen.ids.stufe_dropdown.text.strip()
        if not stufe_text or not stufe_text.isdigit():
            raise ValidationError("Bitte eine Stufe auswählen (5-10)")
        stufe = int(stufe_text)
        if stufe < 5 or stufe > 13:
            raise ValidationError("Stufe muss zwischen 5 und 13 liegen")

        # Geschlecht validieren
        geschlecht = screen.ids.geschlecht_dropdown.text.strip()
        if not geschlecht or geschlecht not in ("M", "W", "Beide"):
            raise ValidationError("Bitte ein Geschlecht auswählen")
        if geschlecht == "Beide":
            geschlecht = "mw"

        # Profil
        profil = screen.ids.checkbox_profil.active

        return name, stufe, klassenendung, geschlecht, profil


class CSVSchemaPopup(Popup):
    """Popup zur Anzeige des CSV-Schemas."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "CSV-Format Dokumentation"
        self.size_hint = (0.9, 0.9)

        from kivy.uix.button import Button
        from kivy.uix.textinput import TextInput

        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

        text_input = TextInput(
            text=CSV_SCHEMA_INFO,
            readonly=True,
            font_size="14sp",
            font_name="RobotoMono",
            size_hint_y=0.9,
        )
        layout.add_widget(text_input)

        close_btn = Button(text="Schließen", size_hint_y=0.1)
        close_btn.bind(on_release=self.dismiss)
        layout.add_widget(close_btn)

        self.content = layout


class ErrorPopup(Popup):
    """Popup für Fehlermeldungen."""

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.title = "Fehler"
        self.size_hint = (0.8, 0.4)

        layout = BoxLayout(orientation="vertical", padding=20, spacing=10)

        error_label = Label(
            text=f"❌ {message}",
            font_size="16sp",
            halign="center",
            valign="middle",
            text_size=(Window.width * 0.7, None),
            color=(1, 0.3, 0.3, 1),
        )
        layout.add_widget(error_label)

        from kivy.uix.button import Button

        close_btn = Button(
            text="OK",
            size_hint=(0.5, 0.3),
            pos_hint={"center_x": 0.5},
            background_color=(0.6, 0.2, 0.2, 1),
        )
        close_btn.bind(on_release=self.dismiss)
        layout.add_widget(close_btn)

        self.content = layout


class SuccessPopup(Popup):
    """Popup für Erfolgsmeldungen."""

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.title = "Erfolg"
        self.size_hint = (0.8, 0.4)

        layout = BoxLayout(orientation="vertical", padding=20, spacing=10)

        success_label = Label(
            text=f"✅ {message}",
            font_size="16sp",
            halign="center",
            valign="middle",
            text_size=(Window.width * 0.7, None),
            color=(0.3, 0.8, 0.3, 1),
        )
        layout.add_widget(success_label)

        from kivy.uix.button import Button

        close_btn = Button(
            text="OK",
            size_hint=(0.5, 0.3),
            pos_hint={"center_x": 0.5},
            background_color=(0.2, 0.6, 0.2, 1),
        )
        close_btn.bind(on_release=self.dismiss)
        layout.add_widget(close_btn)

        self.content = layout


class Admin(MDApp if HAS_KIVYMD else App):
    """Haupt-App für das Admin-Tool."""

    def build(self):
        Window.size = (700, 900)
        self.title = "BJS Admin Tool"

        try:
            self.sm = Builder.load_file("main.kv")
        except Exception as e:
            # Fallback: Create screens programmatically
            print(f"Warning: Could not load main.kv: {e}")
            self.sm = self._create_fallback_ui()

        return self.sm

    def _create_fallback_ui(self):
        """Erstellt eine Fallback-UI wenn main.kv nicht geladen werden kann."""
        sm = ScreenManager()

        # Home Screen
        home = Screen(name="home")
        layout = BoxLayout(orientation="vertical", padding=20, spacing=10)

        from kivy.uix.button import Button

        btn1 = Button(text="Riegen erstellen", size_hint_y=0.2)
        btn1.bind(on_release=lambda x: self.change_screen("riegeneinteilung"))
        layout.add_widget(btn1)

        btn2 = Button(text="DB aus CSV erstellen", size_hint_y=0.2)
        btn2.bind(on_release=lambda x: self.create_db())
        layout.add_widget(btn2)

        btn3 = Button(text="CSV-Format anzeigen", size_hint_y=0.2)
        btn3.bind(on_release=lambda x: self.show_csv_schema())
        layout.add_widget(btn3)

        home.add_widget(layout)
        sm.add_widget(home)

        return sm

    def change_screen(self, screen_name: str):
        """Wechselt zu einem anderen Screen."""
        self.sm.current = screen_name

    def show_csv_schema(self):
        """Zeigt die CSV-Format-Dokumentation an."""
        popup = CSVSchemaPopup()
        popup.open()

    def show_error(self, message: str):
        """Zeigt einen Fehler-Dialog an."""
        popup = ErrorPopup(message)
        popup.open()

    def show_success(self, message: str):
        """Zeigt einen Erfolgs-Dialog an."""
        popup = SuccessPopup(message)
        popup.open()

    def get_csv_all_classes(self):
        """Exportiert alle Klassen als CSV."""
        # TODO: Implementieren
        self.show_error("Diese Funktion ist noch nicht implementiert.")

    # Dropdown-Menüs
    def open_dropdown_geschlecht(self, item):
        """Öffnet das Geschlecht-Dropdown."""
        if HAS_KIVYMD:
            menu_items = [
                {"text": "Jungen", "on_release": lambda: self.set_geschlecht("M")},
                {"text": "Mädchen", "on_release": lambda: self.set_geschlecht("W")},
                {"text": "Beide", "on_release": lambda: self.set_geschlecht("Beide")},
            ]
            MDDropdownMenu(caller=item, items=menu_items).open()
        else:
            # Fallback ohne KivyMD
            from kivy.uix.button import Button
            from kivy.uix.dropdown import DropDown

            dropdown = DropDown()
            for text in ["Jungen (M)", "Mädchen (W)", "Beide"]:
                btn = Button(text=text, size_hint_y=None, height=44)
                value = text.split()[0][0] if text != "Beide" else "Beide"
                btn.bind(
                    on_release=lambda btn, v=value: (
                        self.set_geschlecht(v),
                        dropdown.dismiss(),
                    )
                )
                dropdown.add_widget(btn)
            dropdown.open(item)

    def open_dropdown_stufe(self, item):
        """Öffnet das Stufen-Dropdown."""
        if HAS_KIVYMD:
            menu_items = [
                {"text": f"{i}", "on_release": lambda x=i: self.set_stufe(x)}
                for i in range(5, 14)
            ]
            MDDropdownMenu(caller=item, items=menu_items).open()
        else:
            from kivy.uix.button import Button
            from kivy.uix.dropdown import DropDown

            dropdown = DropDown()
            for i in range(5, 14):
                btn = Button(text=str(i), size_hint_y=None, height=44)
                btn.bind(
                    on_release=lambda btn, v=i: (self.set_stufe(v), dropdown.dismiss())
                )
                dropdown.add_widget(btn)
            dropdown.open(item)

    def set_geschlecht(self, geschlecht: str):
        """Setzt das ausgewählte Geschlecht."""
        try:
            self.root.get_screen(
                "riegeneinteilung"
            ).ids.geschlecht_dropdown.text = geschlecht
        except Exception as e:
            print(f"Error setting geschlecht: {e}")

    def set_stufe(self, stufe: int):
        """Setzt die ausgewählte Stufe."""
        try:
            self.root.get_screen("riegeneinteilung").ids.stufe_dropdown.text = str(
                stufe
            )
        except Exception as e:
            print(f"Error setting stufe: {e}")

    def get_riegen_data(self) -> tuple:
        """Holt und validiert die Riegen-Daten."""
        screen = self.root.get_screen("riegeneinteilung")
        return screen.validate_inputs()

    def reset_entries(self):
        """Setzt alle Eingabefelder zurück."""
        try:
            screen = self.root.get_screen("riegeneinteilung")
            screen.ids.riegenfuehrer_text_input.text = ""
            screen.ids.klassen_text_input.text = ""
            screen.ids.stufe_dropdown.text = "Stufe wählen"
            screen.ids.geschlecht_dropdown.text = "Geschlecht wählen"
            screen.ids.checkbox_profil.active = False
            screen.ids.label_data_not_complete.text = ""
        except Exception as e:
            print(f"Error resetting entries: {e}")

    def create_riege_kv(self):
        """Erstellt eine neue Riege mit Validierung und Fortschrittsanzeige."""
        screen = self.root.get_screen("riegeneinteilung")

        try:
            # Validierung
            data = screen.validate_inputs()
            name, stufe, klassenendung, geschlecht, profil = data

            # Log-Popup öffnen
            popup = LogPopup(title="Riege erstellen")
            popup.open()
            popup.is_running = True

            def do_create():
                try:
                    popup.add_log(f"Erstelle Riege: {name}", "info")
                    popup.add_log(f"Stufe: {stufe}, Klassen: {klassenendung}", "info")
                    popup.add_log(f"Geschlecht: {geschlecht}, Profil: {profil}", "info")
                    popup.set_progress(20, "Riege wird angelegt...")

                    # Riege erstellen
                    create_riege(name, stufe, klassenendung, geschlecht, profil)

                    popup.set_progress(80, "Schüler werden zugewiesen...")
                    popup.add_log("Schüler wurden zugewiesen", "success")
                    popup.add_log(f"Riege '{name}' erfolgreich erstellt!", "success")

                    popup.finish(success=True)

                    # UI zurücksetzen
                    Clock.schedule_once(lambda dt: self.reset_entries(), 0)

                except Exception as e:
                    popup.add_log(f"Fehler: {str(e)}", "error")
                    popup.finish(success=False)

            # In separatem Thread ausführen
            threading.Thread(target=do_create, daemon=True).start()

        except ValidationError as e:
            screen.ids.label_data_not_complete.text = str(e)
            screen.ids.label_data_not_complete.color = (1, 0.3, 0.3, 1)
            self.show_error(str(e))

        except Exception as e:
            screen.ids.label_data_not_complete.text = f"Fehler: {str(e)}"
            self.show_error(f"Unerwarteter Fehler: {str(e)}")

    def create_db(self):
        """Erstellt die Datenbank aus einer CSV-Datei mit Fortschrittsanzeige."""
        csv_path = "alles_neu/admin/test_data.csv"

        if not os.path.exists(csv_path):
            self.show_error(f"CSV-Datei nicht gefunden: {csv_path}")
            return

        # Log-Popup öffnen
        popup = LogPopup(title="Datenbank erstellen")
        popup.open()
        popup.is_running = True

        def do_create():
            try:
                db_path = f"alles_neu/admin/bjs_database_{datetime.now().year}.db"

                popup.add_log(f"Lese CSV: {csv_path}", "info")
                popup.set_progress(10, "CSV wird gelesen...")

                # Prüfe ob DB existiert
                if os.path.exists(db_path):
                    popup.add_log(f"Lösche bestehende DB: {db_path}", "warning")
                    try:
                        os.remove(db_path)
                    except Exception as e:
                        popup.add_log(f"Konnte DB nicht löschen: {e}", "warning")

                popup.set_progress(30, "Schüler werden importiert...")

                # CSV lesen und importieren
                import numpy as np
                import pandas as pd

                df = pd.read_csv(csv_path, delimiter=";")
                total = len(df)
                popup.add_log(f"Gefunden: {total} Schüler", "info")

                db = Database(path=db_path)
                data = np.array(df)

                imported = 0
                errors = 0

                for i, row in enumerate(data):
                    try:
                        stufe = row[1][:-1]
                        klasse = row[1][-1:]

                        # Profil-Handling
                        profil_val = row[5] if len(row) > 5 else False
                        if isinstance(profil_val, str):
                            profil = profil_val.lower() in ("true", "1", "yes")
                        else:
                            profil = bool(profil_val)

                        db.add_schueler(
                            name=row[2],
                            vorname=row[3],
                            geschlecht=row[0].lower(),
                            klasse=int(stufe),
                            klassenbuchstabe=klasse,
                            geburtsjahr=int(row[4]),
                            profil=profil,
                        )
                        imported += 1

                    except Exception as e:
                        errors += 1
                        if errors <= 3:
                            popup.add_log(f"Zeile {i + 1}: {e}", "warning")

                    # Fortschritt aktualisieren
                    if (i + 1) % 10 == 0 or i + 1 == total:
                        progress = 30 + int((i + 1) / total * 60)
                        popup.set_progress(progress, f"Importiert: {imported}/{total}")

                db.connection.close()

                popup.add_log(f"Import abgeschlossen: {imported} Schüler", "success")
                if errors > 0:
                    popup.add_log(f"Fehler: {errors}", "warning")
                popup.add_log(f"Datenbank: {db_path}", "info")

                popup.finish(success=True)

            except FileNotFoundError:
                popup.add_log(f"CSV-Datei nicht gefunden: {csv_path}", "error")
                popup.finish(success=False)

            except Exception as e:
                popup.add_log(f"Fehler: {str(e)}", "error")
                popup.finish(success=False)

        # In separatem Thread ausführen
        threading.Thread(target=do_create, daemon=True).start()

    def export_db(self, target_path: str = None):
        """Exportiert die Datenbank an einen Zielort."""
        import shutil

        source = f"alles_neu/admin/bjs_database_{datetime.now().year}.db"

        if not os.path.exists(source):
            self.show_error(f"Datenbank nicht gefunden: {source}")
            return

        if not target_path:
            target_path = (
                f"alles_neu/app/database/bjs_database_{datetime.now().year}.db"
            )

        popup = LogPopup(title="Datenbank exportieren")
        popup.open()

        def do_export():
            try:
                popup.add_log(f"Quelle: {source}", "info")
                popup.add_log(f"Ziel: {target_path}", "info")
                popup.set_progress(30, "Kopiere Datenbank...")

                # Zielverzeichnis erstellen
                Path(target_path).parent.mkdir(parents=True, exist_ok=True)

                shutil.copy2(source, target_path)

                file_size = Path(target_path).stat().st_size / 1024
                popup.add_log(f"Export erfolgreich: {file_size:.1f} KB", "success")
                popup.finish(success=True)

            except Exception as e:
                popup.add_log(f"Export fehlgeschlagen: {e}", "error")
                popup.finish(success=False)

        threading.Thread(target=do_export, daemon=True).start()


if __name__ == "__main__":
    Admin().run()
