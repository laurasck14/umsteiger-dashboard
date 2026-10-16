# Umsteiger Dashboard

Local-first Python app for the Umsteiger daily challenge group.

What it does:
- Upload a WhatsApp chat export in `.txt` format.
- Extract one score row per person per day.
- Keep the parsed data on your machine in a local JSON state file.
- Show a daily score chart, an average-score chart, daily win totals, and a table of imported rows.
- Export the normalized data as CSV or JSON.

## Run It

1. Start the app.

```bash
python3 app.py
```

2. Open the local URL printed in the terminal.

3. Upload a WhatsApp `.txt` export, or a previously exported `.csv` or `.json` backup.

To create a dashboard that can be opened without the server, run:

```bash
python3 app.py --export-html umsteiger-dashboard.html
```

The generated HTML contains the charts, JavaScript, and local images, so it can be opened directly in a browser or shared as one file. While the server is running, use **Download offline HTML** for the same export.

## Run Tests

```bash
python3 -m unittest discover
```

## Local Storage

The app stores the most recently imported dataset in `.umsteiger_state.json` in the project root. Delete that file if you want to reset the app state.

## Input Format

The parser expects WhatsApp `.txt` exports with lines like:

```text
19.09.2026, 09:01 - Anna: 452
19.09.2026, 09:02 - Ben: umsteigen.app · Berlin 🚇 19. Sept. 390 / 500 · Umsteige-Profi 🟢–🟡–🟢–🟢–🟢
```

Only messages containing the app's formatted score, such as `390 / 500`, are treated as valid score entries. Bare numeric messages like `452` are ignored.

Daily wins are counted by comparing the highest score for each date. Every player tied for the highest score receives one win.

## Player Portraits

Place each participant's portrait in `assets/` with the exact dashboard player name as the filename, for example `Andrea Petrus.png`. PNG, JPEG, WebP, and GIF files are supported. The portrait is shown above that player's highest historical daily score and beside their name in the average-score chart.