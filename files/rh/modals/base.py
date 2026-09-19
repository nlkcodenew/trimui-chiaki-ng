# -*- coding: utf-8 -*-
class BaseModal:
    def __init__(self, engine=None):
        self.engine = engine
        self.active = False
        self.data = None

    def open(self, data=None):
        self.active = True
        self.data = data or {}

    def close(self):
        self.active = False
        self.data = None

    def is_active(self):
        return self.active

    def handle_input(self, inputs):
        return False

    def update(self, dt):
        pass

    def render(self, engine):
        pass