# Käypä hoito MCP Server

MCP-palvelin [Käypä hoito -suosituksille](https://www.kaypahoito.fi/suositukset) — Suomen kansalliset, näyttöön perustuvat hoitosuositukset.

## Työkalut

### `hae_suositukset`
Hae suosituksia hakusanalla WP Search -rajapinnasta.
- Parametri: `hakusana` (esim. `"diabetes"`, `"verenpaine"`, `"astma"`)
- Palauttaa: lista osumista otsikoilla ja URL-osoitteilla

### `hae_suositus`
Hae yksittäisen suosituksen sisältö URL:n perusteella.
- Parametri: `url` (esim. `"hoi50056"` tai `"https://www.kaypahoito.fi/hoi50056"`)
- Palauttaa: otsikko, päivityspäivä, tekijät ja osioidensisällöt

## Käynnistys paikallisesti

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

Testi: `python3 test_tools.py`

## Railway-deployaus

```bash
git init && git add . && git commit -m "Initial build"
railway link
railway up
```

## Yhteys Intriciin

- URL: `https://{railway-domain}.railway.app/mcp`
- Autentikointi: ei tarvita
