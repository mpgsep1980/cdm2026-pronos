"""
fetch_mpp.py
============
Récupère les % de pronos de la foule depuis mpp.football/championship/8 (CDM 2026)
et met à jour les cotes dans liste_matches.js.

Conversion : cote_pseudo = round(1 / (pct / 100), 2)
  → 83% dom → 1,20 | 10% nul → 10,00 | 7% ext → 14,29

Usage :
    python fetch_mpp.py              # Mise à jour normale
    python fetch_mpp.py --login      # Force reconnexion (token expiré)
    python fetch_mpp.py --dry-run    # Affiche sans écrire
    python fetch_mpp.py --dump       # Sauvegarde la réponse API brute dans mpp_raw.json
"""

import sys
import json
import re
import time
import argparse
import requests
from pathlib import Path
from unicodedata import normalize, category

sys.stdout.reconfigure(encoding="utf-8")

DOSSIER   = Path(__file__).parent
TOKEN_FILE = DOSSIER / "mpp_token.txt"
LISTE_JS  = DOSSIER / "liste_matches.js"

MPP_API  = "https://api.mpp.football"
CDM_ID   = 8  # championshipsIds.CDM = 8

# ── Authentification ──────────────────────────────────────────────────────────

def lire_credentials() -> tuple[str, str]:
    cred_file = DOSSIER / "mpp_credentials.json"
    if cred_file.exists():
        data = json.loads(cred_file.read_text(encoding="utf-8"))
        return data["email"], data["password"]
    raise FileNotFoundError(
        "mpp_credentials.json introuvable. "
        "Créez-le avec {'email': '...', 'password': '...'}"
    )


def ouvrir_browser_et_capturer_token() -> str:
    """Lance Chromium, se connecte à MPP avec les credentials, capture le Bearer token."""
    from playwright.sync_api import sync_playwright

    email, password = lire_credentials()
    capturé = {}

    def on_request(req):
        auth = req.headers.get("authorization", "")
        if "Bearer " in auth and "api.mpp.football" in req.url:
            capturé["token"] = auth.replace("Bearer ", "").strip()

    print("Ouverture du navigateur pour connexion MPP…")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=200)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.on("request", on_request)

        # 1. Aller sur MPP
        page.goto("https://mpp.football", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # 1b. Fermer la bannière cookies si présente
        for cookies_sel in ["text=Refuser", "button:has-text('Refuser')", "text=Reject"]:
            try:
                btn = page.locator(cookies_sel).first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    print("  Bannière cookies fermée")
                    page.wait_for_timeout(1000)
                    break
            except Exception:
                pass

        # 2. Chercher et cliquer le bouton de connexion
        for sel in ["text=Se connecter", "text=Connexion", "text=Login",
                    "[data-testid='login-button']", "button:has-text('Connexion')"]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    print(f"  Bouton trouvé : {sel}")
                    break
            except Exception:
                pass

        page.wait_for_timeout(2000)

        # 3. Remplir email puis Enter (Auth0 sépare parfois email / mdp en deux étapes)
        email_inp = None
        for email_sel in ["#username", "input[type='email']", "input[name='email']",
                          "input[placeholder*='mail' i]"]:
            try:
                loc = page.locator(email_sel).first
                if loc.is_visible(timeout=3000):
                    email_inp = loc
                    break
            except Exception:
                pass

        if email_inp:
            email_inp.fill(email)
            print(f"  Email saisi")
            page.wait_for_timeout(500)
            email_inp.press("Enter")
            page.wait_for_timeout(2000)  # attendre que l'étape password apparaisse

        # 4. Remplir mot de passe (peut être sur la même page ou une nouvelle page Auth0)
        pw_inp = None
        for pw_sel in ["#password", "input[type='password']", "input[name='password']"]:
            try:
                loc = page.locator(pw_sel).first
                if loc.is_visible(timeout=5000):
                    pw_inp = loc
                    break
            except Exception:
                pass

        if pw_inp:
            pw_inp.fill(password)
            print("  Mot de passe saisi")
            page.wait_for_timeout(500)
            pw_inp.press("Enter")
            print("  Formulaire soumis")
            page.wait_for_timeout(4000)  # attendre le redirect vers MPP
        else:
            print("  AVERTISSEMENT : champ mot de passe non trouvé")

        # 5. Attendre le redirect + les appels API (jusqu'à 60s)
        print("  Attente du token API…")
        page.wait_for_timeout(3000)

        # Naviguer vers la page CDM pour déclencher les appels API
        if "token" not in capturé:
            page.goto(f"https://mpp.football/championship/{CDM_ID}",
                      wait_until="networkidle", timeout=30000)

        for _ in range(120):  # 60 secondes
            if "token" in capturé:
                break
            time.sleep(0.5)

        browser.close()

    if "token" not in capturé:
        raise RuntimeError(
            "Token non capturé. Vérifiez vos identifiants dans mpp_credentials.json."
        )

    print("  Token capturé.")
    return capturé["token"]


def charger_token(force_login: bool = False) -> str:
    if not force_login and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        # Vérifier validité
        r = requests.get(f"{MPP_API}/championship-calendar/{CDM_ID}",
                         headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if r.status_code == 200:
            return token
        print("Token expiré, reconnexion automatique…")

    token = ouvrir_browser_et_capturer_token()
    TOKEN_FILE.write_text(token, encoding="utf-8")
    print(f"  Token sauvegardé dans {TOKEN_FILE.name}")
    return token


# ── Requêtes API MPP ──────────────────────────────────────────────────────────

def fetch_calendrier(token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    r = requests.get(f"{MPP_API}/championship-calendar/{CDM_ID}", headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_summaries(token: str, match_ids: list) -> dict:
    """Récupère les résumés de matchs (pronos de la foule) via l'endpoint batch."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json",
               "Content-Type": "application/json"}
    # Batch par tranches de 50
    resultats = {}
    for i in range(0, len(match_ids), 50):
        batch = match_ids[i:i + 50]
        r = requests.post(f"{MPP_API}/championship-match/summaries",
                          json={"matchesIds": batch}, headers=headers, timeout=30)
        r.raise_for_status()
        resultats.update(r.json())
    return resultats


# ── Extraction des pourcentages ───────────────────────────────────────────────

def extraire_pronos(summary: dict) -> dict | None:
    """
    Extrait les points MPP depuis un résumé.
    - quotations.{home,draw,away} = points attribués si le pronostic est correct
    - stats.bets.{home,draw,away}  = % de joueurs ayant choisi chaque issue (référence)
    """
    q = summary.get("quotations") or {}
    pts_h = q.get("home")
    pts_n = q.get("draw")
    pts_a = q.get("away")
    if pts_h is None:
        return None

    bets = (summary.get("stats") or {}).get("bets") or {}
    return {
        "pts_home": pts_h,
        "pts_draw": pts_n,
        "pts_away": pts_a,
        "pct_home": round((bets.get("home") or 0) * 100),
        "pct_draw": round((bets.get("draw") or 0) * 100),
        "pct_away": round((bets.get("away") or 0) * 100),
    }


# ── Utilitaires ───────────────────────────────────────────────────────────────

def ts_mpp_vers_local(date_utc: str) -> str | None:
    """
    Convertit '2026-06-11T19:00:00.000Z' en '11/06/2026 21:00:00' (Paris CEST = UTC+2).
    En hiver (CET = UTC+1) : novembre–mars.
    """
    try:
        from datetime import datetime, timezone, timedelta
        dt = datetime.fromisoformat(date_utc.replace("Z", "+00:00"))
        # CDM = juin/juillet → CEST = UTC+2
        mois = dt.month
        offset = timedelta(hours=1 if mois in (11, 12, 1, 2, 3) else 2)
        dt_paris = dt.astimezone(timezone(offset))
        return dt_paris.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return None


def ts_vers_minutes(ts: str) -> int | None:
    """Convertit 'DD/MM/YYYY HH:MM:SS' en minutes depuis epoch (approximatif)."""
    try:
        from datetime import datetime
        dt = datetime.strptime(ts[:16], "%d/%m/%Y %H:%M")
        return int(dt.timestamp() // 60)
    except Exception:
        return None


def trouver_match_local_par_date(ts_paris: str, calendrier: list,
                                  deja_assigne: set) -> dict | None:
    """
    Cherche le match local le plus proche temporellement (tolérance ±90 min).
    Ignore les matchs déjà assignés à un autre match MPP.
    """
    if not ts_paris:
        return None
    ref_min = ts_vers_minutes(ts_paris)
    if ref_min is None:
        return None

    meilleur, ecart_min = None, 91  # seuil de 90 minutes

    for m in calendrier:
        mid = m.get("id")
        if mid in deja_assigne:
            continue
        ts_local = m.get("timestamp", "")
        if not ts_local:
            continue
        loc_min = ts_vers_minutes(ts_local)
        if loc_min is None:
            continue
        ecart = abs(ref_min - loc_min)
        if ecart < ecart_min:
            ecart_min = ecart
            meilleur = m

    return meilleur




# ── Lecture de liste_matches.js ───────────────────────────────────────────────

def lire_calendrier_local() -> list:
    """Parse CALENDRIER_CDM depuis liste_matches.js."""
    texte = LISTE_JS.read_text(encoding="utf-8")
    m = re.search(r'\bCALENDRIER_CDM\s*=\s*\[', texte)
    if not m:
        raise ValueError("CALENDRIER_CDM introuvable dans liste_matches.js")
    debut = m.end() - 1
    depth, i = 0, debut
    while i < len(texte):
        if texte[i] == "[":   depth += 1
        elif texte[i] == "]":
            depth -= 1
            if depth == 0:
                brut = texte[debut:i + 1]
                break
        i += 1
    else:
        raise ValueError("Tableau non fermé")

    brut = re.sub(r"//[^\n]*", "", brut)
    brut = re.sub(r",\s*([}\]])", r"\1", brut)
    brut = re.sub(r"\bNaN\b", "null", brut)
    return json.loads(brut)


# ── Écriture de liste_matches.js ──────────────────────────────────────────────

def ecrire_liste_matches(calendrier: list):
    groupes_ko = {"1/16 de finale", "1/8 de finale", "1/4 de finale",
                  "Demi-finale", "Petite Finale", "Finale"}
    lignes = [
        "// liste_matches.js — Calendrier CDM 2026 + cotes intégrées",
        "// Généré par fetch_mpp.py — NE PAS ÉDITER MANUELLEMENT",
        "",
        "const CALENDRIER_CDM = [",
    ]
    for i, m in enumerate(calendrier):
        virgule = "," if i < len(calendrier) - 1 else ""
        lignes.append(f"  {json.dumps(m, ensure_ascii=False)}{virgule}")

    lignes += [
        "];",
        "",
        "// ── Shims backward-compat ─────────────────────────────────────────────",
        "const COTES_MATCHS = CALENDRIER_CDM.filter(",
        "    m => m.groupe && !['1/16 de finale','1/8 de finale','1/4 de finale',",
        "         'Demi-finale','Petite Finale','Finale'].includes(m.groupe) && m.details",
        ");",
        "const COTES_MATCHS_KO = CALENDRIER_CDM.filter(",
        "    m => m.groupe && ['1/16 de finale','1/8 de finale','1/4 de finale',",
        "         'Demi-finale','Petite Finale','Finale'].includes(m.groupe) && m.details",
        ");",
        "",
        "// ── Source de vérité officielle ────────────────────────────────────────",
        "const OFFICIEL_2026 = {",
        "    scores:   {},",
        "    qualifies: {},",
        "    aliases:   {}",
        "};",
        "",
        "CALENDRIER_CDM.forEach(match => {",
        "    if (!OFFICIEL_2026.scores[match.id]) OFFICIEL_2026.scores[match.id] = null;",
        "});",
    ]
    LISTE_JS.write_text("\n".join(lignes), encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--login",   action="store_true", help="Force reconnexion navigateur")
    parser.add_argument("--dry-run", action="store_true", help="Affiche sans écrire")
    parser.add_argument("--dump",    action="store_true", help="Sauvegarde réponse API brute")
    args = parser.parse_args()

    calendrier = lire_calendrier_local()
    print(f"Calendrier local : {len(calendrier)} matchs")

    token = charger_token(force_login=args.login)

    # 1. Récupérer la structure du calendrier MPP (gameWeeks + IDs)
    print("Récupération du calendrier MPP…")
    data = fetch_calendrier(token)

    if args.dump:
        dump_file = DOSSIER / "mpp_raw.json"
        dump_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Réponse brute sauvegardée dans {dump_file.name}")

    # Extraire tous les matchesIds depuis gameWeeks (dict ou list)
    all_ids = []
    gw_data = data.get("gameWeeks", {})
    if isinstance(gw_data, dict):
        for gw in gw_data.values():
            all_ids.extend(gw.get("matchesIds", []))
    elif isinstance(gw_data, list):
        for gw in gw_data:
            all_ids.extend(gw.get("matchesIds", []))

    if not all_ids:
        print("Aucun match ID trouvé dans le calendrier MPP.")
        return

    all_ids = list(dict.fromkeys(all_ids))  # dédoublonner, conserver l'ordre
    print(f"  {len(all_ids)} matchs MPP trouvés")

    # 2. Récupérer les résumés (pronos de la foule) en batch
    print("Récupération des pronos de la foule…")
    summaries = fetch_summaries(token, all_ids)
    print(f"  {len(summaries)} résumés reçus")

    # 3. Fusion avec le calendrier local
    nb_mis_a_jour = 0
    nb_sans_prono = 0
    non_trouves   = []
    deja_assigne  = set()

    for match_id, summary in summaries.items():
        if not summary or not isinstance(summary, dict):
            nb_sans_prono += 1
            continue
        pronos = extraire_pronos(summary)
        if pronos is None:
            nb_sans_prono += 1
            continue

        # Matcher par date UTC → Paris (tolérance ±90 min, sans doublons)
        ts_paris = ts_mpp_vers_local(summary.get("date", ""))
        local_m  = trouver_match_local_par_date(ts_paris, calendrier, deja_assigne)

        if local_m is None:
            non_trouves.append(f"{ts_paris} (id={match_id})")
            continue
        deja_assigne.add(local_m.get("id"))

        pts_h = str(pronos["pts_home"])
        pts_n = str(pronos["pts_draw"]) if pronos["pts_draw"] is not None else "0"
        pts_a = str(pronos["pts_away"])

        ea = local_m.get("equipeA") or "?"
        eb = local_m.get("equipeB") or "?"
        print(f"  {ea:20s} vs {eb:20s} : "
              f"{pts_h:>4}/{pts_n:>4}/{pts_a:>4} pts "
              f"({pronos['pct_home']:3d}%/{pronos['pct_draw']:3d}%/{pronos['pct_away']:3d}%)")

        if not args.dry_run:
            if "details" not in local_m or not local_m["details"]:
                local_m["details"] = {
                    "domicile":  {"label": local_m.get("equipeA", "?"), "value": pts_h},
                    "nul":       {"label": "N",                          "value": pts_n},
                    "exterieur": {"label": local_m.get("equipeB", "?"), "value": pts_a},
                }
            else:
                local_m["details"]["domicile"]["value"]  = pts_h
                local_m["details"]["nul"]["value"]       = pts_n
                local_m["details"]["exterieur"]["value"] = pts_a
            local_m["mpp"] = {
                "home": pronos["pct_home"],
                "draw": pronos["pct_draw"],
                "away": pronos["pct_away"],
                "total": (pronos["pts_home"] or 0) + (pronos["pts_draw"] or 0) + (pronos["pts_away"] or 0),
            }

        nb_mis_a_jour += 1

    print(f"\n{nb_mis_a_jour} matchs mis a jour")
    if nb_sans_prono:
        print(f"{nb_sans_prono} matchs sans pronos de foule (pas encore ouverts).")
    if non_trouves:
        print(f"Matchs non trouvés dans le calendrier local ({len(non_trouves)}) :")
        for x in non_trouves:
            print(f"  {x}")

    if not args.dry_run and nb_mis_a_jour > 0:
        ecrire_liste_matches(calendrier)
        print(f"liste_matches.js mis a jour ({len(calendrier)} matchs)")


if __name__ == "__main__":
    main()
