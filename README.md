# 🌱 Embryo Risk Insights (Demo)

Full-stack demo inspired by Orchid’s embryo sequencing workflow. **Not clinical** — synthetic data only.  
Shows generalist engineering across **frontend**, **backend**, **ML integration**, **PDF reporting**, and **infra**.

## ✨ Highlights
- **Frontend**: Flask + Jinja, clean UI, Chart.js risk bars, monogenic **badges**, carrier **chip** on cards
- **Backend**: Token-gated JSON API (`/api/embryos`, `/api/embryos/<id>`), SQLite notes & appointments
- **Reports**: Per-embryo PDF via ReportLab (watermark + disclaimer)
- **ML (toy PRS)**: Logistic-style risk per condition from SNPs; monogenic penalties; overall 0–100
- **Infra**: `.env` config, Dockerfile, smoke tests, deploy-ready

## 🚀 Quickstart
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
# open http://127.0.0.1:8000
