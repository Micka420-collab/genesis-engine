"""Genesis Network — réseau de calcul mondial volontaire.

Permet à n'importe qui, sur n'importe quelle plateforme, d'offrir de la
puissance de calcul au monde Genesis via une seule commande (``genesis donate``),
et au monde entier d'observer les civilisations IA évoluer en direct depuis un
site public.

Principe : le monde est découpé en *chunks* déterministes
(``même (world_seed, coord) → contenu bit-pour-bit identique``). Chaque
volontaire calcule des chunks différents ; le coordinateur agrège, **vérifie
par recalcul déterministe** (anti-triche gratuit), et fait croître le monde —
plus de puissance vérifiée → monde plus grand et plus haute résolution.

Couches :
    * ``protocol``    — contrat work-unit / résultat (schémas Pydantic).
    * ``worldgen``    — génération déterministe d'un chunk (unité de travail).
    * ``coordinator`` — serveur FastAPI : assigne, vérifie, agrège, diffuse (SSE).
    * ``worker``      — client ``genesis donate`` (stdlib pur, cross-platform).
    * ``web/``        — site mondial public (carte live + classement + fil IA).
"""

PROTOCOL_VERSION = "ge-net/1"
__all__ = ["PROTOCOL_VERSION"]
