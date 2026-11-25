# Checklist de revue (mainteneur), ticket `T-000`

Déjà refusé par `fx.py merge` si faux (pas à vérifier à la main) : RED-OK pour chaque test du ticket, dernier run de l'agent PASS sur le commit de tête, gates complètes vertes sur le commit rebasé, copie principale sur la branche de base.

Avant de lire le code :
- [ ] Rapport agent complet, statut DONE, aucun BLOCKER.
- [ ] Revue `factory-review` faite : verdict et points traités.
- [ ] `fx.py merge <ID>` vert (sans `--approve`).

Dans le diff :
- [ ] Chaque test du ticket teste le comportement demandé, pas un détail d'implémentation, et n'est pas trivial.
- [ ] Rien hors du sujet du ticket.
- [ ] Faux positif corrigé → jumeau propre pertinent ; constat manqué → cas positif pertinent.
- [ ] `unlock` : chaque fichier déverrouillé a sa raison ; re-pin de golden vérifié à la main sur au moins un cas.
- [ ] Aucune dépendance, appel réseau, exécution de code scanné, écriture hors des chemins de sortie.
- [ ] `INJECTION SEEN` et `OUT OF SCOPE SEEN` lus ; ce qui mérite un ticket devient un ticket.

Décision :
- [ ] `fx.py merge <ID> --approve`, puis `fx.py done <ID>`, puis push / merge request selon le process de l'entreprise.
- [ ] Ou retour à l'agent avec les points numérotés, et `fx.py reset <ID> "<raison>"` si le compteur de tentatives est épuisé.
- [ ] Un contournement ou une erreur de cadrage constatée → nouvelle règle + test dans scanner-prompts, notée au `CHANGELOG.md`.
