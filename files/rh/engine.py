# -*- coding: utf-8 -*-
"""Engine SDL2 don gian cho trimui-chiaki-ng 0.1.0.

Lay nhanh tu RetroHub engine.py, rut gon cho ban dau: chi ho tro surface
software 32-bit ARGB, text qua SDL_ttf (se bind o 0.2.0), input qua keyboard.

Ban 0.1.0 muc tieu: app khoi dong, hien menu, nhan input tu keyboard, scan
host qua UDP, show modal update. Video stream that su se them o 0.2.0
cung codec H264 / H265 (ffpyplayer hoac Native FFmpeg subprocess).
"""

import os
import sys
import time
import ctypes

import sdl2
import sdl2.ext
import sdl2.sdlttf as sdlttf

from . import state
from .paths import APP_DIR, SDCARD_PATH
from .fonts import FALLBACK_FONT, font_candidates, pick_font
from .inputs import InputManager
from .logger import get_logger

log = get_logger()

MENU_IDLE_TIMEOUT_SECONDS = 15 * 60


def _input_active(inputs):
    if inputs.get("edges") or inputs.get("any"):
        return True
    return any(
        abs(int(inputs.get(key, 0) or 0)) > 8000
        for key in ("axis_left_x", "axis_left_y", "axis_right_x", "axis_right_y")
    )


class ChiakiEngine:
    """Engine chinh cua app trimui-chiaki-ng."""

    def __init__(self):
        self.running = False
        self.window = None
        self.renderer = None
        self.input_mgr = InputManager()
        self.screens = {}
        self.screen_stack = []
        self.modals = {}
        self.active_modal = None
        self.screen_w = 1280
        self.screen_h = 720
        self.font_title = None
        self.font_sub = None
        self.font_item = None
        self.font_big = None
        self.controllers = []
        self.joysticks = []
        self.exit_reason = "not_started"

    # ----- SDL init --------------------------------------------------------

    def init_sdl(self):
        sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_JOYSTICK
                      | sdl2.SDL_INIT_GAMECONTROLLER)
        sdlttf.TTF_Init()
        display_mode = sdl2.SDL_DisplayMode()
        if sdl2.SDL_GetCurrentDisplayMode(0, display_mode) == 0:
            self.screen_w = display_mode.w
            self.screen_h = display_mode.h
        if self.screen_w < 800:
            self.screen_w = 1280
        if self.screen_h < 600:
            self.screen_h = 720
        state.SCREEN_W = self.screen_w
        state.SCREEN_H = self.screen_h
        self.window = sdl2.SDL_CreateWindow(
            b"trimui-chiaki-ng",
            0, 0, self.screen_w, self.screen_h,
            sdl2.SDL_WINDOW_SHOWN | sdl2.SDL_WINDOW_FULLSCREEN,
        )
        if not self.window:
            self.window = sdl2.SDL_CreateWindow(
                b"trimui-chiaki-ng",
                0, 0, self.screen_w, self.screen_h,
                sdl2.SDL_WINDOW_SHOWN,
            )
        self.renderer = sdl2.SDL_CreateRenderer(self.window, -1,
                                                sdl2.SDL_RENDERER_ACCELERATED
                                                | sdl2.SDL_RENDERER_PRESENTVSYNC)
        if not self.renderer:
            self.renderer = sdl2.SDL_CreateRenderer(self.window, -1,
                                                    sdl2.SDL_RENDERER_SOFTWARE)
        for index in range(sdl2.SDL_NumJoysticks()):
            if sdl2.SDL_IsGameController(index) == sdl2.SDL_TRUE:
                controller = sdl2.SDL_GameControllerOpen(index)
                if controller:
                    self.controllers.append(controller)
                    self.input_mgr.attach_controller(controller)
            else:
                joystick = sdl2.SDL_JoystickOpen(index)
                if joystick:
                    self.joysticks.append(joystick)
        return self.window is not None and self.renderer is not None

    def init_fonts(self):
        path = pick_font(font_candidates())
        if not path:
            sys.stderr.write("khong co font .ttf kha dung\n")
            return False
        path_b = path.encode("utf-8")
        try:
            self.font_big = sdlttf.TTF_OpenFont(path_b, 56)
            self.font_title = sdlttf.TTF_OpenFont(path_b, 36)
            self.font_sub = sdlttf.TTF_OpenFont(path_b, 26)
            self.font_item = sdlttf.TTF_OpenFont(path_b, 32)
        except Exception:
            return False
        return True

    # ----- screen / modal router ------------------------------------------

    def register_screen(self, name, instance):
        self.screens[name] = instance

    def push_screen(self, name, params=None):
        if name not in self.screens:
            return False
        self.screen_stack.append(self.screens[name])
        self.screens[name].on_enter(params)
        return True

    def pop_screen(self):
        if self.screen_stack:
            s = self.screen_stack.pop()
            s.on_exit()

    def register_modal(self, name, instance):
        self.modals[name] = instance

    def open_modal(self, name, data=None):
        if name not in self.modals:
            return False
        self.modals[name].open(data)
        self.active_modal = self.modals[name]
        return True

    def close_modal(self):
        if self.active_modal:
            self.active_modal.close()
            self.active_modal = None

    @property
    def current_screen(self):
        return self.screen_stack[-1] if self.screen_stack else None

    @property
    def current_screen_name(self):
        return self.current_screen.name if self.current_screen else ""

    # ----- primitives used by screens -------------------------------------

    def fill_rect(self, x, y, w, h, r, g, b, a=255):
        if not self.renderer:
            return
        sdl2.SDL_SetRenderDrawColor(self.renderer, int(r), int(g), int(b), int(a))
        rect = sdl2.SDL_Rect(int(x), int(y), int(w), int(h))
        sdl2.SDL_RenderFillRect(self.renderer, rect)

    def measure_text(self, text, font):
        if not font or not text:
            return 8 * len(str(text))
        try:
            width = ctypes.c_int()
            height = ctypes.c_int()
            if sdlttf.TTF_SizeUTF8(font, text.encode("utf-8"),
                                   ctypes.byref(width), ctypes.byref(height)) == 0:
                return width.value
        except Exception:
            pass
        return 16 * len(str(text))

    def draw_text(self, text, font, x, y, r, g, b, a=255, center_x=False, center_y=False):
        if not font or not text:
            return
        if not self.renderer:
            return
        try:
            color = sdl2.SDL_Color(int(r), int(g), int(b), int(a))
            surf = sdlttf.TTF_RenderUTF8_Blended(font, text.encode("utf-8"), color)
            if not surf:
                surf = sdlttf.TTF_RenderUTF8_Solid(font, text.encode("utf-8"), color)
            if not surf:
                return
            tex = sdl2.SDL_CreateTextureFromSurface(self.renderer, surf)
            if not tex:
                sdl2.SDL_FreeSurface(surf)
                return
            dst = sdl2.SDL_Rect(int(x), int(y), surf.contents.w, surf.contents.h)
            if center_x or center_y:
                if center_x:
                    dst.x = int(x - surf.contents.w // 2)
                if center_y:
                    dst.y = int(y - surf.contents.h // 2)
            sdl2.SDL_RenderCopy(self.renderer, tex, None, dst)
            sdl2.SDL_DestroyTexture(tex)
            sdl2.SDL_FreeSurface(surf)
        except Exception as exc:
            print("draw_text failed: %s" % exc)

    def draw_text_right(self, text, font, x, y, r, g, b, a=255):
        if not font or not text:
            return
        w = self.measure_text(text, font)
        self.draw_text(text, font, int(x - w), int(y), r, g, b, a)

    # ----- main loop ------------------------------------------------------

    def quit(self, reason="user_exit"):
        self.exit_reason = reason
        self.running = False

    def run(self):
        self.running = True
        self.exit_reason = "running"
        footer_h = 56
        header_h = 64
        last = time.time()
        last_input_at = time.monotonic()
        evt = sdl2.SDL_Event()
        while self.running:
            now = time.time()
            while sdl2.SDL_PollEvent(evt):
                self.input_mgr.feed_event(evt)
                if evt.type == sdl2.SDL_QUIT:
                    self.exit_reason = "sdl_quit"
                    log.error("SDL_QUIT received unexpectedly")
                    self.running = False
                    break
            if not self.running:
                break
            inputs = self.input_mgr.poll()
            if _input_active(inputs):
                last_input_at = time.monotonic()
            elif time.monotonic() - last_input_at >= MENU_IDLE_TIMEOUT_SECONDS:
                self.exit_reason = "idle_timeout"
                log.info("menu idle timeout: closing app after %d seconds",
                         MENU_IDLE_TIMEOUT_SECONDS)
                self.running = False
                break

            if self.active_modal:
                modal = self.active_modal
                modal.handle_input(inputs)
                if self.active_modal is modal:
                    modal.update(0.016)
            elif self.current_screen:
                self.current_screen.handle_input(inputs)
                self.current_screen.update(0.016)

            # render
            sdl2.SDL_SetRenderDrawColor(self.renderer, 13, 17, 28, 255)
            sdl2.SDL_RenderClear(self.renderer)
            self.fill_rect(0, 0, self.screen_w, self.screen_h, 13, 17, 28, 255)
            # header
            self.fill_rect(0, 0, self.screen_w, header_h, 20, 28, 46, 255)
            self.fill_rect(0, header_h - 2, self.screen_w, 2, 0, 246, 246, 255)
            title = self.current_screen.get_header_title() if self.current_screen else ""
            if title and self.font_title:
                self.draw_text(title, self.font_title, 30, header_h // 2,
                               255, 255, 255, center_y=True)

            # body
            if self.active_modal:
                if self.current_screen:
                    self.current_screen.render(self)
                self.active_modal.render(self)
            elif self.current_screen:
                self.current_screen.render(self)

            # footer
            foot_y = self.screen_h - footer_h
            self.fill_rect(0, foot_y, self.screen_w, footer_h, 10, 14, 24, 255)
            self.fill_rect(0, foot_y, self.screen_w, 2, 35, 45, 75, 255)
            actions = self.current_screen.get_footer_actions() if self.current_screen else []
            fx = 30
            for key, label in actions:
                self.fill_rect(fx, foot_y + 12, 36, 36, 0, 230, 150, 220)
                if self.font_sub:
                    self.draw_text(key, self.font_sub, fx + 18, foot_y + 16,
                                   10, 14, 24, center_x=True, center_y=True)
                if self.font_sub:
                    self.draw_text(label, self.font_sub, fx + 50, foot_y + 18,
                                   220, 225, 235)
                fx += 280

            sdl2.SDL_RenderPresent(self.renderer)
            time.sleep(0.016)
            last = now
        if self.exit_reason == "running":
            self.exit_reason = "loop_ended"
        log.info("engine stopped: reason=%s", self.exit_reason)
        return self.exit_reason

    def cleanup(self):
        try:
            for controller in self.controllers:
                sdl2.SDL_GameControllerClose(controller)
            for joystick in self.joysticks:
                sdl2.SDL_JoystickClose(joystick)
            if self.renderer:
                sdl2.SDL_DestroyRenderer(self.renderer)
            if self.window:
                sdl2.SDL_DestroyWindow(self.window)
            if self.font_title:
                sdlttf.TTF_CloseFont(self.font_title)
            if self.font_sub:
                sdlttf.TTF_CloseFont(self.font_sub)
            if self.font_item:
                sdlttf.TTF_CloseFont(self.font_item)
            if self.font_big:
                sdlttf.TTF_CloseFont(self.font_big)
            sdlttf.TTF_Quit()
            sdl2.SDL_Quit()
        except Exception:
            pass
