"""ShopImpact - Shop smarter. Live greener.

Single-file Streamlit app. The interface is the ShopImpact web demo, rendered full-screen,
so it looks the same on phone, laptop, desktop and TV.
Python in this file owns: the category multiplier dictionary (CO2 methodology), the demo
purchases, the tips, and the Turtle graphics images (drawn with the Turtle code below).

Run:  pip install -r requirements.txt   then   streamlit run app.py
"""
import base64
import datetime as dt
import io
import json
import math
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw

# ======================================================================
# CALCULATIONS (CO2 methodology)
# ======================================================================
MULTIPLIERS = {                       # kg CO2e per Rs 1
    "Clothing and Fashion": 0.006,
    "Footwear": 0.007,
    "Electronics": 0.004,
    "Groceries": 0.0025,
    "Beauty and Personal Care": 0.003,
    "Home and Furniture": 0.005,
    "Accessories": 0.0045,
    "Other": 0.003,
}
CATEGORIES = list(MULTIPLIERS)
PREOWNED_FACTOR = 0.4                 # second-hand / refurbished / repaired items
LOW_LIMIT, MEDIUM_LIMIT = 5, 25       # kg CO2e thresholds for impact level
CURRENCIES = {"INR": ("₹", 1.0), "USD": ("$", 0.012), "EUR": ("€", 0.011), "GBP": ("£", 0.0095)}  # approx., fixed


def multiplier_for(category, preowned=False):
    m = MULTIPLIERS.get(category, MULTIPLIERS["Other"])
    return m * PREOWNED_FACTOR if preowned else m


def estimate_co2(price_inr, category, preowned=False):
    return round(price_inr * multiplier_for(category, preowned), 2)


def impact_level(co2):
    return "Low" if co2 < LOW_LIMIT else "Medium" if co2 < MEDIUM_LIMIT else "High"

# ======================================================================
# PURCHASE RECORDS (validation, CSV, demo data)
# ======================================================================
FIELDS = ["id", "name", "category", "brand", "price_inr", "date", "status", "preowned", "demo", "co2"]


def validate(name, price, category, status=None):
    errors = []
    if not str(name or "").strip():
        errors.append("Product name cannot be empty.")
    if price is None:
        errors.append("Please enter a price.")
    elif price <= 0:
        errors.append("Price must be greater than zero.")
    if category not in CATEGORIES:
        errors.append("Please choose a valid category.")
    if status is not None and status not in ("Planned", "Purchased"):
        errors.append("Status must be Planned or Purchased.")
    return errors


def make_record(name, category, brand, price_inr, date, status, preowned=False, demo=False, rid=None):
    return {"id": rid or uuid.uuid4().hex[:8], "name": name.strip(), "category": category,
            "brand": (brand or "").strip() or "Unbranded", "price_inr": float(price_inr),
            "date": pd.to_datetime(date).date().isoformat(), "status": status,
            "preowned": bool(preowned), "demo": bool(demo),
            "co2": estimate_co2(float(price_inr), category, preowned)}


def demo_records(today=None):
    today = today or dt.date.today()
    rows = [  # (name, category, brand, price, days ago, status, preowned)
        ("Cotton T-shirt", "Clothing and Fashion", "Demo Brand", 799, 2, "Purchased", False),
        ("Second-hand denim jacket", "Clothing and Fashion", "Thrift Store", 1200, 5, "Purchased", True),
        ("Running shoes", "Footwear", "Demo Brand", 3499, 9, "Purchased", False),
        ("Refurbished laptop", "Electronics", "Demo Refurb", 28000, 14, "Purchased", True),
        ("Wireless earbuds", "Electronics", "Demo Audio", 2999, 20, "Purchased", False),
        ("Weekly vegetables", "Groceries", "Local Market", 650, 1, "Purchased", False),
        ("Rice and lentils", "Groceries", "Local Market", 900, 7, "Purchased", False),
        ("Shampoo bar", "Beauty and Personal Care", "Demo Care", 350, 11, "Purchased", False),
        ("Study desk", "Home and Furniture", "Demo Home", 6500, 24, "Purchased", False),
        ("Reusable steel bottle", "Home and Furniture", "Demo Home", 499, 3, "Purchased", False),
        ("Canvas tote bag", "Accessories", "Demo Brand", 450, 16, "Purchased", False),
        ("Smartwatch", "Electronics", "Demo Tech", 8999, 35, "Purchased", False),
        ("Winter jacket", "Clothing and Fashion", "Demo Brand", 4200, 40, "Purchased", False),
        ("Sandals", "Footwear", "Demo Brand", 1100, 45, "Purchased", False),
        ("Desk lamp", "Home and Furniture", "Demo Home", 1800, 0, "Planned", False),
    ]
    return [make_record(n, c, b, p, today - dt.timedelta(days=d), s, pre, demo=True)
            for n, c, b, p, d, s, pre in rows]


def to_df(records):
    df = pd.DataFrame(records, columns=FIELDS)
    if df.empty:
        return df.assign(month=pd.Series(dtype=str), level=pd.Series(dtype=str), eco=pd.Series(dtype=bool))
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.strftime("%Y-%m")
    df["level"] = df["co2"].map(impact_level)
    df["eco"] = (df["level"] == "Low") | df["preowned"]
    return df.sort_values("date", ascending=False).reset_index(drop=True)


def export_csv(records):
    return pd.DataFrame(records, columns=FIELDS).drop(columns=["demo"]).to_csv(index=False).encode("utf-8")


def import_csv(file):
    """Return (records, skipped_count). CO2 is always recalculated, never trusted."""
    df = pd.read_csv(file)
    need = {"name", "category", "price_inr", "date", "status"}
    if not need.issubset(df.columns):
        raise ValueError("CSV must contain columns: " + ", ".join(sorted(need)))
    out, skipped = [], 0
    for r in df.to_dict("records"):
        try:
            price = float(r["price_inr"])
            if validate(r["name"], price, r["category"], r["status"]):
                skipped += 1
                continue
            out.append(make_record(r["name"], r["category"], str(r.get("brand", "")) if pd.notna(r.get("brand")) else "",
                                   price, r["date"], r["status"], str(r.get("preowned", False)).lower() == "true"))
        except Exception:
            skipped += 1
    return out, skipped

# ======================================================================
# TURTLE GRAPHICS (headless, saves PNG images)
# ======================================================================
FOREST, SAGE, CREAM, MINT = (79, 70, 229), (255, 107, 107), (255, 255, 255), (199, 210, 254)


class Turtle:
    def __init__(self, size=400):
        self.size, self.c = size, size // 2
        self.img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.x = self.y = 0.0
        self.h = 0.0                      # heading in degrees
        self.pen, self.col, self.w, self.poly = True, FOREST, 4, None

    def _p(self, x, y):                   # turtle coords -> pixel coords
        return (self.c + x, self.c - y)

    def color(self, c): self.col = c
    def pensize(self, w): self.w = w
    def penup(self): self.pen = False
    def pendown(self): self.pen = True
    def setheading(self, a): self.h = a
    def left(self, a): self.h += a
    def right(self, a): self.h -= a
    def begin_fill(self): self.poly = [(self.x, self.y)]

    def end_fill(self):
        if self.poly and len(self.poly) > 2:
            self.d.polygon([self._p(*p) for p in self.poly], fill=self.col)
        self.poly = None

    def goto(self, x, y):
        if self.pen and self.poly is None:
            self.d.line([self._p(self.x, self.y), self._p(x, y)], fill=self.col, width=self.w)
        if self.poly is not None:
            self.poly.append((x, y))
        self.x, self.y = x, y

    def forward(self, dist):
        r = math.radians(self.h)
        self.goto(self.x + dist * math.cos(r), self.y + dist * math.sin(r))

    def circle(self, radius, extent=360, steps=72):
        """Arc like turtle.circle: positive radius curves left."""
        n = max(2, int(steps * extent / 360))
        ang = extent / n
        side = 2 * abs(radius) * math.sin(math.radians(ang / 2))
        sign = 1 if radius >= 0 else -1
        self.h += sign * ang / 2
        for _ in range(n):
            self.forward(side)
            self.h += sign * ang
        self.h -= sign * ang / 2

    def save(self, path):
        self.img.save(path)


def _ellipse(t, cx, cy, rx, ry):
    t.penup()
    t.goto(cx + rx, cy)
    t.begin_fill()
    for i in range(61):
        a = 2 * math.pi * i / 60
        t.goto(cx + rx * math.cos(a), cy + ry * math.sin(a))
    t.end_fill()


def draw_leaf(size=400):
    t = Turtle(size)
    t.color(FOREST)
    t.penup(); t.goto(0, -120); t.setheading(45)
    t.begin_fill()
    t.circle(170, 90)          # right edge of the leaf
    t.left(90)
    t.circle(170, 90)          # left edge of the leaf
    t.end_fill()
    t.color(MINT); t.pensize(5); t.pendown()          # central vein
    t.goto(0, -150); t.goto(0, 110)
    for k in range(-60, 61, 40):                      # side veins
        t.penup(); t.goto(0, k); t.pendown(); t.setheading(50); t.forward(48)
        t.penup(); t.goto(0, k); t.pendown(); t.setheading(130); t.forward(48)
    t.color(FOREST); t.pensize(8)
    t.penup(); t.goto(0, -120); t.pendown(); t.goto(0, -165)    # stem
    return t


def draw_footprint(size=400):
    t = Turtle(size)
    t.color(FOREST)
    _ellipse(t, 0, -70, 62, 95)                       # sole
    _ellipse(t, 0, 60, 52, 62)                        # ball of foot
    for cx, cy, r in [(-62, 135, 20), (-28, 160, 18), (8, 165, 17), (42, 155, 16), (70, 135, 14)]:
        _ellipse(t, cx, cy, r, r)                     # toes
    t.color(SAGE)
    _ellipse(t, 0, -150, 32, 18)                      # heel highlight
    return t


def draw_badge(size=400):
    t = Turtle(size)
    t.color(FOREST); t.penup(); t.goto(0, -170); t.setheading(0)
    t.begin_fill(); t.circle(170); t.end_fill()       # outer disc
    t.color(SAGE); t.goto(0, -150); t.begin_fill(); t.circle(150); t.end_fill()
    t.color(CREAM); t.goto(-60, 32); t.setheading(0)  # five-point star
    t.begin_fill()
    for _ in range(5):
        t.forward(120); t.right(144)
    t.end_fill()
    t.color(FOREST); t.pensize(8)                     # tiny sprout in the star
    t.penup(); t.goto(0, -25); t.pendown(); t.goto(0, 15)
    return t


def generate_all(out_dir):
    out = Path(out_dir)
    (out / "badges").mkdir(parents=True, exist_ok=True)
    for name, fn in [("leaf", draw_leaf), ("footprint", draw_footprint), ("badge", draw_badge)]:
        fn().save(out / f"{name}.png")
    logo = draw_leaf(400).img.resize((128, 128))
    logo.save(out / "logo.png")
    for n in ("leaf", "footprint", "badge"):
        (out / "badges" / f"{n}.png").write_bytes((out / f"{n}.png").read_bytes())




PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>ShopImpact – Shop smarter. Live greener.</title>
<style>
:root{--bg:#fff;--card:#fff;--fg:#1B1F3B;--mut:#6B7280;--g:#5B50E6;--g2:#FF6B6B;--line:#ECEEF6;--tip:#EEF0FF;--ok:#12A594;--bad:#E5484D;--grad:linear-gradient(120deg,#5B50E6,#8B5CF6 55%,#FF6B6B);color-scheme:light}
:root[data-theme="grey"]{--bg:#F3F4FA}
:root[data-theme="dark"]{--bg:#0E1120;--card:#171B33;--fg:#EEF0FF;--mut:#A0A8C8;--line:#272C50;--tip:#1F2450;--g:#8B93FF;color-scheme:dark}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;overflow-x:hidden}
body{background:var(--bg);color:var(--fg);font:15px/1.5 Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.app{display:grid;grid-template-columns:268px minmax(0,1fr);min-height:100vh}
aside{background:linear-gradient(180deg,#4338CA,#6D4AE8 55%,#9B5CF6);color:#fff;padding:22px 14px;position:sticky;top:0;height:100vh;overflow-y:auto;display:flex;flex-direction:column;gap:4px;z-index:20}
.brand{display:flex;gap:10px;align-items:center;margin:0 6px 2px}.brand svg{width:38px;flex:none}.brand b{font-size:1.3rem;letter-spacing:-.02em;color:#fff}
.brand svg path:first-child{fill:#fff}.brand svg path:last-child{stroke:#5B50E6}
.tag{margin:0 6px 18px;font-size:.8rem;opacity:.85;color:#fff}
nav{display:flex;flex-direction:column;gap:4px}
nav button{display:flex;align-items:center;gap:10px;width:100%;text-align:left;border:0;background:transparent;color:rgba(255,255,255,.9);padding:11px 14px;border-radius:14px;font:inherit;font-weight:500;cursor:pointer;white-space:nowrap;transition:background .15s,transform .15s}
nav button:hover{background:rgba(255,255,255,.18);transform:translateX(2px)}
nav button.on{background:#fff;color:#4338CA;font-weight:700;box-shadow:0 6px 16px rgba(0,0,0,.18)}
.ni{font-size:1.1rem;width:1.4rem;text-align:center}
main{min-width:0;width:100%;max-width:1200px;margin:0 auto;padding:30px 36px 70px}
h1{font-size:1.8rem;font-weight:800;letter-spacing:-.02em;line-height:1.2;margin:0 0 6px;color:var(--fg)}
h1:after{content:"";display:block;width:56px;height:5px;border-radius:4px;background:var(--grad);margin-top:8px}
h3{font-size:1.08rem;font-weight:700;margin:30px 0 12px;display:flex;align-items:center;gap:10px;color:var(--fg)}
h3:before{content:"";width:6px;height:20px;border-radius:4px;background:var(--grad);flex:none}
.tip{background:var(--tip);color:var(--g);border-radius:14px;padding:11px 15px;margin:10px 0 18px;font-size:.9rem}
.grid{display:grid;gap:16px}.grid>*{min-width:0}
.g4{grid-template-columns:repeat(4,minmax(0,1fr))}.g3{grid-template-columns:repeat(3,minmax(0,1fr))}.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:18px 20px;box-shadow:0 6px 20px rgba(27,31,59,.06);transition:transform .15s,box-shadow .15s;min-width:0}
.card:hover{transform:translateY(-3px);box-shadow:0 14px 30px rgba(91,80,230,.16)}
.g4>.card:nth-child(1){background:linear-gradient(145deg,#EEF0FF,#fff 75%);border-color:#DADDFB}
.g4>.card:nth-child(2){background:linear-gradient(145deg,#FFECEC,#fff 75%);border-color:#FFD3D3}
.g4>.card:nth-child(3){background:linear-gradient(145deg,#DDF6F2,#fff 75%);border-color:#BFEBE3}
.g4>.card:nth-child(4){background:linear-gradient(145deg,#FFF3D9,#fff 75%);border-color:#FBE1A8}
:root[data-theme="dark"] .g4>.card{background:var(--card);border-color:var(--line)}
.lab{font-size:.72rem;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);font-weight:700}
.val{font-size:1.8rem;font-weight:800;line-height:1.25;overflow-wrap:anywhere;color:var(--fg)}
.g4>.card:nth-child(1) .val{color:#4338CA}.g4>.card:nth-child(2) .val{color:#E5484D}.g4>.card:nth-child(3) .val{color:#0F9D8A}.g4>.card:nth-child(4) .val{color:#C77700}
:root[data-theme="dark"] .g4>.card .val{color:var(--fg)}
.sub{font-size:.8rem;color:var(--mut)}.up{color:var(--bad);font-weight:600}.dn{color:var(--ok);font-weight:600}
.chip{width:40px;height:40px;border-radius:13px;display:grid;place-items:center;font-size:1.25rem;margin-bottom:10px;background:#fff;box-shadow:0 4px 10px rgba(27,31,59,.08)}
.bars{display:flex;align-items:flex-end;gap:12px;height:160px;padding-top:10px}
.bar{flex:1;min-width:0;text-align:center;font-size:.72rem;color:var(--mut);display:flex;flex-direction:column;justify-content:flex-end;height:100%}
.bar i{display:block;border-radius:8px 8px 0 0;min-height:4px;background:linear-gradient(180deg,#8B93FF,#5B50E6)}
.bar:nth-child(4n+2) i{background:linear-gradient(180deg,#FF9A9A,#FF6B6B)}.bar:nth-child(4n+3) i{background:linear-gradient(180deg,#5EEAD4,#14B8A6)}.bar:nth-child(4n+4) i{background:linear-gradient(180deg,#FCD34D,#F59E0B)}
.bar b{color:var(--fg);font-size:.75rem}
.donut{width:130px;height:130px;border-radius:50%;flex:none;position:relative}.donut:after{content:"";position:absolute;inset:28px;background:var(--card);border-radius:50%}
.row{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.leg{font-size:.8rem;display:grid;gap:3px;min-width:0}.leg span{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}
.prog{height:12px;background:var(--line);border-radius:99px;overflow:hidden;margin:8px 0}.prog i{display:block;height:100%;background:var(--grad);border-radius:99px;transition:width .4s}
label{display:block;font-size:.82rem;color:var(--mut);margin:12px 0 5px;font-weight:600}
input,select{width:100%;padding:11px 13px;border-radius:12px;border:1.5px solid var(--line);background:var(--card);color:var(--fg);font:inherit}
input:focus,select:focus{outline:0;border-color:var(--g);box-shadow:0 0 0 3px rgba(91,80,230,.18)}
input[type=checkbox]{width:auto}
button.btn{background:var(--grad);color:#fff;border:0;border-radius:12px;padding:11px 20px;font:inherit;font-weight:700;cursor:pointer;box-shadow:0 8px 18px rgba(91,80,230,.28);transition:transform .15s}
button.btn:hover{transform:translateY(-2px)}
button.btn.alt{background:var(--card);color:var(--g);border:1.5px solid var(--g);box-shadow:none}
button.btn.del{background:none;color:var(--bad);border:1.5px solid var(--bad);padding:4px 10px;box-shadow:none}
.pill{padding:2px 10px;border-radius:99px;font-size:.74rem;font-weight:700}.Low{background:#D8EBDD;color:#1F6B3E}.Medium{background:#F3E7C8;color:#8A6A1B}.High{background:#F2D6CC;color:#A04526}
.err{color:var(--bad);font-size:.85rem;margin:6px 0;font-weight:600}
.ok{background:var(--tip);color:var(--g);border-radius:14px;padding:12px 15px;margin-bottom:16px;display:flex;gap:12px;align-items:center}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.88rem}th,td{text-align:left;padding:10px;border-bottom:1px solid var(--line);white-space:nowrap}th{color:var(--mut);font-size:.72rem;text-transform:uppercase;letter-spacing:.05em}
.badge{text-align:center}.badge.lock{opacity:.9}
.empty{text-align:center;padding:44px 20px}.note{font-size:.78rem;color:var(--mut);margin-top:14px}
.hero{display:flex;justify-content:space-between;align-items:center;gap:18px;background:var(--grad);color:#fff;border-radius:26px;padding:26px 30px;margin-bottom:20px;box-shadow:0 16px 34px rgba(91,80,230,.28)}
.hero h1{color:#fff;margin:2px 0 4px}.hero h1:after{display:none}.hero p{margin:0;color:rgba(255,255,255,.9)}.hi{font-weight:600;color:rgba(255,255,255,.9)}
.ring{width:100px;height:100px;border-radius:50%;flex:none;display:grid;place-items:center;position:relative;text-align:center}
.ring:before{content:"";position:absolute;inset:10px;background:#fff;border-radius:50%}.ring div{position:relative;line-height:1.1;color:#1B1F3B}.ring b{font-size:1.35rem}.ring span{display:block;font-size:.62rem;color:#6B7280}
img.ic{width:46px;height:auto;flex:none}.badge img.ic{width:84px;margin-bottom:6px}.badge[style*="44px"] img.ic{width:44px;margin:0}.badge.lock img.ic{filter:grayscale(1);opacity:.3}
.cf{position:fixed;top:-10px;width:9px;height:14px;border-radius:2px;animation:fall 1.6s ease-in forwards;z-index:99;pointer-events:none}
@keyframes fall{to{transform:translateY(105vh) rotate(540deg);opacity:.2}}
/* layouts */
html[data-nav="bar"] .app,html[data-nav="dock"] .app{display:block}
html[data-nav="bar"] aside,html[data-nav="dock"] aside{position:sticky;top:0;height:auto;flex-direction:row;align-items:center;gap:14px;padding:10px 22px;padding-top:max(10px,env(safe-area-inset-top,0px));overflow:visible;background:linear-gradient(90deg,#4338CA,#7C3AED 70%,#9B5CF6)}
html[data-nav="bar"] .brand,html[data-nav="dock"] .brand{margin:0}html[data-nav="bar"] .tag,html[data-nav="dock"] .tag{display:none}
html[data-nav="bar"] nav{flex-direction:row;overflow-x:auto;margin-left:auto;min-width:0;scrollbar-width:none}
html[data-nav="bar"] nav button{width:auto;padding:8px 14px}html[data-nav="bar"] nav button:hover{transform:none}
html[data-nav="dock"] nav{position:fixed;left:50%;transform:translateX(-50%);bottom:max(12px,env(safe-area-inset-bottom,0px));flex-direction:row;background:var(--card);border:1px solid var(--line);border-radius:99px;padding:6px;box-shadow:0 12px 34px rgba(27,31,59,.22);z-index:30;max-width:calc(100% - 24px);overflow-x:auto;scrollbar-width:none}
html[data-nav="dock"] nav button{width:auto;color:var(--fg);padding:8px 14px}html[data-nav="dock"] nav button:hover{transform:none;background:var(--tip)}
html[data-nav="dock"] nav button.on{background:var(--grad);color:#fff}html[data-nav="dock"] main{padding-bottom:130px}
html[data-layout="focus"] main{max-width:780px}
html[data-layout="focus"] .g4{grid-template-columns:repeat(2,minmax(0,1fr))}html[data-layout="focus"] .g2,html[data-layout="focus"] .g3{grid-template-columns:minmax(0,1fr)}
@media(max-width:1100px){.g4,.g3{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:860px){main{padding:20px 16px 60px}.g2{grid-template-columns:minmax(0,1fr)}.hero{flex-wrap:wrap}}
@media(max-width:520px){.g4,.g3{grid-template-columns:minmax(0,1fr)}.val{font-size:1.55rem}h1{font-size:1.5rem}.hero{padding:20px}}
/* chatbot */
.cb{position:fixed;right:max(18px,env(safe-area-inset-right,0px));bottom:max(18px,env(safe-area-inset-bottom,0px));width:60px;height:60px;border-radius:50%;border:0;background:var(--grad);color:#fff;font-size:1.65rem;cursor:pointer;box-shadow:0 12px 30px rgba(91,80,230,.5);z-index:50;transition:transform .15s}
.cb:hover{transform:scale(1.08)}html[data-nav="dock"] .cb{bottom:90px}
.cp{position:fixed;right:max(18px,env(safe-area-inset-right,0px));bottom:92px;width:390px;max-width:calc(100vw - 24px);height:min(600px,calc(100vh - 116px));background:var(--card);border:1px solid var(--line);border-radius:24px;box-shadow:0 24px 70px rgba(27,31,59,.3);display:none;flex-direction:column;overflow:hidden;z-index:60}
html[data-nav="dock"] .cp{bottom:162px;height:min(560px,calc(100vh - 190px))}
.cp.open{display:flex}
.ch{background:var(--grad);color:#fff;padding:14px 16px;display:flex;align-items:center;gap:12px}.ch b{display:block;font-size:1rem}.ch small{opacity:.9;font-size:.74rem}
.ch button{margin-left:auto;background:rgba(255,255,255,.22);border:0;color:#fff;border-radius:50%;width:32px;height:32px;cursor:pointer;font-size:1rem}
.cm{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:var(--bg)}
.m{max-width:90%;padding:10px 13px;border-radius:16px;font-size:.88rem;line-height:1.45;overflow-wrap:anywhere}
.m.b{background:var(--card);border:1px solid var(--line);border-top-left-radius:4px;align-self:flex-start;color:var(--fg)}
.m.u{background:var(--g);color:#fff;border-top-right-radius:4px;align-self:flex-end}
.m ol,.m ul{margin:6px 0 4px 18px;padding:0}.m li{margin:3px 0}
.lk{display:inline-block;margin-top:6px;border:0;background:var(--grad);color:#fff;border-radius:99px;padding:6px 13px;font:inherit;font-size:.78rem;font-weight:600;cursor:pointer}
.chips{display:flex;gap:6px;flex-wrap:wrap;padding:8px 12px;border-top:1px solid var(--line);max-height:92px;overflow-y:auto;background:var(--card)}
.chips button{border:1px solid var(--g);color:var(--g);background:var(--card);border-radius:99px;padding:5px 11px;font:inherit;font-size:.76rem;cursor:pointer}.chips button:hover{background:var(--tip)}
.ci{display:flex;gap:8px;padding:10px 12px;border-top:1px solid var(--line);background:var(--card)}.ci input{flex:1;min-width:0}.ci button.btn{padding:10px 16px}
.dots span{display:inline-block;width:7px;height:7px;margin:0 2px;border-radius:50%;background:var(--mut);animation:bl 1s infinite}.dots span:nth-child(2){animation-delay:.15s}.dots span:nth-child(3){animation-delay:.3s}
@keyframes bl{0%,60%,100%{opacity:.25}30%{opacity:1}}
@media(max-width:520px){.cp{right:8px;left:8px;width:auto;max-width:none;bottom:86px;height:calc(100vh - 106px)}}
</style></head><body>
<div class="app"><aside>
<div class="brand"><svg viewBox="0 0 100 100"><path d="M50 92C8 62 18 20 50 6c32 14 42 56 0 86z" fill="var(--g)"/><path d="M50 92V25" stroke="var(--bg)" stroke-width="5"/></svg><b>ShopImpact</b></div>
<p class="tag">Shop smarter. Live greener.</p><nav id="nav"></nav></aside>
<main id="main"></main></div>
<button class="cb" id="cb" onclick="chatToggle()" aria-label="Open assistant">💬</button>
<div class="cp" id="cp"><div class="ch"><div style="font-size:1.7rem">🤖</div><div><b>ShopImpact Assistant</b><small>Ask me anything about the app</small></div><button onclick="chatToggle()" aria-label="Close">✕</button></div><div class="cm" id="cm"></div><div class="chips" id="chips"></div><div class="ci"><input id="cin" placeholder="Type a message…" onkeydown="if(event.key==='Enter')chatSend()"><button class="btn" onclick="chatSend()">Send</button></div></div>
<script>
var CATS=__CATS__;
var PRE=.4,CUR={INR:["₹",1],USD:["$",.012],EUR:["€",.011],GBP:["£",.0095]},COL=["#4F46E5","#FF6B6B","#14B8A6","#F59E0B","#8B5CF6","#0EA5E9","#EC4899","#84CC16"];
var NI={"Overview":"🏠","Add Purchase":"➕","Impact Analysis":"📊","Green Alternatives":"🌱","Achievements":"🏆","Shopping History":"🧾","Settings":"⚙️"};
var PAGES=["Overview","Add Purchase","Impact Analysis","Green Alternatives","Achievements","Shopping History","Settings"];
var ALT={"Clothing and Fashion":[["Second-hand clothing","Thrift stores and swaps reuse garments that already exist."],["Recycled-fibre fabrics","Can reduce demand for virgin raw materials."],["Durable basics","Lasts longer, so impact per wear drops."]],
"Footwear":[["Recycled-material footwear","Soles or uppers with recycled content."],["Repairable shoes","A cobbler repair beats a new pair."]],
"Electronics":[["Refurbished electronics","Avoids the large manufacturing footprint of a new device."],["Repair your device","New battery or screen is often the greenest option."],["Energy-efficient products","Check the rating label for lower running use."]],
"Groceries":[["Seasonal, local produce","Often less transport and storage."],["Plan meals","Avoided food waste avoids its emissions."]],
"Beauty and Personal Care":[["Solid or refillable products","Less plastic packaging."],["Use up what you own","Avoids waste and spending."]],
"Home and Furniture":[["Reusable products","Replace many single-use items."],["Pre-owned furniture","Reuses existing materials."],["Efficient appliances","Saves electricity for years."]],
"Accessories":[["Second-hand accessories","Reuse beats new production."]],"Other":[["Borrow or share","One item serves many people."],["Wait 48 hours","Many impulse buys never happen."]]};
var TIPS=__TIPS__;
var IMG=__IMG__,DEMO=__DEMO__;
var P=[],cfg={cur:"INR",target:50,name:"Friend",bg:"light",layout:"side"},page="Overview",flash="",hist={q:"",c:""};
try{P=JSON.parse(localStorage.getItem("si_p")||"[]");cfg=Object.assign(cfg,JSON.parse(localStorage.getItem("si_c")||"{}"))}catch(e){}
function save(){try{localStorage.setItem("si_p",JSON.stringify(P));localStorage.setItem("si_c",JSON.stringify(cfg))}catch(e){}}
function $(i){return document.getElementById(i)}
function est(p,c,pre){return Math.round(p*CATS[c]*(pre?PRE:1)*100)/100}
function lvl(x){return x<5?"Low":x<25?"Medium":"High"}
function eco(r){return lvl(r.co2)=="Low"||r.pre}
function money(inr){var c=CUR[cfg.cur];return c[0]+(inr*c[1]).toLocaleString(undefined,{maximumFractionDigits:c[1]==1?0:2})}
function today(){return new Date().toISOString().slice(0,10)}
function ago(d){var x=new Date();x.setDate(x.getDate()-d);return x.toISOString().slice(0,10)}
function mk(d){return d.slice(0,7)}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function rec(n,c,b,p,d,s,pre,demo){return{id:Math.random().toString(36).slice(2,9),n:n,c:c,b:b||"Unbranded",p:p,d:d,s:s,pre:!!pre,demo:!!demo,co2:est(p,c,pre)}}
function demo(){return DEMO.map(function(r){return rec(r[0],r[1],"Demo Brand",r[2],ago(r[3]),r[5],r[4],true)})}
function sum(a,k){return a.reduce(function(s,r){return s+r[k]},0)}
function badges(){var n=P.length,e=P.filter(eco).length,days={},by={};P.forEach(function(r){days[r.d]=1;(by[mk(r.d)]=by[mk(r.d)]||[]).push(r)});
var ch=Object.keys(by).some(function(m){return by[m].length>=3&&sum(by[m],"co2")<=cfg.target}),nd=Object.keys(days).length;
return[["Eco Beginner","leaf",n>=1,"Record your first purchase.",Math.min(n,1)+"/1"],["Mindful Shopper","badge",n>=5,"Record five purchases.",Math.min(n,5)+"/5"],["Green Choice","leaf",e>=1,"Record a Low-impact or second-hand purchase.",Math.min(e,1)+"/1"],["Eco Champion","badge",ch,"A month with 3+ purchases at or under your CO₂ target.",ch?"1/1":"0/1"],["Consistency Star","footprint",nd>=3,"Record purchases on 3 different days.",Math.min(nd,3)+"/3 days"]]}
function ico(t){return'<img class="ic" src="'+IMG[t]+'" alt="">'}
function card(l,v,s){var ic={"Monthly spending":"💸","Estimated CO₂":"☁️","Purchases":"🛍️","Eco-friendly":"🌱","Total CO₂":"☁️","Spending":"💸","Highest impact":"🔥","Lower-impact choices":"✨"}[l]||"📊";return'<div class="card"><div class="chip">'+ic+'</div><div class="lab">'+l+'</div><div class="val">'+v+'</div><div class="sub">'+s+'</div></div>'}
function dlt(c,p){if(!p)return"No previous month data";var x=(c-p)/p*100;return'<span class="'+(x<=0?"dn":"up")+'">'+(x<=0?"▼ ":"▲ ")+Math.abs(x).toFixed(0)+"%</span> vs last month"}
function empty(){return'<div class="card empty"><h3>No purchases yet</h3><p>Add your first purchase, or explore with clearly labelled demo data.</p><button class="btn" onclick="go(\'Add Purchase\')">Add a purchase</button> <button class="btn alt" onclick="loadDemo()">Load demo data</button></div>'}
function by(a,k,v){var o={};a.forEach(function(r){o[r[k]]=(o[r[k]]||0)+(v?r[v]:1)});return Object.keys(o).map(function(x){return[x,o[x]]}).sort(function(a,b){return b[1]-a[1]})}
function donut(a){var t=a.reduce(function(s,x){return s+x[1]},0),acc=0,st=[],lg="";a.forEach(function(x,i){var p=x[1]/t*100;st.push(COL[i%8]+" "+acc+"% "+(acc+p)+"%");acc+=p;lg+='<div><span style="background:'+COL[i%8]+'"></span>'+x[0]+" · "+p.toFixed(0)+"%</div>"});return'<div class="row"><div class="donut" style="background:conic-gradient('+st.join(",")+')"></div><div class="leg">'+lg+"</div></div>"}
function monthly(k){var o={};P.forEach(function(r){o[mk(r.d)]=(o[mk(r.d)]||0)+(k=="co2"?r.co2:r.p*CUR[cfg.cur][1])});var ks=Object.keys(o).sort(),mx=Math.max.apply(null,ks.map(function(m){return o[m]}));
return'<div class="bars">'+ks.map(function(m){return'<div class="bar"><b>'+Math.round(o[m]).toLocaleString()+'</b><i style="height:'+(o[m]/mx*100)+'%"></i>'+new Date(m+"-15").toLocaleString("en",{month:"short"})+"</div>"}).join("")+"</div>"}
function ecoPct(){return P.length?Math.round(P.filter(eco).length/P.length*100):0}
var views={
"Overview":function(){var h='<div class="hero"><div><div class="hi">Hey '+esc(cfg.name)+' 👋</div><h1>Ready to shop smarter?</h1><p>🌿 '+TIPS[new Date().getDate()%TIPS.length]+'</p></div><div class="ring" style="background:conic-gradient(#FF6B6B '+ecoPct()+'%,var(--line) 0)"><div><b>'+ecoPct()+'%</b><span>eco picks</span></div></div></div>';if(!P.length)return h+empty();
var m=mk(today()),pm=new Date();pm.setMonth(pm.getMonth()-1);pm=pm.toISOString().slice(0,7);var c=P.filter(function(r){return mk(r.d)==m}),p=P.filter(function(r){return mk(r.d)==pm}),ne=c.filter(eco).length,u=sum(c,"co2")/cfg.target;
h+=(P.some(function(r){return r.demo})?'<p class="note" style="margin:-6px 0 12px">Your data includes demo records. Remove them in Settings.</p>':"")+'<div class="grid g4">'+card("Monthly spending",money(sum(c,"p")),dlt(sum(c,"p"),sum(p,"p")))+card("Estimated CO₂",sum(c,"co2").toFixed(1)+" kg",dlt(sum(c,"co2"),sum(p,"co2")))+card("Purchases",c.length,"This month")+card("Eco-friendly",ne+" · "+(c.length?Math.round(ne/c.length*100):0)+"%","Low impact or second-hand")+"</div>";
h+='<h3>Monthly analytics</h3><div class="grid g2"><div class="card"><div class="lab">Spending by month ('+CUR[cfg.cur][0]+")</div>"+monthly("p")+'</div><div class="card"><div class="lab">CO₂ by month (kg)</div>'+monthly("co2")+'</div><div class="card"><div class="lab">Category breakdown (purchases)</div>'+donut(by(c.length?c:P,"c"))+'</div><div class="card"><div class="lab">Spending distribution</div>'+donut(by(c.length?c:P,"c","p"))+"</div></div>";
var bd=badges();h+='<h3>Environmental progress</h3><div class="grid g3"><div class="card"><div class="lab">CO₂ vs monthly target</div><b>'+sum(c,"co2").toFixed(1)+" of "+cfg.target+' kg</b><div class="prog"><i style="width:'+Math.min(u*100,100)+'%"></i></div><div class="sub">'+(u<=1?"Within target 🎉":"Over target. Small changes add up.")+'</div></div><div class="card"><div class="lab">Achievements '+bd.filter(function(b){return b[2]}).length+"/5</div><div class=\"row\">"+bd.map(function(b){return'<div class="badge'+(b[2]?"":" lock")+'" style="width:44px">'+ico(b[1]).replace("<svg",'<svg style="width:44px"')+"</div>"}).join("")+'</div></div><div class="card"><div class="lab">Recent sustainable decisions</div>'+(P.filter(eco).sort(function(a,b){return b.d.localeCompare(a.d)}).slice(0,4).map(function(r){return"🌱 "+esc(r.n)+" · "+r.d.slice(5)+"<br>"}).join("")||"None yet")+"</div></div>";
return h+'<h3>Quick actions</h3><div class="row"><button class="btn" onclick="go(\'Add Purchase\')">Add a new purchase</button><button class="btn alt" onclick="go(\'Impact Analysis\')">View impact analysis</button><button class="btn alt" onclick="go(\'Green Alternatives\')">Explore alternatives</button></div>'},
"Add Purchase":function(){return(flash?'<div class="ok">'+flash+"</div>":"")+'<h1>Add Purchase</h1><div class="grid g2"><div><label>Product name</label><input id="fn" oninput="pv()" placeholder="e.g. Cotton T-shirt"><label>Brand (optional)</label><input id="fb"><label>Status</label><select id="fs"><option>Purchased</option><option>Planned</option></select></div><div><label>Category</label><select id="fc" onchange="pv()">'+Object.keys(CATS).map(function(c){return"<option>"+c+"</option>"}).join("")+'</select><label>Price ('+CUR[cfg.cur][0]+')</label><input id="fp" type="number" min="0" step="any" oninput="pv()" placeholder="Enter a number"><label>Date</label><input id="fd" type="date" value="'+today()+'"></div></div><label><input id="fr" type="checkbox" style="width:auto" onchange="pv()"> Second-hand, refurbished or repaired (40% of multiplier)</label><h3>Summary</h3><div id="sum" class="card sub">Enter a name and valid price to see the estimate.</div><div id="errs"></div><p><button class="btn" onclick="add()">Add Purchase</button></p><p class="note">Estimated CO₂ = price (₹) × category multiplier (kg CO₂e per ₹1). Multipliers are illustrative, not exact lifecycle emissions.</p>'},
"Impact Analysis":function(){if(!P.length)return"<h1>Impact Analysis</h1>"+empty();var f=P.filter(function(r){return!hist.c||r.c==hist.c}),cat=by(f,"c","co2");
return'<h1>Impact Analysis</h1><label>Category filter</label><select onchange="hist.c=this.value;draw()"><option value="">All categories</option>'+Object.keys(CATS).map(function(c){return"<option"+(hist.c==c?" selected":"")+">"+c+"</option>"}).join("")+'</select><div class="grid g4" style="margin-top:14px">'+card("Total CO₂",sum(f,"co2").toFixed(1)+" kg","Selected")+card("Spending",money(sum(f,"p")),"Selected")+card("Highest impact",cat.length?cat[0][0]:"–",cat.length?cat[0][1].toFixed(1)+" kg":"")+card("Lower-impact choices",f.filter(eco).length,"of "+f.length)+'</div><h3>CO₂ by category</h3><div class="card">'+cat.map(function(x){return'<div class="sub">'+x[0]+" · "+x[1].toFixed(1)+' kg</div><div class="prog"><i style="width:'+x[1]/cat[0][1]*100+'%"></i></div>'}).join("")+'</div><div class="grid g2"><div><h3>Spending by category</h3><div class="card">'+donut(by(f,"c","p"))+'</div></div><div><h3>Monthly CO₂</h3><div class="card">'+monthly("co2")+"</div></div></div>"},
"Green Alternatives":function(){var mine=P.length?[].concat(Array.from(new Set(P.map(function(r){return r.c})))):Object.keys(CATS),cs=hist.c?[hist.c]:mine,q=hist.q.toLowerCase(),out="";
cs.forEach(function(c){(ALT[c]||[]).forEach(function(a){if(!q||(a[0]+a[1]+c).toLowerCase().indexOf(q)>-1)out+='<div class="card"><div class="lab">'+c+"</div><b>"+a[0]+'</b><div class="sub">'+a[1]+"</div></div>"})});
return'<h1>Green Alternatives</h1><p class="sub">Product characteristics and habits only. We never claim a brand is sustainable.</p><div class="grid g2"><div><label>Category</label><select onchange="hist.c=this.value;draw()"><option value="">'+(P.length?"Recommended for me":"All")+"</option>"+Object.keys(CATS).map(function(c){return"<option"+(hist.c==c?" selected":"")+">"+c+"</option>"}).join("")+'</select></div><div><label>Search</label><input value="'+esc(hist.q)+'" oninput="hist.q=this.value;draw(1)" placeholder="e.g. refurbished"></div></div><div class="grid g2" style="margin-top:14px">'+(out||'<p class="sub">No matches.</p>')+"</div>"},
"Achievements":function(){return'<h1>Achievements</h1><p class="sub">Calculated from your records. Badges never reward buying more.</p><div class="grid g3">'+badges().map(function(b){return'<div class="card badge'+(b[2]?"":" lock")+'">'+ico(b[1])+"<br><b>"+b[0]+"</b> "+(b[2]?"✅":"🔒")+'<div class="sub">'+b[3]+"<br>Progress: "+b[4]+"</div></div>"}).join("")+"</div>"},
"Shopping History":function(){if(!P.length)return"<h1>Shopping History</h1>"+empty();var q=hist.q.toLowerCase(),f=P.filter(function(r){return(!q||(r.n+r.b).toLowerCase().indexOf(q)>-1)&&(!hist.c||r.c==hist.c)}).sort(function(a,b){return b.d.localeCompare(a.d)});
return'<h1>Shopping History</h1><div class="grid g2"><div><label>Search</label><input value="'+esc(hist.q)+'" oninput="hist.q=this.value;draw(1)"></div><div><label>Category</label><select onchange="hist.c=this.value;draw()"><option value="">All</option>'+Object.keys(CATS).map(function(c){return"<option"+(hist.c==c?" selected":"")+">"+c+"</option>"}).join("")+'</select></div></div><p><button class="btn alt" onclick="csv()">Download CSV</button></p><div class="card tw"><table><tr><th>Product</th><th>Brand</th><th>Category</th><th>Price</th><th>Date</th><th>Status</th><th>CO₂ kg</th><th></th></tr>'+f.map(function(r){return"<tr><td>"+esc(r.n)+(r.demo?' <span class="sub">(demo)</span>':"")+"</td><td>"+esc(r.b)+"</td><td>"+r.c+"</td><td>"+money(r.p)+"</td><td>"+r.d+"</td><td>"+r.s+'</td><td><span class="pill '+lvl(r.co2)+'">'+r.co2+'</span></td><td><button class="btn del" onclick="del(\''+r.id+"')\">Delete</button></td></tr>"}).join("")+"</table></div>"},
"Settings":function(){return'<h1>Settings</h1><div class="tip">Preview note: data is saved only in this browser (when allowed). Nothing is uploaded.</div><div class="grid g2"><div><label>Your name</label><input value="'+esc(cfg.name)+'" onchange="cfg.name=this.value||\'Friend\';save()"><label>Currency (approximate fixed rates)</label><select onchange="cfg.cur=this.value;save();draw()">'+Object.keys(CUR).map(function(c){return"<option"+(cfg.cur==c?" selected":"")+">"+c+"</option>"}).join("")+'</select></div><div><label>Monthly CO₂ target (kg)</label><input type="number" min="1" value="'+cfg.target+'" onchange="cfg.target=Math.max(1,+this.value||50);save()"></div></div><h3>Look and layout</h3><div class="grid g2"><div><label>Background</label>'+opts("bg",[["light","White"],["grey","Soft grey"],["dark","Dark"]])+'</div><div><label>Layout</label>'+opts("layout",[["top","Top bar"],["side","Sidebar"],["bottom","Floating dock"],["focus","Focus (narrow)"]])+'</div></div><h3>Data</h3><div class="row"><button class="btn alt" onclick="csv()">Export CSV</button><button class="btn alt" onclick="loadDemo()">Load demo data</button><button class="btn alt" onclick="if(confirm(\'Remove demo records only?\')){P=P.filter(function(r){return!r.demo});save();draw()}">Remove demo data</button><button class="btn del" onclick="if(confirm(\'Delete ALL data? This cannot be undone.\')){P=[];save();draw()}">Delete all data</button></div>'}};
function draw(keep){var a=document.activeElement,id=keep&&a&&a.tagName=="INPUT"?a.value:null;$("main").innerHTML=views[page]();$("nav").innerHTML=PAGES.map(function(p){return'<button class="'+(p==page?"on":"")+'" onclick="go(\''+p+'\')"><b class="ni">'+(NI[p]||"")+'</b>'+p+"</button>"}).join("");
if(id!==null){var i=$("main").querySelector("input[oninput*=hist]");if(i){i.focus();i.setSelectionRange(id.length,id.length)}}}
function go(p){page=p;if(p!="Add Purchase")flash="";hist.c="";hist.q="";draw();scrollTo(0,0)}
function loadDemo(){if(P.some(function(r){return r.demo}))return alert("Demo data is already loaded.");P=P.concat(demo());save();draw()}
function vals(){var p=parseFloat($("fp").value);return{n:$("fn").value.trim(),c:$("fc").value,p:p,pre:$("fr").checked}}
function errs(v){var e=[];if(!v.n)e.push("Product name cannot be empty.");if(isNaN(v.p))e.push("Please enter a numeric price.");else if(v.p<=0)e.push("Price must be greater than zero.");return e}
function pv(){var v=vals(),e=errs(v);if(e.length){$("sum").innerHTML="Enter a name and valid price to see the estimate.";return}var inr=v.p/CUR[cfg.cur][1],co=est(inr,v.c,v.pre);
$("sum").innerHTML="<b>"+esc(v.n)+"</b> · "+v.c+"<br>Multiplier: <b>"+(CATS[v.c]*(v.pre?PRE:1)).toFixed(4)+" kg CO₂e per ₹1</b><br>Estimated impact: <b>"+co+' kg CO₂e</b> <span class="pill '+lvl(co)+'">'+lvl(co)+" impact</span>"}
function add(){var v=vals(),e=errs(v);if(e.length){$("errs").innerHTML=e.map(function(x){return'<div class="err">'+x+"</div>"}).join("");return}
var before=badges().map(function(b){return b[2]}),r=rec(v.n,v.c,$("fb").value.trim(),v.p/CUR[cfg.cur][1],$("fd").value||today(),$("fs").value,v.pre);P.push(r);save();var after=badges(),nb=after.filter(function(b,i){return b[2]&&!before[i]});
flash=(eco(r)?ico("leaf").replace("<svg",'<svg style="width:46px"'):"")+"<div>Added “"+esc(r.n)+"”: "+r.co2+" kg CO₂e ("+lvl(r.co2)+" impact)."+nb.map(function(b){return"<br>🏅 Badge unlocked: <b>"+b[0]+"</b>"}).join("")+"</div>";draw();if(nb.length||eco(r))confetti()}
function opts(k,a){return'<select onchange="cfg.'+k+'=this.value;save();look();draw()">'+a.map(function(o){return'<option value="'+o[0]+'"'+(cfg[k]==o[0]?" selected":"")+">"+o[1]+"</option>"}).join("")+"</select>"}
function confetti(){var c=["#4F46E5","#FF6B6B","#14B8A6","#F59E0B","#8B5CF6"];for(var i=0;i<40;i++){var s=document.createElement("i");s.className="cf";s.style.cssText="left:"+Math.random()*100+"vw;background:"+c[i%5]+";animation-delay:"+Math.random()*.5+"s";document.body.appendChild(s);setTimeout(function(e){e.remove()}.bind(null,s),2400)}}
function del(id){if(confirm("Delete this record permanently?")){P=P.filter(function(r){return r.id!=id});save();draw()}}
function csv(){var t="name,category,brand,price_inr,date,status,preowned,co2\n"+P.map(function(r){return[r.n,r.c,r.b,r.p,r.d,r.s,r.pre,r.co2].map(function(x){return'"'+String(x).replace(/"/g,'""')+'"'}).join(",")}).join("\n");
var a=document.createElement("a");a.href="data:text/csv;charset=utf-8,"+encodeURIComponent(t);a.download="shopimpact.csv";a.click()}
var CHIPS=["How do I add a purchase?","How is CO₂ calculated?","What’s my footprint?","How do I earn badges?","Change layout or colours","Give me a green tip","Help"];
function LK(p,t){return'<br><button class="lk" onclick="go(\''+p+'\')">'+(t||"Open "+p)+" →</button>"}
function steps(t,a,l){return"<b>"+t+"</b><ol>"+a.map(function(x){return"<li>"+x+"</li>"}).join("")+"</ol>"+(l?LK(l):"")}
function mine(){var c=sum(P,"co2"),s=sum(P,"p"),cat=by(P,"c","co2");return{n:P.length,c:c,s:s,top:cat.length?cat[0]:null,eco:P.filter(eco).length}}
function none(){return"You haven’t recorded any purchases yet, so there’s nothing to total. Add one, or load demo data to explore."+LK("Add Purchase","Add a purchase")+' <button class="lk" onclick="loadDemo()">Load demo data</button>'}
var BOT=[
[/^(hi+|hii+|hello+|helo+|hey+|heya|hola|namaste|yo|sup|howdy|good\s*(morning|afternoon|evening|night))\b/,function(q){var h=new Date().getHours(),g=/morning/.test(q)?"Good morning ☀️":/afternoon/.test(q)?"Good afternoon 🌤️":/evening|night/.test(q)?"Good evening 🌙":h<12?"Good morning ☀️":h<18?"Good afternoon 🌤️":"Good evening 🌙";return g+"! I’m the ShopImpact Assistant 👋"+(/how are you|how r u/.test(q)?" I’m doing great, thanks for asking!":"")+" I can guide you step by step, explain how CO₂ is estimated, or tell you about your own numbers. What would you like to do?"},6],
[/how are you|how r u|how s it going|what s up|wassup/,function(){return"I’m doing great, thanks for asking! 😊 Ready to help you shop smarter. What do you need?"}],
[/thank|thanks|thx|tysm|appreciate/,function(){return"You’re very welcome! 🌱 Ask me anything else any time."}],
[/^(bye|goodbye|see you|see ya|cya|later|good night)|talk later/,function(){return"Bye for now! 👋 Shop smart, live green. 🌍"}],
[/who are you|your name|are you (a )?(bot|human|real|ai)|what are you/,function(){return"I’m the ShopImpact Assistant, a built-in helper bot 🤖. I follow simple rules, so I’m best at questions about this app. Try the quick buttons below."}],
[/what can you do|help|menu|options|topics|guide me|support|assist/,function(){return"Here’s what I can help with:<ul><li>Adding, deleting and searching purchases</li><li>How CO₂ and impact levels are calculated</li><li>Your footprint, spending and top category</li><li>Badges and achievements</li><li>Targets, currency, layouts and colours</li><li>Exporting and backing up your data</li><li>Green alternatives and tips</li><li>Fixing problems</li></ul>Just type your question in your own words."}],
[/(add|record|log|enter|save|new).*(purchase|item|product|buy|bought|order)|how.*(use|start|begin)/,function(){return steps("Adding a purchase",["Open <b>Add Purchase</b> from the menu.","Type the product name and pick its category.","Enter the price in your chosen currency.","Pick the date and choose Purchased or Planned.","Tick the box if it’s second-hand or refurbished.","Check the live summary, then press <b>Add Purchase</b>."],["Add Purchase"])+'<div class="sub">Tip: the name must not be empty and the price must be a number above 0.</div>'}],
[/edit|update|modify|correct|mistake|wrong (price|entry|date)/,function(){return"This version doesn’t have an edit button yet. To fix a mistake: open <b>Shopping History</b>, delete the wrong entry, then add it again with the right details."+LK("Shopping History")}],
[/delete|remove.*(purchase|record|item|entry)/,function(){return steps("Deleting a purchase",["Open <b>Shopping History</b>.","Use search or the category filter to find it.","Press <b>Delete</b> on its row and confirm."],["Shopping History"])}],
[/(co2|carbon|emission|footprint).*(calculat|work|formula|estimate|measure|figure)|how.*(calculat|co2|carbon)|formula|multiplier|methodolog/,function(){return"<b>How CO₂ is estimated</b><br>Estimated CO₂ (kg) = price in ₹ × category multiplier.<br>Example: a ₹2,000 jacket × 0.006 = <b>12 kg</b>. Second-hand or refurbished items use 40% of the multiplier, so the same jacket second-hand is 4.8 kg.<br>Multipliers range from 0.0025 (groceries) to 0.007 (footwear) kg per ₹1."+LK("Add Purchase","Try it live")}],
[/accura|reliab|exact|real emission|trust|correct|scientific|true/,function(){return"Good question! These numbers are <b>illustrative estimates</b> based on price × a category average, not exact lifecycle emissions of a specific product or brand. Use them to compare habits and spot big categories, not as a certificate."}],
[/impact level|low impact|medium impact|high impact|eco.?friendly|green choice|what counts|lower.?impact/,function(){return"Impact levels per purchase: <b>Low</b> under 5 kg, <b>Medium</b> 5–25 kg, <b>High</b> 25 kg or more. A purchase counts as <b>eco-friendly</b> if it’s Low impact or second-hand/refurbished."}],
[/(my|total|overall).*(footprint|co2|carbon|emission|impact)|how much (co2|carbon)|footprint/,function(){var m=mine();if(!m.n)return none();return"So far you’ve recorded <b>"+m.n+"</b> purchases with an estimated <b>"+m.c.toFixed(1)+" kg CO₂</b>. Your monthly target is "+cfg.target+" kg."+(m.top?" Your highest-impact category is <b>"+m.top[0]+"</b> ("+m.top[1].toFixed(1)+" kg).":"")+LK("Impact Analysis")}],
[/(how much|total).*(spent|spend|money)|my spending|spent so far/,function(){var m=mine();if(!m.n)return none();return"You’ve recorded <b>"+money(m.s)+"</b> across "+m.n+" purchases (planned and purchased)."+LK("Overview")}],
[/highest|biggest|worst|most.*(impact|co2|emission)|top category/,function(){var m=mine();if(!m.n)return none();return"Your highest-impact category is <b>"+m.top[0]+"</b> at "+m.top[1].toFixed(1)+" kg CO₂. Want ideas to cut it?"+LK("Green Alternatives","See greener alternatives")}],
[/badge|achievement|unlock|reward|trophy/,function(){var b=badges(),u=b.filter(function(x){return x[2]});return"<b>Badges ("+u.length+"/5 unlocked)</b><ul>"+b.map(function(x){return"<li>"+(x[2]?"✅":"🔒")+" <b>"+x[0]+"</b>: "+x[3]+" ("+x[4]+")</li>"}).join("")+"</ul>Badges never reward buying more, only tracking and lower-impact choices."+LK("Achievements")}],
[/target|goal|limit|budget|monthly co2/,function(){return steps("Changing your monthly CO₂ target",["Open <b>Settings</b>.","Edit <b>Monthly CO₂ target (kg)</b>.","The overview progress bar updates straight away."],["Settings"])}],
[/currenc|rupee|dollar|euro|pound|inr|usd|eur|gbp/,function(){return steps("Changing currency",["Open <b>Settings</b>.","Pick INR, USD, EUR or GBP under <b>Currency</b>."],["Settings"])+'<div class="sub">Rates are approximate and fixed. CO₂ is always calculated from the ₹ value.</div>'}],
[/dark|theme|background|colou?r|layout|sidebar|top bar|dock|focus|appearance|design|style|look/,function(){return steps("Changing layout or colours",["Open <b>Settings</b>.","Under <b>Look and layout</b> pick a <b>Background</b>: White, Soft grey or Dark.","Pick a <b>Layout</b>: Sidebar, Top bar, Floating dock or Focus (narrow)."],["Settings"])}],
[/demo|sample|example data|dummy|test data/,function(){return steps("Demo data",["Open <b>Settings</b> and press <b>Load demo data</b> (or use the button on an empty page).","Demo rows are labelled “demo” in your history.","Press <b>Remove demo data</b> in Settings to delete only those rows."],["Settings"])}],
[/export|download|csv|backup|excel|save my data/,function(){return steps("Exporting your data",["Open <b>Shopping History</b> or <b>Settings</b>.","Press <b>Download CSV</b> / <b>Export CSV</b>.","Keep the file as your backup."],["Shopping History"])}],
[/import|upload|restore/,function(){return"Import isn’t available in this version. You can export a CSV backup from Shopping History or Settings."}],
[/reset|clear|wipe|delete all|start over|erase/,function(){return steps("Starting over",["Open <b>Settings</b>.","Use <b>Remove demo data</b> to delete only demo rows, or <b>Delete all data</b> to clear everything.","Confirm the pop-up. This cannot be undone, so export a CSV first."],["Settings"])}],
[/alternative|greener|sustainab|eco tip|reduce|lower my|cut my|planet|tip|advice|suggest/,function(){var t=["Repair before replacing: it’s usually the lowest-impact option.","Buy second-hand or refurbished: it avoids new production.","Wait 48 hours before non-essential purchases.","Choose durable items; cost and impact per use drop.","Plan groceries to cut food waste."];return"🌿 <b>Green tip:</b> "+t[Math.floor(Math.random()*t.length)]+LK("Green Alternatives","See all alternatives")}],
[/search|filter|find.*(purchase|record|item)|sort/,function(){return steps("Finding a purchase",["Open <b>Shopping History</b>.","Type in <b>Search</b> to match name or brand.","Use <b>Category</b> to narrow it down."],["Shopping History"])}],
[/chart|graph|donut|bar|trend|analys|monthly/,function(){return"<b>Reading the charts</b><ul><li>Bar charts show totals per month or category.</li><li>Donuts show each category’s share of spending.</li><li>Impact Analysis lets you filter by category.</li></ul>All charts update automatically when you add or delete a purchase."+LK("Impact Analysis")}],
[/planned|status|purchased/,function(){return"<b>Planned</b> means you’re thinking about buying it; <b>Purchased</b> means you already did. Both are included in totals so you can preview the impact before you buy."}],
[/privacy|safe|stored|where.*(data|saved)|lost|disappear|gone|vanish|persist|cloud|forgot|missing/,function(){return"Your records stay in <b>this browser</b> only (saved locally when your browser allows it). Nothing is uploaded. Clearing browser data or private mode can erase them, so export a CSV backup regularly."+LK("Settings")}],
[/phone|mobile|tablet|laptop|desktop|computer|\btv\b|screen|responsive|device/,function(){return"ShopImpact adapts to phones, tablets, laptops and TVs. On small screens the menu becomes a scrollable bar. For a phone-style bottom menu try <b>Settings → Layout → Floating dock</b>."+LK("Settings")}],
[/not working|bug|error|broken|glitch|stuck|crash|problem|issue|doesn t work|cant|can t|wont|won t/,function(){return steps("Quick fixes",["Refresh the page and try again.","When adding a purchase, make sure the name is filled and the price is a number above 0.","Try another layout in Settings if something looks off.","If data is missing, see how storage works by asking “is my data safe?”."],["Settings"])+'<div class="sub">Tell me exactly what happens and I’ll try to help.</div>'}],
[/joke|funny|bored|fun/,function(){return"I tried to buy a carbon-neutral joke… it was out of stock. 😄🌱"}],
[/love|great|awesome|nice|cool|good job|amazing|perfect/,function(){return"Thank you! 😊 Glad you like it."}],
[/shopimpact|what is this|about|purpose|what does this app|overview/,function(){return"<b>ShopImpact</b> helps you see the estimated CO₂ impact of your shopping, track spending, find greener alternatives and earn badges, all without guilt. Tagline: <i>Shop smarter. Live greener.</i>"+LK("Overview")}]
];
function botReply(t){var q=t.toLowerCase().replace(/[’`]/g,"'").replace(/[^a-z0-9\s']/g," ").replace(/'/g," ").replace(/\s+/g," ").trim(),w=q?q.split(" ").length:0;
for(var i=0;i<BOT.length;i++){if(BOT[i][0].test(q)&&!(BOT[i][2]&&w>BOT[i][2]))return BOT[i][1](q)}
return"Hmm, I’m not sure I understood that 🤔. I can help with adding or deleting purchases, how CO₂ is calculated, your footprint, badges, settings and tips. Try one of the buttons below or rephrase your question."}
function cmsg(w,h){var m=document.createElement("div");m.className="m "+w;m.innerHTML=h;$("cm").appendChild(m);$("cm").scrollTop=$("cm").scrollHeight;return m}
function chatToggle(){var p=$("cp"),o=!p.classList.contains("open");p.classList.toggle("open",o);if(o&&!$("cm").children.length){cmsg("b","Hi! 👋 I’m the <b>ShopImpact Assistant</b>. Ask me anything about the app, or tap a quick question below.");$("chips").innerHTML=CHIPS.map(function(c,i){return'<button onclick="ask('+i+')">'+c+"</button>"}).join("")}if(o)setTimeout(function(){$("cin").focus()},50)}
function ask(i){$("cin").value=CHIPS[i];chatSend()}
function chatSend(){var v=$("cin").value.trim();if(!v)return;$("cin").value="";cmsg("u",esc(v));var t=cmsg("b",'<span class="dots"><span></span><span></span><span></span></span>');setTimeout(function(){t.innerHTML=botReply(v);$("cm").scrollTop=$("cm").scrollHeight},420)}
function look(){var d=document.documentElement;d.dataset.layout=cfg.layout;d.dataset.theme=cfg.bg;d.dataset.nav=cfg.layout=="bottom"?"dock":(cfg.layout=="side"&&innerWidth>860)?"side":"bar"}
addEventListener("resize",look);
look();draw();
</script></body></html>
"""

# ======================================================================
# DATA OWNED BY PYTHON (sent to the interface)
# ======================================================================
TIPS = ["Repairing a device is usually greener than replacing it.",
        "Second-hand clothes avoid new production entirely.",
        "Wait 48 hours before non-essential purchases."]
# name, category, price (INR), days ago, second-hand (1/0), status
DEMO_ROWS = [
    ["Cotton T-shirt", "Clothing and Fashion", 799, 2, 0, "Purchased"],
    ["Second-hand denim jacket", "Clothing and Fashion", 1200, 5, 1, "Purchased"],
    ["Running shoes", "Footwear", 3499, 9, 0, "Purchased"],
    ["Refurbished laptop", "Electronics", 28000, 14, 1, "Purchased"],
    ["Wireless earbuds", "Electronics", 2999, 20, 0, "Purchased"],
    ["Weekly vegetables", "Groceries", 650, 1, 0, "Purchased"],
    ["Rice and lentils", "Groceries", 900, 7, 0, "Purchased"],
    ["Shampoo bar", "Beauty and Personal Care", 350, 11, 0, "Purchased"],
    ["Study desk", "Home and Furniture", 6500, 24, 0, "Purchased"],
    ["Reusable steel bottle", "Home and Furniture", 499, 3, 0, "Purchased"],
    ["Canvas tote bag", "Accessories", 450, 16, 0, "Purchased"],
    ["Smartwatch", "Electronics", 8999, 35, 0, "Purchased"],
    ["Winter jacket", "Clothing and Fashion", 4200, 40, 0, "Purchased"],
    ["Sandals", "Footwear", 1100, 45, 0, "Purchased"],
    ["Desk lamp", "Home and Furniture", 1800, 0, 0, "Planned"],
]


def png_data_uri(turtle_obj):
    """Turtle drawing -> PNG -> data URI the interface can show."""
    buf = io.BytesIO()
    turtle_obj.img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@st.cache_resource
def build_page():
    images = {"leaf": png_data_uri(draw_leaf()), "footprint": png_data_uri(draw_footprint()), "badge": png_data_uri(draw_badge())}
    return (PAGE.replace("__CATS__", json.dumps(MULTIPLIERS)).replace("__TIPS__", json.dumps(TIPS))
                .replace("__IMG__", json.dumps(images)).replace("__DEMO__", json.dumps(DEMO_ROWS)))


# ======================================================================
# STREAMLIT SHELL (full-screen, no Streamlit chrome)
# ======================================================================
st.set_page_config(page_title="ShopImpact", page_icon="🛍️", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
#MainMenu, footer, header {visibility:hidden; height:0;}
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none;}
.stApp {background:#fff;}
.block-container {padding:0 !important; max-width:100% !important;}
[data-testid="stVerticalBlock"] {gap:0 !important;}
iframe {height:100vh !important; height:100dvh !important; width:100% !important; border:0; display:block;}
</style>""", unsafe_allow_html=True)
if hasattr(st, "iframe"):          # newer Streamlit
    st.iframe(build_page(), width="stretch", height=900)
else:                              # older Streamlit
    components.html(build_page(), height=900, scrolling=False)
