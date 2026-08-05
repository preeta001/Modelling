import pandas as pd
import numpy as np

def load_and_clean_batch_data(filepath: str) -> pd.DataFrame:
    """
    Load a CSV or Excel file, standardize columns, and handle missing values.
    """
    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)
        
    # Lowercase columns and strip spaces for easier matching
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    col_map = {
        'time': 'time_min',
        'time (min)': 'time_min',
        'inlet temp': 'T_inlet',
        'inlet temp (c)': 'T_inlet',
        'exhaust temp': 'T_exhaust',
        'exhaust temp (c)': 'T_exhaust',
        'spray rate': 'spray_rate',
        'spray rate (g/min)': 'spray_rate',
        'airflow': 'airflow',
        'airflow (cfm)': 'airflow',
        'inlet rh': 'RH_inlet',
        'exhaust rh': 'RH_exhaust',
        'bed temp': 'T_bed'
    }
    
    df.rename(columns=col_map, inplace=True)
    
    if 'time_min' in df.columns:
        df['time_s'] = df['time_min'] * 60.0
    elif 'time_s' not in df.columns:
        df['time_s'] = np.arange(len(df)) * 60.0
        
    df.ffill(limit=5, inplace=True)
    
    if 'T_inlet' in df.columns:
        df['T_inlet'] = df['T_inlet'].clip(lower=0, upper=150)
    if 'RH_inlet' in df.columns:
        if df['RH_inlet'].max() > 1.5:
            df['RH_inlet'] = df['RH_inlet'] / 100.0
        df['RH_inlet'] = df['RH_inlet'].clip(lower=0.01, upper=0.99)
        
    return df

def generate_synthetic_batch(duration_min=120) -> pd.DataFrame:
    """Generate a realistic test CSV for demo/testing purposes."""
    time_min = np.arange(0, duration_min, 1.0)
    n = len(time_min)
    
    # Base profiles
    T_inlet = np.ones(n) * 60.0
    T_inlet[0:10] = np.linspace(25, 60, 10) # Ramp up
    T_inlet[-10:] = 40.0 # Cool down
    
    spray = np.zeros(n)
    spray[15:-20] = 50.0 # Spray phase
    
    airflow = np.ones(n) * 1200.0
    RH_inlet = np.ones(n) * 0.1
    
    # Measured outputs (mocked with physics + noise)
    # T_exh drops during spray
    T_exhaust = np.ones(n) * 55.0
    T_exhaust[15:-20] = 42.0 + np.random.normal(0, 0.5, len(spray[15:-20]))
    
    RH_exhaust = np.ones(n) * 0.15
    RH_exhaust[15:-20] = 0.65 + np.random.normal(0, 0.02, len(spray[15:-20]))
    
    T_bed = T_exhaust + 1.0 + np.random.normal(0, 0.2, n)
    
    df = pd.DataFrame({
        'time_min': time_min,
        'time_s': time_min * 60.0,
        'T_inlet': T_inlet,
        'airflow': airflow,
        'spray_rate': spray,
        'RH_inlet': RH_inlet,
        'T_exhaust': T_exhaust,
        'RH_exhaust': RH_exhaust,
        'T_bed': T_bed
    })
    return df

