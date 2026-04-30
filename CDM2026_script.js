// Les groupes et les équipes
const FIFA_GROUPS = {
    A: ["Mexique", "Afrique du Sud", "Coree du Sud", "DEN/MKD/CZE/IRL"],
    B: ["Canada", "ITA/NIR/WAL/BIH", "Qatar", "Suisse"],
    C: ["Bresil", "Maroc", "Haïti", "Ecosse"],
    D: ["USA", "Paraguay", "Australie", "TUR/ROU/SVK/KOS"],
    E: ["Allemagne", "Curaçao", "Cote d'Ivoire", "Equateur"],
    F: ["Pays-bas", "Japon", "UKR/SWE/POL/ALB", "Tunisie"],
    G: ["Belgique", "Egypte", "Iran", "Nouvelle-Zelande"],
    H: ["Espagne", "Cap-Vert", "Arabie Saoudite", "Uruguay"],
    I: ["France", "Senegal", "BOL/SUR/IRQ", "Norvege"],
    J: ["Argentine", "Algerie", "Autriche", "Jordanie"],
    K: ["Portugal", "NCL/JAM/COD", "Ouzbekistan", "Colombie"],
    L: ["Angleterre", "Croatie", "Ghana", "Panama"],
};

const CALENDRIER_CDM = [
    {
    "equipeA": "Mexique",
    "equipeB": "Afrique du Sud",
    "date": "2606111900",
    "description": "Mexique vs Afrique du Sud"
  },
  {
    "equipeA": "Etats-Unis",
    "equipeB": "Paraguay",
    "date": "2606130100",
    "description": "Etats-Unis vs Paraguay"
  },
  {
    "equipeA": "Qatar",
    "equipeB": "Suisse",
    "date": "2606131900",
    "description": "Qatar vs Suisse"
  },
  {
    "equipeA": "Brésil",
    "equipeB": "Maroc",
    "date": "2606132200",
    "description": "Brésil vs Maroc"
  },
  {
    "equipeA": "Haïti",
    "equipeB": "Ecosse",
    "date": "2606140100",
    "description": "Haïti vs Ecosse"
  },
  {
    "equipeA": "Allemagne",
    "equipeB": "Curacao",
    "date": "2606141700",
    "description": "Allemagne vs Curacao"
  },
  {
    "equipeA": "Pays-Bas",
    "equipeB": "Japon",
    "date": "2606142000",
    "description": "Pays-Bas vs Japon"
  },
  {
    "equipeA": "Côte d'Ivoire",
    "equipeB": "Equateur",
    "date": "2606142300",
    "description": "Côte d'Ivoire vs Equateur"
  },
  {
    "equipeA": "Espagne",
    "equipeB": "Cap-Vert",
    "date": "2606151600",
    "description": "Espagne vs Cap-Vert"
  },
  {
    "equipeA": "Belgique",
    "equipeB": "Egypte",
    "date": "2606151900",
    "description": "Belgique vs Egypte"
  },
  {
    "equipeA": "ArabieSaoudite",
    "equipeB": "Uruguay",
    "date": "2606152200",
    "description": "ArabieSaoudite vs Uruguay"
  },
  {
    "equipeA": "Iran",
    "equipeB": "Nlle Zélande",
    "date": "2606160100",
    "description": "Iran vs Nlle Zélande"
  },
  {
    "equipeA": "France",
    "equipeB": "Sénégal",
    "date": "2606161900",
    "description": "France vs Sénégal"
  },
  {
    "equipeA": "Argentine",
    "equipeB": "Algérie",
    "date": "2606170100",
    "description": "Argentine vs Algérie"
  },
  {
    "equipeA": "Autriche",
    "equipeB": "Jordanie",
    "date": "2606170400",
    "description": "Autriche vs Jordanie"
  },
  {
    "equipeA": "Angleterre",
    "equipeB": "Croatie",
    "date": "2606172000",
    "description": "Angleterre vs Croatie"
  },
  {
    "equipeA": "Ghana",
    "equipeB": "Panama",
    "date": "2606172300",
    "description": "Ghana vs Panama"
  },
  {
    "equipeA": "Ouzbékistan",
    "equipeB": "Colombie",
    "date": "2606180200",
    "description": "Ouzbékistan vs Colombie"
  },
  {
    "equipeA": "Brésil",
    "equipeB": "Haïti",
    "date": "2606200100",
    "description": "Brésil vs Haïti"
  },
  {
    "equipeA": "Ecosse",
    "equipeB": "Brésil",
    "date": "2606242200",
    "description": "Ecosse vs Brésil"
  }
]

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
function calculateUserPoints(userProno, realResult, matchCotes) {
    // userProno: { scoreA: 2, scoreB: 1 }
    // realResult: { scoreA: 2, scoreB: 1 }
    // matchCotes: { home: 1.52, draw: 3.85, away: 5.50 }

    const isExact = userProno.scoreA === realResult.scoreA && userProno.scoreB === realResult.scoreB;
    
    // Déterminer le signe (1, N ou 2)
    const getSign = (sA, sB) => (sA > sB ? '1' : sA < sB ? '2' : 'N');
    const userSign = getSign(userProno.scoreA, userProno.scoreB);
    const realSign = getSign(realResult.scoreA, realResult.scoreB);

    const isWinnerFound = userSign === realSign;

    // Récupérer la cote correspondante au signe
    const coteKey = realSign === '1' ? 'home' : realSign === '2' ? 'away' : 'draw';
    const coteValue = parseFloat(matchCotes[coteKey].replace(',', '.'));

    if (isExact) return Math.round(coteValue * 10);
    if (isWinnerFound) return Math.round(coteValue * 5);
    
    return 0;
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

document.addEventListener('DOMContentLoaded', async () => { // Ajout de async ici
    try {
        const [cotesRes, matchsRes] = await Promise.all([
            fetch('./cotes.json'),
            fetch('./matchs.json')
        ]);
        
        const cotesData = await cotesRes.json();
        const allMatches = await matchsRes.json();

        initApp(allMatches, cotesData);
        
    } catch (err) {
        console.error("Erreur de chargement des données", err);
    }
});