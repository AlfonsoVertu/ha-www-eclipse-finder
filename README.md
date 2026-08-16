# WWW Eclipse Finder — Home Assistant Add-on Repository

Repository di add-on per [Home Assistant](https://www.home-assistant.io/).

## 🌒 Eclipse Finder

Prevede la **prossima eclissi** (solare e lunare) usando le coordinate di casa già impostate in Home Assistant, e ti aiuta a capire **da quale finestra o balcone sarà meglio visibile** — con una **mappa a bussola** e la **foto della vista con l'eclissi sovrapposta**.

- Calcolo eclissi con la libreria [`astronomy-engine`](https://github.com/cosinekitty/astronomy) (data/ora, tipo, azimut, altezza, % di oscuramento, visibilità dal tuo punto).
- Wizard guidato per mappare finestre/balconi: **direzione via bussola del telefono** (DeviceOrientation) **o inserimento gradi a mano** (PC/senza magnetometro).
- **Foto per ogni finestra** + overlay del Sole/Luna nel punto stimato della vista.
- Interfaccia nel **menu laterale** di Home Assistant (Ingress).

## Installazione

1. In Home Assistant: **Impostazioni → Add-on → Store degli add-on**.
2. Menu in alto a destra (⋮) → **Repository**.
3. Incolla l'URL di questo repo:
   ```
   https://github.com/AlfonsoVertu/ha-www-eclipse-finder
   ```
4. Chiudi, aggiorna, e installa **Eclipse Finder** dall'elenco.
5. Avvia l'add-on e apri **Eclissi** dal menu laterale.

> **Nota bussola:** la lettura della bussola nel browser richiede un contesto sicuro (**HTTPS**). Apri Home Assistant tramite il tuo dominio HTTPS (o Nabu Casa) quando usi la cattura della direzione dal telefono. Su PC usa il campo "gradi a mano".

## Add-on inclusi

| Add-on | Descrizione |
|--------|-------------|
| [Eclipse Finder](./eclipse_finder) | Previsione eclissi + miglior finestra/balcone di casa, con mappa e overlay sulla foto |

## Licenza

MIT — vedi [LICENSE](./LICENSE).
