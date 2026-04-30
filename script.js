// Les groupes et les équipes
const FIFA_GROUPS = {
    A: ["Mexique", "Afrique du Sud", "Corée du Sud", "DEN/MKD/CZE/IRL"],
    // ... jusqu'à L
};

// Les cotes (chargées depuis ton JSON)
let cotesData = {}; 

// Le mapping FIFA pour les 16èmes (qui affronte qui selon les meilleurs 3èmes)
const BRACKET_MAPPING = {
    // Ex: "ABCD" -> { "1A": "3C", "1B": "3D", ... }
};

/** * Calcule le classement d'un groupe selon les critères (a) à (h) 
 */
function calculateGroupStandings(groupMatches) {
    // 1. Calculer points, BP, BC, Diff pour chaque équipe
    // 2. Gérer les égalités avec une sous-boucle (mini-championnat)
    // 3. Retourner le tableau trié [1er, 2e, 3e, 4e]
}

/** * Compare les 12 troisièmes et retourne les 8 meilleurs 
 */
function getBestThirdPlaces(allGroupsResults) {
    // Logique de tri e, f, g, h
}

/** * Calcule les points gagnés par un utilisateur sur un match
 */
function calculateUserPoints(userProno, realResult, cote) {
    // Si score exact -> cote * 10
    // Si bon vainqueur -> cote * 5
    // Sinon -> 0
}

/** * Génère le tableau de la phase finale d'un utilisateur 
 * basé sur ses pronostics de poules
 */
function generateUserBracket(userGroupPronos) {
    // 1. Simuler les classements des groupes de l'utilisateur
    // 2. Extraire ses 1er, 2e et meilleurs 3e
    // 3. Remplir ses 16èmes de finale
}

let currentState = {
    currentUser: null,       // L'ami connecté
    realScores: {},          // Les scores réels saisis par l'admin ou via API
    allUsersScores: []       // Le classement général dynamique
};

function renderLeaderboard() { /* Affiche le classement des amis */ }
function renderGroupTable(groupId) { /* Affiche le tableau d'une poule */ }
function renderBracket() { /* Dessine le tableau final (arbre) */ }

document.addEventListener('DOMContentLoaded', () => {
    // 1. Charger les cotes
    // 2. Vérifier si l'utilisateur est connecté
    // 3. Si Admin -> Activer le panneau de saisie des scores
    // 4. Lancer le calcul global
});