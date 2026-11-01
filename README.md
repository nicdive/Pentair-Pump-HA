# Pentair RS485 — Home Assistant

Intégration custom pour piloter une ou plusieurs pompes **Pentair IntelliFlo** (VS / VF / VSF) en **standalone** via un adaptateur **USB RS485**, sans automate Pentair (EasyTouch / IntelliCenter).

**Version actuelle : v0.7.2**

---

## Table des matières

- [Prérequis](#prérequis)
- [Installation](#installation)
- [Afficheur Lovelace (style LCD pompe)](#afficheur-lovelace-style-lcd-pompe)
- [Configuration](#configuration)
- [Entités](#entités)
- [Utilisation](#utilisation)
- [Boost volet](#boost-volet)
- [Contrôle panneau](#contrôle-panneau)
- [Comportement au redémarrage](#comportement-au-redémarrage)
- [Automations utiles](#automations-utiles)
- [Services](#services)
- [Dépannage](#dépannage)
- [Limites connues](#limites-connues)

---

## Prérequis

### Matériel

| Élément | Détail |
|--------|--------|
| Pompe | IntelliFlo **VS**, **VF** ou **VSF** (bus RS485 natif) |
| Adaptateur | USB ↔ RS485 (ex. FTDI, CH340, …) câblé en **A/B** sur le bus pompe |
| Câblage | Bus partagé possible pour **plusieurs pompes** (adresses 96–111) |
| Host | Home Assistant avec accès au port série (`/dev/ttyUSB0`, `/dev/serial/by-id/…`) |

### Logiciel

| Élément | Détail |
|--------|--------|
| Home Assistant | **2024.2.0** ou plus récent |
| Python deps | `pyserial>=3.5` (installé automatiquement par HA via le `manifest`) |
| Droits | L’utilisateur HA doit pouvoir ouvrir le port série (groupe `dialout` / Docker device mapping) |

### Adresses bus (rappel)

| Index config | Adresse RS485 |
|--------------|---------------|
| 1 | 96 |
| 2 | 97 |
| … | … |
| 16 | 111 |

L’adresse **app** de l’intégration (par défaut **33**) est celle de Home Assistant sur le bus Pentair — **ce n’est pas** le chemin du port USB.

---

## Installation

Ce n’est **pas** un module complémentaire Supervisor (add-on Docker). C’est une **intégration custom**. Pour les mises à jour automatiques, passez par **HACS** + les releases GitHub.

### Option A — HACS (recommandé, mises à jour dans HA)

1. Installez [HACS](https://hacs.xyz/) s’il n’est pas déjà là.
2. **HACS → Intégrations → ⋮ → Dépôts personnalisés**.
3. URL : `https://github.com/nicdive/Pentair-Pump-HA`  
   Type : **Integration**.
4. Cherchez **Pentair RS485**, téléchargez / installez.
5. Redémarrez Home Assistant.
6. **Paramètres → Appareils et services → Ajouter une intégration → Pentair RS485**.

Quand une nouvelle version est publiée sur GitHub (tag `vX.Y.Z` = champ `version` du `manifest.json`), HACS propose la mise à jour. Vous validez, HA redémarre, c’est tout.

Si vous venez d’une 0.5.x : au premier passage en 0.6.2+, HA recrée les entités (`unique_id`). Supprimez les orphelines une fois.

### Option B — ZIP manuel

1. Téléchargez `releases/pentair_rs485_v0.7.2.zip` (ou `pentair_rs485_ha.zip` à la racine = dernière version).
2. Sur le host HA :

```bash
cd /config
rm -rf custom_components/pentair_rs485
unzip -o /chemin/vers/pentair_rs485_v0.7.2.zip -d custom_components/
```

3. Redémarrez Home Assistant.
4. Ajoutez l’intégration si ce n’est pas déjà fait.

### Option C — copie manuelle

```bash
cp -r custom_components/pentair_rs485 /config/custom_components/
```

Puis redémarrage HA et ajout de l’intégration.

### Publier une version (mainteneur)

1. Monter `version` dans `custom_components/pentair_rs485/manifest.json`.
2. Commit + merge sur `main`.
3. `git tag vX.Y.Z && git push origin vX.Y.Z`  
   L’action GitHub construit le zip et ouvre la release ; HACS voit la mise à jour.

### Build local d’un zip

```bash
./build_release.sh
```

Génère `releases/pentair_rs485_vX.Y.Z.zip` et met à jour `pentair_rs485_ha.zip`.

---

## Afficheur Lovelace (style LCD pompe)

Carte optionnelle qui imite l’écran IntelliFlo (RPM, watts, mode, horloge). Elle n’est **pas** obligatoire.

1. Redémarrer HA après installation / mise à jour de l’intégration (la carte JS est servie par le composant).
2. Tableau de bord → **Ajouter une carte** → **Carte personnalisée**, ou en YAML :

```yaml
type: custom:pentair-pump-display-card
entity: switch.pool_pump_marche
```

`entity` = le switch **Marche**. RPM, puissance, mode, afficheur, etc. sont pris sur le même appareil.

Boutons sous l’écran : Start/Stop, LCD on/off (**Afficheur actif**), fiche entité.

Si la carte n’apparaît pas (Lovelace en YAML) : **Paramètres → Tableaux de bord → Ressources** → `/pentair_rs485/pentair-pump-display-card.js` (type `module`).

Exemple : `lovelace/pump_display.yaml`.

---

## Configuration

### Première installation

1. **Port série** — ex. `/dev/ttyUSB0` ou, mieux, un chemin stable :

   ```text
   /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_XXXX-if00-port0
   ```

2. **Adresse bus (appAddress)** — laisser **33** sauf conflit connu sur le bus.
3. **Pompe(s)** — pour chaque pompe :
   - **Index** (1–16) → adresse 96–111
   - **Type** : `VS` (RPM), `VF` (GPM), `VSF` (RPM **et** GPM)
   - **Nom** libre (ex. « Pompe piscine »)
   - Cocher **Ajouter une autre pompe** si besoin

### Options (boost volet + poll)

**Paramètres → Intégrations → Pentair RS485 → Configurer**

| Champ | Description |
|-------|-------------|
| Intervalle de poll RS485 | 10–120 s (défaut **30**). Plus court = UI plus vive, plus de trafic bus |
| Capteur volet / shutter | `cover.*`, `binary_sensor.*` ou `input_boolean.*` |
| Inverser | Si `on` = volet **fermé** chez vous |

Laisser le capteur vide pour désactiver complètement le boost.

### Reconfigurer port / pompes

**Intégration → ⋮ → Reconfigurer** : port, adresse bus, et la liste **Pompes à conserver**.

Décochez une pompe pour la retirer (l’appareil et ses entités sont supprimés au rechargement). Inutile de ressaisir celles que vous gardez. Cochez **Ajouter une autre pompe** seulement pour en créer une nouvelle.

---

## Entités

Chaque pompe expose un appareil Home Assistant avec les entités suivantes.

### Interrupteurs

| Entité | Rôle |
|--------|------|
| **Marche** | Marche / arrêt. Attribut `desired_run` = intention persistée |
| **Afficheur actif** | Mode « display active » (LCD pompe) entre les commandes HA |
| **Contrôle panneau** | ON = boutons physiques ; OFF = contrôle HA (voir ci-dessous) |
| **Boost volet ouvert** | Active le boost automatique quand le volet est ouvert |

### Nombres (consignes)

| Entité | Plage |
|--------|-------|
| **Vitesse (RPM)** | 450 – 3450 |
| **Débit (GPM)** | 15 – 130 |
| **Consigne boost volet** | Selon l’unité choisie |
| **Vitesse programme 1–4** | Consigne mémorisée pour chaque programme |

### Selects

| Entité | Options |
|--------|---------|
| **Profil de commande** | `RPM` ou `GPM` (surtout utile sur **VSF**) |
| **Mode de fonctionnement** | Filtre, manuel débit/RPM, speeds, feature, programmes 1–4 |
| **Unité boost volet** | RPM ou GPM |

### Boutons

| Bouton | Action |
|--------|--------|
| Manuel débit / Manuel RPM / Filtre | Envoie le mode correspondant |
| Lancer programme 1–4 / Stop programme | Démarre ou arrête un programme |
| Sauver lecture → programme 1–4 | Enregistre la vitesse lue dans le slot |

### Capteurs

| Capteur | Description |
|---------|-------------|
| Puissance (W) | Consommation |
| RPM / GPM actuel | Mesure live |
| Mode de fonctionnement | Mode rapporté par la pompe |
| État drive | Drive state |
| Usure filtre (PPC) | % filtre |
| Timer programme | Timer interne |
| Horloge pompe | Heure pompe |
| Erreur | Code / libellé d’erreur |

### Capteurs binaires

| Capteur | Description |
|---------|-------------|
| **RS485 online** | Adaptateur série ouvert, dernier I/O OK |
| **Pompe en ligne** | La pompe a répondu à un poll récent (3 polls manqués → offline) |
| **Boost volet actif** | Un boost est en cours sur cette pompe |

---

## Utilisation

### Démarrer / arrêter

1. Réglez **RPM** ou **GPM** (selon le profil).
2. Activez **Marche**, ou lancez un **programme**.
3. Pour arrêter : **Marche** OFF, ou bouton **Stop programme**.

L’attribut `desired_run` du switch **Marche** indique si HA **souhaite** que la pompe tourne après un redémarrage :

- Arrêt volontaire → `desired_run=false` → **pas** de redémarrage auto
- Pompe laissée en marche → `desired_run=true` → reprise de la consigne au boot

### Choisir RPM ou GPM (VSF)

1. Select **Profil de commande** → `RPM` ou `GPM`
2. Utilisez le nombre **Vitesse** ou **Débit** correspondant
3. Ou passez par le select **Mode de fonctionnement** / les boutons Manuel

### Programmes 1–4

1. Réglez la **vitesse programme N** (ou sauvez la lecture courante)
2. Bouton **Lancer programme N**
3. **Stop programme** pour arrêter

Les plages horaires « classiques » (filtre le matin, etc.) se font avec des **automations Home Assistant**, pas en écrivant l’horloge interne de la pompe.

### Afficheur actif

- **ON** : après chaque commande HA, la pompe revient en contrôle local d’afficheur (comportement type IntelliComm)
- **OFF** : HA garde le contrôle distant entre les polls

Indépendant du switch **Contrôle panneau** (qui, lui, bloque complètement HA).

---

## Boost volet

Quand le capteur configuré passe à **ouvert** :

1. Si le switch **Boost volet ouvert** est ON pour la pompe
2. Et que **Contrôle panneau** est OFF
3. → la pompe passe à la **consigne boost**
4. À la fermeture → restauration de la consigne précédente (snapshot)

Cas particuliers gérés :

- États `unavailable` / `unknown` **ignorés** (pas de faux « fermé »)
- Snapshot conservé après redémarrage HA si le boost était actif
- Si **Contrôle panneau** est ON : boost **reporté** ; réévalué dès le retour au contrôle HA

---

## Contrôle panneau

| État | Comportement |
|------|----------------|
| **ON** | Boutons physiques de la pompe. HA n’envoie plus de commandes ; watchdog et boost volet en veille. Persiste après reboot HA. |
| **OFF** | Retour contrôle HA. Si `desired_run=true`, la consigne est renvoyée. Le boost volet est réévalué. |

Utile pour laisser quelqu’un utiliser la pompe « à la main » sans que HA écrase les réglages.

---

## Comportement au redémarrage

Ordre au démarrage de l’intégration :

1. Restore des entités (`desired_run`, panneau, consignes, snapshot boost)
2. Premier poll RS485
3. Sync volet + reprise des pompes avec `desired_run=true`

| Situation | Résultat |
|-----------|----------|
| HA redémarre, pompe arrêtée volontairement | Reste arrêtée |
| HA redémarre, pompe était en marche | Reprise RPM/GPM |
| Contrôle panneau était ON | Réaffirme le contrôle local, pas de resume HA |
| Coupure électrique **pompe** (HA toujours up) | Watchdog restaure mode + consigne si `desired_run` |
| Débranchement USB RS485 | Tentative de reconnexion automatique |

---

## Automations utiles

### Vitesse selon température d’eau

```yaml
alias: Pompe — courbe température
trigger:
  - platform: state
    entity_id: sensor.temperature_eau
action:
  - choose:
      - conditions:
          - condition: numeric_state
            entity_id: sensor.temperature_eau
            below: 18
        sequence:
          - service: number.set_value
            target:
              entity_id: number.pompe_piscine_vitesse_rpm
            data:
              value: 1200
      - conditions:
          - condition: numeric_state
            entity_id: sensor.temperature_eau
            above: 26
        sequence:
          - service: number.set_value
            target:
              entity_id: number.pompe_piscine_vitesse_rpm
            data:
              value: 2200
    default:
      - service: number.set_value
        target:
          entity_id: number.pompe_piscine_vitesse_rpm
        data:
          value: 1600
```

Adaptez les `entity_id` à votre installation (noms dérivés du friendly name + entry).

### Filtrage matin / soir

```yaml
alias: Pompe — marche 8h–20h
trigger:
  - platform: time
    at: "08:00:00"
  - platform: time
    at: "20:00:00"
action:
  - choose:
      - conditions:
          - condition: time
            after: "08:00:00"
            before: "20:00:00"
        sequence:
          - service: switch.turn_on
            target:
              entity_id: switch.pompe_piscine_marche
    default:
      - service: switch.turn_off
        target:
          entity_id: switch.pompe_piscine_marche
```

### Ne pas commander si panneau actif

```yaml
condition:
  - condition: state
    entity_id: switch.pompe_piscine_controle_panneau_boutons_pompe
    state: "off"
```

---

## Services

Domaine : `pentair_rs485`

### `pentair_rs485.run_program`

| Champ | Description |
|-------|-------------|
| `pump_index` | Index config (1–16) |
| `program` | `0` = stop, `1`–`4` = programme |

### `pentair_rs485.save_program`

| Champ | Description |
|-------|-------------|
| `pump_index` | Index config |
| `program` | Slot 1–4 |
| `speed` | RPM ou GPM selon le profil de commande |

### `pentair_rs485.set_speed`

| Champ | Description |
|-------|-------------|
| `pump_index` | Index config (1–16) |
| `rpm` | Optionnel, 450–3450 — démarre la pompe |
| `gpm` | Optionnel, 15–130 — démarre la pompe |

Fournir `rpm` et/ou `gpm`.

### `pentair_rs485.set_power`

| Champ | Description |
|-------|-------------|
| `pump_index` | Index config (1–16) |
| `power` | `true` = marche (renvoie la dernière consigne RPM/GPM si connue), `false` = arrêt |

---

## Dépannage

| Symptôme | Pistes |
|----------|--------|
| Intégration ne démarre pas | Port incorrect ; droits série ; autre process sur le port |
| Capteur **RS485 online** OFF | Adaptateur / droits série / USB débranché |
| Capteur **Pompe en ligne** OFF | Câblage A/B, masse, adresse index, alimentation pompe |
| Commandes sans effet | Vérifier que **Contrôle panneau** est OFF |
| Pompe redémarre seule après reboot HA | Vérifier l’attribut `desired_run` du switch Marche |
| Boost qui ne se déclenche pas | Options → capteur volet ; switch boost ON ; panneau OFF ; états `open`/`on` |
| Doublons d’entités après upgrade | Anciens `unique_id` : supprimer les entités orphelines dans HA |
| USB qui disparaît | Reconnexion auto ; préférer `/dev/serial/by-id/…` |
| Intégration grisée / indisponible | v0.7.0 : le bus down n’empêche plus le chargement ; les capteurs live passent `unavailable`, les commandes restent utilisables |

Logs utiles : **Paramètres → Système → Journaux**, filtre `pentair_rs485`.

---

## Limites connues

- Les **plannings horaires** et **courbes saison / température** ne sont pas stockés dans la pompe : utilisez les automations HA.
- En **Contrôle panneau ON**, le statut RS485 n’est plus pollé (affichage figé sur la dernière valeur connue) — voulu pour ne pas voler le bus.
- Changement de schéma `unique_id` (v0.6.2) : possibles entités orphelines à nettoyer une fois.
- Pas de support IntelliCenter / EasyTouch en maître concurrent sur le même bus (intégration conçue en **standalone**).
- Les entités GPM sont masquées / indisponibles sur une pompe **VS**. **VF** (WhisperFlo) garde RPM *et* GPM, comme en 0.5.2.

---

## Nouveautés v0.7.2

- **Reconfigurer** affiche les pompes déjà enregistrées : décochez pour enlever une pompe fantôme (ex. VS indisponible).
- Les appareils / entités orphelins sont retirés du registre HA au rechargement.

## Nouveautés v0.7.0

Fiabilité :

- L’intégration **charge même si le port USB est absent** (retry en arrière-plan, plus de `ConfigEntryNotReady` bloquant).
- Poll multi-pompes : on attend la **bonne** pompe, plus la première trame venue.
- Pompe marquée **offline** après 3 polls sans réponse (dernier statut conservé, plus de valeurs « fantômes » présentées comme live).
- Watchdog : rattrape aussi une pompe « allumée » à la **mauvaise vitesse** ; ignore amorçage et boost volet.
- **Stop programme** coupe vraiment `desired_run` (plus de relance au reboot HA).
- Marche ON **renvoie la consigne** RPM/GPM, pas seulement le paquet power.
- Boost volet : **n'écrase plus** la consigne utilisateur ; ne relance pas une pompe qui était arrêtée ; ignore l'état `closing` (boost jusqu'à `closed`).
- I/O série sur un **thread dédié** ; logs de statut passés en debug.

Fonctions / usage :

- Capteur binaire **Pompe en ligne** ; diagnostics HA (menu Intégration → Télécharger les diagnostics).
- Services `set_speed` / `set_power` ; intervalle de poll configurable ; liste des ports série dans le config flow.
- Profil de commande persisté, sans démarrer la pompe au changement RPM/GPM.

---

## Compatibilité pompes

| Type | RPM | GPM | Notes |
|------|-----|-----|-------|
| **VS** | Oui | — | Profil RPM par défaut |
| **VF** | Oui | Oui | WhisperFlo : RPM par défaut (comme 0.5.2), GPM via le profil |
| **VSF** | Oui | Oui | Basculable via **Profil de commande** |

---

## Licence & crédits

Protocole inspiré des travaux communautaires Pentair RS485 (ex. nodejs-poolController).  
Intégration Home Assistant : dépôt **Pentair-Pump-HA**.

Questions / bugs : ouvrez une issue sur le dépôt GitHub.
