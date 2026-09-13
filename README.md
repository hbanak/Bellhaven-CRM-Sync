# Bellhaven-CRM-Sync
Reconciles the Bellhaven Senior Living website against the CRM. Scrapes every community listing on the site, matches each one to a CRM account, and proposes fixes for anything incorrect including wrong parent, old name, duplicate records, accounts that are no longer on website.

## What it does
1. Scrapes every community location listed on the Bellhaven website.
2. Matches each scraped location to a CRM account and classifies results.
3. Proposes updates for accounts under the Bellhaven parent account that are not on the website.
5. Only performs a write action with explicit approval by a human.

## Setup
```bash
pip install -r requirements.txt
```

## Run
```bash
python main.py
```

## Known Limitation: Scheduling
`.github/workflows/daily.yaml` shows the daily cron schedule this is intended to run on. It is not expected to run successfully as committed as the current script is interactive using `input()` prompts which cannot be answered.

## Known Security Risk: Auth Token
`main.py` includes a hard coded API token for simplicity. In a production system this would be pulled from an environment variable or secrets manager rather than committed to source control.
