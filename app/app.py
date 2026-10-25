"""NBA Birthday Explorer: a local website over the nba database.

    .venv\\Scripts\\streamlit run app\\app.py

Then open http://localhost:8501 in a browser. Ctrl+C in the terminal stops it.
This file only sets up the pages; each page is its own file in this folder.
"""
import streamlit as st

st.set_page_config(page_title="NBA Birthday Explorer", page_icon="🏀", layout="wide")

page = st.navigation([
    st.Page("player_explorer.py", title="Player explorer", icon="🏀", default=True),
    st.Page("today.py", title="Today", icon="🎂"),
])
page.run()
