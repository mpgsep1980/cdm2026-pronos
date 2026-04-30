(function() {
    // 1. On récupère l'objet global où sont stockées tes 3000 lignes
    const fullData = window.__INITIAL_STATE__;

    if (!fullData || !fullData.api || !fullData.api.items) {
        console.error("L'objet de données n'est pas accessible. Assure-toi d'être sur la page Parions Sport.");
        return;
    }

    const items = fullData.api.items;
    const cleanMatches = [];

    // 2. On boucle sur les 3000 lignes pour extraire proprement
    Object.keys(items).forEach(key => {
        const item = items[key];
        // On ne prend que les matchs (eType: "G") de la Coupe du Monde
        if (item.eType === "G" && item.pdesc === "Coupe du Monde USA 2026") {
            cleanMatches.push({
                id: key,
                match: item.desc,
                equipeA: item.a,
                equipeB: item.b,
                date: `20${item.start.substring(0,2)}-${item.start.substring(2,4)}-${item.start.substring(4,6)}`,
                heure: `${item.start.substring(6,8)}h${item.start.substring(8,10)}`
            });
        }
    });

    // 3. On transforme en texte JSON et on propose le téléchargement
    const dataStr = JSON.stringify(cleanMatches, null, 2);
    const blob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = 'calendrier_cdm_2026.json';
    link.click();

    console.log(`Terminé ! ${cleanMatches.length} matchs extraits.`);
})();