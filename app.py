import streamlit as st
import google.generativeai as genai
from gtts import gTTS
from streamlit_mic_recorder import mic_recorder
import speech_recognition as sr
import io
from datetime import datetime
import PIL.Image
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Globule Robot", layout="centered", page_icon="💊")

# CSS for KIOSK MODE
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.big-font {
    font-size:26px !important;
    font-weight: bold;
    color: #2E86C1;
    text-align: center;
    margin-bottom: 20px;
}
.user-text {
    font-size:18px;
    color: #333;
    background-color: #f0f2f6;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    border-left: 5px solid #2E86C1;
}
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECT TO GOOGLE & DATABASE ---

# A. Gemini AI Setup
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"AI Error: {e}")
    st.stop()

# B. Google Sheets Connection
def get_google_sheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client.open("globule_database").sheet1
    except Exception as e:
        st.error(f"Database Error: {e}")
        return None

def find_patient(reg_no):
    sheet = get_google_sheet()
    if sheet:
        try:
            cell = sheet.find(str(reg_no))
            # Get the whole row
            return sheet.row_values(cell.row)
        except:
            return None
    return None

def save_patient(reg_no, name, phone, last_rx, notes=""):
    sheet = get_google_sheet()
    if sheet:
        date_now = datetime.now().strftime("%Y-%m-%d")
        try:
            cell = sheet.find(str(reg_no))
            # Update Existing
            sheet.update_cell(cell.row, 4, last_rx)
            sheet.update_cell(cell.row, 5, date_now)
            sheet.update_cell(cell.row, 6, notes) # Save notes in Col F
        except:
            # Create New: RegNo, Name, Phone, Rx, Date, Notes
            sheet.append_row([str(reg_no), name, str(phone), last_rx, date_now, notes])

# --- 3. AUDIO FUNCTIONS ---
def speak_text(text):
    try:
        # Only speak the first sentence to be fast
        short_text = text.split('.')[0]
        tts = gTTS(text=short_text, lang='hi', slow=False)
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        st.audio(audio_bytes, format='audio/mp3', autoplay=True)
    except:
        pass

def recognize_audio(audio_bytes):
    r = sr.Recognizer()
    try:
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data, language="hi-IN") # Hindi input
        return text
    except:
        return None

# --- 4. SESSION STATE ---
if "step" not in st.session_state: st.session_state.step = 0
if "case_data" not in st.session_state: st.session_state.case_data = {}
if "patient_type" not in st.session_state: st.session_state.patient_type = "Chronic"

# --- 5. APP FLOW ---

st.image("https://cdn-icons-png.flaticon.com/512/3774/3774299.png", width=60) 
st.markdown("<h2 style='text-align: center;'>Dr. Robot (Globule Goals)</h2>", unsafe_allow_html=True)

# STEP 0: RECEPTION
if st.session_state.step == 0:
    st.markdown('<p class="big-font">नमस्ते! इलाज शुरू करने के लिए चुनें।</p>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    if c1.button("नया (New Case)"):
        st.session_state.patient_type = "Chronic"
        st.session_state.step = 1
        st.rerun()
    if c2.button("चोट/बुखार (Acute)"):
        st.session_state.patient_type = "Acute"
        st.session_state.step = 1
        st.rerun()
    if c3.button("पुराना (Follow-up)"):
        st.session_state.patient_type = "Old"
        st.session_state.step = 1
        st.rerun()

# STEP 1: REGISTRATION / LOOKUP
if st.session_state.step == 1:
    if st.session_state.patient_type in ["Chronic", "Acute"]:
        st.markdown('<p class="big-font">नाम और नंबर बताएं</p>', unsafe_allow_html=True)
        reg_no = datetime.now().strftime("%d%H%M")
        
        with st.form("new_pt"):
            name = st.text_input("Name")
            phone = st.text_input("Mobile")
            if st.form_submit_button("Start Case"):
                st.session_state.case_data = {"Name": name, "RegNo": reg_no, "Phone": phone}
                save_patient(reg_no, name, phone, "Started")
                st.session_state.step = 2
                st.rerun()
                
    else: # OLD PATIENT LOGIC
        st.markdown('<p class="big-font">रजिस्ट्रेशन नंबर लिखें</p>', unsafe_allow_html=True)
        reg_input = st.text_input("Reg No:")
        if st.button("Search"):
            data = find_patient(reg_input)
            if data:
                # Load Data
                st.session_state.case_data = {
                    "RegNo": data[0], 
                    "Name": data[1], 
                    "Phone": data[2], 
                    "LastRx": data[3] if len(data) > 3 else "None"
                }
                st.success(f"Found: {data[1]}")
                st.session_state.step = 15 # Go to Follow-up
                st.rerun()
            else:
                st.error("Patient Not Found")

# STEP 2-8: MAIN INTERVIEW (New/Acute)
steps_map = {
    2: "मुख्य समस्या क्या है? (Chief Complaint)",
    3: "यह कब शुरू हुआ? (Onset)",
    4: "कब बढ़ता या घटता है? (Modalities)",
    5: "कोई और तकलीफ? (Concomitants)",
    6: "पुरानी बीमारी या इतिहास? (History)",
    7: "प्यास और भूख कैसी है? (Generals)",
    8: "स्वभाव कैसा है? (Mentals)",
}

last_step = 5 if st.session_state.patient_type == "Acute" else 8

if 2 <= st.session_state.step <= last_step:
    current_q = steps_map[st.session_state.step]
    st.markdown(f'<p class="big-font">{current_q}</p>', unsafe_allow_html=True)
    
    # Text Input Backup (Because Audio fails on mobile sometimes)
    text_input = st.chat_input("Type answer here if mic fails...")
    
    # Audio Input
    audio = mic_recorder(start_prompt="🎤 Speak", stop_prompt="⏹ Stop", key=f"mic_{st.session_state.step}")
    
    user_response = None
    
    if text_input:
        user_response = text_input
    elif audio:
        user_response = recognize_audio(audio['bytes'])
    
    if user_response:
        st.markdown(f'<p class="user-text">{user_response}</p>', unsafe_allow_html=True)
        st.session_state.case_data[f"Q{st.session_state.step}"] = user_response
        
        # Next Button Logic
        if st.button("Next Question ->", type="primary"):
            st.session_state.step += 1
            # Check if done
            is_done = (st.session_state.patient_type == "Acute" and st.session_state.step > 5) or (st.session_state.step > 8)
            if is_done:
                st.session_state.step = 10 # Go to Camera
            st.rerun()

# STEP 15: FOLLOW-UP (SPECIAL KEYNOTE LOGIC)
if st.session_state.step == 15:
    name = st.session_state.case_data.get('Name')
    last_rx = st.session_state.case_data.get('LastRx')
    
    st.markdown(f'<p class="big-font">Welcome back {name}.<br>Last Medicine: {last_rx}</p>', unsafe_allow_html=True)
    
    # A. General Update
    st.write("1. दवा लेने के बाद कैसा महसूस हुआ? (General Update)")
    fu_gen = st.text_input("Answer 1")
    
    # B. AI Generates KEYNOTE QUESTIONS based on Last Rx
    if "keynote_q" not in st.session_state:
        with st.spinner("Analyzing Last Prescription..."):
            prompt = f"Patient took {last_rx}. Create 1 simple 'Yes/No' question in Hindi based on the Keynote of this remedy to check if the symptom still exists."
            res = model.generate_content(prompt)
            st.session_state.keynote_q = res.text
            
    st.write(f"2. Specific Check: {st.session_state.keynote_q}")
    fu_keynote = st.text_input("Answer 2 (Yes/No)")
    
    if st.button("Analyze Follow-up"):
        if fu_gen:
            st.session_state.case_data["FollowUp_Report"] = f"General: {fu_gen}. Keynote Check ({st.session_state.keynote_q}): {fu_keynote}"
            st.session_state.step = 11 # Go to Analysis
            st.rerun()

# STEP 10: CAMERA
if st.session_state.step == 10:
    st.markdown('<p class="big-font">जीभ या चेहरे की फोटो (Tongue/Face)</p>', unsafe_allow_html=True)
    img = st.camera_input("Camera")
    
    c1, c2 = st.columns(2)
    if img:
        st.session_state.case_data["Img"] = img
        st.session_state.step = 11
        st.rerun()
    if c2.button("Skip Photo"):
        st.session_state.case_data["Img"] = None
        st.session_state.step = 11
        st.rerun()

# STEP 11: FINAL ANALYSIS
if st.session_state.step == 11:
    st.markdown('<p class="big-font">Dr. Robot Thinking...</p>', unsafe_allow_html=True)
    
    if "final_rx" not in st.session_state:
        with st.spinner("Analyzing Miasms & Rubrics..."):
            
            # Prepare Data
            pt_data = str(st.session_state.case_data)
            has_img = st.session_state.case_data.get("Img") is not None
            
            prompt = f"""
            You are an expert Homeopath.
            Analyze this case carefully.
            
            PATIENT DATA: {pt_data}
            
            TASK:
            1. Analyze the Mental & Physical Generals.
            2. If this is a Follow-up, decide if the remedy needs to be repeated (Placebo/SL) or changed based on the Keynote answer.
            3. Suggest ONE Final Remedy with Potency and Dosage.
            4. Explain WHY in simple Hindi/English mix.
            """
            
            try:
                if has_img:
                    img_file = PIL.Image.open(st.session_state.case_data["Img"])
                    response = model.generate_content([prompt, img_file])
                else:
                    response = model.generate_content(prompt)
                
                st.session_state.final_rx_text = response.text
                
                # Extract Remedy Name (First line usually)
                rx_short = response.text.splitlines()[0]
                save_patient(
                    st.session_state.case_data["RegNo"],
                    st.session_state.case_data.get("Name"),
                    st.session_state.case_data.get("Phone"),
                    rx_short,
                    notes=response.text[:200]
                )
                
            except Exception as e:
                st.session_state.final_rx_text = f"Error: {e}"

    st.success("Prescription Generated!")
    st.write(st.session_state.final_rx_text)
    speak_text("इलाज तैयार है। " + st.session_state.final_rx_text[:100])
    
    if st.button("Finish & New Patient"):
        st.session_state.clear()
        st.rerun()
    
