# Hlava – Discord reader (read-only)

Malý skript pre môjho osobného AI asistenta („Hlava“), ktorý mi plánuje rozvrh a termíny.
Jeho jediná úloha: raz za čas prečítať najnovšie správy v pár vybraných kanáloch a uložiť
ich do lokálneho Markdown súboru, aby asistent vedel o oznamoch a termínoch stretnutí.

## Čo robí
- `GET /channels/{id}/messages` (REST, max. 100 správ) pre každý kanál v `DISCORD_CHANNELS`
- berie len správy za posledné `DISCORD_DAYS` dní (predvolene 3) a najviac 15 na kanál
- text skráti na 140 znakov, e-maily a telefónne čísla nahradí `[e-mail]` / `[číslo]`,
  označenia používateľov (`<@id>`) nahradí slovom `@niekto`
- výsledok zapíše do `discord-prehlad.md` na počítači majiteľa, stav do `state.json`

## Čo nerobí
- nič nepíše: žiadne správy, reakcie, DM, hlas
- nečíta DM, zoznam členov ani kanály mimo zoznamu `DISCORD_CHANNELS`
- nesťahuje prílohy, nič nikam neodosiela ani neukladá do cloudu
- nepoužíva gateway (websocket) ani privilegované intenty; stačí mu
  **View Channels** + **Read Message History** (permissions = 66560)

## Spustenie
```bash
pip install -r requirements.txt
cp .env.example .env   # doplniť DISCORD_BOT_TOKEN a DISCORD_CHANNELS
python -I -X utf8 hlava_discord_reader.py
```

Celý kód je v jednom súbore: [`hlava_discord_reader.py`](hlava_discord_reader.py).

---

*English:* read-only Discord reader for a personal AI planning assistant. Polls a few channels
over REST, masks contact data, keeps a trimmed local Markdown summary. Never posts, never
reads DMs or member lists, no gateway connection. Needs only View Channels + Read Message History.
