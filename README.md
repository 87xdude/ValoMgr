# ValoMgr – Riot Account Manager (Valorant / League of Legends / TFT)

Aus Jucks und tollerei von ChatGPT und mir zusammengeschustert.

---

## 📦 Download

➡️ **Lade die aktuelle Version unter Releases:**  
https://github.com/87xdude/ValoMgr/releases

Lade die ZIP herunter, entpacke sie, und starte `AccountMgr.exe`.

---

## 🔑 API-Schlüssel (erforderlich)

Für Rang-Abrufe werden **zwei** Dienste benötigt:

1. **Riot Developer Portal** (offiziell)  
   Registriere dich und erstelle einen **Developer API Key** (temporär):  
   https://developer.riotgames.com/

2. **HenrikDev (Valorant API)**  
   Trete dem Discord bei und fordere dort einen API-Key an:  
   https://discord.com/invite/X3GaVkX2YN

> **Hinweise & Fehlermeldungen**
> - **401/403 „Unknown apikey/Forbidden“** bei Riot → Key abgelaufen/neu generieren.  
> - **403 bei /tft/** → Im Riot Dev Portal das **Produkt „Teamfight Tactics“** aktivieren, dann **neuen** Key erzeugen.
> - Keys sind streng rate-limitiert; zu viele Anfragen blockieren zeitweise weitere Requests.

---

## 🧰 Features

- 🗂️ Getrennte Verwaltung für **Valorant**, **LoL** und **TFT**
- 🏅 Rang-Abruf inkl. Rank-Icons (Valorant über HenrikDev; LoL/TFT über Riot)
- 🔐 **Verschlüsselter Vault** (Passwort, kein Klartext)
- 🔑 **KeePassXC-Auto-Type** Login in den Riot Client (keine Passwörter im Manager nötig)
- ⚙️ Einstellungsdialog für **APIs**, **Pfade** (Riot Client, Icons, …) und Hotkeys
- 🔁 Batch-Update (alle Accounts aktualisieren), Caching & Retry-Logik
- 🌍 Region-Erkennung (RiotID `Name#Tag`)
- 📤 Export/📥 Import des verschlüsselten Vaults
- 🧱 Optionale App-Sperre („Gesperrt“-Zustand) ohne Programmende
- 🧪 Portable EXE (PyInstaller), Ressourcen neben der EXE (schneller Start)

---

## 🚀 Schnellstart

1. **Downloaden & starten**: ZIP aus Releases entpacken, `AccountMgr.exe` ausführen.  
2. **Vault anlegen/entsperren**: Beim ersten Start Passwort setzen.  
3. **Einstellungen öffnen**:
   - **Riot API Key** eintragen  
   - **HenrikDev API Key** eintragen (Basis-URL i. d. R. `https://api.henrikdev.xyz`)  
   - Optional: **Riot Client Pfad** (für Auto-Type Login)
4. **Accounts hinzufügen**: `RiotID` (z. B. `Nickname#0815`) anlegen, Spiel zuordnen.
5. **Rang abrufen**: Konto auswählen → „Rank aktualisieren“.

---

## 🔏 KeePassXC-Integration (Auto-Type)

- Aktiviere in **KeePassXC** Auto-Type und erstelle einen Eintrag pro Account (Titel oder benutzerdefiniertes Feld = **RiotID**).
- Im Manager kannst du für jeden Account einen **KeePassXC-Eintragsschlüssel** hinterlegen (z. B. exakt die RiotID).  
- Beim **Login**:
  1. Der Manager fokussiert den **„Riot Client“** (ohne das Spiel zu starten).
  2. Optional prüft er, ob das **Benutzername-Feld** aktiv ist.
  3. Dann wird **Auto-Type** ausgelöst (Username/Password aus KeePassXC, **nicht** aus dem Manager).

> Vorteil: Im Manager sind keine PW gespeichert; nur Referenz auf den KeePass-Eintrag.

---

## ⚙️ Konfiguration & Pfade

- **Vault-Pfad**: wird automatisch auf einen stabilen, **nicht-Temp**-Ort gelegt.  
  Du kannst ihn via **Einstellungen** oder Umgebungsvariable überschreiben:
  - `CVALOMGR_VAULT` – absoluter Pfad zu `vault.dat`
- **Icons**: Valorant-Rank-Icons können lokal bereitgestellt werden (z. B. `app/resources/valo_tracker_icons/…`).  
  Dateinamen folgen dem Rang (`dia1.png`, `asc3.png`, …); der Manager findet sie automatisch.
- **Taskleisten-Icon**: `app/resources/exe_logo.ico` (Multi-Size-ICO) wird als App-Icon verwendet.

---
