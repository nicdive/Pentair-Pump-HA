# Releases Pentair RS485

Chaque version est archivée ici : `pentair_rs485_vX.Y.Z.zip`

Le zip à la racine (`pentair_rs485_ha.zip`) = dernière version.

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
unzip -o pentair_rs485_v0.7.0.zip -d custom_components/
```

Puis redémarrer HA. Doc complète : [README racine](../README.md). Pour le volet : **Paramètres → Intégrations → Pentair RS485 → Configurer**.

## Build

```bash
./build_release.sh
```
