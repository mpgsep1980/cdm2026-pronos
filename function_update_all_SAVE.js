// --- CORE : UPDATE ALL ---

    function trierGroupeUEFA(equipes, _matchesDuGroupe) {
        return equipes.slice().sort((a, b) => {
            if (b.pts !== a.pts) return b.pts - a.pts;
            if (b.diff !== a.diff) return b.diff - a.diff;
            if (b.bp !== a.bp) return b.bp - a.bp;
            return a.nom.localeCompare(b.nom);
        });
    }

    function updateAll() {
        // 1. Sauvegarde
        savePronosGlobal();
        
        const groupes = {};

        // 2. Calcul des points
        CALENDRIER_CDM.forEach(m => {
            // --- CORRECTION ICI : ON NETTOIE LE NOM DU GROUPE ---
            // On transforme "Groupe A" en "A", ou on garde "A" si c'est déjà bon.
            const codeGroupe = m.groupe.replace("Groupe ", "").trim();
            if (!groupes[codeGroupe]) groupes[codeGroupe] = {};
            [m.equipeA, m.equipeB].forEach(e => {
                if (!groupes[codeGroupe][e]) {
                    groupes[codeGroupe][e] = { nom: e, pts: 0, bp: 0, bc: 0, diff: 0 };
                }
            });
            const sa = parseInt(document.getElementById(`scoreA_${m.id}`).value);
            const sb = parseInt(document.getElementById(`scoreB_${m.id}`).value);
            if (!isNaN(sa) && !isNaN(sb)) {
                const tA = groupes[codeGroupe][m.equipeA];
                const tB = groupes[codeGroupe][m.equipeB];
                tA.bp += sa; tA.bc += sb;
                tB.bp += sb; tB.bc += sa;
                if (sa > sb) tA.pts += 3; 
                else if (sb > sa) tB.pts += 3; 
                else { tA.pts += 1; tB.pts += 1; }
                tA.diff = tA.bp - tA.bc; 
                tB.diff = tB.bp - tB.bc;
            }
        });

        // 3. Préparation de l'affichage
        const zones = {
            res: document.getElementById('zone-resultats'),
            z16: document.getElementById('zone-16emes')
        };
        if (!zones.res || !zones.z16) return;

        zones.res.innerHTML = "";
        
        let troisiemes = [];
        const resGroupesTriés = {};

        // 4. Tri et Affichage des tableaux de groupes
        // On trie les clés (A, B, C...) pour que l'affichage soit propre
        Object.keys(groupes).sort().forEach(g => {
            const tri = trierGroupeUEFA(Object.values(groupes[g]), []);
            resGroupesTriés[g] = tri;
            
            // On stocke le 3ème pour plus tard
            if (tri[2]) {
                const le3e = tri[2];
                le3e.groupe = g; // Important : g est maintenant "A", "B", etc.
                troisiemes.push(le3e);
            }

            let html = `<div class="group-card"><strong>GROUPE ${g}</strong><table><tr><th>Pays</th><th>Pts</th><th>+/-</th></tr>`;
            tri.forEach((eq, i) => {
                const cl = i < 2 ? 'qualifie' : '';
                html += `<tr class="${cl}"><td>${eq.nom}</td><td align="center">${eq.pts}</td><td align="center">${eq.diff}</td></tr>`;
            });
            zones.res.innerHTML += html + `</table></div>`;
        });

        // 5. Génération des 1/16es
        // On vérifie juste si des scores existent
        const scoresSaisis = CALENDRIER_CDM.some(m => document.getElementById(`scoreA_${m.id}`).value !== "");
        
        if (scoresSaisis) {
            // DEBUG : Regarde dans la console (F12) si tu vois les groupes s'afficher correctement
            console.log("Groupes triés disponibles :", Object.keys(resGroupesTriés));

            const top8 = troisiemes.sort((a, b) => b.pts - a.pts || b.diff - a.diff).slice(0, 8);
            const les16emes = genererAffiches16emes(resGroupesTriés, top8);

            zones.z16.innerHTML = les16emes.map(m => {
                const n1 = m.t1 || "En attente";
                const n2 = m.t2 || "En attente";
                
                return `
                    <div class="match-card" style="border-left: 5px solid var(--gold); margin-bottom: 15px; position:relative;">
                        <div style="position: absolute; left: 10px; top: 2px; font-size: 0.65em; color: var(--gold); font-weight: bold; opacity: 0.7;">
                            ${m.label}
                        </div>
                        <div class="team team-home">
                            ${n1} <img src="${getFlag(n1)}" style="margin-left:10px; vertical-align:middle; width:25px;">
                        </div>
                        <div class="score-inputs">
                            <input type="number" id="score_16_${m.id}_A" placeholder="0">
                            <span>:</span>
                            <input type="number" id="score_16_${m.id}_B" placeholder="0">
                        </div>
                        <div class="team team-away">
                            <img src="${getFlag(n2)}" style="margin-right:10px; vertical-align:middle; width:25px;"> ${n2}
                        </div>
                    </div>`;
            }).join('');
        } else {
            zones.z16.innerHTML = `<p style="text-align:center; color:#888;">Remplissez les scores.</p>`;
        }
    }

    function genererAffiches8emes() {
        const savedData = getPronos();

        // On ajoute 'rel' pour le numéro relatif (1, 2, 3...)
        const getV = (id, rel) => {
            const inputA = document.getElementById(`score_16_${id}_A`);
            const inputB = document.getElementById(`score_16_${id}_B`);
            
            // Le meta technique (ex: "Match 1")
            const metaMatch = `Match ${rel}`;

            // Si les inputs n'existent pas ou sont vides
            if (!inputA || !inputB || inputA.value === "" || inputB.value === "") {
                return { nom: metaMatch, meta: metaMatch };
            }

            const sA = parseInt(inputA.value);
            const sB = parseInt(inputB.value);
            const card = inputA.closest('.match-card');
            if (!card) return { nom: metaMatch, meta: metaMatch };

            const elementA = card.querySelector('.team-home');
            const elementB = card.querySelector('.team-away');
            const nomA = elementA ? elementA.textContent.trim() : `?`;
            const nomB = elementB ? elementB.textContent.trim() : `?`;

            let vainqueurNom = metaMatch; // Par défaut on affiche "Match X"
            
            // On détermine le vainqueur réel
            const manualWin = savedData[`winner_16_${id}`];
            if (sA > sB || manualWin === 'A') {
                vainqueurNom = nomA;
            } else if (sB > sA || manualWin === 'B') {
                vainqueurNom = nomB;
            }

            // IMPORTANT : Si le vainqueurNom est encore une provenance (ex: "2e Gr.F"), 
            // on garde "Match X" pour la clarté tant qu'un vrai pays n'est pas là.
            if (vainqueurNom.includes("Gr.") || vainqueurNom.includes("attente")) {
                vainqueurNom = metaMatch;
            }

            return { nom: vainqueurNom, meta: metaMatch };
        };

        // Table de correspondance avec les numéros relatifs (1 à 16)
        return [
            { id: 89, label: "Huitième 1 | Los Angeles", t1: getV(73, 1),  t2: getV(74, 2) },
            { id: 90, label: "Huitième 2 | Houston",     t1: getV(75, 3),  t2: getV(76, 4) },
            { id: 91, label: "Huitième 3 | Dallas",      t1: getV(77, 5),  t2: getV(78, 6) },
            { id: 92, label: "Huitième 4 | Seattle",     t1: getV(79, 7),  t2: getV(80, 8) },
            { id: 93, label: "Huitième 5 | Mexico City", t1: getV(81, 9),  t2: getV(82, 10) },
            { id: 94, label: "Huitième 6 | Kansas City", t1: getV(83, 11), t2: getV(84, 12) },
            { id: 95, label: "Huitième 7 | Miami",       t1: getV(85, 13), t2: getV(86, 14) },
            { id: 96, label: "Huitième 8 | Atlanta",     t1: getV(87, 15), t2: getV(88, 16) }
        ];
    }

    function genererAffichesQuarts() {
        const savedData = JSON.parse(localStorage.getItem('mes_pronos_2026')) || {};

        const getV8 = (id) => {
            const inputA = document.getElementById(`score_8_${id}_A`);
            const inputB = document.getElementById(`score_8_${id}_B`);
            const metaOrigine = `Match ${id}`;

            // Si les scores ne sont pas saisis
            if (!inputA || !inputB || inputA.value === "" || inputB.value === "") {
                return { nom: `Vainqueur M.${id}`, meta: metaOrigine };
            }

            const sA = parseInt(inputA.value);
            const sB = parseInt(inputB.value);
            const card = inputA.closest('.match-card');
            
            if (!card) return { nom: `Vainqueur M.${id}`, meta: metaOrigine };

            const nomA = (card.querySelector('.team-home') || {}).textContent?.trim() || `?`;
            const nomB = (card.querySelector('.team-away') || {}).textContent?.trim() || `?`;

            let vainqueur = `Vainqueur M.${id}`;
            if (sA > sB) {
                vainqueur = nomA;
            } else if (sB > sA) {
                vainqueur = nomB;
            } else {
                const manualWin = savedData[`winner_8_${id}`];
                if (manualWin === 'A') vainqueur = nomA;
                else if (manualWin === 'B') vainqueur = nomB;
            }

            return { nom: vainqueur, meta: metaOrigine };
        };

        return [
            { id: 97, label: "Quart 1 | Boston", t1: getV8(89), t2: getV8(90) },
            { id: 98, label: "Quart 2 | Los Angeles", t1: getV8(91), t2: getV8(92) },
            { id: 99, label: "Quart 3 | Miami", t1: getV8(93), t2: getV8(94) },
            { id: 100, label: "Quart 4 | Kansas City", t1: getV8(95), t2: getV8(96) }
        ];
    }

    function genererAffichesDemies() {
        const savedData = getPronos();

        const getV4 = (id) => {
            const inputA = document.getElementById(`score_4_${id}_A`);
            const inputB = document.getElementById(`score_4_${id}_B`);
            const metaOrigine = `Match ${id}`;

            if (!inputA || !inputB || inputA.value === "" || inputB.value === "") {
                return { nom: `Vainqueur M.${id}`, meta: metaOrigine };
            }

            const sA = parseInt(inputA.value);
            const sB = parseInt(inputB.value);
            const card = inputA.closest('.match-card');

            if (!card) return { nom: `Vainqueur M.${id}`, meta: metaOrigine };

            const nomA = (card.querySelector('.team-home') || {}).textContent?.trim() || `?`;
            const nomB = (card.querySelector('.team-away') || {}).textContent?.trim() || `?`;

            let vainqueur = `Vainqueur M.${id}`;
            if (sA > sB) {
                vainqueur = nomA;
            } else if (sB > sA) {
                vainqueur = nomB;
            } else {
                const manualWin = savedData[`winner_4_${id}`];
                if (manualWin === 'A') vainqueur = nomA;
                else if (manualWin === 'B') vainqueur = nomB;
            }

            return { nom: vainqueur, meta: metaOrigine };
        };

        return [
            { id: 101, label: "Demi-finale 1 | Dallas", t1: getV4(97), t2: getV4(98) },
            { id: 102, label: "Demi-finale 2 | Atlanta", t1: getV4(99), t2: getV4(100) }
        ];
        
    }