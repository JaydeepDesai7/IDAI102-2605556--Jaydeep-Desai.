"""ShopImpact - Shop smarter. Live greener.  (Streamlit app entry point)"""
import datetime as dt
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from PIL import Image, ImageOps

from modules import achievements as ach
from modules import analytics as an
from modules import calculations as calc
from modules import purchases as pur
from modules import recommendations as rec

ASSETS = Path(__file__).parent / "assets"
if not (ASSETS / "leaf.png").exists():          # regenerate Turtle art if assets are missing
    import turtle_art
    turtle_art.generate_all(ASSETS)

st.set_page_config(page_title="ShopImpact", page_icon=str(ASSETS / "logo.png"), layout="wide")

NAV = ["Overview Dashboard", "Add Purchase", "Impact Analysis", "Green Alternatives",
       "Achievements", "Shopping History", "Settings"]
PALETTE = ["#4F46E5", "#FF6B6B", "#14B8A6", "#F59E0B", "#8B5CF6", "#0EA5E9", "#EC4899", "#84CC16"]
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
    return calc.CURRENCIES[CFG["currency"]]


def money(inr):
    sym, rate = sym_rate()
    return f"{sym}{inr * rate:,.0f}" if rate == 1 else f"{sym}{inr * rate:,.2f}"


def df_all():
    return pur.to_df(S["purchases"])


def refresh_badges():
    """Return ids of badges unlocked since we last looked (for celebrations)."""
    unlocked = {b["id"] for b in ach.evaluate(df_all(), CFG["co2_target"]) if b["unlocked"]}
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
MAXW = 760 if CFG["layout"].startswith("Focus") else 1200
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
    pct = an.pct_change(cur, prev)
    if pct is None:
        return "No previous month data"
    cls, arrow = ("good", "▼") if pct <= 0 else ("bad", "▲")
    return f"<span class='{cls}'>{arrow} {abs(pct):.0f}%</span> vs last month"


def style_fig(fig, h=320):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#1E2235"),
                      colorway=PALETTE, legend=dict(orientation="h", y=-0.2))
    return fig


def empty_state():
    st.markdown("<div class='si-card' style='text-align:center;padding:40px'><h3>No purchases yet</h3>"
                "<p>Add your first purchase to see your spending and CO₂ estimates, or explore with clearly labelled demo data.</p></div>",
                unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 2])
    c1.button("Add a purchase", type="primary", on_click=go, args=("Add Purchase",), width="stretch")
    if c2.button("Load demo data", width="stretch"):
        S["purchases"] += pur.demo_records()
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
    months = an.months_available(df)
    sel = st.selectbox("Month", months, index=len(months) - 1, format_func=an.month_label)
    cur, prev = df[df.month == sel], df[df.month == an.prev_month(sel)]
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
    mt = an.month_totals(df)
    mt["label"] = mt.month.map(an.month_label)
    a, b = st.columns(2)
    a.plotly_chart(style_fig(px.bar(mt, x="label", y=mt.spend * sym_rate()[1], title="Spending by month",
                                    labels={"y": f"Spending ({sym_rate()[0]})", "label": ""})), width="stretch")
    b.plotly_chart(style_fig(px.line(mt, x="label", y="co2", markers=True, title="Estimated CO₂ by month (kg)",
                                     labels={"co2": "kg CO₂e", "label": ""})), width="stretch")
    if cur.empty:
        st.caption("No purchases in the selected month, so the category charts are empty.")
    else:
        cat = an.by_category(cur)
        a, b = st.columns(2)
        a.plotly_chart(style_fig(px.bar(cat.sort_values("n"), x="n", y="category", orientation="h",
                                        title="Purchases by category", labels={"n": "Purchases", "category": ""})), width="stretch")
        b.plotly_chart(style_fig(px.pie(cat, names="category", values="spend", hole=.55, title="Spending distribution")),
                       width="stretch")

    st.markdown("### Environmental progress")
    a, b, d = st.columns(3)
    with a:
        used = cur.co2.sum() / CFG["co2_target"] if CFG["co2_target"] else 0
        st.markdown(f"**CO₂ vs monthly target**  \n{cur.co2.sum():,.1f} of {CFG['co2_target']:,.0f} kg ({used * 100:.0f}%)")
        st.progress(min(used, 1.0))
        st.caption("Within target 🎉" if used <= 1 else "Over target this month. No judgement, small changes add up.")
    badges = ach.evaluate(df, CFG["co2_target"])
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
    q[0].button("➕ Add a new purchase", on_click=go, args=("Add Purchase",), width="stretch")
    q[1].button("📊 View impact analysis", on_click=go, args=("Impact Analysis",), width="stretch")
    q[2].button("🌱 Explore green alternatives", on_click=go, args=("Green Alternatives",), width="stretch")


def page_add():
    st.title("Add Purchase")
    n = S["form_n"]
    sym, rate = sym_rate()
    c1, c2 = st.columns(2)
    name = c1.text_input("Product name", key=f"name{n}", placeholder="e.g. Cotton T-shirt")
    category = c2.selectbox("Product category", calc.CATEGORIES, key=f"cat{n}")
    brand = c1.text_input("Brand", key=f"brand{n}", placeholder="Optional")
    price = c2.number_input(f"Price ({sym})", min_value=0.0, value=None, step=1.0, key=f"price{n}",
                            placeholder="Enter a number")
    date = c1.date_input("Purchase date", value=dt.date.today(), key=f"date{n}")
    status = c2.radio("Purchase status", ["Purchased", "Planned"], horizontal=True, key=f"status{n}")
    pre = st.checkbox("Second-hand, refurbished or repaired item (lower multiplier)", key=f"pre{n}")

    price_inr = (price / rate) if price else None
    errors = pur.validate(name, price, category, status)
    st.markdown("### Summary")
    if errors:
        st.caption("Fill in the product name and a valid price to see the impact estimate.")
    else:
        m = calc.multiplier_for(category, pre)
        co2 = calc.estimate_co2(price_inr, category, pre)
        lvl = calc.impact_level(co2)
        st.markdown(f"""<div class='si-card'><b>{name.strip()}</b> · {category} · {brand.strip() or 'Unbranded'}<br>
        Price: {sym}{price:,.2f} · Date: {date:%d %b %Y} · {status}<br>
        Multiplier applied: <b>{m:.4f} kg CO₂e per ₹1</b> · Estimated impact: <b>{co2:,.2f} kg CO₂e</b>
        <span class='pill {lvl}'>{lvl} impact</span></div>""", unsafe_allow_html=True)
    with st.expander("How is this calculated?"):
        st.write("**Estimated CO₂ = price (in ₹) × category multiplier** (kg CO₂e per ₹1). Second-hand items use "
                 f"{int(calc.PREOWNED_FACTOR * 100)}% of the multiplier. Multipliers are illustrative averages, "
                 "not exact product lifecycle emissions, so treat results as rough estimates.")
        st.dataframe(pd.DataFrame({"Category": calc.CATEGORIES, "kg CO₂e per ₹1": list(calc.MULTIPLIERS.values())}),
                     hide_index=True, width="stretch")
    if st.button("Add Purchase", type="primary"):
        if errors:
            for e in errors:
                st.error(e)
            return
        rec_ = pur.make_record(name, category, brand, price_inr, date, status, pre)
        S["purchases"].append(rec_)
        S["celebrate"] = refresh_badges()
        S["flash"] = f"Added “{rec_['name']}”: estimated {rec_['co2']:,.2f} kg CO₂e ({calc.impact_level(rec_['co2'])} impact)."
        if pre or calc.impact_level(rec_["co2"]) == "Low":
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
    cats = f2.multiselect("Categories", calc.CATEGORIES, default=calc.CATEGORIES)
    if not (isinstance(rng, tuple) and len(rng) == 2):
        st.info("Pick both a start and an end date.")
        return
    f = df[(df.date.dt.date >= rng[0]) & (df.date.dt.date <= rng[1]) & df.category.isin(cats)]
    if f.empty:
        st.warning("No purchases match these filters.")
        return
    cat = an.by_category(f)
    c = st.columns(4)
    c[0].markdown(card("Total CO₂", f"{f.co2.sum():,.1f} kg", "In selected range"), unsafe_allow_html=True)
    c[1].markdown(card("Total spending", money(f.price_inr.sum()), "In selected range"), unsafe_allow_html=True)
    c[2].markdown(card("Highest-impact category", cat.iloc[0]["category"], f"{cat.iloc[0]['co2']:,.1f} kg CO₂e"), unsafe_allow_html=True)
    c[3].markdown(card("Lower-impact choices", int(f.eco.sum()), f"of {len(f)} purchases"), unsafe_allow_html=True)
    a, b = st.columns(2)
    a.plotly_chart(style_fig(px.bar(cat, x="category", y="co2", title="CO₂ by category (kg)", labels={"co2": "kg CO₂e", "category": ""})),
                   width="stretch")
    a.caption("Estimated emissions per category: which kinds of purchases drive your footprint.")
    b.plotly_chart(style_fig(px.pie(cat, names="category", values="spend", hole=.55, title="Spending by category")),
                   width="stretch")
    b.caption("Share of your spending in each category.")
    mt = an.month_totals(f)
    mt["label"] = mt.month.map(an.month_label)
    a, b = st.columns(2)
    a.plotly_chart(style_fig(px.bar(mt, x="label", y="co2", text_auto=".1f", title="Monthly comparison (kg CO₂e)",
                                    labels={"co2": "kg CO₂e", "label": ""})), width="stretch")
    a.caption("Total estimated CO₂ for each month in range.")
    t = f.sort_values("date").assign(cum=lambda x: x.co2.cumsum())
    b.plotly_chart(style_fig(px.line(t, x="date", y="cum", markers=True, title="Cumulative CO₂ trend",
                                     labels={"cum": "kg CO₂e", "date": ""})), width="stretch")
    b.caption("Running total over time; a flatter line means fewer high-impact purchases.")
    st.markdown("### Lower-impact choices")
    low = f[f.eco][["name", "category", "price_inr", "co2", "date"]]
    if low.empty:
        st.caption("No lower-impact purchases in this range yet.")
    else:
        st.dataframe(low.assign(price=low.price_inr.map(money), date=low.date.dt.date)[["name", "category", "price", "co2", "date"]]
                     .rename(columns={"co2": "CO₂ (kg)"}), hide_index=True, width="stretch")
    st.caption("All figures are estimates based on price × illustrative category multipliers.")


def page_alternatives():
    st.title("Green Alternatives")
    st.caption("We recommend product characteristics and habits. We never claim a brand is sustainable; check labels yourself.")
    mine = sorted(set(df_all().category)) if S["purchases"] else []
    c1, c2 = st.columns(2)
    cat = c1.selectbox("Category", ["Recommended for me" if mine else "All categories"] + (["All categories"] if mine else []) + calc.CATEGORIES)
    text = c2.text_input("Search", placeholder="e.g. refurbished, repair")
    cats = mine if cat == "Recommended for me" else calc.CATEGORIES if cat == "All categories" else [cat]
    results = rec.search(cats, text)
    if not results:
        st.info("No alternatives match your search.")
    for i in range(0, len(results), 2):
        cols = st.columns(2)
        for col, r in zip(cols, results[i:i + 2]):
            col.markdown(f"<div class='si-card'><div class='si-label'>{r['category']}</div><b>{r['name']}</b><br>"
                         f"{r['how']}<br><span class='si-sub'>Why it may be better: {r['why']}</span></div>", unsafe_allow_html=True)
            col.write("")
    st.markdown("### Sustainable shopping habits")
    for h in rec.HABITS:
        st.markdown(f"- {h}")


def page_achievements():
    st.title("Achievements")
    st.caption("Badges are calculated automatically from your records. Shop only what you need; badges never reward buying more.")
    badges = ach.evaluate(df_all(), CFG["co2_target"])
    cols = st.columns(3)
    for i, b in enumerate(badges):
        with cols[i % 3]:
            st.image(badge_img(b["icon"], not b["unlocked"]), width=110)
            st.markdown(f"**{b['title']}** {'✅ Unlocked' if b['unlocked'] else '🔒 Locked'}  \n{b['desc']}  \n"
                        f"*Unlock: {b['condition']}*  \nProgress: {b['progress']}")


def filtered_history(df):
    c1, c2, c3 = st.columns(3)
    q = c1.text_input("Search", placeholder="Name or brand")
    cats = c2.multiselect("Category", calc.CATEGORIES)
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
    st.dataframe(show, hide_index=True, width="stretch")
    st.caption(f"{len(f)} of {len(df)} records shown.")
    st.download_button("⬇ Download filtered CSV", pur.export_csv(f[pur.FIELDS].to_dict("records")), "shopimpact_history.csv", "text/csv")
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
        ct = b.selectbox("Category", calc.CATEGORIES, index=calc.CATEGORIES.index(rec_["category"]))
        br = a.text_input("Brand", rec_["brand"])
        pr = b.number_input(f"Price ({sym})", min_value=0.0, value=float(round(rec_["price_inr"] * rate, 2)), step=1.0)
        dtv = a.date_input("Date", value=pd.to_datetime(rec_["date"]).date())
        stt = b.radio("Status", ["Purchased", "Planned"], index=["Purchased", "Planned"].index(rec_["status"]), horizontal=True)
        pre = st.checkbox("Second-hand / refurbished", value=rec_["preowned"])
        if st.form_submit_button("Save changes", type="primary"):
            errs = pur.validate(nm, pr, ct, stt)
            if errs:
                for e in errs:
                    st.error(e)
            else:
                new = pur.make_record(nm, ct, br, pr / rate, dtv, stt, pre, demo=rec_["demo"], rid=rid)
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
        cur = b.selectbox("Currency (approximate fixed rates)", list(calc.CURRENCIES), index=list(calc.CURRENCIES).index(CFG["currency"]))
        co2 = a.number_input("Monthly CO₂ target (kg)", min_value=1.0, value=float(CFG["co2_target"]), step=5.0)
        sp = b.number_input(f"Monthly spending target ({calc.CURRENCIES[cur][0]})", min_value=1.0,
                            value=float(round(CFG["spend_target_inr"] * calc.CURRENCIES[CFG["currency"]][1], 2)), step=100.0)
        theme = a.selectbox("Background", THEMES, index=THEMES.index(CFG["theme"]))
        layout = b.selectbox("Layout", LAYOUTS, index=LAYOUTS.index(CFG["layout"]))
        if st.form_submit_button("Save settings", type="primary"):
            CFG.update(name=name.strip() or "Friend", currency=cur, co2_target=co2,
                       spend_target_inr=sp / calc.CURRENCIES[cur][1], theme=theme, layout=layout)
            refresh_badges()
            S["flash"] = "Settings saved."
            st.rerun()
    st.markdown("### Data")
    st.download_button("⬇ Export all records (CSV)", pur.export_csv(S["purchases"]), "shopimpact_export.csv", "text/csv",
                       disabled=not S["purchases"])
    up = st.file_uploader("Import records from CSV (added to your current records)", type="csv")
    if up and st.button("Import file"):
        try:
            recs, skipped = pur.import_csv(up)
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
            S["purchases"] += pur.demo_records()
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
        b = next(x for x in ach.BADGES if x["id"] == bid)
        st.image(str(ASSETS / "badges" / f"{b['icon']}.png"), width=120, caption=f"Badge unlocked: {b['title']}")
    S["flash"], S["celebrate"] = None, []

{"Overview Dashboard": page_overview, "Add Purchase": page_add, "Impact Analysis": page_analysis,
 "Green Alternatives": page_alternatives, "Achievements": page_achievements,
 "Shopping History": page_history, "Settings": page_settings}[S["page"]]()
