# EcoAgent — Smart Home Energy Assistant

A Streamlit demo project with user registration/login, appliance energy estimation, Random Forest prediction, SQLite persistence, monthly/yearly projections, estimated CO₂, CSV/PDF reports, and an admin dashboard.

## 1. Install

Use Python 3.10–3.12 if possible. Open a terminal in this folder:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

On macOS/Linux activate with `source .venv/bin/activate`.

## 2. Dataset format

Place `smart_home_energy_consumption_large.csv` in this folder. Required columns:

- `hours`: daily operating hours
- `quantity`: number of appliances
- `watts`: power rating per appliance
- `temperature`: temperature in °C
- `kwh`: target energy value in kWh/day

Train the model:

```bash
python train_model.py
```

The model is saved as `energy_rf.joblib`. The app also attempts to train it on first prediction if the model file is absent. It cannot train without the dataset.

## 3. Run

User portal:

```bash
streamlit run app.py
```

Admin dashboard (in a second terminal):

```bash
streamlit run admin.py
```

Initial admin demo credentials: `admin` / `admin123`. Change the credentials and use a production-grade password-hashing approach before deployment.

## Important notes

- This project does not bundle or claim to provide the named real-world energy dataset. Add a dataset you have permission to use.
- The current weather field is manually entered; live Open-Meteo integration is not yet implemented in this build.
- State electricity tariffs are illustrative defaults, not verified current tariffs. Edit `STATE_TARIFF` in `db.py` for your project's assumptions.
- Monthly/yearly totals extrapolate the saved daily estimates across 30/365 days, rather than filtering by calendar month/year.
- CO₂ uses a simplified illustrative factor of 0.708 kg/kWh; replace with a sourced factor appropriate to your study.
- The Random Forest prediction is blended with the standard energy formula (hours × quantity × watts / 1000) to keep demo estimates physically plausible. It is an educational estimate, not a meter reading.
- Before production use, improve password hashing, add CSRF/session hardening and authorization checks, and secure the database and secrets.
