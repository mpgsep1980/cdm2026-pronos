"""
fetch_resultats.py
==================
Récupère les résultats CDM 2026 depuis lequipe.fr et génère resultats.js

Prérequis :
    pip install playwright
    playwright install chromium

Usage :
    python fetch_resultats.py            # une seule passe
    python fetch_resultats.py --watch    # boucle toutes les 5 minutes
"""

import argparse
import json
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── CONFIGURATION ────────────────────────────────────────────────────────────

DOSSIER       = Path(__file__).parent
FICHIER_OUT   = DOSSIER / "resultats.js"
CALENDRIER_JS = DOSSIER / "liste_matches.js"

# URL de la page des directs lequipe.fr (matchs en cours + récents)
URL_CDM = "https://www.lequipe.fr/Directs"

# Intervalle en minutes entre deux passes en mode --watch
INTERVALLE_MIN = 2

# Avance (en minutes) avant le coup d'envoi pour démarrer le scraping
AVANCE_MIN = 5

# Fichier calendrier fusionné (contient les timestamps de tous les matchs)
COTES_POULES_JS = DOSSIER / "liste_matches.js"

# Fichier de debug HTML (créé avec --debug)
FICHIER_DEBUG = DOSSIER / "debug_page.html"

# Fichier d'état persistant entre deux passes
FICHIER_ETAT  = DOSSIER / "etat_scores.json"

# Mapping noms lequipe.fr normalisés → noms dans notre app
# À compléter si des écarts apparaissent au fil de la compétition
NOMS_MAPPING = {
    "etats-unis":                        "États-Unis",
    "coree du sud":                      "Corée du Sud",
    "cote d'ivoire":                     "Côte d'Ivoire",
    "ecosse":                            "Écosse",
    "egypte":                            "Égypte",
    "equateur":                          "Equateur",
    "bosnie-herzegovine":                "Bosnie-H.",
    "republique tcheque":                "Rep. Tchèque",
    "rd congo":                          "RD Congo",
    "republique democratique du congo":  "RD Congo",
    "arabie saoudite":                   "Arabie Saoudite",
    "nouvelle-zelande":                  "Nouvelle-Zélande",
    "macedoine du nord":                 "Macédoine du Nord",
    "bresil":                            "Brésil",
    "pays-bas":                          "Pays-Bas",
    "senegal":                           "Sénégal",
    "haiti":                             "Haïti",
    "algerie":                           "Algérie",
    "nigeria":                           "Nigéria",
    "cap-vert":                          "Cap-Vert",
    "curcao":                            "Curaçao",
    "curacao":                           "Curaçao",
}

# ── MAPPING TEST ─────────────────────────────────────────────────────────────
# Associe un vrai ID lequipe.fr à l'ID interne de notre calendrier CDM.
# À remplir la veille du test avec les matchs du soir.
# Format : "vrai_id_lequipe": "id_interne_calendrier"
# Laisser vide ({}) hors période de test.
ID_TEST = {
    # "673864": "686902",  # ex: Aston Villa → Mexique-AfSud (11 juin)
    # "689405": "686903",  # ex: Chelsea → Corée-RepTch (11 juin)
}

# Sélecteurs CSS lequipe.fr — page /Directs
# Candidats testés dans l'ordre ; le premier qui retourne des éléments est utilisé
SEL_CARTE_CANDIDATS = [
    "a.EventCard",
    "a.TeamScore__top",
    "a.LiveCard",
    "a.MatchCard",
    ".EventCard a",
    "a[href*='football'][href*='direct']",
    "a[href*='2026']",
]

# Filtre sport : on ne garde que les cartes Football
# (le href commence par /Football/)
FILTRE_FOOTBALL = "/Football/"
SEL_NOM       = ".TeamScore__nameshort > span:first-child, .EventCard__teamName, .LiveCard__team"
SEL_SCORE_A   = ".TeamScore__score--home"
SEL_SCORE_B   = ".TeamScore__score--away"
SEL_STATUT    = ".TeamScore__status, .EventCard__status, .LiveCard__status"

# ── UTILITAIRES ──────────────────────────────────────────────────────────────

def normaliser(nom: str) -> str:
    """Supprime accents, met en minuscules, strip."""
    nfd = unicodedata.normalize("NFD", nom or "")
    sans = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return sans.lower().strip()


def mapper_nom(nom: str) -> str:
    """Applique NOMS_MAPPING après normalisation, ou retourne le nom normalisé."""
    n = normaliser(nom)
    return NOMS_MAPPING.get(n, nom.strip())


# ── LECTURE DU CALENDRIER ────────────────────────────────────────────────────

def charger_calendrier() -> list:
    """
    Extrait CALENDRIER_CDM depuis liste_matches.js.
    Retourne une liste de dicts {id, equipeA, equipeB, groupe, date}.
    """
    texte = CALENDRIER_JS.read_text(encoding="utf-8")

    debut = texte.index("[")
    fin   = texte.index("];") + 1
    brut  = texte[debut:fin]

    # Supprime les commentaires JS single-line avant de parser
    brut = re.sub(r"//[^\n]*", "", brut)

    try:
        return json.loads(brut)
    except json.JSONDecodeError as e:
        print(f"❌ Erreur parsing liste_matches.js : {e}")
        return []


# ── SCRAPING ─────────────────────────────────────────────────────────────────

def scraper_resultats(page, debug=False) -> list:
    """
    Retourne une liste de dicts pour chaque match terminé :
        { equipeA, equipeB, sA, sB, termine: True }
    """
    resultats = []

    if debug:
        FICHIER_DEBUG.write_text(page.content(), encoding="utf-8")
        print(f"📄 HTML sauvegardé → {FICHIER_DEBUG.name}")

    # Détection automatique du sélecteur actif
    sel_carte = None
    for candidat in SEL_CARTE_CANDIDATS:
        try:
            page.wait_for_selector(candidat, timeout=5_000)
            sel_carte = candidat
            print(f"   ✅ Sélecteur détecté : {candidat}")
            break
        except PWTimeout:
            continue

    if not sel_carte:
        print("⚠️  Aucune carte de match détectée. Vérifier l'URL ou les sélecteurs.")
        if not debug:
            print("   → Relancer avec --debug pour sauvegarder le HTML et inspecter.")
        return resultats

    cartes = page.query_selector_all(sel_carte)
    print(f"   {len(cartes)} carte(s) de match trouvée(s)")

    for carte in cartes:
        try:
            href = carte.get_attribute("href") or ""

            # Extraction de l'ID depuis n'importe quel segment numérique final du href
            # ex: /Football/match-direct/.../689422  ou  /Football/Resultats/689422.html
            id_match = re.search(r'/(\d{5,})(?:[^/]*)?$', href.rstrip('/'))
            if not id_match:
                continue
            match_id = id_match.group(1)

            # Noms des équipes (pour les logs)
            noms = carte.query_selector_all(SEL_NOM)
            nomA = noms[0].inner_text().strip() if len(noms) > 0 else "?"
            nomB = noms[1].inner_text().strip() if len(noms) > 1 else "?"

            # Statut
            statut_el = carte.query_selector(SEL_STATUT)
            statut = statut_el.inner_text().strip().lower() if statut_el else ""
            # Classe CSS --ended = match terminé (plus fiable que le texte du statut)
            est_termine = (carte.query_selector(".TeamScore__score--ended") is not None
                           or "termin" in statut or "ap" in statut or "tab" in statut)
            est_live    = (not est_termine and (
                           any(c.isdigit() for c in statut)
                           or "mi-temps" in statut or "mi temps" in statut
                           or statut in ("ht", "mt", "live", "en cours")))

            # Scores
            el_sA = carte.query_selector(SEL_SCORE_A)
            el_sB = carte.query_selector(SEL_SCORE_B)
            sA_txt = el_sA.inner_text().strip() if el_sA else ""
            sB_txt = el_sB.inner_text().strip() if el_sB else ""
            a_scores = sA_txt.isdigit() and sB_txt.isdigit()

            # On capture si : scores présents (live/terminé)
            # OU si l'ID est dans notre calendrier (même sans scores — début de match)
            if not a_scores and not est_termine and not est_live:
                continue  # vraiment pas commencé, pas dans notre calendrier

            resultats.append({
                "id":      match_id,
                "equipeA": nomA,
                "equipeB": nomB,
                "sA": int(sA_txt) if a_scores else 0,
                "sB": int(sB_txt) if a_scores else 0,
                "termine": est_termine,
                "live":    est_live,  # statut vide = ni live ni terminé → géré par run_once
                "statut":  statut,
                "href":    href,
            })

        except Exception as e:
            print(f"  ⚠️  Erreur sur une carte : {e}")
            continue

    return resultats


# ── CROISEMENT AVEC NOTRE CALENDRIER ─────────────────────────────────────────

def croiser(resultats_lequipe: list, calendrier: list) -> dict:
    """
    Utilise l'ID extrait du href lequipe.fr directement.
    Ne garde que les matchs dont l'ID figure dans notre calendrier.
    Retourne { "matchId": { sA, sB, termine, live, statut } }
    """
    ids_calendrier = {m["id"] for m in calendrier}
    scores = {}
    hors_calendrier = []

    # Log tous les IDs trouvés pour diagnostic
    print(f"   🔍 IDs extraits : {[r['id'] for r in resultats_lequipe]}")

    for r in resultats_lequipe:
        mid = ID_TEST.get(r["id"], r["id"])  # substitution test si définie
        if mid in ids_calendrier:
            scores[mid] = {
                "sA":      r["sA"],
                "sB":      r["sB"],
                "termine": r["termine"],
                "live":    r["live"],
                "statut":  r["statut"],
            }
            flag = "🔴 LIVE" if r["live"] else "✅ Terminé"
            print(f"   {flag} [{mid}] {r['equipeA']} {r['sA']}-{r['sB']} {r['equipeB']} ({r['statut']})")
        else:
            hors_calendrier.append(f"[{mid}] {r['equipeA']} - {r['equipeB']}")

    if hors_calendrier:
        print(f"   ⏭  {len(hors_calendrier)} match(es) hors calendrier CDM (ignorés) :")
        for n in hors_calendrier:
            print(f"      • {n}")

    return scores


# ── ÉCRITURE DE resultats.js ──────────────────────────────────────────────────

def ecrire_resultats_js(scores: dict):
    """Génère resultats.js."""
    maintenant = datetime.now().strftime("%d/%m/%Y %H:%M")

    lignes = [
        f"// resultats.js — Généré le {maintenant} par fetch_resultats.py",
        "// NE PAS ÉDITER MANUELLEMENT",
        "",
        "// === PHASE DE GROUPES ===",
    ]

    for mid in sorted(scores.keys()):
        s = scores[mid]
        termine_js = "true" if s.get("termine") else "false"
        live_js    = "true" if s.get("live")    else "false"
        statut     = s.get("statut", "")
        statut_js  = f', statut: "{statut}"' if statut else ""
        lignes.append(
            f'OFFICIEL_2026.scores["{mid}"] = '
            f'{{ sA: {s["sA"]}, sB: {s["sB"]}, termine: {termine_js}, live: {live_js}{statut_js} }};'
        )

    lignes += [
        "",
        "// === TABLEAU 1/16e (alimenté manuellement après les groupes) ===",
        "// OFFICIEL_2026.qualifies[\"team_16_687045_A\"] = \"Mexique\";",
    ]

    FICHIER_OUT.write_text("\n".join(lignes), encoding="utf-8")
    print(f"✅ {len(scores)} résultat(s) → {FICHIER_OUT.name}")


# ── EXÉCUTION ─────────────────────────────────────────────────────────────────

def premier_match_du_jour() -> datetime | None:
    """
    Lit liste_matches.js et retourne l'heure du premier match d'aujourd'hui.
    Retourne None si aucun match aujourd'hui ou si le fichier est absent.
    """
    if not COTES_POULES_JS.exists():
        print(f"⚠️  {COTES_POULES_JS.name} introuvable.")
        return None

    texte = COTES_POULES_JS.read_text(encoding="utf-8")
    aujourd_hui = datetime.now().date()
    matchs_jour = []

    for m in re.finditer(r'"timestamp"\s*:\s*"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})"', texte):
        try:
            dt = datetime.strptime(m.group(1), "%d/%m/%Y %H:%M:%S")
            if dt.date() == aujourd_hui:
                matchs_jour.append(dt)
        except ValueError:
            pass

    if not matchs_jour:
        return None

    matchs_jour.sort()
    return matchs_jour[0]


def charger_etat() -> dict:
    """Charge l'état persistant. Si absent, bootstrap depuis resultats.js."""
    if FICHIER_ETAT.exists():
        try:
            return json.loads(FICHIER_ETAT.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Bootstrap : extraire les scores depuis resultats.js existant
    etat = {}
    if FICHIER_OUT.exists():
        texte = FICHIER_OUT.read_text(encoding="utf-8")
        for m in re.finditer(
            r'OFFICIEL_2026\.scores\["(\d+)"\]\s*=\s*\{([^}]+)\}',
            texte
        ):
            mid  = m.group(1)
            bloc = m.group(2)
            def val(key):
                r = re.search(rf'{key}\s*:\s*([^,}}]+)', bloc)
                return r.group(1).strip() if r else None
            try:
                etat[mid] = {
                    "sA":      int(val("sA") or 0),
                    "sB":      int(val("sB") or 0),
                    "termine": val("termine") == "true",
                    "live":    val("live")    == "true",
                    "statut":  (val("statut") or "").strip('"'),
                }
            except Exception:
                pass
        if etat:
            print(f"   📂 État bootstrappé depuis {FICHIER_OUT.name} ({len(etat)} match(es))")
            sauvegarder_etat(etat)
    return etat


def sauvegarder_etat(etat: dict):
    FICHIER_ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")


def run_once(debug=False):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Lancement de la mise à jour…")

    calendrier = charger_calendrier()
    if not calendrier:
        print("❌ Calendrier vide, abandon.")
        return

    # Chargement de l'état précédent
    etat_precedent = charger_etat()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"Accept-Language": "fr-FR,fr;q=0.9"})
        print(f"🌐 Chargement : {URL_CDM}")
        try:
            page.goto(URL_CDM, timeout=30_000)
            page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception as e:
            print(f"❌ Impossible de charger la page : {e}")
            browser.close()
            return

        resultats = scraper_resultats(page, debug=debug)
        browser.close()

    print(f"📋 {len(resultats)} match(es) trouvé(s) sur la page")

    # Croisement avec notre calendrier
    scores_nouveaux = croiser(resultats, calendrier)

    # Fusion avec l'état précédent
    etat_final = dict(etat_precedent)  # base = tout ce qu'on connaît déjà

    for mid, s in scores_nouveaux.items():
        prec = etat_precedent.get(mid, {})
        # Transition live → terminé : était live, statut maintenant vide/non reconnu
        if prec.get("live") and not s.get("live") and not s.get("termine"):
            s = {**s, "termine": True, "live": False, "statut": "Terminé"}
            print(f"   ✅ Terminé (statut vidé) [{mid}] {s['sA']}-{s['sB']}")
        etat_final[mid] = s

    # Transition live → terminé : un match qui était live et n'est plus visible
    for mid, s_prec in etat_precedent.items():
        if s_prec.get("live") and mid not in scores_nouveaux:
            print(f"   ✅ Terminé (disparu de /Directs) [{mid}] {s_prec['sA']}-{s_prec['sB']}")
            etat_final[mid] = {**s_prec, "termine": True, "live": False, "statut": "Terminé"}

    if not etat_final:
        print("ℹ️  Aucun résultat connu, rien à écrire.")
        return

    sauvegarder_etat(etat_final)
    ecrire_resultats_js(etat_final)


def main():
    parser = argparse.ArgumentParser(description="Fetch CDM 2026 results from lequipe.fr")
    parser.add_argument(
        "--watch", action="store_true",
        help=f"Mode continu : rafraîchit toutes les {INTERVALLE_MIN} min (Ctrl+C pour arrêter)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help=f"Sauvegarde le HTML brut dans {FICHIER_DEBUG.name} pour inspecter les sélecteurs"
    )
    parser.add_argument(
        "--at", metavar="HH:MM",
        help="Attend jusqu'à cette heure aujourd'hui avant de démarrer (ex: 20:55)"
    )
    parser.add_argument(
        "--auto", action="store_true",
        help=f"Démarre automatiquement {AVANCE_MIN} min avant le premier match du jour (lit les timestamps de {COTES_POULES_JS.name})"
    )
    parser.add_argument(
        "--test-in", metavar="MINUTES", type=int, default=None,
        help="Test : démarre le watch dans N minutes (sans modifier les données)"
    )
    args = parser.parse_args()

    # --test-in : démarrage dans N minutes (test sans modifier les données)
    if args.test_in is not None:
        attente = args.test_in * 60
        heure_demarrage = (datetime.now() + __import__('datetime').timedelta(seconds=attente)).strftime('%H:%M')
        print(f"[TEST] Démarrage dans {args.test_in} min (à {heure_demarrage}) — aucune donnée modifiée")
        print("   (Ctrl+C pour annuler)")
        try:
            time.sleep(attente)
        except KeyboardInterrupt:
            print("\n Annulé.")
            return
        print(f"[TEST] Démarrage du watch !")

    # --auto : calcul depuis les timestamps du fichier de cotes
    elif args.auto:
        premier = premier_match_du_jour()
        if not premier:
            print("ℹ️  Aucun match trouvé aujourd'hui dans les cotes — démarrage immédiat.")
        else:
            cible = premier - __import__('datetime').timedelta(minutes=AVANCE_MIN)
            maintenant = datetime.now()
            attente = (cible - maintenant).total_seconds()
            if attente > 0:
                print(f"⏰ Premier match à {premier.strftime('%H:%M')} — démarrage à {cible.strftime('%H:%M')} ({int(attente // 60)} min {int(attente % 60)} sec)")
                print("   (Ctrl+C pour annuler)")
                try:
                    time.sleep(attente)
                except KeyboardInterrupt:
                    print("\n👋 Annulé.")
                    return
                print(f"🚀 {cible.strftime('%H:%M')} — démarrage du watch !")
            else:
                print(f"⚡ Premier match à {premier.strftime('%H:%M')}, heure déjà passée — démarrage immédiat.")

    # --at : attente manuelle
    elif args.at:
        try:
            h, m = map(int, args.at.split(":"))
        except ValueError:
            print(f"❌ Format invalide pour --at : utilisez HH:MM (ex: 20:55)")
            return
        maintenant = datetime.now()
        cible = maintenant.replace(hour=h, minute=m, second=0, microsecond=0)
        if cible <= maintenant:
            cible = cible.replace(day=maintenant.day + 1)  # demain si l'heure est déjà passée
        attente = (cible - maintenant).total_seconds()
        print(f"⏰ Démarrage programmé à {args.at} — attente de {int(attente // 60)} min {int(attente % 60)} sec…")
        print("   (Ctrl+C pour annuler)")
        try:
            time.sleep(attente)
        except KeyboardInterrupt:
            print("\n👋 Annulé.")
            return
        print(f"🚀 {args.at} — démarrage du watch !")

    if args.watch or args.at or args.auto or args.test_in is not None:
        print(f"⏱️  Mode watch actif — intervalle : {INTERVALLE_MIN} min")
        while True:
            try:
                run_once(debug=args.debug)
            except KeyboardInterrupt:
                print("\n👋 Arrêt demandé.")
                break
            except Exception as e:
                print(f"❌ Erreur inattendue : {e}")
            print(f"💤 Prochain refresh dans {INTERVALLE_MIN} min…")
            try:
                time.sleep(INTERVALLE_MIN * 60)
            except KeyboardInterrupt:
                print("\n👋 Arrêt demandé.")
                break
    else:
        run_once(debug=args.debug)


if __name__ == "__main__":
    main()
