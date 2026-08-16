# Eclipse Finder

Add-on per Home Assistant che **prevede la prossima eclissi** (solare e lunare) dalle coordinate di casa e ti mostra **da quale finestra/balcone si vede meglio**, con mappa a bussola e overlay sulla foto della vista.

## Cosa fa

- Legge automaticamente **latitudine/longitudine** dalla configurazione di Home Assistant.
- Calcola la prossima **eclissi solare** e **lunare**: data/ora locale, tipo (parziale/totale/anulare/penombrale), **azimut + direzione bussola**, **altezza sull'orizzonte**, **% di oscuramento** e se è **visibile dal tuo punto**.
- **Wizard "Aggiungi finestra"**:
  1. Nome (es. *Balcone soggiorno*).
  2. Direzione: **bussola del telefono** (*Attiva bussola → Blocca direzione*) **oppure gradi a mano** (N=0, E=90, S=180, O=270).
  3. **Foto** della vista.
- Per ogni finestra mostra:
  - una **mappa a bussola** con il campo visivo della finestra e la posizione dell'eclissi;
  - la **foto con il Sole/Luna sovrapposto** nel punto stimato (o l'indicazione "ruota verso …" se fuori inquadratura).

## Uso

1. Installa e avvia l'add-on, poi apri **Eclissi** dal menu laterale.
2. Dal telefono (per la bussola serve **HTTPS**): apri Home Assistant via dominio HTTPS / Nabu Casa.
3. Aggiungi le tue finestre/balconi. L'add-on ti dirà da dove sarà visibile la prossima eclissi.

## Note tecniche

- Motore astronomico: [`astronomy-engine`](https://github.com/cosinekitty/astronomy).
- I dati (finestre + foto) sono salvati nel volume persistente `/data` dell'add-on.
- La bussola nel browser (DeviceOrientation API) funziona solo in **contesto sicuro (HTTPS)**; su desktop usa l'inserimento manuale dei gradi.
- L'altezza del Sole/Luna sulla foto è **stimata** (centro foto ~15°, FOV ~66°); l'accuratezza verticale migliorerà catturando l'inclinazione del telefono allo scatto (roadmap).

## Privacy

L'add-on non invia dati all'esterno: tutti i calcoli e i file (foto incluse) restano su Home Assistant.
