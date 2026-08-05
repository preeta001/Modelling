import streamlit as st
import os

def render_documentation_page():
    st.set_page_config(page_title="Model Documentation", page_icon="📚", layout="wide")
    
    st.title("📚 Model Documentation")
    
    doc_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "DOCUMENTATION.md")
    
    try:
        with open(doc_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
            
        # Streamlit's markdown renderer supports most standard markdown
        st.markdown(markdown_content, unsafe_allow_html=True)
        
    except FileNotFoundError:
        st.error(f"Could not find {doc_path}. Please ensure the documentation file exists.")

if __name__ == "__main__":
    render_documentation_page()
