# Bloomberg Global Trading Challenge 2026 · ESILV

Portefeuille quantitatif long-only de 1 M$ sur les actions de l'indice Bloomberg World Large, Mid & Small Cap (WLS).

## Objectif

Le classement repose sur le rendement relatif face à l'indice WLS.

- **Objectif plancher** · battre l'indice
- **Objectif cible** · finir dans le top 5 % des équipes

## Contraintes du règlement

- Long-only, sans levier, sans ETF
- Actions membres du WLS uniquement
- 20 % maximum par position (plafond interne fixé à 18 %)
- 1 M$ investi en totalité dès la première semaine
- Commissions simulées

## Ligne rouge de la stratégie

Trois briques, chacune avec un rôle unique.

| Brique | Méthode | Rôle |
|---|---|---|
| 1. Rendements | Elastic Net en coupe transversale | Classer les titres selon leur rendement relatif attendu à 5 semaines |
| 2. Covariance | Shrinkage de Ledoit-Wolf | Estimer un risque stable sur 200 à 500 titres |
| 3. Allocation | Optimisation robuste en poids actifs | Transformer prévisions et risque en poids, sous contraintes |

**Brique 1 · Elastic Net**
Un modèle commun à tous les titres, estimé sur un panel titre × semaine. Variables transformées en rangs par date (momentum 12-1, retour à la moyenne 1 mois, révisions d'analystes, surprises de résultats, volatilité, valeur, qualité). Validation walk-forward avec purge de 5 semaines. Les scores sont convertis en alphas par la formule de Grinold, α = IC × σ × z.

**Brique 2 · Ledoit-Wolf**
Covariance estimée sur un an de rendements en USD, utilisée pour mesurer la tracking error face à l'indice.

**Brique 3 · Optimisation robuste**
L'optimiseur raisonne en poids actifs (écart à l'indice), pas en poids absolus, pour éviter un biais de bêta implicite.

$$
\max_{w} \; \hat{\alpha}^{\top}(w - w_b) - \kappa \, \lVert \Omega^{1/2}(w - w_b) \rVert_2 - \gamma \, \lVert w - w_{prec} \rVert_1
$$

Avec w_b le benchmark répliqué, κ le paramètre de robustesse, γ la pénalité de rotation calée sur les commissions. Contraintes de positivité, somme à 100 %, 18 % par titre et tracking error maximale.

## Feuille de route

- [ ] Pipeline Elastic Net transversal avec walk-forward purgé
- [ ] Requêtes BQL (composition historique du WLS, prix hebdomadaires, variables point-in-time)
- [ ] Panel réel et mesure de l'IC hors échantillon
- [ ] Module Ledoit-Wolf
- [ ] Optimiseur robuste (cvxpy)
- [ ] Backtest sur fenêtres de 5 semaines, commissions incluses
- [ ] Validation avec le Faculty Advisor
- [ ] Portefeuille initial prêt avant le lancement

## Structure du dépôt

```
.
├── README.md
├── data/                          # exports BQL, non versionnés
├── src/
│   ├── elastic_net_transversal.py # brique 1
│   ├── covariance.py              # brique 2
│   ├── optimisation.py            # brique 3
│   └── backtest.py
├── notebooks/                     # explorations
└── tests/                         # tests placebo et contrôles de conformité
```

## Démarrage

```bash
pip install numpy pandas scikit-learn cvxpy
python src/elastic_net_transversal.py   # démonstration sur données synthétiques
```

## Garde-fous

1. **Pas de fuite de données.** Toute variable doit être connue à la date t. Le test placebo (données sans signal) doit donner un IC proche de zéro.
2. **IC réaliste.** Un IC compris entre 0,02 et 0,05 est normal. Au-delà de 0,08, chercher la fuite avant de s'en réjouir.
3. **Indicateurs du backtest.** Probabilité de battre l'indice et probabilité de dépasser +10 % relatif, pas le ratio de Sharpe.
4. **Règles figées.** Les paramètres sont fixés avant le lancement et ne changent pas pendant le challenge, sauf erreur avérée.

## Points ouverts avec le Faculty Advisor

- Calibrage du paramètre de robustesse κ face à un signal faible
- Pilotage dynamique de la tracking error (CPPI relatif à cliquet)
- Ajustement du bêta selon un signal de tendance sur l'indice
- Barème exact des commissions et règles 2026 sur le cash

La stratégie pourra évoluer après ces échanges. Toute modification de la ligne rouge est consignée dans ce fichier.
