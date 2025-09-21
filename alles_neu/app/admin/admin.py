from kivy.lang import Builder
from kivymd.app import MDApp
from kivy.core.window import Window
from kivy.uix.screenmanager import Screen

class Home(Screen):
    pass

class Admin(MDApp):
    def build(self):
        Window.size = (600, 800)
        self.sm = Builder.load_file("main.kv")
        return self.sm

    def get_csv_all_classes(self):
        pass

if __name__ == "__main__":
    Admin().run()
