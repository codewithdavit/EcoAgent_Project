from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from tools import DATASET_PATH, MODEL_PATH, FEATURES

def train():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f'Place your smart home energy CSV at {DATASET_PATH}')
    df=pd.read_csv(DATASET_PATH)
    required=FEATURES+['kwh']
    missing=[c for c in required if c not in df.columns]
    if missing: raise ValueError('Dataset is missing required columns: '+', '.join(missing))
    df=df[required].apply(pd.to_numeric,errors='coerce').dropna()
    df=df[(df.hours>=0)&(df.quantity>0)&(df.watts>0)&(df.kwh>=0)]
    if len(df)<10: raise ValueError('At least 10 valid dataset rows are required to train the model.')
    X,y=df[FEATURES],df['kwh']
    X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=0.2,random_state=42)
    model=RandomForestRegressor(n_estimators=150,random_state=42,n_jobs=-1)
    model.fit(X_train,y_train)
    pred=model.predict(X_test)
    joblib.dump(model,MODEL_PATH)
    rmse=float(np.sqrt(mean_squared_error(y_test,pred)))
    metrics={'rows':len(df),'MAE':float(mean_absolute_error(y_test,pred)),'RMSE':rmse,'R2':float(r2_score(y_test,pred))}
    return model,metrics

if __name__=='__main__':
    _,m=train(); print('Model saved to',MODEL_PATH); print(m)
