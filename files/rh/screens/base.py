# -*- coding: utf-8 -*-
class BaseScreen:
    def __init__(self, engine=None, name=""):
        self.engine = engine
        self.name = name

    def on_enter(self, params=None):
        pass

    def on_exit(self):
        pass

    def handle_input(self, inputs):
        return False

    def update(self, dt):
        pass

    def render(self, engine):
        pass

    def get_header_title(self):
        return ""

    def get_footer_actions(self):
        return []