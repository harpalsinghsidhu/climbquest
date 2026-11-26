import math, random, wave, array, os
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.core.window import Window 
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, Rectangle, Triangle, Line,
                           PushMatrix, PopMatrix, Translate, Scale, Rotate)
                           
RATE = 16000
HSP = 250                       # sideways speed of the hero (units/sec)

# name, gap between branches, branch width, gravity, jump speed,
# flood speed, chance of moving branch, chance of crumbling cloud
LV = [
    dict(name='JUNGLE', tip='Tap left or right to jump', gap=(85, 125), w=(115, 170), g=1500, jump=800,
         flood=20, moving=0.0, crumble=0.0),
    dict(name='SKY', tip='Wings on! Watch the wind', gap=(105, 150), w=(85, 120), g=1500, jump=800,
         flood=32, moving=0.2, crumble=0.3),
    dict(name='SPACE', tip='Spacesuit on! Low gravity', gap=(125, 185), w=(65, 95), g=850, jump=720,
         flood=46, moving=0.35, crumble=0.0),
]

L2, L3, GOAL = 1500, 3500, 5500      # height where level 2 starts, level 3 starts, and the summit

def level_at(y):
    return 0 if y < L2 else (1 if y < L3 else 2)
    
BG = [(0, (0.06, 0.26, 0.10)), (L2 - 400, (0.06, 0.26, 0.10)),
      (L2 + 400, (0.42, 0.74, 1.0)), (L3 - 800, (0.30, 0.55, 0.90)),
      (L3 + 400, (0.0, 0.0, 0.0))]
      
def bg(y):
    if y <= BG[0][0]:
        return BG[0][1]
    for (y0, c0), (y1, c1) in zip(BG, BG[1:]):
        if y <= y1:
            t = (y - y0) / (y1 - y0)
            return tuple(c0[i] + (c1[i] - c0[i]) * t for i in range(3))
    return BG[-1][1]
    
# ------------------------SOUND SYNTHESIS---------------------
def wv(kind, phase):
    p = phase % 1
    if kind == 'sq':
        return 1 if p < 0.5 else -1
    if kind == 'tri':
        return 4 * abs(p - 0.5) - 1
    if kind == 'noise':
        return random.uniform(-1, 1)
    return math.sin(2 * math.pi * p)
    
def fx(f0, f1, dur, vol, kind):
    n = int(RATE * dur)
    out, ph = [], 0
    for i in range(n):
        t = i / n
        ph += (f0 + (f1 - f0) * t) / RATE
        out.append(wv(kind, ph) * (1 - t) * vol)
    return out
    
def hz(k):                      # semitones above middle C
    return 261.63 * 2 ** (k / 12)
    
def build_music(step, bass, lead, kind, lv, drums=False):
    n = int(RATE * step * len(lead))
    mix = [0.0] * n
    
    def note(s, f, dur, vol, k):
        st, m = int(s * step * RATE), int(dur * RATE)
        for i in range(m):
            if st + i >= n:
                break 
            mix[st + i] += wv(k, i * f / RATE) * (1 - i / m) * vol
            
    for s, k in enumerate(lead):
        if k is not None:
            note(s, hz(k), step * 0.95, lv, kind)
    for s, k in enumerate(bass):
        if k is not None:
            note(s, hz(k), step * 2, 0.28, 'tri')
    if drums:
        for s in range(0, len(lead), 2):
            note(s, 100, 0.04, 0.2 if s % 4 == 0 else 0.08, 'noise')
    return mix
    
def track_jungle():             # bouncy pentatonic with drums
    a = [0, 4, 7, 4, 9, 7, 4, 2, 0, 4, 7, 12, 9, 7, 4, 7]
    b = [7, 9, 12, 9, 7, 4, 2, 4, 0, 2, 4, 7, 4, 2, 0, None]
    bass = [None] * 32
    for i, r in enumerate([-12, -17, -15, -17, -12, -17, -15, -19]):
        bass[i * 4] = r
    return build_music(0.17, bass, a + b, 'sq', 0.09, True)
    
def track_sky():                # slow dreamy arpeggios
    chords = [(0, 4, 7, 11), (-3, 0, 4, 7), (-7, -3, 0, 4), (-5, -1, 2, 5)]
    lead, bass = [], [None] * 32
    for ci, c in enumerate(chords):
        for j in (0, 1, 2, 3, 2, 1, 0, 1):
            lead.append(c[j] + 12)
        bass[ci * 8] = c[0] - 12
        bass[ci * 8 + 4] = c[2] - 12
    return build_music(0.3, bass, lead,'sin', 0.16)
    
def track_space():              # driving minor arpeggios
    chords = [(9, 12, 16), (5, 9, 12), (0, 4, 7), (7, 11, 14)]
    lead, bass = [], [None] * 32
    for ci, c in enumerate(chords):
        for j in (0, 1, 2, 1, 0, 1, 2, 1):
            lead.append(c[j] + 12)
        for k in range(0, 8, 2):
            bass[ci * 8 + k] = c[0] - 12
    return build_music(0.16, bass, lead, 'sq', 0.08, True)
    
def save_wav(path, samples):
    buf = array.array('h', (int(max(-1, min(1, v)) * 32767) for v in samples))
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(buf.tobytes())
        
def make_sounds(folder):
    specs = {
        'jump': lambda: fx(350, 750, 0.12, 0.2, 'sq'),
        'land': lambda: fx(160, 70, 0.07, 0.3, 'sin'),
        'banana': lambda: fx(900, 1500, 0.14, 0.25, 'sin'),
        'power': lambda: fx(400, 1200, 0.25, 0.25, 'tri'),
        'hit': lambda: fx(300, 80, 0.25, 0.4, 'sq'),
        'over': lambda: fx(400, 60, 0.9, 0.4, 'tri'),
        'level': lambda: (fx(523, 523, 0.1, 0.25, 'sq') + fx(659, 659, 0.1, 0.25, 'sq') +
                          fx(784, 784, 0.1, 0.25, 'sq') + fx(1047, 1047, 0.3, 0.25, 'sq')),
        'music0': track_jungle,
        'music1': track_sky,
        'music2': track_space,
    }
    for name, fn in specs.items():
        p = os.path.join(folder, name + '.wav')
        if not os.path.exists(p):
            save_wav(p, fn())
            
# ---------------------GAME-----------------
class Game(Widget):
    def __init__(self, folder, **kw):
        super().__init__(**kw)
        self.folder = folder
        self.snd = {}
        for n in ('jump', 'land', 'banana', 'power', 'hit', 'over', 'level'):
            self.snd[n] = SoundLoader.load(os.path.join(folder, n + '.wav'))
        self.music = [SoundLoader.load(os.path.join(folder, 'music%d.wav' % i))
                      for i in range(3)]
        for m in self.music:
            if m:
                m.loop = True
        self.cur_music = -1
        self.hi = self.load_hi()
        self.time = 0
        self.over_t = 0
        W, H = Window.size 
        self.stars = [[random.random() * W, random.random() * H, random.choice((1, 2, 3))]
                      for _ in range(70)]
        self.decor = [[random.random() * 480, random.random() * 1600] for _ in range(7)]
        self.score_lbl = Label(size_hint=(None, None), halign='left', valign='top')
        self.over_lbl = Label(size_hint=(None, None), halign='center', valign='middle')
        self.banner_lbl = Label(size_hint=(None, None), halign='center', valign='middle')
        for lb in (self.score_lbl, self.over_lbl, self.banner_lbl):
            self.add_widget(lb)
        self.reset()
        Clock.schedule_interval(self.update, 1 / 60)
        
    # ------ helpers -----
    def sfx(self, name):
        s = self.snd.get(name)
        if s:
            s.stop()
            s.play()
            
    def set_music(self, i):
        if i == self.cur_music:
            return 
        if self.cur_music >= 0 and self.music[self.cur_music]:
            self.music[self.cur_music].stop()
        self.cur_music = i
        m = self.music[i]
        if m: 
            m.volume = 0.5
            m.play()
            
    def music_vol(self, v):
        m = self.music[self.cur_music] if self.cur_music >= 0 else None
        if m:
            m.volume = v
            
    def pause_music(self):
        m = self.music[self.cur_music] if self.cur_music >= 0 else None
        if m:
            m.stop()
            
    def resume_music(self):
        m = self.music[self.cur_music] if self.cur_music >= 0 else None
        if m:
            m.play()
            
    def load_hi(self):
        try:
            with open(os.path.join(self.folder, 'best.txt')) as f:
                return int(f.read())
        except Exception:
            return 0
            
    def save_hi(self):
        try:
            with open(os.path.join(self.folder, 'best.txt'), 'w') as f:
                f.write(str(self.hi))
        except Exception:
            pass 
            
    def total(self):
        return self.best_h + 10 * self.bananas
        
    def banner(self, txt, secs):
        self.banner_txt, self.banner_t = txt, secs
        
    def burst(self, x, y, col, n=10):
        for _ in range(n):
            a, s = random.random() * 6.28, random.uniform(60, 240)
            self.parts.append([x, y, math.cos(a) * s, math.sin(a) * s, 0.6, col])
    
    # ------ new game ---------
    def reset(self):
        W, H = Window.size 
        self.S = W / 480
        self.HU = H / self.S
        self.x, self.y, self.vx, self.vy = 240.0, 0.0, 0.0, 0.0
        first = dict(x=240, y=0, w=420, lvl=0, vx=0, crumble=False, t=None, dead=False)
        self.plats = [first]
        self.stand = first 
        self.haz, self.items, self.parts = [], [], []
        self.top, self.last_x = 0.0, 240.0
        self.cam = -self.HU * 0.38
        self.threat = self.cam - 260
        self.lives, self.bananas, self.best_h = 3, 0, 0
        self.inv, self.shield, self.spring = 0, False, False
        self.state, self.lvl, self.face = 'play', 0, 1
        self.wind, self.wind_t = 0, 3
        self.timers = {'coco': 2.0, 'bird': 3.0, 'met': 2.0, 'ufo': 4.0}
        self.over_lbl.text = ''
        self.flash = 0
        self.banner('LEVEL 1: JUNGLE\n' + LV[0]['tip'], 3.5)
        self.gen()
        self.set_music(0)
        self.music_vol(0.5)
        
    def gen(self):
        while self.top < GOAL and self.top < self.cam + self.HU + 250:
            lv = level_at(self.top + 100)
            P = LV[lv]
            y = self.top + random.uniform(*P['gap'])
            w = random.uniform(*P['w'])
            kind = None
            for g in (L2, L3, GOAL):                  # a gate or the summit falls in this step
                if self.top < g <= y:
                    y, kind = g, ('goal' if g == GOAL else 'gate')
                    break
            if kind:
                x, w, lv = 240, 440, level_at(y)
            else:
                x = min(max(self.last_x + random.uniform(-170, 170), w / 2 + 10), 470 - w / 2)
            p = dict(x=x, y=y, w=w, lvl=lv, vx=0, crumble=False, t=None, dead=False, kind=kind)
            if not kind:
                if random.random() < P['crumble']:
                    p['crumble'] = True
                elif random.random() < P['moving']:
                    p['vx'] = random.choice((-1, 1)) * random.uniform(50, 100)
            self.plats.append(p)
            if not kind:
                if lv == 0 and w > 125 and y > 400 and random.random() < 0.22:
                    self.haz.append(dict(k='snake', plat=p, off=0, d=1, r=15, x=x, y=y))
                if p['vx'] == 0 and random.random() < 0.55:
                    self.items.append(dict(k='ban', x=x + random.uniform(-w / 3, w / 3), y=y + 45))
                elif random.random() < 0.08:
                    self.items.append(dict(k=random.choice(('spring', 'shield')), x=x, y=y + 45))
            self.top, self.last_x = y, x
            
    # ---------- damage / death ----------
    def damage(self):
        if self.inv > 0:
            return 
        self.burst(self.x, self.y + 16, (1, 0.5, 0.3), 14)
        self.sfx('hit')
        if self.shield:
            self.shield = False
            self.inv = 1.0
            return 
        self.lives -= 1
        self.inv = 1.5
        self.stand = None
        self.vy = 300
        if self.lives <= 0:
            self.game_over()
            
    def fall(self):
        self.lives -= 1
        self.sfx('hit')
        self.burst(self.x, self.cam + 20, (1, 0.5, 0.3), 14)
        if self.lives <= 0:
            self.game_over()
            return 
        goal = self.cam + self.HU * 0.35
        cands = [p for p in self.plats if not p['dead'] and self.cam + 60 < p['y'] < self.cam + self.HU * 0.8]
        if cands:
            p = min(cands, key=lambda q: abs(q['y'] - goal))
        else:
            p = dict(x=240, y=goal, w=200, lvl=self.lvl, vx=0, crumble=False, t=None, dead=False)
            self.plats.append(p)
        self.x, self.y, self.vx, self.vy = p['x'], p['y'], 0, 0
        self.stand = p
        self.inv = 2.0
        self.threat = self.cam - 260
        
    def game_over(self):
        self.state = 'over'
        self.hi = max(self.hi, self.total())
        self.save_hi()
        self.sfx('over')
        self.music_vol(0.15)
        self.over_t = self.time
        self.over_lbl.text = ('GAME OVER\nScore %d\nHeight %d m\nBest %d\nTap to play again'
                              % (self.total(), self.best_h, self.hi))
                              
    def win(self):
        self.state = 'win'
        self.hi = max(self.hi, self.total())
        self.save_hi()
        self.sfx('level')
        self.music_vol(0.5)
        self.win_t0 = self.time
        self.over_t = self.time + 1.2             # ignore taps for about 2 seconds
        self.haz = []
        self.threat = self.cam - 300
        self.vx = self.vy = 0
        self.burst(self.x, self.y + 20, (1, 0.9, 0.3), 30)
        self.over_lbl.text = ('YOU WIN!\nScore %d\nBest %d\nTap to play again'
                              % (self.total(), self.hi))
        
    # ------ touch ---------
    def on_touch_down(self, t):
        if self.state in ('over', 'win'):
            if self.time - self.over_t > 0.8:
                self.reset()
            return True
        d = -1 if t.x < Window.width / 2 else 1
        self.face = d
        if self.stand:
            self.vy = LV[self.lvl]['jump'] * (1.55 if self.spring else 1)
            self.spring = False
            self.vx = d * HSP
            self.stand = None
            self.sfx('jump')
        else:
            self.vx = d * HSP          # steer while in the air
        return True
        
    # ------ update -----
    def update(self, dt):
        dt = min(dt, 0.05)
        self.time += dt
        self.flash = max(0, self.flash - 1.5 * dt)
        W, H = Window.size 
        self.S = W / 480
        self.HU = H / self.S
        if self.state == 'play':
            self.step(dt)
        elif self.state == 'win':
            self.cam += (self.y - self.HU * 0.38 - self.cam) * min(1, 4 * dt)
            if random.random() < 0.6:                 # confetti falls from the top
                self.parts.append([random.random() * 480, self.cam + self.HU + 10,
                                   random.uniform(-40, 40), random.uniform(-220, -80), 1.8,
                                   random.choice(((1, 0.3, 0.3), (1, 0.9, 0.3), (0.4, 0.9, 1),
                                                  (0.6, 1, 0.5), (1, 0.5, 1)))])
        for p in self.parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] -= 500 * dt
            p[4] -= dt
        self.parts = [p for p in self.parts if p[4] > 0]
        for s in self.stars:                      # stars drift
            s[1] -= (6 + s[2] * 6) * self.S * dt
            if s[1] < 0:
                s[0], s[1] = random.random() * W, H
        self.draw(W, H, self.S)
        
    def step(self, dt):
        P = LV[self.lvl]
        self.inv = max(0, self.inv - dt)
        self.banner_t = max(0, self.banner_t - dt)
        
        # moving / crumbling branches
        for p in self.plats:
            if p['vx']:
                p['x'] += p['vx'] * dt
                if p['x'] < p['w'] / 2 + 5 or p['x'] > 475 - p['w'] / 2:
                    p['vx'] = -p['vx']
            if p['t'] is not None:
                p['t'] -= dt
                if p['t'] <= 0:
                    p['dead'] = True
            if p['dead']:
                p['y'] -= 500 * dt
                
        # wind (sky only)
        self.wind_t -= dt
        if self.wind_t <= 0:
            self.wind = random.choice((-90, 0, 90))
            self.wind_t = random.uniform(2.5, 4.5)
            
        # hero physics
        if self.stand:
            self.x += self.stand['vx'] * dt
            if self.stand['dead']:
                self.stand = None
        if not self.stand:
            prev = self.y
            self.vy -= P['g'] * dt
            self.y += self.vy * dt
            if self.lvl == 1:
                self.vx = max(-HSP * 1.3, min(HSP * 1.3, self.vx + self.wind * dt))
            self.x += self.vx * dt
            if self.vy < 0:
                for p in self.plats:
                    if (not p['dead'] and prev >= p['y'] - 1 and self.y <= p['y']
                            and abs(self.x - p['x']) <= p['w'] / 2 + 8):
                        self.y, self.vy, self.vx = p['y'], 0, 0
                        self.stand = p
                        self.sfx('land')
                        if p['crumble'] and p['t'] is None:
                            p['t'] = 0.7
                        break 
        if self.x < 0:
            self.x += 480
        elif self.x > 480:
            self.x -= 480
        self.best_h = max(self.best_h, int(self.y / 10))
        if self.stand and self.stand.get('kind') == 'goal':
            self.win()
            return
        
        # camera, world generation, rising danger
        target = self.y - self.HU * 0.38
        if target > self.cam:
            self.cam += (target - self.cam) * min(1, 8 * dt)
        self.gen()
        self.threat = max(self.threat + P['flood'] * dt, self.cam - 250)
        
        # level change
        lv = level_at(self.y)
        if lv > self.lvl:
            self.lvl = lv
            self.banner('LEVEL %d: %s\n%s' % (lv + 1, LV[lv]['name'], LV[lv]['tip']), 3.5)
            self.burst(self.x, self.y + 18, (1, 1, 0.6), 24)
            self.sfx('level')
            self.flash = 0.8                          # white flash on every level change
            self.set_music(lv)
            
        # spawn hazards
        for k in self.timers:
            self.timers[k] -= dt
        c, HU = self.cam, self.HU
        if self.lvl == 0 and self.timers['coco'] <= 0:
            self.timers['coco'] = random.uniform(2.2, 3.6)
            self.haz.append(dict(k='coco', x=random.uniform(30, 450), y=c + HU + 30,
                                 vx=0, vy=-random.uniform(220, 300), r=11))
        if self.lvl == 1 and self.timers['bird'] <= 0:
            self.timers['bird'] = random.uniform(2.2, 3.6)
            d = random.choice((-1, 1))
            self.haz.append(dict(k='bird', x=-30 if d > 0 else 510, y=c + random.uniform(0.3, 0.95) * HU,
                                 vx=d * random.uniform(120, 180), vy=0, r=15, ph=random.random() * 6))
        if self.lvl == 2:
            if self.timers['met'] <= 0:
                self.timers['met'] = random.uniform(1.0, 1.8)
                self.haz.append(dict(k='met', x=random.uniform(30, 450), y=c + HU + 30,
                                     vx=random.uniform(-120, 120), vy=-random.uniform(300, 420),
                                     r=random.uniform(13, 20)))
            if self.timers['ufo'] <= 0:
                self.timers['ufo'] = random.uniform(3, 5)
                d = random.choice((-1, 1))
                self.haz.append(dict(k='ufo', x=-30 if d > 0 else 510, y=c + random.uniform(0.3, 0.95) * HU,
                                     vx=d * random.uniform(160, 230), vy=0, r=20, ph=random.random() * 6))
                                     
        # move hazards
        for h in self.haz:
            if h['k'] == 'snake':
                p = h['plat']
                h['off'] += h['d'] * 40 * dt
                if abs(h['off']) > p['w'] / 2 - 16:
                    h['d'] = -h['d']
                h['x'], h['y'] = p['x'] + h['off'], p['y'] + 9
            else:
                h['x'] += h['vx'] * dt
                h['y'] += h['vy'] * dt
                if h['k'] in ('bird', 'ufo'):
                    h['y'] += math.sin(self.time * 4 + h['ph']) * 30 * dt
                    
        # clean up
        cam = self.cam
        self.plats = [p for p in self.plats if p['y'] > cam - 120]
        self.haz = [h for h in self.haz if h['y'] > cam - 80 and -80 < h['x'] < 560]
        self.items = [i for i in self.items if i['y'] > cam - 60]
        
        # collisions
        cx, cy = self.x, self.y + 16
        for h in self.haz[:]:
            if self.inv <= 0 and math.hypot(cx - h['x'], cy - h['y']) < h['r'] + 12:
                if h['k'] != 'snake':
                    self.haz.remove(h)
                self.damage()
                break 
        if self.state != 'play':
            return 
        for it in self.items[:]:
            if math.hypot(cx - it['x'], cy - it['y']) < 26:
                self.items.remove(it)
                if it['k'] == 'ban':
                    self.bananas += 1
                    self.sfx('banana')
                else:
                    if it['k'] == 'spring':
                        self.spring = True
                    else:
                        self.shield = True
                    self.sfx('power')
                self.burst(it['x'], it['y'], (1, 0.9, 0.3), 6)
        if self.y < self.cam - 30 or self.y + 10 < self.threat:
            self.fall()
            
    # ---------------- DRAWING ---------------------
    def draw(self, W, H, S):
        self.score_lbl.font_size = 26 * S
        self.score_lbl.size = (330 * S, 140 * S)
        self.score_lbl.text_size = self.score_lbl.size 
        self.score_lbl.pos = (15 * S, H - 150 * S)
        extra = ('  SHIELD' if self.shield else '') + ('  SPRING' if self.spring else '')
        marks = (L2, L3, GOAL)
        nxt = next((m for m in marks if m > self.y), None)
        goal_txt = ''
        if nxt:
            goal_txt = '\n%s in %d m' % (('Sky gate', 'Space gate', 'SUMMIT')[marks.index(nxt)],
                                        (nxt - self.y) // 10)
        self.score_lbl.text = 'Score %d\n%s  %d m%s%s' % (
            self.total(), LV[self.lvl]['name'].title(), self.best_h, extra, goal_txt)
        self.banner_lbl.font_size = 34 * S
        self.banner_lbl.size = (W, 160 * S)
        self.banner_lbl.text_size = self.banner_lbl.size 
        self.banner_lbl.pos = (0, H * 0.66)
        self.banner_lbl.text = self.banner_txt if (self.banner_t > 0 and self.state == 'play') else ''
        self.over_lbl.font_size = 36 * S
        self.over_lbl.size = (W, 360 * S)
        self.over_lbl.text_size = self.over_lbl.size 
        self.over_lbl.pos = (0, H * 0.55 if self.state == 'win' else H / 2 - 180 * S)
        
        cam, HU, t = self.cam, self.HU, self.time 
        c = self.canvas.before 
        c.clear()
        with c:
            Color(*bg(cam + HU / 2), 1)
            Rectangle(pos=(0, 0), size=(W, H))
            a = min(1, max(0, (cam - (L3 - 1200)) / 1500))
            if a > 0:                                        # stars
                Color(1, 1, 1, 0.9 * a)
                for s in self.stars:
                    Ellipse(pos=(s[0], s[1]), size=(s[2] * 2, s[2] * 2))
                pw = min(1, max(0, (cam - (L3 - 200)) / 800))      # planet
                Color(0.5, 0.25, 0.7, pw)
                Ellipse(pos=(W * 0.62, H * 0.72 - (cam - (L3 - 200)) * 0.08 * S), size=(150 * S, 150 * S))
                Color(0.9, 0.7, 1, 0.7 * pw)
                Line(ellipse=(W * 0.62 - 25 * S, H * 0.72 + 55 * S - (cam - (L3 - 200)) * 0.08 * S,
                              200 * S, 40 * S), width=2 * S)
            
            PushMatrix()
            Translate(0, -cam * S, 0)
            Scale(S, S, 1)
            
            jw = min(1, max(0, 1 - (cam - (L2 - 600)) / 900))
            if jw > 0:                                       # jungle trunks
                Color(0.03, 0.13, 0.05, 0.6 * jw)
                for i in range(5):
                    Rectangle(pos=(30 + i * 100, cam), size=(30, HU))
            sw = min(1, max(0, (cam - (L2 - 200)) / 800)) * min(1, max(0, 1 - (cam - (L3 - 800)) / 1200))
            if sw > 0:                                       # drifting clouds
                Color(1, 1, 1, 0.5 * sw)
                for d in self.decor:
                    yy = cam - 80 + (d[1] - cam * 0.5) % (HU + 160)
                    Ellipse(pos=(d[0], yy), size=(90, 28))
                    Ellipse(pos=(d[0] + 20, yy + 10), size=(50, 26))
            if self.lvl == 1 and self.wind:                  # wind streaks
                Color(1, 1, 1, 0.35)
                for i in range(7):
                    Rectangle(pos=((i * 83 + t * self.wind * 2.5) % 520 - 20,
                                    cam + (i * 157) % int(HU)), size=(34, 2))
                                    
            for p in self.plats:
                self.plat(p)
            for it in self.items:
                self.item(it, t)
            for h in self.haz:
                self.hazard(h, t)
            if self.state == 'win':
                self.hero_dance()
            elif self.state == 'play' and not (self.inv > 0 and int(self.inv * 10) % 2):
                self.hero()
            for p in self.parts:
                Color(p[5][0], p[5][1], p[5][2], min(1, p[4] * 2))
                r = 2 + 4 * p[4]
                Ellipse(pos=(p[0] - r, p[1] - r), size=(2 * r, 2 * r))
                
            top = self.threat                               # rising danger
            if top > cam:
                fc = [((0.1, 0.45, 0.75, 0.7), (0.6, 0.85, 1, 0.9)),
                      ((0.25, 0.27, 0.35, 0.85), (0.8, 0.8, 0.95, 0.8)),
                      ((0.18, 0, 0.3, 0.88), (0.8, 0.3, 1, 0.9))][self.lvl]
                Color(*fc[0])
                Rectangle(pos=(0, cam - 10), size=(480, top - cam + 10))
                Color(*fc[1])
                for i in range(8):
                    Ellipse(pos=(i * 64 - 10 + math.sin(t * 2 + i) * 8, top - 10), size=(70, 20))
            PopMatrix()
            
            if self.flash > 0:                              # level-change flash
                Color(1, 1, 1, min(1, self.flash))
                Rectangle(pos=(0, 0), size=(W, H))
            
            Color(1, 0.25, 0.3, 1)                          # hearts
            for i in range(self.lives):
                hx, hy = W - (30 + i * 34) * S, H - 40 * S
                Ellipse(pos=(hx - 11 * S, hy - 1 * S), size=(12 * S, 12 * S))
                Ellipse(pos=(hx - 1 * S, hy - 1 * S), size=(12 * S, 12 * S))
                Triangle(points=[hx - 11 * S, hy + 3 * S, hx + 11 * S, hy + 3 * S, hx, hy - 12 * S])
                
    def plat(self, p):
        x, y, w =p['x'], p['y'], p['w']
        if p.get('kind'):
            self.portal(p)
        a = 0.3 if p['dead'] else (1 if p['t'] is None else max(0.25, p['t'] / 0.7))
        if p['lvl'] == 0:                                   # tree branch
            Color(0.4, 0.25, 0.12, a)
            Rectangle(pos=(x - w / 2, y - 12), size=(w, 12))
            Ellipse(pos=(x - w / 2 - 6, y - 12), size=(12, 12))
            Ellipse(pos=(x + w / 2 - 6, y - 12), size=(12, 12))
            Color(0.55, 0.36, 0.18, a)
            Rectangle(pos=(x - w / 2, y - 4), size=(w, 4))
            Color(0.2, 0.62, 0.25, a)
            Ellipse(pos=(x - w / 3, y - 12), size=(30, 14))
            Ellipse(pos=(x + w / 6, y - 12), size=(26, 12))
        elif p['lvl'] == 1:                                 # cloud
            if p['vx']:
                Color(0.85, 0.93, 1, a)
            else:
                Color(1, 1, 1, a)
            Ellipse(pos=(x - w / 2, y - 18), size=(w, 20))
            Ellipse(pos=(x - w / 4 - 15, y - 12), size=(32, 14))
            Ellipse(pos=(x + w  / 6 - 18, y - 10), size=(36, 12))
        else:                                              # space rock / metal
            Color(0.42, 0.47, 0.6, a)
            Rectangle(pos=(x - w / 2, y  - 10), size=(w, 10))
            Ellipse(pos=(x - w / 2 - 5, y - 10), size=(10, 10))
            Ellipse(pos=(x + w / 2 - 5, y - 10), size=(10, 10))
            if p['vx']:
                Color(1, 0.6, 0.2, 0.8 * a)
            else:
                Color(0.3, 1, 0.9, 0.8 * a)
            Rectangle(pos=(x - w / 2 + 4, y - 12), size=(w - 8, 2.5))
            
    def portal(self, p):
        x, y, w = p['x'], p['y'], p['w']
        pulse = 0.5 + 0.5 * math.sin(self.time * 4)
        if p['kind'] == 'gate':
            r, g, b = (0.55, 0.85, 1) if p['lvl'] == 1 else (0.85, 0.5, 1)
            Color(r, g, b, 0.28 + 0.2 * pulse)                         # glowing doorway
            Rectangle(pos=(x - w / 2 + 12, y), size=(w - 24, 120))
            Color(r, g, b, 1)
            Rectangle(pos=(x - w / 2 + 4, y), size=(12, 126))          # pillars
            Rectangle(pos=(x + w / 2 - 16, y), size=(12, 126))
            Rectangle(pos=(x - w / 2 + 4, y + 114), size=(w - 8, 12))  # top bar
            for i in range(3):                                         # arrows pointing up
                ax, ay = x - 70 + i * 70, y + 30 + (self.time * 40 + i * 25) % 60
                Triangle(points=[ax - 12, ay, ax + 12, ay, ax, ay + 20])
        else:
            Color(1, 0.85, 0.2, 0.12 + 0.12 * pulse)                   # golden glow
            Ellipse(pos=(x - 90, y), size=(180, 150))
            Color(0.85, 0.85, 0.9, 1)                                  # flag pole
            Rectangle(pos=(x - 2, y), size=(4, 110))
            Color(1, 0.25, 0.3, 1)                                     # flag
            Triangle(points=[x + 2, y + 110, x + 2, y + 80, x + 44, y + 95])
            Color(1, 0.85, 0.2, 1)                                     # star on top
            Ellipse(pos=(x - 8, y + 108), size=(16, 16))
            
    def hero_dance(self):
        t = self.time - self.win_t0
        beat = abs(math.sin(t * 7))                    # hop on every beat
        f = 1 if int(t * 3.5) % 2 == 0 else -1         # turn left and right
        x = self.x + math.sin(t * 3.5) * 14            # sway side to side
        y = self.y + beat * 20
        PushMatrix()
        Rotate(angle=math.sin(t * 7) * 14, origin=(x, y))
        self.spaceman(x, y, 4 + 10 * beat, f, False)   # arms pump up and down
        PopMatrix()
        
    def item(self, it, t):
        x, y = it['x'], it['y'] + math.sin(t * 4 + it['x']) * 3
        if it['k'] == 'ban':
            PushMatrix()
            Rotate(angle=35, origin=(x, y))
            Color(1, 0.9, 0.2, 1)
            Ellipse(pos=(x - 4, y - 10), size=(8, 20))
            Color(0.5, 0.35, 0.1, 1)
            Rectangle(pos=(x - 1.5, y + 9), size=(3, 4))
            PopMatrix()
        elif it['k'] == 'spring':
            Color(0.3, 0.9, 0.3, 1)
            for k in (-8, -1, 6):
                Rectangle(pos=(x - 9, y + k), size=(18, 4))
            Triangle(points=[x - 7, y + 12, x + 7, y + 12, x, y + 22])
        else:
            Color(0.3, 0.7, 1, 1)
            Ellipse(pos=(x - 11, y - 11), size=(22, 22))
            Color(1, 1, 1, 0.8)
            Ellipse(pos=(x - 6, y - 6), size=(12, 12))
            
    def hazard(self, h, t):
        x, y, k = h['x'], h['y'], h['k']
        if k == 'snake':
            Color(0.2, 0.75, 0.25, 1)
            for i in range(5):
                Ellipse(pos=(x - 12 + i * 5, y - 4 + math.sin(t * 8 + i) * 3), size=(8, 8))
            Color(0.15, 0.55, 0.2, 1)
            Ellipse(pos=(x + h['d'] * 13 - 6, y - 5), size=(12, 11))
            Color(1, 0.2, 0.2, 1)
            Rectangle(pos=(x + h['d'] * 19 - 2, y), size=(4, 1.5))
        elif k == 'coco':
            Color(1, 0.85, 0.3, 0.35)                              # warning glow
            Ellipse(pos=(x - 17, y - 17), size=(34, 34))
            Color(0.62, 0.38, 0.16, 1)                             # coconut
            Ellipse(pos=(x - 11, y - 11), size=(22, 22))
            Color(0.85, 0.62, 0.35, 1)                             # highlight
            Ellipse(pos=(x - 7, y + 1), size=(7, 7))
            Color(0.2, 0.1, 0.05, 1)                               # eyes
            Ellipse(pos=(x - 6, y - 4), size=(4, 4))
            Ellipse(pos=(x + 2, y - 4), size=(4, 4))
        elif k == 'bird':
            d = 1 if h['vx'] > 0 else -1
            f = math.sin(t * 14 + h['ph'])
            Color(0.15, 0.15, 0.22, 1)
            Ellipse(pos=(x - 12, y - 6), size=(24, 12))
            Ellipse(pos=(x + d * 9 - 5, y - 2), size=(10, 10))
            Triangle(points=[x - 6, y, x + 6, y, x, y + 14 + 9 * f])
            Color(1, 0.65, 0.1, 1)
            Triangle(points=[x + d * 14, y + 1, x + d * 14, y + 5, x + d * 21, y + 3])
        elif k == 'ufo':
            Color(0.7, 0.75, 0.85, 1)
            Ellipse(pos=(x - 10, y - 1), size=(44, 14))
            Color(0.5, 1, 0.9, 0.9)
            Ellipse(pos=(x - 10, y - 1), size=(20, 16))
            Color(1, 1, 0.3, 1)
            for dx in (-14, -2, 10):
                Ellipse(pos=(x + dx - 2, y - 6), size=(4, 4))
        else:                                                 # meteor
            r = h['r']
            Color(1, 0.5, 0.1, 0.6)
            Triangle(points=[x - r * 0.7, y, x + r * 0.7, y, x - h['vx'] * 0.12, y - h['vy'] * 0.12])
            Color(0.45, 0.4, 0.38, 1)
            Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
            Color(0.3, 0.27, 0.25, 1)
            Ellipse(pos=(x - r * 0.4, y - r * 0.1), size=(r * 0.5, r * 0.5))
            
    def hero(self):
        x, y = self.x, self.y
        if self.shield:
            Color(0.4, 0.8, 1, 0.35)
            Ellipse(pos=(x - 26, y - 4), size=(52, 52))
        if self.spring:
            Color(0.4, 1, 0.4, 1)
            Rectangle(pos=(x - 8, y - 5), size=(16, 4))
        air = self.stand is None
        lift = 6 if air else 0
        if self.lvl == 0:
            self.caveman(x, y, lift, self.face)
        elif self.lvl == 1:
            self.aviator(x, y, lift, self.face, air)
        else:
            self.spaceman(x, y, lift, self.face, air)
            
    def caveman(self, x, y, lift, f):
        skin, dark = (0.86, 0.62, 0.42, 1), (0.14, 0.08, 0.04, 1)
        Color(*skin)                                            # legs and arms
        Ellipse(pos=(x - 8, y), size=(7, 13))
        Ellipse(pos=(x + 1, y), size=(7, 13))
        Ellipse(pos=(x - 17, y + 10 + lift), size=(7, 15))
        Ellipse(pos=(x + 10, y + 10 + lift), size=(7, 15))
        Ellipse(pos=(x - 10, y + 9), size=(20, 17))             # bare chest
        Color(0.92, 0.6, 0.2, 1)                                # leopard loincloth
        Triangle(points=[x - 11, y + 14, x + 11, y + 14, x, y + 3])
        Color(0.25, 0.12, 0.05, 1)
        Ellipse(pos=(x - 5, y + 8), size=(3, 3))
        Ellipse(pos=(x + 2, y + 6), size=(3, 3))
        Ellipse(pos=(x - 1, y + 10.5), size=(2.5, 2.5))
        Color(0.4, 0.25, 0.12, 1)                                # belt
        Rectangle(pos=(x - 11, y + 13), size=(22, 3))
        Color(*dark)                                             # long hair
        Rectangle(pos=(x - 10, y + 16), size=(4, 15))
        Rectangle(pos=(x + 6, y + 16), size=(4, 15))
        Color(*skin)
        Ellipse(pos=(x - 8.5, y + 22), size=(17, 16))             # head
        Color(*dark)
        Ellipse(pos=(x - 10, y + 30), size=(20, 9))               # hair on top
        Color(0.05, 0.05, 0.05, 1)
        Ellipse(pos=(x - 4.5 + f * 1.5, y + 26.5), size=(3, 3))
        Ellipse(pos=(x + 1.5 + f * 1.5, y + 26.5), size=(3, 3))
        Color(0.6, 0.35, 0.3, 1)
        Ellipse(pos=(x - 2.5 + f, y + 24), size=(5, 2))
        PushMatrix()                                              # wooden club
        Rotate(angle=-35 * f, origin=(x + f * 14, y + 18 + lift))
        Color(0.45, 0.28, 0.12, 1)
        Rectangle(pos=(x + f * 14 - 2.5, y + 16 + lift), size=(5, 17))
        Ellipse(pos=(x + f * 14 - 5.5, y + 29 + lift), size=(11, 11))
        PopMatrix()
        
    def aviator(self, x, y, lift, f, air):
        w = math.sin(self.time * 14) if air else 0.2
        for s in (-1, 1):                                         # feathered wings
            Color(0.55, 0.7, 0.95, 1)
            Triangle(points=[x + s * 6, y + 25, x + s * 33, y + 27 + 11 * w, x + s * 6, y + 12])
            Color(1, 1, 1, 1)
            Triangle(points=[x + s * 6, y + 23, x + s * 29, y + 26 + 10 * w, x + s * 6, y + 14])
        Color(0.45, 0.28, 0.12, 1)                                 # boots
        Ellipse(pos=(x - 9, y), size=(8, 6))
        Ellipse(pos=(x + 1, y), size=(8, 6))                     
        Color(0.3, 0.3, 0.5, 1)                                    # trousers
        Ellipse(pos=(x - 8, y + 3), size=(7, 11))
        Ellipse(pos=(x + 1, y + 3), size=(7, 11))
        Color(0.6, 0.36, 0.16, 1)                                  # leather jacket
        Ellipse(pos=(x - 17, y + 10 + lift), size=(7, 15))
        Ellipse(pos=(x + 10, y + 10 + lift), size=(7, 15))
        Ellipse(pos=(x - 10, y + 9), size=(20, 17))
        Color(0.9, 0.2, 0.2, 1)                                    # red scarf
        Rectangle(pos=(x - 8, y + 22), size=(16, 4))
        Triangle(points=[x - f * 8, y + 25, x - f * 8, y + 21,
                         x - f * (22 + 4 * math.sin(self.time * 10)),
                         y + 23 + 3 * math.sin(self.time * 12)])
        Color(0.95, 0.75, 0.55, 1)                                 # head
        Ellipse(pos=(x - 8.5, y + 22), size=(17, 16))
        Color(0.45, 0.28, 0.12, 1)                                 # leather cap
        Ellipse(pos=(x - 9.5, y + 30), size=(19, 9))
        Color(0.2, 0.15, 0.1, 1)                                   # goggles
        Ellipse(pos=(x - 8 + f, y + 26), size=(7, 7))
        Ellipse(pos=(x + 1 + f, y + 26), size=(7, 7))
        Color(0.2, 0.15, 0.1, 1)
        Ellipse(pos=(x - 6.5 + f, y + 27.5), size=(4, 4))
        Ellipse(pos=(x + 2.5 + f, y + 27.5), size=(4, 4))
        
    def spaceman(self, x, y, lift, f, air):
        Color(0.55, 0.55, 0.62, 1)                                # jetpack
        Rectangle(pos=(x - 13, y + 10), size=(26, 16))
        if air:
            fl = 7 + 4 * math.sin(self.time * 30)
            Color(1, 0.6, 0.15, 0.9)
            Triangle(points=[x - 11, y + 10, x - 5, y + 10, x - 8, y + 10 - fl])
            Triangle(points=[x + 5, y + 10, x + 11, y + 10, x + 8, y + 10 - fl])
        Color(0.95, 0.5, 0.15, 1)                                 # boots
        Ellipse(pos=(x - 9, y), size=(8, 6))
        Ellipse(pos=(x + 1, y), size=(8, 6))
        Color(0.93, 0.93, 0.97, 1)                                # white suit
        Ellipse(pos=(x - 8, y + 3), size=(7, 11))
        Ellipse(pos=(x + 1, y + 3), size=(7, 11))
        Ellipse(pos=(x - 17, y + 10 + lift), size=(7, 15))
        Ellipse(pos=(x + 10, y + 10 + lift), size=(7, 15))
        Ellipse(pos=(x - 10, y + 9), size=(20, 17))
        Color(0.55, 0.55, 0.62, 1)                                # gloves
        Ellipse(pos=(x - 17, y + 10 + lift), size=(7, 5))
        Ellipse(pos=(x + 10, y + 10 + lift), size=(7, 5))
        Color(0.2, 0.2, 0.25, 1)                                  # chest panel
        Rectangle(pos=(x - 5, y + 14), size=(10, 6))
        Color(1, 0.2, 0.2, 1)
        Ellipse(pos=(x - 5, y + 14), size=(10, 6))
        Color(1, 0.2, 0.2, 1)
        Ellipse(pos=(x - 4, y + 16), size=(2.5, 2.5))
        Color(0.88, 0.88, 0.93, 1)                                # helmet
        Ellipse(pos=(x - 12, y + 20), size=(24, 20))
        Color(0.1, 0.18, 0.42, 1)                                 # visor
        Ellipse(pos=(x - 9, y + 22), size=(18, 15))
        Color(0.55, 0.8, 1, 0.8)
        Ellipse(pos=(x - 6, y + 30), size=(6, 4))
        Color(0.9, 0.95, 1, 1)                                    # eyes
        Ellipse(pos=(x - 4.5 + f * 1.5, y + 26), size=(3, 3))
        Ellipse(pos=(x + 1.5 + f * 1.5, y + 26), size=(3, 3))
        Color(0.7, 0.7, 0.75, 1)                                 # antenna
        Rectangle(pos=(x + 7, y + 38), size=(1.5, 6))
        Color(1, 0.2, 0.2, 1)
        Ellipse(pos=(x + 5.9, y + 43), size=(4, 4))
        
class ClimbQuest(App):
    def build(self):
        folder = self.user_data_dir
        os.makedirs(folder, exist_ok=True)
        make_sounds(folder)
        self.game = Game(folder)
        return self.game 
        
    def on_pause(self):
        self.game.pause_music()
        return True
    
    def on_resume(self):
        self.game.resume_music()
        
ClimbQuest().run()

        
            
            
            
