from kivy.lang import Builder
from kivymd.app import MDApp
from kivy.core.window import Window
from kivy.uix.screenmanager import Screen
from kivymd.uix.menu import MDDropdownMenu


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

    def get_csv_all_classes(self):
        pass

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
        try:
            name_rf = self.root.get_screen('riegeneinteilung').ids.riegenfuehrer_text_input.text
            klasse = self.root.get_screen('riegeneinteilung').ids.klassen_text_input.text
            stufe = int(self.root.get_screen('riegeneinteilung').ids.stufe_dropdown.text)
            geschlecht = self.root.get_screen('riegeneinteilung').ids.geschlecht_dropdown.text
            profil = self.root.get_screen('riegeneinteilung').ids.checkbox_profil.active

            if geschlecht == 'Beide':
                geschlecht = None
        
            print(name_rf, klasse, stufe, geschlecht, profil)
        except:
            print('Daten unvollständig!')
    
    def riege_erstellen(self):
        pass

if __name__ == "__main__":
    Admin().run()
