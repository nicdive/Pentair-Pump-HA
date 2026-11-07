# Releases Pentair RS485

Chaque version est archivée ici : `pentair_rs485_vX.Y.Z.zip`

Le zip à la racine (`pentair_rs485_ha.zip`) = dernière version.

## v0.8.2 — Carte Lovelace sous HA 2026.11

- Enregistre la carte comme ressource Lovelace (`/local/community/`) : plus de *Custom element not found* après Marketplace
- Licence MIT + icône de marque

## v0.8.1 — Programmes sur l’afficheur Lovelace

- Carte LCD : boutons **1 / 2 / 3 / 4** à la place de **Entités**

## v0.8.0 — Un module, même nom qu’en 0.7.3

- HACS : **Pentair RS485** uniquement
- Mode afficheur sans USB pour le HA principal

## v0.7.7 — HACS « No manifest.json pentair_pump_display »

- Remet le dossier `pentair_pump_display` attendu par HACS après l’install 0.7.5

## v0.7.6 — HACS afficheur (un seul module)

- Setup : Pompe USB **ou** Afficheur Remote HA
- Plus de second custom_component (HACS n’en gère qu’un)
- Plus de `zip_release` (le zip 0.7.5 se décompactait au mauvais endroit)

## v0.7.5 — HACS sur le HA principal

- Le zip HACS contient `pentair_rs485` **et** `pentair_pump_display`
- Même dépôt custom : piscine → ajouter RS485 ; principal → ajouter l’afficheur seulement

## v0.7.4 — Afficheur seul (HA principal)

- Nouveau module `pentair_pump_display` (zip dédié) : carte Lovelace, pas de pompe
- Lookup Remote HA : `sensor.pump_1_*` depuis `switch.pump_1_marche`

## v0.7.3 — Fantôme VS 0.5.2

- Supprime l’ancien appareil Pool Pump (identifiants 0.5.2) même s’il a le même index que la pompe actuelle

## v0.7.2 — Retirer une pompe à la reconfiguration

- Reconfigurer : liste **Pompes à conserver** (décocher VS fantôme, etc.)
- Appareils et entités orphelins supprimés au rechargement

## v0.7.1 — VF WhisperFlo : RPM comme en 0.5.2

- Une pompe **VF** expose à nouveau Vitesse (RPM) + RPM actuel
- Profil de commande par défaut = **RPM** (GPM reste disponible)
- Plus de curseur RPM grisé sur IntelliFlo WhisperFlo VF

## v0.7.0 — Fiabilité bus, watchdog, boost, usage

- Poll : attendre la pompe demandée ; offline après 3 misses ; thread série dédié
- Setup HA même si USB absent ; capteurs live `unavailable` si pompe muette
- Stop programme → `desired_run=false` ; Marche ON ré-applique la consigne
- Boost volet : consigne utilisateur préservée ; restore `was_on` ; debounce ; `closing` ≠ fermé
- Watchdog : dérive RPM/GPM ; skip amorçage / boost ; plus de combat avec le volet
- Services `set_speed` / `set_power` ; poll interval ; diagnostics ; pompe en ligne
- Config flow : liste des ports + test d’ouverture

## v0.6.4 — Audit robustesse

- Premier poll RS485 **après** restore des entités (plus de vol du panneau au boot)
- Commandes HA en mode panneau : **aucun** effet de bord (desired_run / consignes inchangés)
- Restore boost volet différé si contrôle panneau actif ; réévalué à la sortie du mode panneau

## v0.6.3 — Switch contrôle panneau

- Bouton « Rendre la main » → switch **Contrôle panneau** (persistant)
- ON = boutons physiques ; OFF = retour contrôle HA (+ reprise consigne si desired_run)
- Watchdog / commandes HA / boost volet ignorés tant que le switch est ON

## v0.6.2 — desired_run, USB reconnect, reconfigure

- Arrêt volontaire avant reboot HA → **pas** de redémarrage auto (`desired_run`)
- Reprise consigne seulement si `desired_run=true`
- `pyserial` en requirement ; unique_id liés à l’entrée config
- Reconnexion USB RS485 ; Reconfigure port/pompes
- Binary sensors : RS485 online, boost volet actif

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

**Recommandé** : HACS → dépôt custom `https://github.com/nicdive/Pentair-Pump-HA` (catégorie Integration). Les mises à jour suivent les releases GitHub (`vX.Y.Z`).

ZIP manuel :

```bash
cd /config
rm -rf custom_components/pentair_rs485
unzip -o pentair_rs485_v0.8.0.zip -d custom_components/
```

Puis redémarrer HA. Doc complète : [README racine](../README.md). Pour le volet : **Paramètres → Intégrations → Pentair RS485 → Configurer**.

## Build

```bash
./build_release.sh
```
