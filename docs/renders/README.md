# Renders — source canonique

Ce répertoire est la **référence documentaire** pour les PNG de démonstration
du pipeline monde (macro, chunks, iso, atmosphère).

## Migration depuis `docs/compliance/renders/`

Les PNG historiques sous [`../compliance/renders/`](../compliance/renders/) sont
conservés tant qu’ils n’ont pas été régénérés. Ne pas les supprimer sans regen.

| Emplacement | Rôle |
|-------------|------|
| `docs/renders/` | Canonique pour la doc produit (README, sprints) |
| `docs/compliance/renders/` | Preuves compliance / audit (waves numérotées) |

## Régénération

```bash
PYTHONPATH=runtime python runtime/scripts/regenerate_compliance_renders.py
```

Ce script enchaîne les smokes qui produisent des sorties (p72 atmosphère, p75/p80
Köppen, etc.) sans effacer les fichiers existants.

Pour des renders complets Wave 27/36, lancer aussi les smokes dédiés listés dans
[`runtime/README.md`](../../runtime/README.md#smoke-tests).
