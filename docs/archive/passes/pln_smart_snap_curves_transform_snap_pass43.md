# Pass 43 — PLN smart snap, courbes MOD et transform snap enrichi

## PLN

- Le traceur de plan utilise maintenant uniquement le smart snap pendant le dessin.
- Le grid snap est volontairement désactivé pour PLN, même si le snap global de la scène est actif.
- Les ancres de smart snap incluent :
  - les points du tracé ;
  - les échantillons de la courbe ;
  - les points de contrôle implicites des segments ;
  - les coins/arêtes projetés des objets déjà présents dans la scène.
- Le mode MOD permet de sélectionner un point puis de régler la courbe du segment associé.
- Les nouveaux sliders PLN sont :
  - Curve radius ;
  - Curve force.
- La preview, la validation et le mesh final utilisent la même frontière échantillonnée.

## Transform Translation

Le smart snap de translation ne se limite plus aux min/center/max de la bounding box.
Il ajoute aussi les coordonnées réelles des sommets/arêtes du mesh cible sur l’axe actif.
Cela permet de coller plus naturellement un objet sur un bord, une arrête ou une ligne interne d’un autre objet.

## Tests

Ajout de `tests/test_pln_curves_and_snap_pass43.py`.
