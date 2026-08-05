import streamlit as st
import pandas as pd
from coating_model.data_loader import load_and_clean_batch_data

st.title("Data Upload & Quality Check")

uploaded_file = st.file_uploader("Upload Batch Data (CSV or Excel)", type=['csv', 'xlsx', 'xls'])

if uploaded_file is not None:
    # Save temporarily to parse
    with open("sample_data/temp_upload.csv", "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    try:
        df = load_and_clean_batch_data("sample_data/temp_upload.csv")
        st.success("Data loaded and cleaned successfully!")
        
        st.subheader("Data Preview")
        st.dataframe(df.head())
        
        st.subheader("Quality Report")
        col1, col2, col3 = st.columns(3)
        col1.metric("Rows", len(df))
        if 'T_inlet' in df.columns:
            col2.metric("Max Inlet Temp", f"{df['T_inlet'].max():.1f} °C")
        if 'spray_rate' in df.columns:
            col3.metric("Max Spray Rate", f"{df['spray_rate'].max():.1f} g/min")
            
        st.info("In a full implementation, this page will run the Phase Machine to auto-detect preheat, spray, and drying phases.")
    except Exception as e:
        st.error(f"Error processing file: {e}")
