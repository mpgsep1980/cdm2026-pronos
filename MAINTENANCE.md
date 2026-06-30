# Maintenance CDM 2026 — Guide d'urgence

> **Usage mobile** : ouvre ce fichier sur GitHub, copie-colle son contenu dans une nouvelle conversation Claude (claude.ai), décris ton problème. Claude aura tout le contexte nécessaire.

---

## Architecture en deux mots

L'app est un fichier HTML statique hébergé sur **GitHub Pages** (`mpgsep1980.github.io/cdm2026-pronos/`).

Les scores sont dans **`resultats.js`** : un fichier JS régénéré automatiquement toutes les 5 minutes par un robot GitHub (GitHub Actions) qui scrape **lequipe.fr**.

```
GitHub Actions (toutes les 5 min)
  └─ fetch_resultats.py
       ├─ scrape lequipe.fr/Directs        → scores live + temps de jeu
       ├─ scrape lequipe.fr/calendrier     → scores finaux historiques
       └─ génère resultats.js → git push → GitHub Pages se redéploie
```

Aucun serveur, aucun backend. Tout repose sur GitHub.

---

## Fichiers importants

| Fichier | Rôle |
|---|---|
| `index.html` | Toute l'app (pronos, classement, admin) |
| `resultats.js` | Scores officiels (généré automatiquement, **ne pas éditer à la main sauf urgence**) |
| `liste_matches.js` | Calendrier CDM avec IDs internes (édité manuellement) |
| `fetch_resultats.py` | Script de scraping (lancé par GitHub Actions et en local) |
| `requirements.txt` | Version Playwright épinglée (`playwright==1.61.0`) |
| `.github/workflows/update_resultats.yml` | Configuration GitHub Actions |
| `etat_scores.json` | État persistant local entre deux passes (gitignored — absent en CI) |

---

## Vérifier si GitHub Actions tourne

→ `github.com/mpgsep1980/cdm2026-pronos/actions`

- ✅ vert = tout va bien
- ❌ rouge = bug, cliquer sur le run pour voir les logs

**Forcer un run manuel** : onglet Actions → "Mise à jour résultats CDM 2026" → bouton "Run workflow" (en haut à droite de la liste).

---

## Problèmes courants et solutions

### 1. Les scores ne se mettent plus à jour

**Symptôme** : `resultats.js` date d'il y a plus de 10 min pendant un match.

**Diagnostic** : aller dans Actions, regarder quel step échoue.

**Causes fréquentes** :

| Step qui échoue | Cause | Fix |
|---|---|---|
| `Install playwright` | Dépendance cassée | Voir section "Mettre à jour Playwright" |
| `Install Chromium` | Dépendances système manquantes | Le `--with-deps` devrait suffire, sinon ouvrir un ticket |
| `Fetch et mise à jour résultats` | Sélecteurs CSS L'Équipe changés | Voir section "Sélecteurs cassés" |
| `git push` / `Configure git` | Problème de permissions | Vérifier que `permissions: contents: write` est dans le workflow |

---

### 2. Un score est faux dans l'app

**Fix immédiat depuis GitHub web** (sans PC) :

1. Aller sur `github.com/mpgsep1980/cdm2026-pronos/blob/main/resultats.js`
2. Cliquer le crayon ✏️ (Edit this file)
3. Trouver la ligne du match par son ID (ex: `687049`)
4. Corriger `sA` et `sB`, mettre `termine: true, live: false`
5. Commit directement sur `main`

**Fix permanent** (pour que le scraper ne réécrase pas) : éditer `fetch_resultats.py`, ajouter dans `CORRECTIONS_MANUELLES` :
```python
CORRECTIONS_MANUELLES = {
    "686972": {"sA": 0, "sB": 2, "termine": True, "live": False, "statut": "Terminé"},
    "686973": {"sA": 2, "sB": 1, "termine": True, "live": False, "statut": "Terminé"},
    # Ajouter ici :
    "XXXXXX": {"sA": 0, "sB": 1, "termine": True, "live": False, "statut": "Terminé"},
}
```

L'ID du match se trouve dans `liste_matches.js` (champ `"id"`).

---

### 3. Match avec vainqueur aux tirs au but (TAB)

Dans `resultats.js`, le match doit avoir :
```javascript
OFFICIEL_2026.scores["687047"] = { sA: 1, sB: 1, termine: true, live: false, statut: "t.a.b.", vainqueur: "B" };
```
- `statut: "t.a.b."` (obligatoire pour activer le barème TAB)
- `vainqueur: "A"` = équipe domicile gagne, `vainqueur: "B"` = équipe extérieure gagne

Le scraper détecte normalement le vainqueur TAB automatiquement depuis L'Équipe. Si ce n'est pas le cas, corriger manuellement dans `resultats.js` (édition web GitHub) **et** dans `CORRECTIONS_MANUELLES`.

---

### 4. Mettre à jour Playwright après une casse

La version est épinglée dans `requirements.txt` (`playwright==1.61.0`). Si une mise à jour est nécessaire :

1. Aller sur `github.com/mpgsep1980/cdm2026-pronos/blob/main/requirements.txt`
2. Crayon ✏️ → changer la version → commit
3. Aller sur `pypi.org/project/playwright/` pour voir la dernière version stable

---

### 5. Sélecteurs CSS cassés (L'Équipe a changé son HTML)

Les sélecteurs sont dans `fetch_resultats.py` vers la ligne 111 :
```python
SEL_CARTE_CANDIDATS = ["a.EventCard", "a.TeamScore__top", ...]
SEL_NOM   = ".TeamScore__nameshort > span:first-child, ..."
SEL_SCORE_A = ".TeamScore__score--home"
SEL_SCORE_B = ".TeamScore__score--away"
SEL_STATUT  = ".TeamScore__status, ..."
```

Ce type de fix nécessite d'inspecter le HTML de L'Équipe (DevTools) et de mettre à jour les sélecteurs. Difficile à faire sans PC — contacter quelqu'un avec accès à l'environnement ou attendre le retour.

---

## Barème des points (phase KO)

| Situation | Points |
|---|---|
| Bon résultat (1/N/2) | base × 1 |
| Score exact OU bon vainqueur TAB | base × 2 |
| Score exact ET bon vainqueur TAB | base × 3 (💎) |

Les points de base (domicile / nul / extérieur) sont définis dans `liste_matches.js` → champ `details`.

---

## Liens utiles

- App : `mpgsep1980.github.io/cdm2026-pronos/`
- Repo : `github.com/mpgsep1980/cdm2026-pronos`
- Actions : `github.com/mpgsep1980/cdm2026-pronos/actions`
- `resultats.js` : `github.com/mpgsep1980/cdm2026-pronos/blob/main/resultats.js`
- `liste_matches.js` : `github.com/mpgsep1980/cdm2026-pronos/blob/main/liste_matches.js`
- `fetch_resultats.py` : `github.com/mpgsep1980/cdm2026-pronos/blob/main/fetch_resultats.py`
