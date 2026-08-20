# Releases Pentair RS485

Chaque version est archivée ici : `pentair_rs485_vX.Y.Z.zip`

Le zip à la racine (`pentair_rs485_ha.zip`) = dernière version.

## v0.6.1 — Résilience redémarrage / coupure

- Boost volet : plus de course au boot ; ignore `unavailable` ; snapshot restauré
- Watchdog : re-envoie aussi la consigne RPM/GPM ; seed depuis l’état live après reboot HA

## v0.6.0 — Boost volet + inventaire capteurs

- Capteur **% filtre (PPC)** déjà exposé (sensor *Usure filtre*)
- Options UI : choisir le **capteur volet** (+ invert)
- Par pompe : switch *Boost volet ouvert*, consigne, unité RPM/GPM
- À l’ouverture → consigne boost ; à la fermeture → restauration
- Plannings horaires : via automations HA (pas d’écriture de schedule pompe)

## v0.5.3 — VSF + mode select + programmes

| Type | Entités |
|------|---------|
| Switch (2) | Marche, Afficheur actif |
| Select (2) | Profil RPM/GPM, Mode de fonctionnement |
| Button (12) | Manuel débit, Manuel RPM, Filtre, Rendre la main, Prog 1–4, Stop, Sauver 1–4 |
| Number (6) | RPM, GPM, Vitesse programme 1–4 |
| Sensor (9) | Puissance, RPM, GPM, Mode, Drive state, PPC, Timer, Horloge, Erreur |

## Historique

| Version | Fichier | Notes |
|---------|---------|-------|
| 0.6.0 | `pentair_rs485_v0.6.0.zip` | Boost volet (options + switch/consigne) |
| 0.5.3 | `pentair_rs485_v0.5.3.zip` | VSF, select mode/profil, programmes 1–4 |
| 0.5.2 | `pentair_rs485_v0.5.2.zip` | Correctifs divers |
| 0.5.0 | `pentair_rs485_v0.5.0.zip` | UI simplifiée, modes uniquement |
| 0.4.0 | `pentair_rs485_v0.4.0.zip` | Version complète (selects, RPM/GPM) |

## Déploiement

```bash
cd /config
rm -rf custom_components/pentair_rs485
unzip -o pentair_rs485_v0.6.0.zip -d custom_components/
```

Puis redémarrer HA. Pour le volet : **Paramètres → Intégrations → Pentair RS485 → Configurer**.

## Build

```bash
./build_release.sh
```
