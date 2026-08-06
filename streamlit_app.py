import streamlit as st

st.set_page_config(
    page_title="Track A: Coating Model",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Glassmorphism Dark UI
st.markdown("""
<style>
    /* Global Background with subtle gradient */
    .stApp {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
        color: #c9d1d9;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: rgba(22, 27, 34, 0.8) !important;
        backdrop-filter: blur(15px);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Premium Glassmorphism Cards */
    .glass-card {
        background: rgba(33, 38, 45, 0.4);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .glass-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.12);
    }
    
    /* Headers with modern typography */
    h1, h2, h3 {
        color: #58a6ff !important;
        font-family: 'Inter', 'Roboto', sans-serif;
        font-weight: 600;
        letter-spacing: -0.5px;
    }
    
    h1 {
        background: -webkit-linear-gradient(45deg, #58a6ff, #a371f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Enhanced Metrics */
    div[data-testid="stMetricValue"] {
        color: #3fb950;
        font-weight: 700;
        font-size: 2.2rem !important;
    }
    
    div[data-testid="stMetricLabel"] {
        color: #8b949e;
        font-size: 0.95rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Modern Primary Buttons */
    button[kind="primary"] {
        background: linear-gradient(90deg, #238636 0%, #2ea043 100%) !important;
        border: none !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 15px rgba(46, 160, 67, 0.4) !important;
        transition: all 0.2s ease !important;
    }
    
    button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(46, 160, 67, 0.6) !important;
        background: linear-gradient(90deg, #2ea043 0%, #3fb950 100%) !important;
    }
    
    /* Dataframes */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# Initialize global session state for solvent overrides
if 'solvent_not_water' not in st.session_state:
    st.session_state.solvent_not_water = False
if 'custom_antoine_A' not in st.session_state:
    st.session_state.custom_antoine_A = 8.1182
if 'custom_antoine_B' not in st.session_state:
    st.session_state.custom_antoine_B = 1580.92
if 'custom_antoine_C' not in st.session_state:
    st.session_state.custom_antoine_C = 219.62
if 'custom_enthalpy_A' not in st.session_state:
    st.session_state.custom_enthalpy_A = -1.8199
if 'custom_enthalpy_B' not in st.session_state:
    st.session_state.custom_enthalpy_B = 815.0
if 'custom_Rv' not in st.session_state:
    st.session_state.custom_Rv = 138.3361

# Navigation Restructured to Track A Paradigm
pages = {
    "🏠 Home & Overview": [
        st.Page("app_pages/home.py", title="Home", icon="🏠"),
        st.Page("app_pages/documentation_page.py", title="Documentation", icon="📚")
    ],
    "🧪 STEP 1: MODEL VALIDATION": [
        st.Page("app_pages/validation_page.py", title="Model Calibration", icon="⚙️")
    ],
    "🔫 STEP 2: GUN VALIDATION": [
        st.Page("app_pages/gun_validation.py", title="Spray Pump Calibration", icon="🔫")
    ],
    "🔬 STEP 3: MODEL EXECUTION": [
        st.Page("app_pages/simulation_page.py", title="Simulation & Optimization", icon="📈"),
        st.Page("app_pages/spray_uniformity_page.py", title="Spray & Uniformity", icon="💧"),
        st.Page("app_pages/cqa_page.py", title="CQA Predictions", icon="🎯"),
        st.Page("app_pages/execution_summary.py", title="Execution Summary", icon="📋")
    ],
    "🎲 STEP 4: RISK & DESIGN SPACE": [
        st.Page("app_pages/uncertainty_page.py", title="Uncertainty & Risk", icon="🎲"),
    ],
    "📥 EXPORT": [
        st.Page("app_pages/export_page.py", title="Export Reports", icon="📥")
    ]
}

pg = st.navigation(pages)

with st.sidebar:
    st.markdown("---")
    st.subheader("⚙️ Global Process Settings")
    
    is_not_water = st.toggle("Solvent is NOT water", value=st.session_state.solvent_not_water)
    st.session_state.solvent_not_water = is_not_water
    st.session_state['global_solvent'] = "custom" if is_not_water else "water"
    
    if is_not_water:
        st.warning("Custom Solvent Physics Active. Defaults reflect Isopropyl Alcohol (IPA).")
        
        st.markdown("**Antoine Coefficients**\n`log10(P_sat) = A - B/(C+T)`")
        st.session_state.custom_antoine_A = st.number_input("Antoine A", value=st.session_state.custom_antoine_A)
        st.session_state.custom_antoine_B = st.number_input("Antoine B", value=st.session_state.custom_antoine_B)
        st.session_state.custom_antoine_C = st.number_input("Antoine C", value=st.session_state.custom_antoine_C)
        
        st.markdown("**Vapor Enthalpy**\n`h_v = A*T + B`")
        st.session_state.custom_enthalpy_A = st.number_input("Enthalpy A", value=st.session_state.custom_enthalpy_A)
        st.session_state.custom_enthalpy_B = st.number_input("Enthalpy B", value=st.session_state.custom_enthalpy_B)
        
        st.markdown("**Gas Constant**\n`R_u / MW`")
        st.session_state.custom_Rv = st.number_input("Gas Constant (R_v)", value=st.session_state.custom_Rv)

pg.run()
