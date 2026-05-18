"""
fetch_calendrier.py
===================
Récupère le calendrier CDM 2026 depuis lequipe.fr/Football/coupe-du-monde/page-calendrier-general
et compare avec notre liste_matches.js.

Prérequis :
    pip install playwright
    playwright install chromium

Usage :
    python fetch_calendrier.py              # compare et affiche les écarts
    python fetch_calendrier.py --export     # exporte le calendrier lequipe en JSON
    python fetch_calendrier.py --debug      # sauvegarde le HTML brut
"""

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

DOSSIER        = Path(__file__).parent
CALENDRIER_JS  = DOSSIER / "liste_matches.js"
FICHIER_DEBUG  = DOSSIER / "debug_calendrier.html"
FICHIER_EXPORT = DOSSIER / "calendrier_lequipe.json"

URL_CALENDRIER = "https://www.lequipe.fr/Football/coupe-du-monde/page-calendrier-general"

MOIS_FR = {
    "janvier": "01", "février": "02", "mars": "03", "avril": "04",
    "mai": "05", "juin": "06", "juillet": "07", "août": "08",
    "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12",
}


def normaliser(txt: str) -> str:
    nfd = unicodedata.normalize("NFD", txt or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower().strip()


def parser_date_fr(texte: str) -> str:
    """'jeudi 11 juin 2026' → '11/06/2026'"""
    m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", texte.lower())
    if not m:
        return ""
    jour, mois_txt, annee = m.group(1), m.group(2), m.group(3)
    mois = MOIS_FR.get(mois_txt, "??")
    return f"{int(jour):02d}/{mois}/{annee}"


# ── LECTURE DU CALENDRIER LOCAL ───────────────────────────────────────────────

def charger_calendrier_local() -> list:
    texte = CALENDRIER_JS.read_text(encoding="utf-8")
    debut = texte.index("[")
    fin   = texte.index("];") + 1
    brut  = re.sub(r"//[^\n]*", "", texte[debut:fin])
    try:
        return json.loads(brut)
    except json.JSONDecodeError as e:
        print(f"❌ Erreur parsing liste_matches.js : {e}")
        return []


# ── SCRAPING ──────────────────────────────────────────────────────────────────

def scraper_calendrier(page, debug=False) -> list:
    """
    Retourne une liste de dicts :
        { id, equipeA, equipeB, groupe, journee, date, heure, timestamp }
    """
    if debug:
        FICHIER_DEBUG.write_text(page.content(), encoding="utf-8")
        print(f"📄 HTML sauvegardé → {FICHIER_DEBUG.name}")

    matchs = []

    # Attendre que les blocs de date soient présents
    try:
        page.wait_for_selector(".jsListMatches", timeout=20_000)
    except PWTimeout:
        print("⚠️  .jsListMatches introuvable — vérifier la page ou relancer avec --debug")
        return matchs

    blocs_date = page.query_selector_all(".jsListMatches")
    print(f"   {len(blocs_date)} bloc(s) de date trouvé(s)")

    for bloc in blocs_date:
        # Date du jour
        el_date = bloc.query_selector(".caption--grey.caption--large")
        date_txt = el_date.inner_text().strip() if el_date else ""
        date_fmt  = parser_date_fr(date_txt)

        # Sous-blocs (groupe + match(s))
        sous_blocs = bloc.query_selector_all("div")

        groupe_journee = ""
        for sb in sous_blocs:
            # Libellé groupe/journée
            el_grp = sb.query_selector(".caption--small")
            if el_grp:
                groupe_journee = el_grp.inner_text().strip()  # ex: "Groupe A - 1re j."

            # Carte de match
            cartes = sb.query_selector_all(".CalendarGeneral__match, .TeamScore--before, .TeamScore--live, .TeamScore--after")
            for carte in cartes:
                try:
                    # Équipes
                    el_home = carte.query_selector(".TeamScore__team--home .TeamScore__nameshort span")
                    el_away = carte.query_selector(".TeamScore__team--away .TeamScore__nameshort span")
                    equipeA = el_home.inner_text().strip() if el_home else "?"
                    equipeB = el_away.inner_text().strip() if el_away else "?"

                    # Heure + ID depuis le bouton/lien schedule
                    el_sched = carte.query_selector(".TeamScore__schedule, .TeamScore__data button, .TeamScore__data a")
                    heure = ""
                    match_id = ""
                    if el_sched:
                        href = el_sched.get_attribute("href") or ""
                        m_id = re.search(r'/(\d{5,})(?:[^/]*)?$', href.rstrip('/'))
                        if m_id:
                            match_id = m_id.group(1)
                        # Heure dans le texte du bouton
                        heure_txt = el_sched.inner_text().strip()
                        m_h = re.search(r'\d{1,2}h\d{2}', heure_txt)
                        if m_h:
                            heure = m_h.group(0)

                    # Timestamp au format JJ/MM/AAAA HH:MM:SS
                    ts = ""
                    if date_fmt and heure:
                        h_num = heure.replace("h", ":")
                        if len(h_num.split(":")[1]) == 2:
                            ts = f"{date_fmt} {h_num}:00"

                    # Groupe / journée
                    g_match = re.match(r"(Groupe\s+\w+)\s*[-–]\s*(.+)", groupe_journee)
                    groupe   = g_match.group(1) if g_match else groupe_journee
                    journee  = g_match.group(2).strip() if g_match else ""

                    matchs.append({
                        "id":       match_id,
                        "equipeA":  equipeA,
                        "equipeB":  equipeB,
                        "groupe":   groupe,
                        "journee":  journee,
                        "date":     date_txt,
                        "date_fmt": date_fmt,
                        "heure":    heure,
                        "timestamp": ts,
                    })

                except Exception as e:
                    print(f"  ⚠️  Erreur sur une carte : {e}")

    return matchs


# ── COMPARAISON ───────────────────────────────────────────────────────────────

def comparer(matchs_lequipe: list, calendrier_local: list):
    """Compare l'Equipe vs notre calendrier, signale les écarts."""

    # Index par ID
    idx_local   = {m["id"]: m for m in calendrier_local}
    ids_lequipe = {m["id"] for m in matchs_lequipe if m["id"]}

    print("\n" + "="*60)
    print("COMPARAISON lequipe.fr vs liste_matches.js")
    print("="*60)

    ecarts = []
    manquants_local = []
    manquants_lequipe = []

    for m in matchs_lequipe:
        mid = m["id"]
        if not mid:
            continue
        if mid not in idx_local:
            manquants_local.append(m)
            continue

        loc = idx_local[mid]
        diffs = []

        # Équipes (normalisation)
        nA_leq = normaliser(m["equipeA"])
        nB_leq = normaliser(m["equipeB"])
        nA_loc = normaliser(loc.get("equipeA", ""))
        nB_loc = normaliser(loc.get("equipeB", ""))
        if nA_leq != nA_loc:
            diffs.append(f"equipeA: lequipe='{m['equipeA']}' local='{loc.get('equipeA')}'")
        if nB_leq != nB_loc:
            diffs.append(f"equipeB: lequipe='{m['equipeB']}' local='{loc.get('equipeB')}'")

        # Timestamp
        ts_leq = m.get("timestamp", "")
        ts_loc = loc.get("timestamp", "")
        if ts_leq and ts_loc and ts_leq != ts_loc:
            diffs.append(f"timestamp: lequipe='{ts_leq}' local='{ts_loc}'")

        if diffs:
            ecarts.append({"id": mid, "diffs": diffs, "lequipe": m, "local": loc})

    # IDs dans notre local mais pas sur l'Equipe
    for m in calendrier_local:
        if (m.get("groupe", "").startswith("Groupe")
                and m["id"] not in ids_lequipe):
            manquants_lequipe.append(m)

    # Affichage
    if not ecarts and not manquants_local and not manquants_lequipe:
        print("✅ Tout est cohérent — aucun écart détecté.")
        return

    if ecarts:
        print(f"\n⚠️  {len(ecarts)} match(es) avec écart(s) :")
        for e in ecarts:
            print(f"\n  [{e['id']}] {e['lequipe']['equipeA']} vs {e['lequipe']['equipeB']}")
            for d in e["diffs"]:
                print(f"    • {d}")

    if manquants_local:
        print(f"\n🆕 {len(manquants_local)} match(es) sur lequipe.fr mais ABSENT de liste_matches.js :")
        for m in manquants_local:
            print(f"  [{m['id']}] {m['equipeA']} vs {m['equipeB']} — {m['groupe']} {m['journee']} {m['date']} {m['heure']}")

    if manquants_lequipe:
        print(f"\n❌ {len(manquants_lequipe)} match(es) dans liste_matches.js mais ABSENT de lequipe.fr :")
        for m in manquants_lequipe:
            print(f"  [{m['id']}] {m.get('equipeA','?')} vs {m.get('equipeB','?')} — {m.get('timestamp','')}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compare CDM 2026 calendar: lequipe.fr vs liste_matches.js")
    parser.add_argument("--debug",  action="store_true", help="Sauvegarde le HTML brut")
    parser.add_argument("--export", action="store_true", help="Exporte le calendrier lequipe en JSON")
    args = parser.parse_args()

    print(f"🌐 Chargement : {URL_CALENDRIER}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "Accept-Language": "fr-FR,fr;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        })
        try:
            page.goto(URL_CALENDRIER, timeout=30_000)
            page.wait_for_load_state("networkidle", timeout=25_000)
        except Exception as e:
            print(f"❌ Impossible de charger la page : {e}")
            browser.close()
            return

        matchs = scraper_calendrier(page, debug=args.debug)
        browser.close()

    print(f"📋 {len(matchs)} match(es) extraits de lequipe.fr")

    if args.export:
        FICHIER_EXPORT.write_text(
            json.dumps(matchs, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"💾 Exporté → {FICHIER_EXPORT.name}")

    calendrier_local = charger_calendrier_local()
    print(f"📁 {len(calendrier_local)} match(es) dans liste_matches.js")

    # Ne comparer que la phase de groupes (KO = équipes inconnues)
    groupes_lequipe = [m for m in matchs if "Groupe" in m.get("groupe", "")]
    groupes_local   = [m for m in calendrier_local if m.get("groupe", "").startswith("Groupe")]

    print(f"   → {len(groupes_lequipe)} matchs groupes lequipe / {len(groupes_local)} local")

    comparer(groupes_lequipe, groupes_local)


if __name__ == "__main__":
    main()
