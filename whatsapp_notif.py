"""
whatsapp_notif.py
=================
Notifications WhatsApp via Green API (https://green-api.com).

Setup :
    1. Créer un compte sur app.green-api.com (tier gratuit : 200 msg/mois)
    2. Créer une instance → scanner le QR code avec le téléphone du groupe
    3. Récupérer idInstance et apiTokenInstance dans le dashboard
    4. Lancer : python whatsapp_notif.py --list-groups  → trouver le chatId du groupe
    5. Remplir green_api_config.json

Prérequis :
    pip install requests
"""

import argparse
import json
import requests
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "green_api_config.json"
CONFIG_EXEMPLE = {
    "idInstance":   "XXXXXXXXXXXXXXX",
    "apiToken":     "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
    "chatId":       "XXXXXXXXXXX-XXXXXXXXXX@g.us",
    "actif":        True
}

BASE_URL = "https://api.green-api.com"


# ── CONFIG ────────────────────────────────────────────────────────────────────

def charger_config() -> dict:
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(CONFIG_EXEMPLE, indent=2), encoding="utf-8")
        raise FileNotFoundError(
            f"❌ {CONFIG_FILE.name} créé — renseignez idInstance, apiToken et chatId "
            "avant de relancer."
        )
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


# ── ENVOI ─────────────────────────────────────────────────────────────────────

def envoyer_message(texte: str) -> bool:
    """Envoie un message dans le groupe WhatsApp. Retourne True si succès."""
    try:
        cfg = charger_config()
        if not cfg.get("actif", True):
            return True  # désactivé sans erreur
        url = f"{BASE_URL}/waInstance{cfg['idInstance']}/sendMessage/{cfg['apiToken']}"
        resp = requests.post(url, json={"chatId": cfg["chatId"], "message": texte}, timeout=15)
        if resp.status_code == 200:
            print(f"   📲 WhatsApp envoyé : {texte[:60]}…" if len(texte) > 60 else f"   📲 WhatsApp envoyé : {texte}")
            return True
        print(f"   ⚠️  Green API HTTP {resp.status_code} : {resp.text[:200]}")
    except FileNotFoundError as e:
        print(e)
    except Exception as e:
        print(f"   ⚠️  Erreur WhatsApp : {e}")
    return False


# ── MESSAGES ──────────────────────────────────────────────────────────────────

def msg_but(equipeA: str, equipeB: str, sA: int, sB: int, statut: str = "") -> str:
    heure = f" ({statut})" if statut else ""
    if sA > sB:
        scoreur = equipeA.upper()
    elif sB > sA:
        scoreur = equipeB.upper()
    else:
        scoreur = f"{equipeA} & {equipeB}".upper()
    return f"⚽ BUT pour {scoreur} !\n{equipeA} {sA}—{sB} {equipeB}{heure}"


def msg_fin(equipeA: str, equipeB: str, sA: int, sB: int) -> str:
    if sA > sB:
        resultat = f"Victoire {equipeA} !"
    elif sB > sA:
        resultat = f"Victoire {equipeB} !"
    else:
        resultat = "Match nul !"
    return f"🏁 FT : {equipeA} {sA}—{sB} {equipeB}\n{resultat}"


def msg_classement(classement: list[dict]) -> str:
    """
    classement = [{"nom": "Sep", "pts": 234}, ...]  trié par pts desc
    Retourne les 3 premiers (podium) + le dernier (lanterne rouge).
    """
    if not classement:
        return ""
    medailles = ["🥇", "🥈", "🥉"]
    lignes = ["📊 Classement :"]
    for i, joueur in enumerate(classement[:3]):
        lignes.append(f"  {medailles[i]} {joueur['nom']} — {joueur['pts']} pts")
    if len(classement) > 3:
        dernier = classement[-1]
        lignes.append(f"  🔴 {dernier['nom']} — {dernier['pts']} pts (lanterne rouge)")
    return "\n".join(lignes)


def msg_changement_podium(avant: list[dict], apres: list[dict]) -> str:
    """Génère une phrase pour chaque changement de podium."""
    phrases = []
    noms_avant  = [j["nom"] for j in avant]
    noms_apres  = [j["nom"] for j in apres]
    positions   = ["podium (1er)", "podium (2e)", "podium (3e)"]

    for i, pos in enumerate(positions):
        a = noms_avant[i] if i < len(noms_avant) else None
        b = noms_apres[i] if i < len(noms_apres) else None
        if a and b and a != b:
            phrases.append(f"  📈 {b} entre sur le {pos} !")
            phrases.append(f"  📉 {a} quitte le {pos}.")

    # Lanterne rouge
    lr_avant = noms_avant[-1] if noms_avant else None
    lr_apres = noms_apres[-1] if noms_apres else None
    if lr_avant and lr_apres and lr_avant != lr_apres:
        phrases.append(f"  🔴 {lr_apres} attrape la lanterne rouge.")
        phrases.append(f"  😮‍💨 {lr_avant} échappe à la lanterne rouge.")

    return "\n".join(phrases)


# ── DÉTECTION ET NOTIFICATION ─────────────────────────────────────────────────

def detecter_et_notifier(etat_precedent: dict, etat_final: dict,
                          calendrier: list, classement_fn=None):
    """
    Compare etat_precedent et etat_final pour détecter :
      - Un ou des buts marqués (score change pendant un live)
      - Une fin de match

    classement_fn : fonction optionnelle () → list[dict] qui retourne le classement actuel.
    """
    for mid, s in etat_final.items():
        prec   = etat_precedent.get(mid, {})
        match  = next((m for m in calendrier if str(m.get("id")) == str(mid)), {})
        eqA    = match.get("equipeA", "Équipe A")
        eqB    = match.get("equipeB", "Équipe B")

        sA_new, sB_new = s.get("sA", 0), s.get("sB", 0)
        sA_old, sB_old = prec.get("sA", 0), prec.get("sB", 0)

        # BUT(S) détecté(s) pendant un live
        if s.get("live") and (sA_new + sB_new) > (sA_old + sB_old):
            statut = s.get("statut", "")
            envoyer_message(msg_but(eqA, eqB, sA_new, sB_new, statut))

        # FIN DE MATCH
        if s.get("termine") and not prec.get("termine"):
            texte = msg_fin(eqA, eqB, sA_new, sB_new)

            if classement_fn:
                try:
                    cl_avant = classement_fn(avant=True)
                    cl_apres = classement_fn(avant=False)
                    changements = msg_changement_podium(cl_avant, cl_apres)
                    classement  = msg_classement(cl_apres)
                    if changements:
                        texte += f"\n\n{changements}"
                    texte += f"\n\n{classement}"
                except Exception as e:
                    print(f"   ⚠️  Classement non disponible : {e}")

            envoyer_message(texte)


# ── UTILITAIRE : lister les groupes ──────────────────────────────────────────

def lister_groupes():
    """Affiche les groupes WhatsApp disponibles pour trouver le chatId."""
    try:
        cfg = charger_config()
        url = f"{BASE_URL}/waInstance{cfg['idInstance']}/getChats/{cfg['apiToken']}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        chats   = resp.json()
        groupes = [c for c in chats if str(c.get("id", "")).endswith("@g.us")]
        print(f"\n📱 {len(groupes)} groupe(s) WhatsApp :")
        for g in groupes:
            print(f"   {g['id']}  —  {g.get('name', '(sans nom)')}")
        print(f"\n→ Copiez le chatId dans {CONFIG_FILE.name}\n")
    except Exception as e:
        print(f"❌ Erreur : {e}")


# ── TEST RAPIDE ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Notifications WhatsApp — CDM 2026")
    parser.add_argument("--list-groups", action="store_true", help="Liste les groupes WhatsApp disponibles")
    parser.add_argument("--test",        action="store_true", help="Envoie un message de test dans le groupe")
    args = parser.parse_args()

    if args.list_groups:
        lister_groupes()
    elif args.test:
        ok = envoyer_message("🧪 Test CDM 2026 — bot opérationnel !")
        print("✅ Envoyé" if ok else "❌ Échec")
    else:
        parser.print_help()
