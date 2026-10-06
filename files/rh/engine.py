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
import math
import ctypes

import sdl2
import sdl2.ext
import sdl2.sdlttf as sdlttf

from . import state
from .paths import APP_DIR, SDCARD_PATH
from .fonts import FALLBACK_FONT, font_candidates, pick_font
from .inputs import InputManager
from .logger import get_logger
from .ui.primitives import FOOTER_H, HEADER_H, footer_layout, theme

log = get_logger()

# Logo khoi dong NLK kieu Netflix (port tu Music-Player docs/NLK_INTRO_LOGO.md).
INTRO_BG = (8, 8, 12, 255)      # nen gan den
INTRO_RED = (229, 9, 20, 255)   # do Netflix
INTRO_DARK = (60, 5, 8, 255)    # do sam (glyph toi / glow)
INTRO_WHITE = (255, 255, 255, 255)
INTRO_LETTERS = "NLK"
INTRO_DURATION = 2.2
INTRO_FONT_SIZE = 168  # font_big (56) x 3, nhu "giant" = hero x 3 ben Music-Player


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
        self.font_intro = None
        self.controllers = []
        self.joysticks = []
        self.texture_cache = {}
        self.exit_reason = "not_started"

    # ----- SDL init --------------------------------------------------------

    def init_sdl(self):
        try:
            with open("/tmp/stay_alive", "w") as f:
                pass
        except Exception:
            pass
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
            self.font_intro = sdlttf.TTF_OpenFont(path_b, INTRO_FONT_SIZE)
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

    def draw_text_right(self, text, font, x, y, r, g, b, a=255,
                          center_y=False):
        if not font or not text:
            return
        w = self.measure_text(text, font)
        self.draw_text(text, font, int(x - w), int(y), r, g, b, a,
                       center_y=center_y)

    def draw_bmp(self, path, x, y, width=None, height=None):
        """Load a BMP once and draw it at the requested size."""
        if not self.renderer or not path:
            return False
        cached = self.texture_cache.get(path)
        if cached is None:
            try:
                surf = sdl2.SDL_LoadBMP(os.fsencode(path))
                if not surf:
                    self.texture_cache[path] = False
                    return False
                texture = sdl2.SDL_CreateTextureFromSurface(self.renderer, surf)
                source_w = int(surf.contents.w)
                source_h = int(surf.contents.h)
                sdl2.SDL_FreeSurface(surf)
                if not texture:
                    self.texture_cache[path] = False
                    return False
                cached = (texture, source_w, source_h)
                self.texture_cache[path] = cached
            except Exception as exc:
                log.warning("cannot load BMP %s: %s", path, exc)
                self.texture_cache[path] = False
                return False
        if cached is False:
            return False
        texture, source_w, source_h = cached
        draw_w = int(width or source_w)
        draw_h = int(height or source_h)
        dst = sdl2.SDL_Rect(int(x), int(y), draw_w, draw_h)
        return sdl2.SDL_RenderCopy(self.renderer, texture, None, dst) == 0

    # ----- NLK boot logo (intro 2.2s, port tu Music-Player) -------------------

    def play_intro(self, duration=INTRO_DURATION):
        """Chay intro NLK ngay sau init SDL/fonts, truoc main loop.

        Tra ve "quit" neu nhan SDL_QUIT giua intro, None trong moi truong
        hop con lai (het gio / skip / intro off / thieu renderer).
        Trong vong lap chi lam toan vi tri + dan texture + Present;
        tuyet doi khong TTF_Render*, khong file/IO/network.
        """
        try:
            enabled = bool(getattr(state, "intro", True))
        except Exception:
            enabled = True
        if not enabled:
            return None
        if not self.renderer:
            return None
        glyphs = self._build_intro_glyphs()
        try:
            start = time.monotonic()
            evt = sdl2.SDL_Event()
            while True:
                elapsed = time.monotonic() - start
                if elapsed >= duration:
                    break
                while sdl2.SDL_PollEvent(evt):
                    if evt.type == sdl2.SDL_QUIT:
                        self.exit_reason = "sdl_quit"
                        self.running = False
                        return "quit"
                    try:
                        self.input_mgr.feed_event(evt)
                    except Exception:
                        pass
                try:
                    inputs = self.input_mgr.poll()
                except Exception:
                    inputs = {}
                # Bat ky phim/nut nao cung skip ngay lap tuc.
                if inputs.get("edges") or inputs.get("any"):
                    break
                self._render_intro_frame(min(1.0, elapsed / duration), glyphs)
                try:
                    sdl2.SDL_Delay(16)
                except Exception:
                    try:
                        time.sleep(0.016)
                    except Exception:
                        break
        finally:
            self._free_intro_glyphs(glyphs)
        return None

    def _render_intro_glyph(self, letter, color):
        """Pre-render 1 chu x 1 mau thanh texture (goi 1 lan truoc loop)."""
        if not self.font_intro or not self.renderer:
            return (None, 0, 0)
        try:
            rgba = sdl2.SDL_Color(int(color[0]), int(color[1]),
                                  int(color[2]), int(color[3]))
            surf = sdlttf.TTF_RenderUTF8_Blended(
                self.font_intro, letter.encode("utf-8"), rgba)
            if not surf:
                return (None, 0, 0)
            tex = sdl2.SDL_CreateTextureFromSurface(self.renderer, surf)
            try:
                width, height = surf.contents.w, surf.contents.h
            except Exception:
                width, height = (0, 0)
            try:
                sdl2.SDL_FreeSurface(surf)
            except Exception:
                pass
            if not tex:
                return (None, 0, 0)
            return (tex, width, height)
        except Exception:
            return (None, 0, 0)

    def _build_intro_glyphs(self):
        """Ve truoc moi chu NLK x 3 mau (sam/tuoi/trang), giu trong dict."""
        cache = {}
        if not self.font_intro or not self.renderer:
            return cache
        colors = {
            "dark": INTRO_DARK,
            "bright": INTRO_RED,
            "white": INTRO_WHITE,
        }
        for letter in INTRO_LETTERS:
            for name, color in colors.items():
                try:
                    texture, width, height = self._render_intro_glyph(letter, color)
                except Exception:
                    texture, width, height = (None, 0, 0)
                if texture:
                    cache[(letter, name)] = (texture, width, height)
        return cache

    def _free_intro_glyphs(self, glyphs):
        for texture, _width, _height in (glyphs or {}).values():
            try:
                if texture:
                    sdl2.SDL_DestroyTexture(texture)
            except Exception:
                pass

    def _blit_intro_texture(self, texture, x, y, width, height):
        if not texture or not self.renderer or width <= 0 or height <= 0:
            return False
        try:
            dst = sdl2.SDL_Rect(int(x), int(y), int(width), int(height))
            sdl2.SDL_RenderCopy(self.renderer, texture, None, dst)
            return True
        except Exception:
            return False

    @staticmethod
    def _intro_spread(progress):
        ease = min(1.0, max(0.0, progress / 0.55))
        return 4 + (30 - 4) * (1 - (1 - ease) * (1 - ease))

    def _render_intro_frame(self, progress, glyphs=None):
        progress = max(0.0, min(1.0, float(progress)))
        if not self.renderer:
            return
        self.fill_rect(0, 0, self.screen_w, self.screen_h,
                       INTRO_BG[0], INTRO_BG[1], INTRO_BG[2], INTRO_BG[3])
        center_y = self.screen_h // 2
        if glyphs:
            self._render_intro_glyphs(progress, glyphs, center_y)
        else:
            # Fallback khi thieu font_intro: ve chu thuong, khong crash.
            spacing = 18
            try:
                widths = [self.measure_text(letter, self.font_big)
                          for letter in INTRO_LETTERS]
            except Exception:
                widths = [60, 60, 60]
            total = sum(widths) + spacing * (len(INTRO_LETTERS) - 1)
            cursor = (self.screen_w - total) // 2
            layout = []
            for letter, width in zip(INTRO_LETTERS, widths):
                layout.append((letter, cursor, width))
                cursor += width + spacing
            for index, (letter, x, _width) in enumerate(layout):
                enter_at = 0.05 + index * 0.16
                local = (progress - enter_at) / 0.30
                if local <= 0.0:
                    continue
                local = min(1.0, local)
                rise = int((1.0 - local) * 60)
                blend = min(1.0, local * 1.5)
                color = tuple(
                    int(INTRO_DARK[c] + (INTRO_RED[c] - INTRO_DARK[c]) * blend)
                    for c in range(3)
                ) + (255,)
                self.draw_text(letter, self.font_big or self.font_title,
                               x, center_y - 30 + rise,
                               color[0], color[1], color[2])
            if progress > 0.72:
                sweep = (progress - 0.72) / 0.28
                for index, (letter, x, _width) in enumerate(layout):
                    center = index / 2.0
                    if abs(sweep - center * 0.9) < 0.18:
                        self.draw_text(letter, self.font_big or self.font_title,
                                       x, center_y - 30, 255, 255, 255)
        try:
            sdl2.SDL_RenderPresent(self.renderer)
        except Exception:
            pass

    def _render_intro_glyphs(self, progress, glyphs, center_y):
        spacing = self._intro_spread(progress)
        try:
            widths = [glyphs[(letter, "bright")][1] for letter in INTRO_LETTERS]
        except (KeyError, TypeError):
            try:
                widths = [self.measure_text(letter, self.font_intro)
                          for letter in INTRO_LETTERS]
            except Exception:
                widths = [180, 180, 180]
        total = sum(widths) + spacing * 2
        fit = min(1.0, (self.screen_w - 80) / total) if total > 0 else 1.0
        cursor = (self.screen_w - total * fit) // 2
        for index, letter in enumerate(INTRO_LETTERS):
            width = widths[index]
            try:
                _texture, tex_w, tex_h = glyphs[(letter, "bright")]
            except (KeyError, TypeError):
                cursor += (width + spacing) * fit
                continue
            if tex_w <= 0 or tex_h <= 0:
                cursor += (width + spacing) * fit
                continue
            dest_w, dest_h = tex_w * fit, tex_h * fit
            x = cursor + (width * fit - dest_w) // 2
            enter_at = 0.05 + index * 0.16
            local = (progress - enter_at) / 0.30
            if local > 0.0:
                local = min(1.0, local)
                rise = int((1.0 - local) * 90)
                if local > 0.65:
                    rise += int(-14 * math.sin((local - 0.65) / 0.35 * math.pi))
                y = center_y - dest_h // 2 + rise
                bright = local * 1.5 >= 0.75
                if bright:
                    try:
                        glow, _gw, _gh = glyphs[(letter, "dark")]
                        self._blit_intro_texture(glow, x + 4 * fit, y + 6 * fit,
                                                 dest_w, dest_h)
                    except (KeyError, TypeError):
                        pass
                    key = "bright"
                else:
                    key = "dark"
                try:
                    texture, _tw, _th = glyphs[(letter, key)]
                except (KeyError, TypeError):
                    texture = None
                self._blit_intro_texture(texture, x, y, dest_w, dest_h)
            cursor += (width + spacing) * fit
        if progress > 0.72:
            sweep = (progress - 0.72) / 0.28
            cursor = (self.screen_w - total * fit) // 2
            for index, letter in enumerate(INTRO_LETTERS):
                width = widths[index]
                try:
                    texture, tex_w, tex_h = glyphs[(letter, "white")]
                except (KeyError, TypeError):
                    cursor += (width + spacing) * fit
                    continue
                center = index / 2.0
                if abs(sweep - center * 0.9) < 0.18:
                    self._blit_intro_texture(
                        texture, cursor + (width * fit - tex_w * fit) // 2,
                        center_y - tex_h * fit // 2, tex_w * fit, tex_h * fit)
                cursor += (width + spacing) * fit

    # ----- main loop ------------------------------------------------------

    def quit(self, reason="user_exit"):
        self.exit_reason = reason
        self.running = False

    def run(self):
        self.running = True
        self.exit_reason = "running"
        if self.play_intro() == "quit":
            log.info("engine stopped during intro: reason=%s", self.exit_reason)
            return self.exit_reason
        footer_h = 56
        header_h = 64
        last = time.time()
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

            if self.active_modal:
                modal = self.active_modal
                modal.handle_input(inputs)
                if self.active_modal is modal:
                    modal.update(0.016)
            elif self.current_screen:
                self.current_screen.handle_input(inputs)
                self.current_screen.update(0.016)

            # render
            colors = theme(getattr(state, "theme", "dark"))
            sdl2.SDL_SetRenderDrawColor(self.renderer, *colors["bg"], 255)
            sdl2.SDL_RenderClear(self.renderer)
            self.fill_rect(0, 0, self.screen_w, self.screen_h, *colors["bg"], 255)
            # header
            self.fill_rect(0, 0, self.screen_w, header_h, *colors["header"], 255)
            self.fill_rect(0, header_h - 2, self.screen_w, 2, *colors["header_line"], 255)
            title = self.current_screen.get_header_title() if self.current_screen else ""
            if title and self.font_title:
                self.draw_text(title, self.font_title, 30, header_h // 2,
                               *colors["text"], center_y=True)
            right = (self.current_screen.get_header_right()
                     if self.current_screen else "")
            if right and self.font_sub:
                self.draw_text_right(right, self.font_sub, self.screen_w - 30,
                                     header_h // 2, *colors["muted"], center_y=True)

            # body
            if self.active_modal:
                if self.current_screen:
                    self.current_screen.render(self)
                self.active_modal.render(self)
            elif self.current_screen:
                self.current_screen.render(self)

            # footer
            foot_y = self.screen_h - footer_h
            self.fill_rect(0, foot_y, self.screen_w, footer_h, *colors["footer"], 255)
            self.fill_rect(0, foot_y, self.screen_w, 2, *colors["footer_line"], 255)
            actions = self.current_screen.get_footer_actions() if self.current_screen else []
            for key, label, chip_x, chip_w, label_x in footer_layout(
                    self, actions, start_x=30, max_x=self.screen_w - 30):
                self.fill_rect(chip_x, foot_y + 10, chip_w, 36,
                               *colors["accent"], 220)
                if self.font_sub:
                    self.draw_text(key, self.font_sub, chip_x + chip_w // 2,
                                   foot_y + 28, *colors["chip_text"],
                                   center_x=True, center_y=True)
                if self.font_sub:
                    self.draw_text(label, self.font_sub, label_x, foot_y + 28,
                                   *colors["sub"], center_y=True)

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
            for cached in getattr(self, "texture_cache", {}).values():
                if cached:
                    sdl2.SDL_DestroyTexture(cached[0])
            self.texture_cache = {}
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
            if self.font_intro:
                sdlttf.TTF_CloseFont(self.font_intro)
            sdlttf.TTF_Quit()
            sdl2.SDL_Quit()
        except Exception:
            pass
