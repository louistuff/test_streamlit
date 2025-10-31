import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
import json

creds_dict = json.loads(st.secrets["gcp_service_account"])
creds = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
client = gspread.authorize(creds)


# --- Configuration Streamlit ---
st.set_page_config(page_title="Questionnaire conditionnel", page_icon="🧠", layout="centered")

# --- Connexion Google Sheets ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = "service_account.json"   # ton fichier d'identifiants
SHEET_NAME = "Questionnaire_Responses"          # nom de ta feuille Google Sheets

@st.cache_resource
def connect_to_gsheet():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPE)
    client = gspread.authorize(creds)
    try:
        sheet = client.open(SHEET_NAME).sheet1
    except gspread.SpreadsheetNotFound:
        st.error(f"Feuille '{SHEET_NAME}' introuvable. Vérifie le partage et le nom.")
        st.stop()
    return sheet

sheet = connect_to_gsheet()

# --- Lecture du fichier Excel ---
@st.cache_data
def load_questions(file_path):
    return pd.read_excel(file_path)

questions_df = load_questions("questions.xlsx")

# --- Initialisation session ---
if "page" not in st.session_state:
    st.session_state.page = 1
if "responses" not in st.session_state:
    st.session_state.responses = {}

# --- Navigation ---
def next_page():
    st.session_state.page += 1

def prev_page():
    st.session_state.page = max(1, st.session_state.page - 1)

# --- Sauvegarde vers Google Sheets ---
def save_to_gsheet(responses):
    responses["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    headers = sheet.row_values(1)
    if not headers:
        sheet.insert_row(list(responses.keys()), 1)
        sheet.insert_row(list(responses.values()), 2)
    else:
        sheet.append_row(list(responses.values()))

# --- Interface ---
st.title("🧠 Questionnaire connecté à Google Sheets")

current_page = st.session_state.page
pages = sorted(questions_df["page"].unique())
st.markdown(f"### Page {current_page}/{len(pages)}")

# --- Questions de la page actuelle ---
page_questions = questions_df[questions_df["page"] == current_page]

for _, row in page_questions.iterrows():
    qid = row["id"]
    qtext = row["question"]
    qtype = row["type"]
    options = str(row["options"]).split(";") if pd.notna(row["options"]) else []
    condition = row["condition"]

    # Condition dynamique
    if pd.notna(condition) and condition.strip():
        try:
            if not eval(condition, {}, st.session_state.responses):
                continue
        except Exception as e:
            st.warning(f"Condition invalide pour {qid}: {condition}")
            continue

    # Rendu de la question
    if qtype == "text":
        st.session_state.responses[qid] = st.text_input(qtext, st.session_state.responses.get(qid, ""))
    elif qtype == "number":
        st.session_state.responses[qid] = st.number_input(qtext, value=st.session_state.responses.get(qid, 0))
    elif qtype == "select":
        st.session_state.responses[qid] = st.selectbox(qtext, options, index=options.index(st.session_state.responses[qid]) if qid in st.session_state.responses else 0)
    elif qtype == "yesno":
        st.session_state.responses[qid] = st.radio(qtext, ["Oui", "Non"], index=0 if st.session_state.responses.get(qid) == "Oui" else 1)
    else:
        st.warning(f"Type de question inconnu : {qtype}")

# --- Navigation / Validation ---
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    if current_page > 1:
        st.button("⬅️ Précédent", on_click=prev_page)

with col3:
    if current_page < len(pages):
        st.button("Suivant ➡️", on_click=next_page)
    else:
        if st.button("✅ Terminer et envoyer"):
            save_to_gsheet(st.session_state.responses)
            st.success("✅ Réponses enregistrées dans Google Sheets !")
            st.session_state.responses = {}
            st.session_state.page = 1

# --- Aperçu en cours ---
st.divider()
with st.expander("📋 Réponses temporaires"):
    st.json(st.session_state.responses)

