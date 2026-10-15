from pathlib import Path
import pandas as pd
import numpy as np
import joblib

BASE=Path(__file__).resolve().parent
DATASET_PATH=BASE/'smart_home_energy_consumption_large.csv'
MODEL_PATH=BASE/'energy_rf.joblib'
FEATURES=['hours','quantity','watts','temperature']

def load_data():
    if not DATASET_PATH.exists(): raise FileNotFoundError(f'Dataset not found: {DATASET_PATH}')
    return pd.read_csv(DATASET_PATH,encoding='utf-8-sig')

def load_model():
    if not MODEL_PATH.exists():
        from train_model import train
        train()
    return joblib.load(MODEL_PATH)

def predict_kwh(hours,quantity,watts,temperature=25):
    x=pd.DataFrame([[float(hours),int(quantity),float(watts),float(temperature)]],columns=FEATURES)
    return max(0.0,float(load_model().predict(x)[0]))

def calculate_cost(kwh,state):
    from db import STATE_TARIFF
    return kwh*STATE_TARIFF.get(state,7.0)

def calculate_summary(usage_df,state):
    if usage_df.empty: return {'monthly_kwh':0,'monthly_cost':0,'yearly_kwh':0,'yearly_cost':0,'co2_kg':0,'score':100}
    # Each saved entry is a typical daily appliance estimate; aggregate estimates to monthly/yearly values.
    daily=float(usage_df['kwh'].sum()); rate=float(usage_df['cost'].sum())
    monthly_kwh=daily*30; monthly_cost=rate*30; yearly_kwh=daily*365; yearly_cost=rate*365
    co2=monthly_kwh*0.708
    score=max(0,min(100,100-monthly_kwh/20))
    return {'monthly_kwh':monthly_kwh,'monthly_cost':monthly_cost,'yearly_kwh':yearly_kwh,'yearly_cost':yearly_cost,'co2_kg':co2,'score':score}

def recommendations(usage_df):
    if usage_df.empty: return ['Add appliance usage to receive personalized energy-saving suggestions.']
    tips=[]
    top=usage_df.groupby('appliance')['kwh'].sum().sort_values(ascending=False)
    if not top.empty: tips.append(f"Your highest estimated daily energy user is {top.index[0]}. Reduce its runtime or use an efficient setting where practical.")
    if (usage_df['hours']>6).any(): tips.append('Review appliances recorded as running more than 6 hours per day and switch them off when not needed.')
    tips.append('Prefer LED lighting, efficient appliances, and standby-off habits to reduce avoidable consumption.')
    return tips


def get_live_weather(state):
    """Fetch current temperature for a state's capital via Open-Meteo; no API key required."""
    import requests
    capitals={'Andhra Pradesh':'Amaravati','Arunachal Pradesh':'Itanagar','Assam':'Dispur','Bihar':'Patna','Chhattisgarh':'Raipur','Goa':'Panaji','Gujarat':'Gandhinagar','Haryana':'Chandigarh','Himachal Pradesh':'Shimla','Jharkhand':'Ranchi','Karnataka':'Bengaluru','Kerala':'Thiruvananthapuram','Madhya Pradesh':'Bhopal','Maharashtra':'Mumbai','Manipur':'Imphal','Meghalaya':'Shillong','Mizoram':'Aizawl','Nagaland':'Kohima','Odisha':'Bhubaneswar','Punjab':'Chandigarh','Rajasthan':'Jaipur','Sikkim':'Gangtok','Tamil Nadu':'Chennai','Telangana':'Hyderabad','Tripura':'Agartala','Uttar Pradesh':'Lucknow','Uttarakhand':'Dehradun','West Bengal':'Kolkata'}
    place=capitals.get(state, 'New Delhi')
    geo=requests.get('https://geocoding-api.open-meteo.com/v1/search',params={'name':place,'count':1,'language':'en','format':'json'},timeout=8)
    geo.raise_for_status(); results=geo.json().get('results',[])
    if not results: raise ValueError(f'Could not find coordinates for {place}.')
    loc=results[0]
    weather=requests.get('https://api.open-meteo.com/v1/forecast',params={'latitude':loc['latitude'],'longitude':loc['longitude'],'current':'temperature_2m'},timeout=8)
    weather.raise_for_status(); current=weather.json().get('current',{})
    if 'temperature_2m' not in current: raise ValueError('Current temperature was not returned by the weather service.')
    return {'place':place,'temperature':float(current['temperature_2m']),'time':current.get('time','')}
