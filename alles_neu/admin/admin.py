from kivy.lang import Builder
from kivymd.app import MDApp
from kivy.core.window import Window
from kivy.uix.screenmanager import Screen
from kivymd.uix.menu import MDDropdownMenu
from alles_neu.admin.utils import create_db_from_csv, create_riege
from plyer import filechooser

class Home(Screen):
    pass

class Riegeneinteilung(Screen):
    pass

class Admin(MDApp):
    def build(self):
        Window.size = (600, 800)
        self.sm = Builder.load_file("main.kv")
        return self.sm

    def change_screen(self, screen_name):
        self.sm.current = screen_name

    def open_dropdown_geschlecht(self, item):
        menu_items = [
            {
                "text": "Jungen",
                "on_release": lambda: self.set_geschlecht('M')
            },
            {
                "text": "Mädchen",
                "on_release": lambda: self.set_geschlecht('W')
            },
            {
                "text": "Beide",
                "on_release": lambda: self.set_geschlecht('Beide')
            }
        ]
        MDDropdownMenu(caller=item, items=menu_items).open()
    
    def open_dropdown_stufe(self, item):
        menu_items = [
            {
                "text": f"{i}",
                "on_release": lambda x=i: self.set_stufe(x),
            } for i in range(5, 11)
        ]
        MDDropdownMenu(caller=item, items=menu_items).open()

    def set_geschlecht(self, geschlecht):
        self.root.get_screen('riegeneinteilung').ids.geschlecht_dropdown.text = f"{geschlecht}"

    def set_stufe(self, stufe):
        self.root.get_screen('riegeneinteilung').ids.stufe_dropdown.text = f"{stufe}"

    def get_riegen_data(self):
            name_rf = self.root.get_screen('riegeneinteilung').ids.riegenfuehrer_text_input.text
            klassenendung = self.root.get_screen('riegeneinteilung').ids.klassen_text_input.text.replace(",", "").replace(" ", "")
            stufe = int(self.root.get_screen('riegeneinteilung').ids.stufe_dropdown.text)
            geschlecht = self.root.get_screen('riegeneinteilung').ids.geschlecht_dropdown.text
            profil = self.root.get_screen('riegeneinteilung').ids.checkbox_profil.active
            if geschlecht == 'Beide':
                geschlecht = 'mw'
            return name_rf, stufe, klassenendung, geschlecht, profil


    def reset_entries(self):
        self.root.get_screen('riegeneinteilung').ids.riegenfuehrer_text_input.text = ''
        self.root.get_screen('riegeneinteilung').ids.klassen_text_input.text = ''
        self.root.get_screen('riegeneinteilung').ids.stufe_dropdown.text = ''
        self.root.get_screen('riegeneinteilung').ids.geschlecht_dropdown.text = ''
        self.root.get_screen('riegeneinteilung').ids.checkbox_profil.active = False

    def create_riege_kv(self):
        try:
            data = self.get_riegen_data()
        except Exception:
            self.root.get_screen('riegeneinteilung').ids.label_data_not_complete.text = 'Eintrag ist im falschen Format.'
            return

        create_riege(*data)
        self.root.get_screen('riegeneinteilung').ids.label_data_not_complete.text = 'Riege wurde hinzugefügt.'
        self.reset_entries()

    def create_db(self):
        filechooser.open_file(on_selection=self.call_create_db_from_csv)

    def call_create_db_from_csv(self, selection):
        if selection:
            print(selection[0])
            create_db_from_csv(selection[0])


if __name__ == "__main__":
    Admin().run()
