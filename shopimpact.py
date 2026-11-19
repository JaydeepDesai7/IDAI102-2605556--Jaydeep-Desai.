"""ShopImpact - Shop smarter. Live greener.

Single-file Streamlit app (everything is in this one file).
Run:  pip install -r requirements.txt   then   streamlit run app.py
"""
import datetime as dt
import math
import tempfile
import uuid
from pathlib import Path

import pandas as pd
import altair as alt
import streamlit as st
from PIL import Image, ImageDraw, ImageOps

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
# ANALYTICS
# ======================================================================
def month_label(m):
    return pd.Period(m).strftime("%B %Y")


def prev_month(m):
    return str(pd.Period(m) - 1)


def months_available(df):
    cur = dt.date.today().strftime("%Y-%m")
    return sorted(set(df["month"]) | {cur})


def month_totals(df):
    if df.empty:
        return pd.DataFrame(columns=["month", "spend", "co2", "n"])
    g = df.groupby("month").agg(spend=("price_inr", "sum"), co2=("co2", "sum"), n=("id", "count")).reset_index()
    return g.sort_values("month")


def by_category(df):
    if df.empty:
        return pd.DataFrame(columns=["category", "spend", "co2", "n"])
    return (df.groupby("category").agg(spend=("price_inr", "sum"), co2=("co2", "sum"), n=("id", "count"))
              .reset_index().sort_values("co2", ascending=False))


def pct_change(cur, prev):
    return None if not prev else (cur - prev) / prev * 100

# ======================================================================
# ACHIEVEMENTS
# ======================================================================
BADGES = [
    {"id": "beginner", "title": "Eco Beginner", "icon": "leaf", "desc": "You started tracking your shopping impact.",
     "condition": "Record your first purchase."},
    {"id": "mindful", "title": "Mindful Shopper", "icon": "badge", "desc": "Five purchases tracked and understood.",
     "condition": "Record five purchases."},
    {"id": "green", "title": "Green Choice", "icon": "leaf", "desc": "You picked a lower-impact option.",
     "condition": "Record a purchase rated Low impact or bought second-hand/refurbished."},
    {"id": "champion", "title": "Eco Champion", "icon": "badge", "desc": "You stayed within your monthly CO₂ target.",
     "condition": "Have a month with 3+ purchases and total CO₂ at or under your target."},
    {"id": "consistency", "title": "Consistency Star", "icon": "footprint", "desc": "You track regularly, not just once.",
     "condition": "Record purchases on 3 different days."},
]


def evaluate(df, co2_target):
    n = len(df)
    eco = int(df["eco"].sum()) if n else 0
    days = df["date"].dt.date.nunique() if n else 0
    champ = 0
    if n:
        g = df.groupby("month").agg(n=("id", "count"), co2=("co2", "sum"))
        champ = int(((g.n >= 3) & (g.co2 <= co2_target)).sum())
    state = {"beginner": (n >= 1, f"{min(n, 1)}/1"), "mindful": (n >= 5, f"{min(n, 5)}/5"),
             "green": (eco >= 1, f"{min(eco, 1)}/1"), "champion": (champ >= 1, f"{min(champ, 1)}/1 month"),
             "consistency": (days >= 3, f"{min(days, 3)}/3 days")}
    return [{**b, "unlocked": state[b["id"]][0], "progress": state[b["id"]][1]} for b in BADGES]

# ======================================================================
# GREEN ALTERNATIVES
# ======================================================================
ALTERNATIVES = {
    "Clothing and Fashion": [
        ("Second-hand clothing", "Thrift stores, swaps and resale apps.", "Extends the life of garments that already exist, avoiding new production."),
        ("Recycled-fibre fabrics", "Look for recycled polyester or cotton blends.", "Can reduce demand for virgin raw materials."),
        ("Durable basics", "Tight stitching, quality seams, classic styles.", "Lasts longer, so cost and impact per wear drop."),
        ("Responsibly sourced materials", "Check for credible third-party labels.", "Verify any label yourself; we do not certify brands.")],
    "Footwear": [
        ("Recycled-material footwear", "Soles or uppers made partly from recycled content.", "Reduces use of new materials."),
        ("Durable shoes", "Stitched soles and sturdy materials.", "Fewer replacements over time."),
        ("Repairable footwear", "Replaceable soles and laces.", "A cobbler repair is usually far lower impact than a new pair.")],
    "Electronics": [
        ("Refurbished electronics", "Certified refurbished phones and laptops.", "Avoids the large manufacturing footprint of a new device."),
        ("Repair your current device", "New battery, screen or storage upgrade.", "Often the lowest-impact option."),
        ("Energy-efficient products", "Check the energy rating label.", "Lower electricity use over the product's life.")],
    "Groceries": [
        ("Seasonal and local produce", "Buy what is in season nearby.", "Often less transport and storage."),
        ("Plan meals to cut waste", "Shop with a list.", "Avoided food waste avoids its emissions."),
        ("Bulk and refill", "Bring your own containers.", "Less packaging waste.")],
    "Beauty and Personal Care": [
        ("Refillable or solid products", "Shampoo bars, refill pouches.", "Less plastic packaging."),
        ("Use up what you own", "Finish products before buying new.", "Avoids waste and unnecessary spending.")],
    "Home and Furniture": [
        ("Reusable products", "Steel bottles, cloth bags, glass containers.", "Replaces many single-use items."),
        ("Pre-owned or recycled-material furniture", "Check local resale and restoration.", "Reuses existing materials."),
        ("Energy-efficient appliances", "Choose a high star rating.", "Saves electricity for years.")],
    "Accessories": [
        ("Second-hand accessories", "Bags, watches and jewellery resale.", "Reuse beats new production."),
        ("Timeless, repairable pieces", "Choose items that can be mended.", "Longer useful life.")],
    "Other": [
        ("Borrow, rent or share", "Tools and rarely used items.", "One item serves many people."),
        ("Pause before buying", "Wait 48 hours on non-essentials.", "Many impulse buys never happen.")],
}
HABITS = ["Ask: do I need it, or can I borrow, repair or buy it second-hand?",
          "Choose quality over quantity; cost per use is what matters.",
          "Combine orders to reduce packaging and deliveries.",
          "Recycle or donate items instead of discarding them."]


def search(categories, text=""):
    text = text.lower().strip()
    out = []
    for c in categories:
        for name, how, why in ALTERNATIVES.get(c, []):
            if not text or text in (name + how + why + c).lower():
                out.append({"category": c, "name": name, "how": how, "why": why})
    return out

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



# ======================================================================
# STREAMLIT APP
# ======================================================================
# Turtle images are generated at start-up into a temp folder (works on Streamlit Cloud)
ASSETS = Path(tempfile.gettempdir()) / "shopimpact_assets"
if not (ASSETS / "leaf.png").exists():
    generate_all(ASSETS)

st.set_page_config(page_title="ShopImpact", page_icon="🛍️", layout="wide")

NAV = ["Overview Dashboard", "Add Purchase", "Impact Analysis", "Green Alternatives",
       "Achievements", "Shopping History", "Settings"]
PALETTE = ["#4F46E5", "#FF6B6B", "#14B8A6", "#F59E0B", "#8B5CF6", "#0EA5E9", "#EC4899", "#84CC16"]

# ======================================================================
# CHART HELPERS (Altair ships with Streamlit, so no extra install needed)
# ======================================================================
STRETCH = {"width": "stretch"} if tuple(int(v) for v in st.__version__.split(".")[:2]) >= (1, 50) else {"use_container_width": True}


class px:
    """Tiny helpers that build Altair charts (named px only to keep the page code short)."""

    @staticmethod
    def _prep(df, x, y, labels):
        if not isinstance(y, str):
            df, y = df.assign(_y=list(y)), "_y"
        labels = labels or {}
        xs = alt.X(x, title=labels.get(x, ""), sort=None if pd.api.types.is_datetime64_any_dtype(df[x]) else list(df[x]))
        return df, y, xs, labels.get(y, labels.get("y", ""))

    @staticmethod
    def bar(df, x, y, title=None, labels=None, orientation=None, text_auto=None):
        df, y, xs, yt = px._prep(df, x, y, labels)
        if orientation == "h":
            enc = dict(x=alt.X(y, title=yt), y=alt.Y(x, sort="-x", title=""))
        else:
            enc = dict(x=xs, y=alt.Y(y, title=yt))
        return alt.Chart(df).mark_bar(color=PALETTE[0], cornerRadiusEnd=6).encode(tooltip=[x, y], **enc).properties(title=title or "", height=300)

    @staticmethod
    def line(df, x, y, markers=True, title=None, labels=None):
        df, y, xs, yt = px._prep(df, x, y, labels)
        return alt.Chart(df).mark_line(point=True, color=PALETTE[0]).encode(x=xs, y=alt.Y(y, title=yt), tooltip=[x, y]).properties(title=title or "", height=300)

    @staticmethod
    def pie(df, names, values, hole=0.5, title=None):
        return (alt.Chart(df).mark_arc(innerRadius=60 if hole else 0)
                .encode(theta=alt.Theta(values, type="quantitative"),
                        color=alt.Color(names, type="nominal", scale=alt.Scale(range=PALETTE), legend=alt.Legend(orient="bottom", title=None)),
                        tooltip=[names, values]).properties(title=title or "", height=300))

TIPS = ["Repairing a device is usually greener than replacing it.",
        "Second-hand clothes avoid new production entirely.",
        "Buying fewer, longer-lasting items lowers cost per use.",
        "Wait 48 hours before non-essential purchases.",
        "Local, seasonal food often needs less transport and storage."]

# ---------- session state ----------
S = st.session_state
S.setdefault("purchases", [])
S.setdefault("settings", {"name": "Friend", "currency": "INR", "co2_target": 50.0,
                          "spend_target_inr": 20000.0, "theme": "White"})
S.setdefault("page", NAV[0])
S.setdefault("badges_seen", set())
S.setdefault("flash", None)
S.setdefault("celebrate", [])
S.setdefault("form_n", 0)
CFG = S["settings"]


def go(page):
    S["page"] = page


def sym_rate():
    return CURRENCIES[CFG["currency"]]


def money(inr):
    sym, rate = sym_rate()
    return f"{sym}{inr * rate:,.0f}" if rate == 1 else f"{sym}{inr * rate:,.2f}"


def df_all():
    return to_df(S["purchases"])


def refresh_badges():
    """Return ids of badges unlocked since we last looked (for celebrations)."""
    unlocked = {b["id"] for b in evaluate(df_all(), CFG["co2_target"]) if b["unlocked"]}
    new = sorted(unlocked - S["badges_seen"])
    S["badges_seen"] = unlocked
    return new


@st.cache_data
def badge_img(icon, locked):
    im = Image.open(ASSETS / "badges" / f"{icon}.png").convert("RGBA")
    if locked:
        a = im.split()[3]
        g = ImageOps.grayscale(im.convert("RGB")).convert("RGBA")
        g.putalpha(a.point(lambda v: int(v * 0.35)))
        return g
    return im


# ---------- styling ----------
THEMES = ["White", "Soft grey", "Lavender"]
LAYOUTS = ["Top bar", "Sidebar", "Focus (narrow)"]
CFG.setdefault("layout", "Top bar")
BG = {"White": ("#FFFFFF", "#FFFFFF"), "Soft grey": ("#F3F4F8", "#FFFFFF"), "Lavender": ("#F3F2FF", "#FFFFFF")}[CFG["theme"]]
FOCUS = CFG["layout"].startswith("Focus")
MAXW = 760 if FOCUS else 1400
TV_RULE = "" if FOCUS else "@media (min-width:1900px){.block-container{max-width:1750px !important;}}"
HIDE_SIDEBAR = "" if CFG["layout"] == "Sidebar" else 'section[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none;}'
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown {{ font-family: 'Inter', sans-serif; color:#1E2235; }}
.stApp {{ background:{BG[0]}; }}
.block-container {{ padding-top:1.6rem; max-width:{MAXW}px; overflow-x:hidden; }}
section[data-testid="stSidebar"] {{ background:#E9EFE6; border-right:1px solid #D7E0D3; }}
h1,h2,h3 {{ color:#4F46E5; letter-spacing:-0.01em; }}
h1 {{ font-size:1.8rem !important; }} h3 {{ font-size:1.15rem !important; }}
.si-card {{ background:{BG[1]}; border:1px solid #ECEEF4; border-radius:16px; padding:18px 20px;
  box-shadow:0 2px 10px rgba(79,70,229,.06); transition:transform .15s, box-shadow .15s; height:100%; }}
.si-card:hover {{ transform:translateY(-2px); box-shadow:0 6px 18px rgba(79,70,229,.12); }}
.si-label {{ font-size:.78rem; color:#7A7F7C; text-transform:uppercase; letter-spacing:.06em; font-weight:600; }}
.si-value {{ font-size:1.9rem; font-weight:700; color:#4F46E5; margin:2px 0; }}
.si-sub {{ font-size:.8rem; color:#7A7F7C; }}
.good {{ color:#12A594; font-weight:600; }} .bad {{ color:#C0623F; font-weight:600; }}
.tip {{ background:#EEF0FF; border-radius:12px; padding:10px 14px; color:#4F46E5; font-size:.9rem; margin:6px 0 16px; }}
.pill {{ display:inline-block; padding:2px 10px; border-radius:99px; font-size:.75rem; font-weight:600; }}
.Low {{ background:#D8EBDD; color:#1F6B3E; }} .Medium {{ background:#F3E7C8; color:#8A6A1B; }} .High {{ background:#F2D6CC; color:#A04526; }}
.stButton>button, .stDownloadButton>button {{ border-radius:10px; border:1px solid #4F46E5; font-weight:600; }}
.stButton>button[kind="primary"] {{ background:#4F46E5; color:white; }}
{HIDE_SIDEBAR}
#MainMenu, footer {{ visibility:hidden; }}
header[data-testid="stHeader"] {{ background:transparent; }}
html {{ font-size:clamp(15px,1.05vw,21px); }}
.block-container {{ padding-top:1rem !important; }}
div[role="radiogroup"] {{ flex-wrap:nowrap !important; overflow-x:auto; gap:6px !important; padding:4px 2px 8px; scrollbar-width:none; }}
div[role="radiogroup"]::-webkit-scrollbar {{ display:none; }}
div[role="radiogroup"] label {{ white-space:nowrap; cursor:pointer; background:#fff; border:1px solid #ECEEF4; border-radius:99px; padding:6px 14px !important; margin:0 !important; transition:all .15s; }}
div[role="radiogroup"] label:hover {{ background:#EEF0FF; }}
div[role="radiogroup"] label > div:first-child {{ display:none; }}
div[role="radiogroup"] label:has(input:checked) {{ background:#4F46E5; border-color:#4F46E5; box-shadow:0 4px 12px rgba(79,70,229,.35); }}
div[role="radiogroup"] label:has(input:checked) * {{ color:#fff !important; }}
div[data-testid="stVegaLiteChart"], div[data-testid="stArrowVegaLiteChart"] {{ background:#fff; border:1px solid #ECEEF4; border-radius:20px; padding:12px; box-shadow:0 4px 18px rgba(30,34,53,.06); }}
div[data-testid="stForm"] {{ border:1px solid #ECEEF4; border-radius:20px; background:#fff; }}
div[data-testid="stDataFrame"] {{ border-radius:16px; overflow:hidden; }}
input, textarea, div[data-baseweb="select"] > div {{ border-radius:12px !important; }}
.stButton>button, .stDownloadButton>button {{ min-height:2.6rem; }}
.si-card {{ height:auto; min-height:118px; }}
{TV_RULE}
@media (max-width:640px) {{ .hero {{ flex-direction:column; align-items:flex-start; }} .si-card {{ min-height:0; }} }}
h1,h2,h3{{color:#1E2235 !important;font-weight:800;}} .si-value{{color:#1E2235;}}
.si-card{{border-radius:20px;}} .chip{{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;font-size:1.2rem;margin-bottom:8px;background:#EEF0FF;}}
.hero{{display:flex;justify-content:space-between;align-items:center;gap:16px;background:linear-gradient(120deg,#EEF0FF,#FFF1EC);border-radius:24px;padding:22px 26px;margin-bottom:16px;}}
.hero h2{{margin:2px 0 4px;}} .hero p{{margin:0;color:#6B7280;}} .hi{{font-weight:600;color:#4F46E5;}}
.ring{{width:92px;height:92px;border-radius:50%;flex:none;display:grid;place-items:center;position:relative;text-align:center;}}
.ring:before{{content:"";position:absolute;inset:9px;background:#fff;border-radius:50%;}} .ring div{{position:relative;line-height:1.1;}} .ring b{{font-size:1.25rem;}} .ring span{{display:block;font-size:.62rem;color:#6B7280;}}
div[role="radiogroup"] label{{background:#fff;border:1px solid #ECEEF4;border-radius:99px;padding:2px 14px;}}
@media (max-width:640px) {{ .si-value {{ font-size:1.5rem; }} .block-container {{ padding:1rem .8rem; }} }}
</style>""", unsafe_allow_html=True)


ICONS = {"Monthly spending": "💸", "Estimated CO₂ footprint": "☁️", "Purchases recorded": "🛍️", "Eco-friendly purchases": "🌱",
         "Total CO₂": "☁️", "Total spending": "💸", "Highest-impact category": "🔥", "Lower-impact choices": "✨"}


def card(label, value, sub=""):
    return f"<div class='si-card'><div class='chip'>{ICONS.get(label, '📊')}</div><div class='si-label'>{label}</div><div class='si-value'>{value}</div><div class='si-sub'>{sub}</div></div>"


def delta_sub(cur, prev):
    pct = pct_change(cur, prev)
    if pct is None:
        return "No previous month data"
    cls, arrow = ("good", "▼") if pct <= 0 else ("bad", "▲")
    return f"<span class='{cls}'>{arrow} {abs(pct):.0f}%</span> vs last month"


def style_fig(fig, h=320):
    return fig.configure_view(strokeWidth=0)


def empty_state():
    st.markdown("<div class='si-card' style='text-align:center;padding:40px'><h3>No purchases yet</h3>"
                "<p>Add your first purchase to see your spending and CO₂ estimates, or explore with clearly labelled demo data.</p></div>",
                unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 2])
    c1.button("Add a purchase", type="primary", on_click=go, args=("Add Purchase",), **STRETCH)
    if c2.button("Load demo data", **STRETCH):
        S["purchases"] += demo_records()
        refresh_badges()
        S["flash"] = "Demo data loaded. These records are marked as demo and can be removed in Settings."
        st.rerun()


# ---------- pages ----------
def page_overview():
    df = df_all()
    pct = int(df.eco.mean() * 100) if len(df) else 0
    st.markdown(f"""<div class='hero'><div><div class='hi'>Hey {CFG['name']} 👋</div><h2>Ready to shop smarter?</h2>
    <p>🌿 {TIPS[dt.date.today().toordinal() % len(TIPS)]}</p></div>
    <div class='ring' style='background:conic-gradient(#FF6B6B {pct}%,#EEF0FF 0)'><div><b>{pct}%</b><span>eco picks</span></div></div></div>""", unsafe_allow_html=True)
    if df.empty:
        return empty_state()
    if any(S["purchases"][i]["demo"] for i in range(len(S["purchases"]))):
        st.info("Your data includes demo records. Remove them any time in Settings.")
    months = months_available(df)
    sel = st.selectbox("Month", months, index=len(months) - 1, format_func=month_label)
    cur, prev = df[df.month == sel], df[df.month == prev_month(sel)]
    has_prev = not prev.empty
    n_eco = int(cur.eco.sum())
    pct_eco = (n_eco / len(cur) * 100) if len(cur) else 0
    c = st.columns(4)
    c[0].markdown(card("Monthly spending", money(cur.price_inr.sum()),
                       delta_sub(cur.price_inr.sum(), prev.price_inr.sum() if has_prev else None)), unsafe_allow_html=True)
    c[1].markdown(card("Estimated CO₂ footprint", f"{cur.co2.sum():,.1f} kg",
                       delta_sub(cur.co2.sum(), prev.co2.sum() if has_prev else None)), unsafe_allow_html=True)
    c[2].markdown(card("Purchases recorded", len(cur), "Planned + purchased"), unsafe_allow_html=True)
    c[3].markdown(card("Eco-friendly purchases", f"{n_eco} · {pct_eco:.0f}%", "Low impact or second-hand"), unsafe_allow_html=True)

    st.markdown("### Monthly analytics")
    mt = month_totals(df)
    mt["label"] = mt.month.map(month_label)
    a, b = st.columns(2)
    a.altair_chart(style_fig(px.bar(mt, x="label", y=mt.spend * sym_rate()[1], title="Spending by month",
                                    labels={"y": f"Spending ({sym_rate()[0]})", "label": ""})), **STRETCH)
    b.altair_chart(style_fig(px.line(mt, x="label", y="co2", markers=True, title="Estimated CO₂ by month (kg)",
                                     labels={"co2": "kg CO₂e", "label": ""})), **STRETCH)
    if cur.empty:
        st.caption("No purchases in the selected month, so the category charts are empty.")
    else:
        cat = by_category(cur)
        a, b = st.columns(2)
        a.altair_chart(style_fig(px.bar(cat.sort_values("n"), x="n", y="category", orientation="h",
                                        title="Purchases by category", labels={"n": "Purchases", "category": ""})), **STRETCH)
        b.altair_chart(style_fig(px.pie(cat, names="category", values="spend", hole=.55, title="Spending distribution")),
                       **STRETCH)

    st.markdown("### Environmental progress")
    a, b, d = st.columns(3)
    with a:
        used = cur.co2.sum() / CFG["co2_target"] if CFG["co2_target"] else 0
        st.markdown(f"**CO₂ vs monthly target**  \n{cur.co2.sum():,.1f} of {CFG['co2_target']:,.0f} kg ({used * 100:.0f}%)")
        st.progress(min(used, 1.0))
        st.caption("Within target 🎉" if used <= 1 else "Over target this month. No judgement, small changes add up.")
    badges = evaluate(df, CFG["co2_target"])
    with b:
        st.markdown(f"**Achievements: {sum(x['unlocked'] for x in badges)}/{len(badges)} unlocked**")
        ic = st.columns(len(badges))
        for col, bd in zip(ic, badges):
            col.image(badge_img(bd["icon"], not bd["unlocked"]), width=44)
    with d:
        st.markdown("**Recent sustainable decisions**")
        rec_eco = df[df.eco].head(5)
        if rec_eco.empty:
            st.caption("None yet. Try second-hand or refurbished options.")
        for _, r in rec_eco.iterrows():
            st.markdown(f"🌱 {r['name']} · {r['date']:%d %b}")

    st.markdown("### Quick actions")
    q = st.columns(3)
    q[0].button("➕ Add a new purchase", on_click=go, args=("Add Purchase",), **STRETCH)
    q[1].button("📊 View impact analysis", on_click=go, args=("Impact Analysis",), **STRETCH)
    q[2].button("🌱 Explore green alternatives", on_click=go, args=("Green Alternatives",), **STRETCH)


def page_add():
    st.title("Add Purchase")
    n = S["form_n"]
    sym, rate = sym_rate()
    c1, c2 = st.columns(2)
    name = c1.text_input("Product name", key=f"name{n}", placeholder="e.g. Cotton T-shirt")
    category = c2.selectbox("Product category", CATEGORIES, key=f"cat{n}")
    brand = c1.text_input("Brand", key=f"brand{n}", placeholder="Optional")
    price = c2.number_input(f"Price ({sym})", min_value=0.0, value=None, step=1.0, key=f"price{n}",
                            placeholder="Enter a number")
    date = c1.date_input("Purchase date", value=dt.date.today(), key=f"date{n}")
    status = c2.radio("Purchase status", ["Purchased", "Planned"], horizontal=True, key=f"status{n}")
    pre = st.checkbox("Second-hand, refurbished or repaired item (lower multiplier)", key=f"pre{n}")

    price_inr = (price / rate) if price else None
    errors = validate(name, price, category, status)
    st.markdown("### Summary")
    if errors:
        st.caption("Fill in the product name and a valid price to see the impact estimate.")
    else:
        m = multiplier_for(category, pre)
        co2 = estimate_co2(price_inr, category, pre)
        lvl = impact_level(co2)
        st.markdown(f"""<div class='si-card'><b>{name.strip()}</b> · {category} · {brand.strip() or 'Unbranded'}<br>
        Price: {sym}{price:,.2f} · Date: {date:%d %b %Y} · {status}<br>
        Multiplier applied: <b>{m:.4f} kg CO₂e per ₹1</b> · Estimated impact: <b>{co2:,.2f} kg CO₂e</b>
        <span class='pill {lvl}'>{lvl} impact</span></div>""", unsafe_allow_html=True)
    with st.expander("How is this calculated?"):
        st.write("**Estimated CO₂ = price (in ₹) × category multiplier** (kg CO₂e per ₹1). Second-hand items use "
                 f"{int(PREOWNED_FACTOR * 100)}% of the multiplier. Multipliers are illustrative averages, "
                 "not exact product lifecycle emissions, so treat results as rough estimates.")
        st.dataframe(pd.DataFrame({"Category": CATEGORIES, "kg CO₂e per ₹1": list(MULTIPLIERS.values())}),
                     hide_index=True, **STRETCH)
    if st.button("Add Purchase", type="primary"):
        if errors:
            for e in errors:
                st.error(e)
            return
        rec_ = make_record(name, category, brand, price_inr, date, status, pre)
        S["purchases"].append(rec_)
        S["celebrate"] = refresh_badges()
        S["flash"] = f"Added “{rec_['name']}”: estimated {rec_['co2']:,.2f} kg CO₂e ({impact_level(rec_['co2'])} impact)."
        if pre or impact_level(rec_["co2"]) == "Low":
            S["flash_leaf"] = True
        S["form_n"] += 1
        st.rerun()


def page_analysis():
    st.title("Impact Analysis")
    df = df_all()
    if df.empty:
        return empty_state()
    f1, f2 = st.columns(2)
    rng = f1.date_input("Date range", value=(df.date.min().date(), max(df.date.max().date(), dt.date.today())))
    cats = f2.multiselect("Categories", CATEGORIES, default=CATEGORIES)
    if not (isinstance(rng, tuple) and len(rng) == 2):
        st.info("Pick both a start and an end date.")
        return
    f = df[(df.date.dt.date >= rng[0]) & (df.date.dt.date <= rng[1]) & df.category.isin(cats)]
    if f.empty:
        st.warning("No purchases match these filters.")
        return
    cat = by_category(f)
    c = st.columns(4)
    c[0].markdown(card("Total CO₂", f"{f.co2.sum():,.1f} kg", "In selected range"), unsafe_allow_html=True)
    c[1].markdown(card("Total spending", money(f.price_inr.sum()), "In selected range"), unsafe_allow_html=True)
    c[2].markdown(card("Highest-impact category", cat.iloc[0]["category"], f"{cat.iloc[0]['co2']:,.1f} kg CO₂e"), unsafe_allow_html=True)
    c[3].markdown(card("Lower-impact choices", int(f.eco.sum()), f"of {len(f)} purchases"), unsafe_allow_html=True)
    a, b = st.columns(2)
    a.altair_chart(style_fig(px.bar(cat, x="category", y="co2", title="CO₂ by category (kg)", labels={"co2": "kg CO₂e", "category": ""})),
                   **STRETCH)
    a.caption("Estimated emissions per category: which kinds of purchases drive your footprint.")
    b.altair_chart(style_fig(px.pie(cat, names="category", values="spend", hole=.55, title="Spending by category")),
                   **STRETCH)
    b.caption("Share of your spending in each category.")
    mt = month_totals(f)
    mt["label"] = mt.month.map(month_label)
    a, b = st.columns(2)
    a.altair_chart(style_fig(px.bar(mt, x="label", y="co2", text_auto=".1f", title="Monthly comparison (kg CO₂e)",
                                    labels={"co2": "kg CO₂e", "label": ""})), **STRETCH)
    a.caption("Total estimated CO₂ for each month in range.")
    t = f.sort_values("date").assign(cum=lambda x: x.co2.cumsum())
    b.altair_chart(style_fig(px.line(t, x="date", y="cum", markers=True, title="Cumulative CO₂ trend",
                                     labels={"cum": "kg CO₂e", "date": ""})), **STRETCH)
    b.caption("Running total over time; a flatter line means fewer high-impact purchases.")
    st.markdown("### Lower-impact choices")
    low = f[f.eco][["name", "category", "price_inr", "co2", "date"]]
    if low.empty:
        st.caption("No lower-impact purchases in this range yet.")
    else:
        st.dataframe(low.assign(price=low.price_inr.map(money), date=low.date.dt.date)[["name", "category", "price", "co2", "date"]]
                     .rename(columns={"co2": "CO₂ (kg)"}), hide_index=True, **STRETCH)
    st.caption("All figures are estimates based on price × illustrative category multipliers.")


def page_alternatives():
    st.title("Green Alternatives")
    st.caption("We recommend product characteristics and habits. We never claim a brand is sustainable; check labels yourself.")
    mine = sorted(set(df_all().category)) if S["purchases"] else []
    c1, c2 = st.columns(2)
    cat = c1.selectbox("Category", ["Recommended for me" if mine else "All categories"] + (["All categories"] if mine else []) + CATEGORIES)
    text = c2.text_input("Search", placeholder="e.g. refurbished, repair")
    cats = mine if cat == "Recommended for me" else CATEGORIES if cat == "All categories" else [cat]
    results = search(cats, text)
    if not results:
        st.info("No alternatives match your search.")
    for i in range(0, len(results), 2):
        cols = st.columns(2)
        for col, r in zip(cols, results[i:i + 2]):
            col.markdown(f"<div class='si-card'><div class='si-label'>{r['category']}</div><b>{r['name']}</b><br>"
                         f"{r['how']}<br><span class='si-sub'>Why it may be better: {r['why']}</span></div>", unsafe_allow_html=True)
            col.write("")
    st.markdown("### Sustainable shopping habits")
    for h in HABITS:
        st.markdown(f"- {h}")


def page_achievements():
    st.title("Achievements")
    st.caption("Badges are calculated automatically from your records. Shop only what you need; badges never reward buying more.")
    badges = evaluate(df_all(), CFG["co2_target"])
    cols = st.columns(3)
    for i, b in enumerate(badges):
        with cols[i % 3]:
            st.image(badge_img(b["icon"], not b["unlocked"]), width=110)
            st.markdown(f"**{b['title']}** {'✅ Unlocked' if b['unlocked'] else '🔒 Locked'}  \n{b['desc']}  \n"
                        f"*Unlock: {b['condition']}*  \nProgress: {b['progress']}")


def filtered_history(df):
    c1, c2, c3 = st.columns(3)
    q = c1.text_input("Search", placeholder="Name or brand")
    cats = c2.multiselect("Category", CATEGORIES)
    status = c3.multiselect("Status", ["Purchased", "Planned"])
    d1, d2, d3 = st.columns(3)
    rng = d1.date_input("Date range", value=(df.date.min().date(), max(df.date.max().date(), dt.date.today())))
    key = d2.selectbox("Sort by", ["Date", "Price", "CO₂", "Name"])
    asc = d3.radio("Order", ["Descending", "Ascending"], horizontal=True) == "Ascending"
    f = df
    if q:
        f = f[f.name.str.contains(q, case=False) | f.brand.str.contains(q, case=False)]
    if cats:
        f = f[f.category.isin(cats)]
    if status:
        f = f[f.status.isin(status)]
    if isinstance(rng, tuple) and len(rng) == 2:
        f = f[(f.date.dt.date >= rng[0]) & (f.date.dt.date <= rng[1])]
    col = {"Date": "date", "Price": "price_inr", "CO₂": "co2", "Name": "name"}[key]
    return f.sort_values(col, ascending=asc)


def page_history():
    st.title("Shopping History")
    df = df_all()
    if df.empty:
        return empty_state()
    f = filtered_history(df)
    show = pd.DataFrame({"Product": f.name, "Brand": f.brand, "Category": f.category, "Price": f.price_inr.map(money),
                         "Date": f.date.dt.date, "Status": f.status, "CO₂ (kg)": f.co2, "Demo": f.demo.map({True: "Yes", False: ""})})
    st.dataframe(show, hide_index=True, **STRETCH)
    st.caption(f"{len(f)} of {len(df)} records shown.")
    st.download_button("⬇ Download filtered CSV", export_csv(f[FIELDS].to_dict("records")), "shopimpact_history.csv", "text/csv")
    if f.empty:
        return
    st.markdown("### Edit or delete")
    opts = {r.id: f"{r['name']} · {r.date:%d %b %Y} · {money(r.price_inr)}" for _, r in f.iterrows()}
    rid = st.selectbox("Choose a record", list(opts), format_func=opts.get)
    rec_ = next(r for r in S["purchases"] if r["id"] == rid)
    sym, rate = sym_rate()
    with st.form(f"edit_{rid}"):
        a, b = st.columns(2)
        nm = a.text_input("Product name", rec_["name"])
        ct = b.selectbox("Category", CATEGORIES, index=CATEGORIES.index(rec_["category"]))
        br = a.text_input("Brand", rec_["brand"])
        pr = b.number_input(f"Price ({sym})", min_value=0.0, value=float(round(rec_["price_inr"] * rate, 2)), step=1.0)
        dtv = a.date_input("Date", value=pd.to_datetime(rec_["date"]).date())
        stt = b.radio("Status", ["Purchased", "Planned"], index=["Purchased", "Planned"].index(rec_["status"]), horizontal=True)
        pre = st.checkbox("Second-hand / refurbished", value=rec_["preowned"])
        if st.form_submit_button("Save changes", type="primary"):
            errs = validate(nm, pr, ct, stt)
            if errs:
                for e in errs:
                    st.error(e)
            else:
                new = make_record(nm, ct, br, pr / rate, dtv, stt, pre, demo=rec_["demo"], rid=rid)
                S["purchases"][S["purchases"].index(rec_)] = new
                refresh_badges()
                S["flash"] = "Record updated; statistics recalculated."
                st.rerun()
    if st.button("🗑 Delete this record"):
        S["confirm_delete"] = rid
    if S.get("confirm_delete") == rid:
        st.warning("Delete this record permanently?")
        y, n_ = st.columns(2)
        if y.button("Yes, delete", type="primary"):
            S["purchases"] = [r for r in S["purchases"] if r["id"] != rid]
            S["confirm_delete"] = None
            refresh_badges()
            S["flash"] = "Record deleted."
            st.rerun()
        if n_.button("Cancel"):
            S["confirm_delete"] = None
            st.rerun()


def page_settings():
    st.title("Settings")
    st.warning("Data lives in your browser session only. It disappears when you close or refresh the tab, "
               "so download a CSV backup to keep it. Nothing is stored in the cloud.")
    sym, rate = sym_rate()
    with st.form("settings"):
        a, b = st.columns(2)
        name = a.text_input("Your name", CFG["name"])
        cur = b.selectbox("Currency (approximate fixed rates)", list(CURRENCIES), index=list(CURRENCIES).index(CFG["currency"]))
        co2 = a.number_input("Monthly CO₂ target (kg)", min_value=1.0, value=float(CFG["co2_target"]), step=5.0)
        sp = b.number_input(f"Monthly spending target ({CURRENCIES[cur][0]})", min_value=1.0,
                            value=float(round(CFG["spend_target_inr"] * CURRENCIES[CFG["currency"]][1], 2)), step=100.0)
        theme = a.selectbox("Background", THEMES, index=THEMES.index(CFG["theme"]))
        layout = b.selectbox("Layout", LAYOUTS, index=LAYOUTS.index(CFG["layout"]))
        if st.form_submit_button("Save settings", type="primary"):
            CFG.update(name=name.strip() or "Friend", currency=cur, co2_target=co2,
                       spend_target_inr=sp / CURRENCIES[cur][1], theme=theme, layout=layout)
            refresh_badges()
            S["flash"] = "Settings saved."
            st.rerun()
    st.markdown("### Data")
    st.download_button("⬇ Export all records (CSV)", export_csv(S["purchases"]), "shopimpact_export.csv", "text/csv",
                       disabled=not S["purchases"])
    up = st.file_uploader("Import records from CSV (added to your current records)", type="csv")
    if up and st.button("Import file"):
        try:
            recs, skipped = import_csv(up)
            S["purchases"] += recs
            refresh_badges()
            S["flash"] = f"Imported {len(recs)} records ({skipped} skipped as invalid)."
            st.rerun()
        except Exception as e:
            st.error(f"Could not import: {e}")
    a, b = st.columns(2)
    if a.button("Load demo data"):
        if any(r["demo"] for r in S["purchases"]):
            st.info("Demo data is already loaded.")
        else:
            S["purchases"] += demo_records()
            refresh_badges()
            S["flash"] = "Demo data added alongside your records, marked “Demo” in History."
            st.rerun()
    st.markdown("### Reset")
    ok = st.checkbox("I understand this cannot be undone")
    if st.button("Remove demo data only", disabled=not ok):
        S["purchases"] = [r for r in S["purchases"] if not r["demo"]]
        refresh_badges()
        S["flash"] = "Demo data removed. Your own records are untouched."
        st.rerun()
    if st.button("Delete ALL data", disabled=not ok):
        S["purchases"] = []
        refresh_badges()
        S["flash"] = "All data deleted."
        st.rerun()


# ---------- shell ----------
if CFG["layout"] == "Sidebar":
    with st.sidebar:
        st.image(str(ASSETS / "logo.png"), width=56)
        st.markdown("<b style='font-size:1.25rem;color:#4F46E5'>ShopImpact</b>", unsafe_allow_html=True)
        st.caption("Shop smarter. Live greener.")
        st.radio("Navigate", NAV, key="page", label_visibility="collapsed")
else:
    top = st.columns([1.3, 5])
    with top[0]:
        st.markdown("<b style='font-size:1.25rem;color:#4F46E5'>🛍️ ShopImpact</b>", unsafe_allow_html=True)
        st.caption("Shop smarter. Live greener.")
    with top[1]:
        st.radio("Navigate", NAV, key="page", horizontal=True, label_visibility="collapsed")
st.caption("CO₂ values are estimates (price × category multiplier), not exact lifecycle emissions.")

if S["flash"]:
    st.success(S["flash"])
    if S.pop("flash_leaf", False):
        st.image(str(ASSETS / "leaf.png"), width=90, caption="Lower-impact choice!")
    for bid in S["celebrate"]:
        b = next(x for x in BADGES if x["id"] == bid)
        st.image(str(ASSETS / "badges" / f"{b['icon']}.png"), width=120, caption=f"Badge unlocked: {b['title']}")
    S["flash"], S["celebrate"] = None, []

{"Overview Dashboard": page_overview, "Add Purchase": page_add, "Impact Analysis": page_analysis,
 "Green Alternatives": page_alternatives, "Achievements": page_achievements,
 "Shopping History": page_history, "Settings": page_settings}[S["page"]]()
