import sys
import math
import argparse
import sounddevice as sd
import numpy as np

# Use PyGObject GTK3 + Cairo for True 32-bit ARGB per-pixel transparency
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import cairo

# Shared audio energy measurement
current_audio_energy = 0.0

def audio_monitor_callback(indata, frames, time_info, status):
    """Calculate real-time RMS audio volume from mic input."""
    global current_audio_energy
    try:
        rms = float(np.sqrt(np.mean(indata**2)))
        current_audio_energy = current_audio_energy * 0.6 + rms * 0.4
    except Exception:
        pass

def get_waveform_points(cx, cy, rx, ry, t, energy, num_points=72, scale=1.0):
    """
    Generate harmonic fluid contour with audio-reactive spikes that can freely
    reach outside the ellipse boundary.
    """
    points = []
    # Boost sensitivity so speaking voice causes dramatic out-bursting ripples
    audio_boost = min(1.0, energy * 32.0)

    for i in range(num_points):
        theta = 2.0 * math.pi * i / num_points
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        # Base elliptical contour matching the ellipse outline
        r_base = (rx * ry) / math.sqrt((ry * cos_t)**2 + (rx * sin_t)**2)

        # Harmonic ambient fluid wobble
        wobble1 = 3.5 * math.sin(3 * theta + t * 4.0)
        wobble2 = 2.0 * math.cos(5 * theta - t * 3.5)

        # High energy audio voice ripples: these dynamically expand outwards into the transparent zone!
        voice_ripple = (6.0 + 22.0 * audio_boost) * math.sin(7 * theta + t * 6.5) * (audio_boost + 0.12)
        voice_subripple = (3.0 + 12.0 * audio_boost) * math.cos(11 * theta - t * 8.0) * (audio_boost + 0.08)

        r_total = (r_base + wobble1 + wobble2 + voice_ripple + voice_subripple) * scale
        px = cx + r_total * cos_t
        py = cy + r_total * sin_t
        points.append((px, py))

    return points

def draw_smooth_polygon(cr, points):
    """Draw a smooth closed Bezier spline path through points."""
    n = len(points)
    if n < 3:
        return
    cr.move_to((points[0][0] + points[-1][0]) / 2.0, (points[0][1] + points[-1][1]) / 2.0)
    for i in range(n):
        p0 = points[i]
        p1 = points[(i + 1) % n]
        mid_x = (p0[0] + p1[0]) / 2.0
        mid_y = (p0[1] + p1[1]) / 2.0
        cr.curve_to(p0[0], p0[1], p0[0], p0[1], mid_x, mid_y)
    cr.close_path()

class GlowingFluidOSD(Gtk.Window):
    def __init__(self, position="top-left", duration=2.0, always_on=False):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.position = position
        self.duration = duration
        self.always_on = always_on

        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_above(True)

        # Support 32-bit ARGB visual for true per-pixel transparency
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        # Window dimensions (generous margin to allow glowing waves to burst outwards freely)
        self.win_width = 440
        self.win_height = 240
        self.cx = self.win_width / 2.0
        self.cy = self.win_height / 2.0

        # Ellipse base axes (Core GUI fits nicely inside rx=145, ry=72)
        self.rx = 145.0
        self.ry = 72.0

        # Position calculation: Detect which monitor currently has the mouse cursor
        display = Gdk.Display.get_default()
        monitor = None
        try:
            seat = display.get_default_seat()
            if seat:
                pointer = seat.get_pointer()
                if pointer:
                    _, mouse_x, mouse_y = pointer.get_position()
                    monitor = display.get_monitor_at_point(mouse_x, mouse_y)
        except Exception:
            monitor = None

        if not monitor:
            monitor = display.get_primary_monitor() or display.get_monitor(0)

        geom = monitor.get_geometry() if monitor else None
        base_x = geom.x if geom else 0
        base_y = geom.y if geom else 0
        screen_w = geom.width if geom else screen.get_width()
        screen_h = geom.height if geom else screen.get_height()
        margin_x = 24
        margin_y = 36

        if position == "top-left":
            pos_x = base_x + margin_x
            pos_y = base_y + margin_y
        elif position == "top-right":
            pos_x = base_x + max(0, screen_w - self.win_width - margin_x)
            pos_y = base_y + margin_y
        elif position == "bottom-left":
            pos_x = base_x + margin_x
            pos_y = base_y + max(0, screen_h - self.win_height - margin_y - 20)
        elif position == "bottom-right":
            pos_x = base_x + max(0, screen_w - self.win_width - margin_x)
            pos_y = base_y + max(0, screen_h - self.win_height - margin_y - 20)
        elif position == "center":
            pos_x = base_x + max(0, (screen_w - self.win_width) // 2)
            pos_y = base_y + max(0, (screen_h - self.win_height) // 2)
        else:
            pos_x = base_x + margin_x
            pos_y = base_y + margin_y

        self.set_default_size(self.win_width, self.win_height)
        self.move(pos_x, pos_y)

        # Connect drawing event
        self.connect("draw", self.on_draw)

        # Audio stream
        try:
            self.stream = sd.InputStream(
                channels=1,
                samplerate=16000,
                dtype="float32",
                callback=audio_monitor_callback
            )
            self.stream.start()
        except Exception as e:
            self.stream = None
            print(f"[OSD] Microphone notice: {e}")

        self.t = 0.0

        # Animation timer ~ 30 FPS (33ms)
        GLib.timeout_add(33, self.on_tick)

        # Auto close timeout if not always_on
        if not self.always_on:
            close_ms = int(max(0.5, self.duration) * 1000)
            GLib.timeout_add(close_ms, self.on_timeout)

    def on_tick(self):
        self.t += 0.07
        self.queue_draw()
        return True

    def on_timeout(self):
        self.cleanup()
        return False

    def cleanup(self):
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        Gtk.main_quit()

    def on_draw(self, widget, cr):
        # 1. Clear background to 100% transparent
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        cr.paint()

        cr.set_operator(cairo.OPERATOR_OVER)

        t = self.t
        energy = current_audio_energy
        audio_boost = min(1.0, energy * 30.0)

        # ----------------------------------------------------
        # 2. RADIAL GRADIENT ELLIPSE BACKGROUND
        # Center = 80% Opacity (dark black/slate core)
        # Boundary = Smoothly fades to 0% Opacity (fully transparent outside)
        # Expanded by 20% (rx * 1.20, ry * 1.20) as requested, allowing the
        # glowing waveform to sit comfortably inside the ambient backdrop
        # ----------------------------------------------------
        cr.save()
        cr.translate(self.cx, self.cy)
        cr.scale(self.rx * 1.20, self.ry * 1.20)

        # Unit circle radial gradient
        rad_pat = cairo.RadialGradient(0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
        # Center: deep rich black/midnight blue with reduced opacity (~20% lower for a sleek translucent glass look)
        rad_pat.add_color_stop_rgba(0.00, 0.03, 0.06, 0.10, 0.80)  # 80% opacity center
        rad_pat.add_color_stop_rgba(0.45, 0.03, 0.05, 0.09, 0.76)
        rad_pat.add_color_stop_rgba(0.70, 0.02, 0.04, 0.07, 0.56)
        rad_pat.add_color_stop_rgba(0.88, 0.01, 0.02, 0.04, 0.28)
        rad_pat.add_color_stop_rgba(1.00, 0.00, 0.00, 0.00, 0.00) # 0% opacity edge!

        cr.set_source(rad_pat)
        cr.arc(0.0, 0.0, 1.0, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

        # ----------------------------------------------------
        # 3. GLOWING WAVEFORM CONTOURS
        # Perfectly fitted to the ellipse outline at baseline,
        # with audio-reactive spikes erupting outwards into open space!
        # Multi-layer glow: outer blur haze -> neon body -> intense laser core
        # ----------------------------------------------------
        pts_wave = get_waveform_points(self.cx, self.cy, self.rx, self.ry, t, energy, num_points=72, scale=1.0)

        # Layer 1: Broad soft ambient cyan glow halo
        cr.save()
        draw_smooth_polygon(cr, pts_wave)
        cr.set_source_rgba(0.02, 0.55, 0.85, 0.22 + 0.25 * audio_boost)
        cr.set_line_width(9.0 + 6.0 * audio_boost)
        cr.stroke()
        cr.restore()

        # Layer 2: Medium vibrant cyan neon glow
        cr.save()
        draw_smooth_polygon(cr, pts_wave)
        cr.set_source_rgba(0.06, 0.75, 0.95, 0.55 + 0.35 * audio_boost)
        cr.set_line_width(4.5 + 2.5 * audio_boost)
        cr.stroke()
        cr.restore()

        # Layer 3: Sharp laser core (Intense bright turquoise/white line)
        cr.save()
        draw_smooth_polygon(cr, pts_wave)
        cr.set_source_rgba(0.75, 0.95, 1.00, 0.95)
        cr.set_line_width(1.8)
        cr.stroke()
        cr.restore()

        # Extra secondary subtle wave pulse
        pts_wave2 = get_waveform_points(self.cx, self.cy, self.rx, self.ry, t + 0.4, energy * 0.7, num_points=64, scale=1.02)
        cr.save()
        draw_smooth_polygon(cr, pts_wave2)
        cr.set_source_rgba(0.14, 0.80, 0.98, 0.35 * audio_boost + 0.1)
        cr.set_line_width(1.5)
        cr.stroke()
        cr.restore()

        # ----------------------------------------------------
        # 4. FLOATING BIOLUMINESCENT DROPLETS (Shot 1 Style)
        # ----------------------------------------------------
        droplets = [
            (0.38, 1.05, 3.2),
            (2.80, 1.07, 3.8),
            (5.45, 1.06, 3.0)
        ]
        for angle_b, dist_b, r_b in droplets:
            da = angle_b + math.sin(t * 1.5 + angle_b) * 0.08
            dist_curr = dist_b + math.cos(t * 2.0 + r_b) * 0.04 + (audio_boost * 0.06)
            dx = self.cx + self.rx * dist_curr * math.cos(da)
            dy = self.cy + self.ry * dist_curr * math.sin(da)
            
            # Glow halo for droplet
            cr.set_source_rgba(0.06, 0.75, 0.95, 0.35)
            cr.arc(dx, dy, r_b + 3.0, 0, 2 * math.pi)
            cr.fill()
            
            # Droplet core
            cr.set_source_rgba(0.55, 0.92, 1.0, 0.90)
            cr.arc(dx, dy, r_b, 0, 2 * math.pi)
            cr.fill()

        # ----------------------------------------------------
        # 5. CENTRAL MORPHING BLOB (Shot 1 Sci-Fi Core Icon)
        # ----------------------------------------------------
        blob_cx = self.cx - 105
        blob_cy = self.cy - 12
        base_r = 18.0
        pulse = (math.sin(t * 3.5) + 1.0) * 0.5
        
        # Glow ring around blob
        glow_r = base_r + 7.0 + pulse * 3.0 + energy * 35.0
        cr.set_source_rgba(0.03, 0.57, 0.70, 0.45)
        cr.set_line_width(1.5)
        cr.arc(blob_cx, blob_cy, glow_r, 0, 2 * math.pi)
        cr.stroke()

        # Organic morphing blob body
        blob_pts = []
        for i in range(24):
            angle = 2.0 * math.pi * i / 24.0
            wobble = (5.0 + 8.0 * audio_boost) * math.sin(3 * angle + t * 4.5) + (3.5 + 5.0 * audio_boost) * math.cos(2 * angle - t * 3.2)
            r = base_r + wobble + (audio_boost * 5.0)
            blob_pts.append((blob_cx + r * math.cos(angle), blob_cy + r * math.sin(angle)))
        
        cr.save()
        draw_smooth_polygon(cr, blob_pts)
        cr.set_source_rgba(0.01, 0.41, 0.63, 0.85)
        cr.fill_preserve()
        cr.set_source_rgba(0.13, 0.83, 0.93, 0.95)
        cr.set_line_width(2.0)
        cr.stroke()
        cr.restore()

        # Shiny central core dot
        core_r = 4.0 + math.cos(t * 4.0) * 1.0 + (audio_boost * 2.0)
        cr.set_source_rgba(0.90, 0.98, 1.0, 0.95)
        cr.arc(blob_cx, blob_cy, core_r, 0, 2 * math.pi)
        cr.fill()

        # ----------------------------------------------------
        # 6. INNER GUI CONTENT (Clean vector icons, VU bar & key badges)
        # ----------------------------------------------------
        # Vector microphone icon
        mic_x = self.cx - 72
        mic_y = self.cy - 34
        mic_size = 15.0
        
        cr.save()
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        # Mic capsule
        mc_w = mic_size * 0.44
        mc_h = mic_size * 0.72
        mc_r = mc_w / 2.0
        # Color reacts to voice: vibrant cyan if speaking, soft slate if quiet
        if audio_boost > 0.15:
            cr.set_source_rgba(0.22, 0.85, 0.98, 1.0) # Active cyan
        else:
            cr.set_source_rgba(0.45, 0.62, 0.78, 0.85)

        cr.arc(mic_x + mc_r, mic_y + mc_r, mc_r, math.pi, 0)
        cr.arc(mic_x + mc_r, mic_y + mc_h - mc_r, mc_r, 0, math.pi)
        cr.close_path()
        cr.fill()
        
        # Mic cradle arc
        cr.set_line_width(1.6)
        arc_r = mc_w * 0.82
        cr.arc(mic_x + mc_r, mic_y + mc_h * 0.56, arc_r, 0, math.pi)
        cr.stroke()
        
        # Mic stem
        cr.move_to(mic_x + mc_r, mic_y + mc_h * 0.56 + arc_r)
        cr.line_to(mic_x + mc_r, mic_y + mic_size * 1.05)
        cr.stroke()
        cr.restore()

        # "Listening..." Title text with speech activity indicator
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12.5)
        if audio_boost > 0.15:
            cr.set_source_rgba(0.25, 0.90, 1.00, 1.0)
            status_title = "Listening..."
        else:
            cr.set_source_rgba(0.65, 0.78, 0.90, 0.85)
            status_title = "Ready..."
        cr.move_to(mic_x + 16, self.cy - 23)
        cr.show_text(status_title)

        # Real-time Volume Level Meter (Linear VU Gauge Bar)
        vu_x = mic_x + 16
        vu_y = self.cy - 16
        vu_w = 46.0
        vu_h = 3.2
        # Background bar track
        cr.save()
        cr.set_source_rgba(0.12, 0.18, 0.28, 0.8)
        cr.rectangle(vu_x, vu_y, vu_w, vu_h)
        cr.fill()
        # Active filled level
        fill_w = max(2.0, min(vu_w, vu_w * audio_boost))
        # Gradient for VU meter (cyan to emerald)
        vu_pat = cairo.LinearGradient(vu_x, vu_y, vu_x + vu_w, vu_y)
        vu_pat.add_color_stop_rgba(0.0, 0.06, 0.75, 0.95, 0.95)
        vu_pat.add_color_stop_rgba(0.8, 0.16, 0.85, 0.75, 0.95)
        vu_pat.add_color_stop_rgba(1.0, 0.95, 0.40, 0.40, 1.00) # Peak yellow/red
        cr.set_source(vu_pat)
        cr.rectangle(vu_x, vu_y, fill_w, vu_h)
        cr.fill()
        cr.restore()

        # Mode Shortcuts (Aligned horizontally on one line)
        def draw_horizontal_shortcut(x_start, y_pos, key_char, label_text, border_rgba):
            badge_h = 16.0
            cr.save()
            cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(9.0)
            ke = cr.text_extents(key_char)
            key_w = max(18.0, ke.width + 8.0)

            # Key background
            cr.set_source_rgba(0.10, 0.16, 0.26, 0.85)
            cr.rectangle(x_start, y_pos, key_w, badge_h)
            cr.fill()

            # Key border
            cr.set_source_rgba(*border_rgba)
            cr.set_line_width(1.0)
            cr.rectangle(x_start, y_pos, key_w, badge_h)
            cr.stroke()

            # Key text
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
            cr.move_to(x_start + (key_w - ke.width) / 2.0 - ke.x_bearing, y_pos + (badge_h - ke.height) / 2.0 - ke.y_bearing)
            cr.show_text(key_char)

            # Label text
            cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(9.5)
            cr.set_source_rgba(0.85, 0.90, 0.96, 0.95)
            le = cr.text_extents(label_text)
            cr.move_to(x_start + key_w + 5.0, y_pos + (badge_h - le.height) / 2.0 - le.y_bearing)
            cr.show_text(label_text)
            cr.restore()
            return key_w + 5.0 + le.width

        # Render all 3 options on a single horizontal line
        line_y = self.cy + 10
        gap = 14.0
        # Calculate total width to center align the group
        w_e = 18.0 + 5.0 + 35.0 # English
        w_z = 18.0 + 5.0 + 38.0 # Chinese
        w_esc = 27.0 + 5.0 + 34.0 # Cancel
        total_group_w = w_e + w_z + w_esc + gap * 2
        cur_x = self.cx - total_group_w / 2.0 + 10

        cur_x += draw_horizontal_shortcut(cur_x, line_y, "E", "English", (0.06, 0.71, 0.83, 0.5)) + gap
        cur_x += draw_horizontal_shortcut(cur_x, line_y, "Z", "Chinese", (0.06, 0.71, 0.83, 0.5)) + gap
        draw_horizontal_shortcut(cur_x, line_y, "ESC", "Cancel", (0.95, 0.25, 0.37, 0.5))

        # ----------------------------------------------------
        # 7. RIGHT-SIDE MINI EQUALIZER BARS
        # ----------------------------------------------------
        eq_x = self.cx + 56
        eq_y = self.cy - 18
        num_bars = 6
        cr.set_line_width(2.0)
        for i in range(num_bars):
            bar_h = 3.0 + 10.0 * audio_boost * (0.35 + 0.65 * (math.sin(t * 8.0 + i * 1.3)**2))
            bx = eq_x + i * 5
            # Glow bar
            cr.set_source_rgba(0.06, 0.75, 0.95, 0.4)
            cr.set_line_width(3.0)
            cr.move_to(bx, eq_y - bar_h)
            cr.line_to(bx, eq_y + bar_h)
            cr.stroke()

            # Solid bar
            cr.set_source_rgba(0.22, 0.85, 0.98, 0.95)
            cr.set_line_width(1.6)
            cr.move_to(bx, eq_y - bar_h)
            cr.line_to(bx, eq_y + bar_h)
            cr.stroke()

        return False

def main():
    parser = argparse.ArgumentParser(description="True ARGB Glowing Fluid Waveform OSD")
    parser.add_argument("--position", default="top-left", choices=["top-left", "top-right", "bottom-left", "bottom-right", "center"])
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--always-on", action="store_true")
    args = parser.parse_args()

    win = GlowingFluidOSD(
        position=args.position,
        duration=args.duration,
        always_on=args.always_on
    )
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
