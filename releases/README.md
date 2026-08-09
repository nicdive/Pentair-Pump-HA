# Releases Pentair RS485

Chaque version est archivée ici : `pentair_rs485_vX.Y.Z.zip`

Le zip à la racine (`pentair_rs485_ha.zip`) = dernière version.

## v0.5.0 — entités par pompe (27)

Interface simplifiée pour VF WhisperFlo : contrôle par **mode** (pas de consigne RPM/GPM directe).

| Type | Entités |
|------|---------|
| Switch (2) | Marche, Afficheur actif |
| Button (12) | Manuel débit, Manuel RPM, Filtre, Rendre la main, Prog 1–4, Stop, Sauver 1–4 |
| Number (4) | Vitesse programme 1–4 |
| Sensor (9) | Puissance, RPM, GPM, Mode, Drive state, PPC, Timer, Horloge, Erreur |

**Watchdog :** restaure le mode (Manuel débit / Manuel RPM / Filtre) après coupure.

## Historique

| Version | Fichier | Notes |
|---------|---------|-------|
| 0.5.0 | `pentair_rs485_v0.5.0.zip` | UI simplifiée, modes uniquement |
| 0.4.0 | `pentair_rs485_v0.4.0.zip` | Version complète (selects, RPM/GPM) |
| 0.3.3 | `pentair_rs485_v0.3.3.zip` | Fix crash parser |
| 0.3.2 | `pentair_rs485_v0.3.2.zip` | Watchdog mode |
| 0.3.1 | `pentair_rs485_v0.3.1.zip` | Afficheur actif |
| 0.3.0 | — | Non archivée |
| 0.2.0 | — | Non archivée |
| 0.1.0 | — | Non archivée |

## Déploiement

```bash
cd /config
rm -rf custom_components/pentair_rs485
unzip -o pentair_rs485_v0.4.0.zip -d custom_components/
ls custom_components/pentair_rs485/__init__.py
```

Puis **Supprimer l'intégration → Redémarrer HA → Réajouter** (recommandé après gros upgrade pour recréer toutes les entités).

## Build

```bash
./build_release.sh
```
