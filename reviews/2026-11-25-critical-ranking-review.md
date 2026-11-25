# Revue de la proposition « promotion CRITICAL » (branche `feat/critical-ranking`)

Date : 2026-11-25. Base : captures de `docs/ranking.md`, du diff de `.claude/skills/triage/SKILL.md` (STEP 2b) et de l'explication de la chaîne d'attribution. Comparé au skill `triage` public d'Anthropic (Phase 4, STEP 1 à 6) et à l'échelle de sévérité publique d'evilsocket/audit, dont lynceus dérive.

## Avis

La structure est bonne et à garder : le scanner ne peut pas émettre CRITICAL, un seul chemin y mène, il passe par le triage, et la sévérité reste catégorielle. Mais le mécanisme tel qu'écrit ne répond pas encore aux deux enjeux : **des CRITICAL qui ont de la valeur** et **un mécanisme qu'on comprend exactement**. Trois raisons :

1. La décision CRITICAL est prise par le modèle, en texte libre, sur des critères dont deux sont déjà vrais par construction et un est subjectif.
2. L'échelle sous CRITICAL n'a pas d'axe d'impact, ce qui décale anduril d'un cran par rapport à lynceus sur tout ce qui est authentifié.
3. Rien ne teste la décision elle-même (les 3 tests couvrent la plomberie du reporting).

Proposition : le modèle ne décide plus, il **répond à des questions factuelles avec preuve `fichier:ligne`** ; une **fonction pure en Python calcule la sévérité** à partir de ces réponses et écrit la trace des règles appliquées ; chaque candidat CRITICAL passe une **contre-vérification adverse** avant d'être confirmé. Détail dans le prompt `2026-11-25-02` (brouillon).

## Constats

### C1 — Deux des quatre facteurs sont toujours vrais
La table du STEP 2 ne donne HIGH que pour « 0 précondition + non authentifié distant ». Quand STEP 2b s'exécute sur un HIGH, `reach` et `preconditions` sont donc déjà acquis. Le verrou réel est `impact` + `confirmation`. La norme présente quatre verrous indépendants ; il y en a deux.

### C2 — `confirmation` est subjectif
« Leaves no real doubt » n'est pas vérifiable. Version mécanique : `verify_verdict == exploitable`, votes de vérification unanimes, et contre-vérification adverse passée. À noter : le reporting prend la sévérité du triage pour les statuts `confirmed` **et** `needs_manual_test`. Un `needs_manual_test` peut donc sortir CRITICAL aujourd'hui. À plafonner à HIGH dans le code.

### C3 — `reach` repose sur une preuve négative
« No auth check on the path you traced » : le cas d'erreur classique est un handler sans contrôle, derrière un middleware global ou une passerelle qui authentifie. Il faut exiger la preuve de la façon dont la route est enregistrée et de ce qui s'applique globalement. Sans cette preuve : `unknown`, donc pas de CRITICAL.

### C4 — L'échelle n'a pas d'axe d'impact sous CRITICAL
La table (reprise d'Anthropic) ne regarde que préconditions et accès :
- tout ce qui est authentifié plafonne à MEDIUM : RCE par n'importe quel compte, SQLi sur une route connectée, IDOR sur les données d'autres clients ;
- tout ce qui est non authentifié sans précondition est HIGH, quel que soit l'impact.

L'échelle d'evilsocket/audit classe « authenticated RCE, SQLi or path-traversal on a reachable route, IDOR with sensitive data » en **high**. Sur le même bug, anduril dira MEDIUM et lynceus HIGH. Pour un scanner censé se concentrer sur high/critical, c'est le point le plus coûteux : ces findings existent mais sortent du périmètre affiché, et la comparaison croisée montrera un désaccord systématique d'un cran.

Correctif proposé (décision D2) : plancher HIGH quand `reach = compte ordinaire`, aucune autre précondition, et impact de premier rang.

### C5 — Le threat model ne peut pas qualifier l'impact
Un match threat-model monte d'un cran sans jamais atteindre CRITICAL : bien. Mais l'impact du contrat est générique (compromission complète, secrets, données d'autres utilisateurs). Une modification non autorisée d'un actif métier critique (une transaction, par exemple) sort en `data alteration`, donc jamais CRITICAL. Proposition : une valeur d'impact `critical_asset_write`, valable seulement si l'actif est nommé dans le threat model. Ce n'est pas une escalade : `reach` et les préconditions doivent tenir seuls.

### C6 — La ligne facteurs ne permet pas l'audit
- Texte libre en fin de `RANK_RATIONALE`, récupéré comme « dernier paragraphe » : fragile.
- Émise seulement si la sévérité change : un HIGH resté HIGH n'explique pas pourquoi il n'est pas CRITICAL, alors que c'est la question qui sera posée dans la plateforme.
- Elle ne reflète pas le contrat : `confirmation` absent, `chaining` en plus, `preconditions=<none|...>` ouvert, l'énumération d'impact ne contient ni « données d'autres utilisateurs » ni « contournement d'authentification », « critical path » n'est pas défini.

Proposition : champs structurés dans `TRIAGE.json` pour tout finding confirmé, ligne lisible générée par le code, plus `critical_blockers` (la liste des conditions non remplies) sur chaque HIGH.

### C7 — La décision n'est pas testée
Il faut trois niveaux :
1. tests unitaires de la fonction de calcul (table de cas, déterministe, gratuit) ;
2. un jeu de calibration : une douzaine de petits cas synthétiques placés de part et d'autre de chaque frontière, passés N fois, pour mesurer la précision des CRITICAL et le taux de bascule d'un run à l'autre ;
3. la comparaison croisée avec lynceus (protocole ci-dessous).

### C8 — SARIF et plateforme
`security-severity` 9.5 / 8.0 / 5.5 / 3.0 tombe dans les seuils usuels (critique ≥ 9.0, élevé ≥ 7.0). Mais CRITICAL et HIGH ont le même `level: error` : si la plateforme lit `level`, les deux sont confondus à l'ingestion. À vérifier (question Q5). À ajouter dans chaque résultat : les facteurs, la trace, et une empreinte stable (`partialFingerprints`) pour dédupliquer entre runs et rapprocher avec lynceus.

### Ce qui est juste et reste
- Le scanner (`/vuln-scan`) reste en HIGH / MEDIUM / LOW.
- Un seul chemin vers CRITICAL, au triage, jamais par classe de vulnérabilité, jamais par quota.
- Pas de score composite, pas de PoC obligatoire. La contre-vérification adverse compense l'absence de PoC, sur les seuls candidats CRITICAL (peu nombreux, donc peu coûteux).
- L'argument « 2b avant STEP 3 » est correct ; il devient sans objet si le code calcule.

## Mécanisme proposé (v2), en une page

```
vuln-scan            claim HIGH|MEDIUM|LOW                      (inchangé)
triage Phase 3       N votes : true_positive / false_positive   (inchangé)
triage Phase 4       le modèle répond, avec preuve fichier:ligne :
                       REACH   unauth_remote | auth_low | auth_priv | local | unknown
                       AUTH_EVIDENCE   où l'authentification est (ou serait) appliquée
                       IMPACT  full_compromise | secrets_or_bulk_data | critical_asset_write
                               | limited | availability | none
                       PRECONDITIONS   une par ligne, étiquetée [config] [victim] [race]
                                       [knowledge] [chain] [other]
                       PROD_PATH  yes | no
                       VERIFY_VERDICT  exploitable | mitigated | needs_manual_test
code (fonction pure) sévérité = table(préconditions, reach)          règle T2
                     plancher HIGH si auth_low + 0 précondition + impact rang A   règle F1
                     +1 cran si match threat model, plafonné à HIGH  règle T3
                     candidat CRITICAL si TOUTES les conditions :    règle C1
                       reach = unauth_remote, AUTH_EVIDENCE présent,
                       0 précondition, impact rang A, PROD_PATH = yes,
                       verdict = exploitable, votes unanimes
contre-vérification  un agent neuf essaie de réfuter UN facteur      règle C2
                     réfuté ou incertain → HIGH ; sinon CRITICAL
sortie               severity, severity_trace[], critical_blockers[], factors{}
```

Chaque sévérité finale s'explique par la liste des règles appliquées, par exemple `["T2: 0 precondition + unauth_remote = HIGH", "C1: all critical conditions hold", "C2: challenge survived"]`, ou pour un HIGH : `critical_blockers: ["impact=limited"]`.

## Comparaison croisée anduril / lynceus (protocole, à spécifier ensuite)

1. Normaliser les deux rapports de la même application en lignes : outil, id, famille de vulnérabilité, fichier, lignes, point d'entrée, sévérité, statut.
2. Apparier : même fichier et lignes qui se recouvrent, ou même sink et même famille. Le reste est tranché à la main.
3. Mesurer : rappel d'anduril sur les critical + high confirmés de lynceus ; findings HIGH / CRITICAL propres à anduril, jugés vrais ou faux ; matrice d'accord des sévérités sur les findings appariés ; précision des CRITICAL de chaque côté ; durée et coût.
4. Cible à fixer par le mainteneur, de la forme : « anduril retrouve au moins X % des critical de lynceus en moins de Y % de sa durée ».

Les deux échelles sont compatibles au sommet : le critical d'evilsocket/audit (RCE non authentifiée, contournement complet d'authentification, lecture de secrets, SSRF vers les métadonnées cloud) correspond à `unauth_remote` + impact de rang A. La différence qui reste : chez lynceus le chasseur attribue la sévérité à l'émission, chez anduril elle est calculée après vérification.

## Décisions à prendre

- **D1** — CRITICAL réservé au non authentifié (recommandé : oui, comme l'échelle de lynceus), ou aussi ouvert aux comptes ordinaires auto-inscriptibles ?
- **D2** — Plancher HIGH pour compte ordinaire + aucune précondition + impact de rang A (recommandé : oui ; c'est un écart assumé par rapport à la table d'Anthropic).
- **D3** — Contre-vérification adverse sur chaque candidat CRITICAL (recommandé : oui ; un agent de plus par candidat).
- **D4** — Unanimité des votes de vérification exigée pour CRITICAL (recommandé : oui).
- **D5** — `critical_asset_write` lié aux actifs nommés dans le threat model (recommandé : oui si le threat model liste des actifs).

## Questions

- **Q1** — Combien d'agents classent chaque finding en Phase 4, et avec quelles entrées ? (Chez Anthropic : un seul, après les N votes de la Phase 3.)
- **Q2** — Quel réglage de tolérance au bruit en production (`precision` ou `recall`) ? Il décide si un vote partagé arrive en Phase 4.
- **Q3** — Le modèle qui exécute le triage est-il le même que celui du scan ?
- **Q4** — Le threat model liste-t-il des actifs avec un niveau de criticité ?
- **Q5** — Quelle plateforme ingère les findings, et quel champ SARIF lit-elle pour la sévérité ?

Le prompt `2026-11-25-01` fait répondre le dépôt à Q1, Q3, Q4 et au reste des faits manquants.

## Addendum — faits reçus (prompt `2026-11-25-01`) et plan retenu

Ce que les faits changent :

1. **Aucun code ne lit le bloc de la Phase 4.** C'est l'agent orchestrateur du skill qui le recopie dans `TRIAGE.json` ; le schéma accepte n'importe quelle chaîne pour `severity`. Aujourd'hui un CRITICAL sans ligne facteurs passe sans contrôle. La fonction de calcul se place donc **après** la validation de `TRIAGE.json`, dans le pipeline, et la sortie brute de l'agent est conservée dans `TRIAGE.model.json`.
2. **Un seul vote par finding en run normal** (le skill prévoit 3, le harness en passe 1), et un seul agent classe chaque finding. Un CRITICAL reposerait sur une seule réponse. La condition « votes unanimes sur au moins 2 votes » devient « aucun vote contraire », et la contre-vérification adverse devient obligatoire, pas optionnelle : c'est elle le second regard. Elle peut tourner sur un autre modèle (`stages.challenge.model`).
3. **Le threat model transmis au classement est vide** dans les runs, alors que `THREAT_MODEL.md` existe avec une table d'actifs (colonne sensibilité) et une table de menaces (colonne impact). Le STEP 3 est donc sauté et la règle T3 ne se déclenche jamais. À décider séparément (D6) : le brancher fera monter des MEDIUM en HIGH, il faut mesurer avant.
4. **Le triage rétrograde massivement les HIGH claimés.** C'est la conséquence attendue de la table (constat C4) sur une application surtout authentifiée. La règle F1 est celle qui aura le plus d'effet sur un scanner « focus high / critical » ; son effet se mesure avec `--stats` sur un run existant, sans relancer de scan.
5. **Le scanner n'enregistre ni point d'entrée ni état d'authentification.** Le classement est le premier endroit où `reach` est établi. Faire émettre ces deux faits par le scan est une piste pour la suite (ordre de triage, comparaison avec lynceus).
6. SARIF : `properties.security-severity` et `partialFingerprints` existent déjà. L'empreinte dépend du numéro de ligne, donc elle change quand le code bouge : acceptable pour comparer deux rapports du même commit, à revoir pour le suivi dans le temps.

Décisions intégrées dans les prompts : D1 (CRITICAL réservé au non authentifié), D2 (plancher HIGH, règle F1), D3 (contre-vérification), D4 adaptée (aucun vote contraire), D5 en option (inactive tant qu'aucun actif n'est nommé).

Plan, un prompt par tâche, à coller dans l'ordre et un à la fois :

| Prompt | Contenu | Effet sur les runs |
|---|---|---|
| `2026-11-25-03` | `anduril/ranking.py` : `normalise`, `derive_severity`, `--stats`, tests | aucun (rien ne l'appelle) |
| `2026-11-25-04` | STEP 2b factuel, nouveaux champs, calcul après validation, « Why this severity » | sévérités calculées ; candidats CRITICAL marqués, aucun CRITICAL |
| `2026-11-25-05` | skill de contre-vérification, étape pipeline, `docs/ranking.md` | CRITICAL possibles |

Après `-04` : relancer le triage d'un run existant et comparer `--stats` avant et après. Après `-05` : même chose, puis lire à la main chaque CRITICAL et chaque candidat réfuté.

Restent à écrire ensuite : le jeu de calibration (12 cas synthétiques), le protocole de comparaison avec lynceus, et D6.

## Mise à jour — un seul prompt de bout en bout

Les prompts `-03`, `-04`, `-05` sont regroupés dans `2026-11-25-06`, qui ajoute :
- **D6 tranchée par la mesure** : un réglage `stages.triage.threat_model` (`off` par défaut, `on` pour transmettre `THREAT_MODEL.md` au classement) et deux variantes de triage sur les mêmes findings de scan, comparées dans un tableau.
- **Modèles** : scan et triage sur un modèle, contre-vérification sur l'autre quand deux sont configurés.
- **`only_blocked_by_reach`** : le nombre de HIGH qui seraient candidats CRITICAL si D1 autorisait les comptes ordinaires. C'est la donnée qui permettra de revoir D1 sans changer la règle à l'aveugle.
- Une règle explicite : zéro CRITICAL est un résultat valide, aucun réglage n'est modifié pour en obtenir.
