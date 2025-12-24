import streamlit as st
import google.generativeai as genai
from gtts import gTTS
from streamlit_mic_recorder import mic_recorder
import speech_recognition as sr
import io
from datetime import datetime
import PIL.Image
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Globule Goals Robot", layout="centered")

# CSS for KIOSK MODE
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Robot Question Text */
.big-font {
    font-size:32px !important;
    font-weight: bold;
    color: #2E86C1;
    text-align: center;
    line-height: 1.4;
    margin-bottom: 20px;
    font-family: 'Arial', sans-serif;
}

/* User Answer Text */
.user-text {
    font-size:20px;
    color: #333;
    background-color: #e8f4f8;
    padding: 15px;
    border-radius: 12px;
    margin: 10px 0;
    border-left: 5px solid #2E86C1;
}

/* Button Styling */
.stButton button {
    height: 3em;
    width: 100%;
    font-size: 20px;
}
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECT TO GOOGLE & DATABASE ---

# A. Gemini AI Setup
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("Error: GEMINI_API_KEY missing.")
    st.stop()

# B. Google Sheets Connection
def get_google_sheet():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
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
            if cell:
                row_values = sheet.row_values(cell.row)
                if len(row_values) >= 4:
                    return row_values
        except gspread.exceptions.CellNotFound:
            return None
    return None

def save_patient(reg_no, name, phone, last_rx):
    sheet = get_google_sheet()
    if sheet:
        date_now = datetime.now().strftime("%Y-%m-%d")
        try:
            cell = sheet.find(str(reg_no))
            sheet.update_cell(cell.row, 4, last_rx)
            sheet.update_cell(cell.row, 5, date_now)
        except gspread.exceptions.CellNotFound:
            sheet.append_row([str(reg_no), name, str(phone), last_rx, date_now])

# --- 3. AUDIO FUNCTIONS ---

def speak_text(text):
    try:
        tts = gTTS(text=text, lang='hi', slow=False)
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
            text = r.recognize_google(audio_data, language="hi-IN")
        return text
    except:
        return None

# --- 4. SESSION STATE ---
if "step" not in st.session_state: st.session_state.step = 0
if "case_data" not in st.session_state: st.session_state.case_data = {}
if "patient_type" not in st.session_state: st.session_state.patient_type = "Chronic"
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

# --- 5. APP FLOW ---

st.image("https://cdn-icons-png.flaticon.com/512/3774/3774299.png", width=80) 
st.markdown("<h2 style='text-align: center;'>Dr. Robot (Globule Goals)</h2>", unsafe_allow_html=True)

# STEP 0: RECEPTION (TRIAGE)
if st.session_state.step == 0:
    st.markdown('<p class="big-font">नमस्ते! इलाज शुरू करने के लिए चुनें।</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("नया मरीज (New Case)"):
            st.session_state.patient_type = "Chronic" # Full Case
            st.session_state.step = 1
            st.rerun()
            
    with col2:
        if st.button("चोट / बुखार (Acute)"):
            st.session_state.patient_type = "Acute"   # Fast Case
            st.session_state.step = 1
            st.rerun()
            
    with col3:
        if st.button("पुराना मरीज (Follow-up)"):
            st.session_state.patient_type = "Old"
            st.session_state.step = 1
            st.rerun()

# STEP 1: REGISTRATION
if st.session_state.step == 1:
    if st.session_state.patient_type in ["Chronic", "Acute"]:
        st.markdown('<p class="big-font">विवरण भरें।</p>', unsafe_allow_html=True)
        reg_no = datetime.now().strftime("%d%H%M") 
        st.info(f"Reg No: **{reg_no}**")
        
        with st.form("new_patient"):
            name = st.text_input("Name")
            phone = st.text_input("Mobile")
            submit = st.form_submit_button("Start Case")
            
            if submit and name:
                st.session_state.case_data["Name"] = name
                st.session_state.case_data["RegNo"] = reg_no
                st.session_state.case_data["Phone"] = phone
                save_patient(reg_no, name, phone, "Case Started")
                speak_text(f"स्वागत है {name}. चलिए शुरू करते हैं।")
                st.session_state.step = 2
                st.rerun()

    else: # OLD PATIENT
        st.markdown('<p class="big-font">रजिस्ट्रेशन नंबर लिखें।</p>', unsafe_allow_html=True)
        reg_input = st.text_input("Reg No:")
        if st.button("Search"):
            data = find_patient(reg_input) 
            if data:
                name = data[1]
                last_rx = data[3]
                st.session_state.case_data["Name"] = name
                st.session_state.case_data["RegNo"] = reg_input
                st.session_state.case_data["LastRx"] = last_rx
                
                msg = f"स्वागत है {name}. पिछली बार दवा {last_rx} दी थी।"
                speak_text(msg)
                st.session_state.step = 15 # Follow Up
                st.rerun()
            else:
                st.error("Patient Not Found.")

# STEP 2-9: QUESTIONS (SMART LOGIC)
steps_map = {
    2: "मुख्य समस्या क्या है? (Chief Complaint)",
    3: "यह कब शुरू हुआ? (Onset)",
    4: "कब बढ़ता या घटता है? (Modalities)",
    5: "कोई और तकलीफ? (Concomitants)",
    6: "पुरानी बीमारी या ऑपरेशन? (History)",
    7: "प्यास और भूख कैसी है? (Generals)",
    8: "स्वभाव कैसा है? (Mentals)",
}

# ACUTE LOGIC: Stop after Q5. CHRONIC: Go to Q8.
last_step = 5 if st.session_state.patient_type == "Acute" else 8

if 2 <= st.session_state.step <= last_step:
    current_q = steps_map[st.session_state.step]
    st.markdown(f'<p class="big-font">{current_q}</p>', unsafe_allow_html=True)
    
    if f"spoken_{st.session_state.step}" not in st.session_state:
        speak_text(current_q)
        st.session_state[f"spoken_{st.session_state.step}"] = True
    
    audio = mic_recorder(start_prompt="बोलिये (Speak)", stop_prompt="रुकिए (Stop)", key=f"mic_{st.session_state.step}")
    
    if audio and audio['id'] != st.session_state.last_audio_id:
        st.session_state.last_audio_id = audio['id']
        text = recognize_audio(audio['bytes'])
        if text:
            st.markdown(f'<p class="user-text">{text}</p>', unsafe_allow_html=True)
            st.session_state.case_data[f"Q{st.session_state.step}"] = text
            if st.button("Next"):
                st.session_state.step += 1
                
                # CHECK: Are we done with questions?
                is_done_questioning = (st.session_state.patient_type == "Acute" and st.session_state.step > 5) or (st.session_state.step > 8)
                
                if is_done_questioning:
                    # SMART CAMERA LOGIC: Check for Skin Keywords
                    all_text = " ".join([str(v) for k,v in st.session_state.case_data.items()]).lower()
                    skin_keywords = ["skin", "rash", "khujli", "daad", "eczema", "psoriasis", "acne", "muhase", "chale", "ulcer", "boil", "foda", "jalan", "fungal", "ringworm", "wounds", "safed", "dag", "spot", "chehra", "face"]
                    
                    is_skin_case = any(word in all_text for word in skin_keywords)
                    st.session_state.image_type = "Lesion" if is_skin_case else "Tongue"
                    st.session_state.step = 10 # Go to Camera
                    
                st.rerun()

# STEP 15: FOLLOW UP
if st.session_state.step == 15:
    q = "दवा के बाद क्या बदलाव आया?"
    st.markdown(f'<p class="big-font">{q}</p>', unsafe_allow_html=True)
    audio = mic_recorder(start_prompt="Speak", stop_prompt="Stop", key="mic_fu")
    if audio and audio['id'] != st.session_state.last_audio_id:
        st.session_state.last_audio_id = audio['id']
        text = recognize_audio(audio['bytes'])
        if text:
            st.session_state.case_data["FollowUp_Report"] = text
            st.session_state.step = 10
            st.rerun()

# STEP 10: SMART CAMERA (Context Aware)
if st.session_state.step == 10:
    img_type = st.session_state.get("image_type", "Tongue")
    
    if img_type == "Lesion":
        msg = "कृपया अपनी त्वचा/समस्या दिखाएं। (Show Skin)"
        st.warning("Note: Keep phone 30cm away for focus.")
    else:
        msg = "जीभ बाहर निकालें (Tongue Diagnosis)."
        st.warning("Note: Do not get too close.")
        
    st.markdown(f'<p class="big-font">{msg}</p>', unsafe_allow_html=True)
    speak_text(msg)
    
    img = st.camera_input("Camera", label_visibility="collapsed")
    if img:
        st.session_state.case_data["Face_Img"] = img
        st.session_state.step = 11
        st.rerun()
    
    if st.button("Skip Photo (Low Light / Privacy)"):
        st.session_state.case_data["Face_Img"] = None
        st.session_state.step = 11
        st.rerun()

# STEP 11: AI ANALYSIS (Hybrid Mode)
if st.session_state.step == 11:
    st.markdown('<p class="big-font">Analyzing...</p>', unsafe_allow_html=True)
    if "dd_questions" not in st.session_state:
        with st.spinner("Dr. Robot is diagnosing..."):
            
            has_image = st.session_state.case_data.get("Face_Img") is not None
            img_type = st.session_state.get("image_type", "Tongue")
            
            # PROMPT CONSTRUCTION
            prompt = f"""
            Act as Expert Homeopath (BHMS).
            Patient Data: {str(st.session_state.case_data)}
            Case Type: {st.session_state.patient_type}
            
            INSTRUCTIONS:
            {' - IMAGE PROVIDED: Analyze the ' + img_type + ' visually.' if has_image else ' - NO IMAGE: Rely 100% on Patient Speech & Symptoms.'}
            - If Acute: Focus on Causation & Modalities.
            - If Chronic: Focus on Constitution & Miasm.
            
            TASK:
            1. Analyze Symptoms {'+ Visual Signs' if has_image else ''}.
            2. Select Top Remedy.
            3. Ask 2 Tie-Breaker Questions (Hindi).
            
            Respond JSON: {{ "analysis": "...", "questions": "..." }}
            """
            
            try:
                if has_image:
                    img = PIL.Image.open(st.session_state.case_data["Face_Img"])
                    res = model.generate_content([prompt, img])
                else:
                    res = model.generate_content(prompt)
                
                data = json.loads(res.text.replace("```json","").replace("```",""))
                st.session_state.dd_questions = data["questions"]
                st.session_state.analysis = data["analysis"]
            except:
                st.session_state.dd_questions = "और कुछ बताना चाहेंगे?"

    st.markdown(f'<p class="big-font">{st.session_state.dd_questions}</p>', unsafe_allow_html=True)
    speak_text(st.session_state.dd_questions)
    
    audio = mic_recorder(start_prompt="Speak", stop_prompt="Stop", key="mic_dd")
    if audio and audio['id'] != st.session_state.last_audio_id:
        st.session_state.last_audio_id = audio['id']
        ans = recognize_audio(audio['bytes'])
        if ans:
            st.session_state.case_data["DD_Answer"] = ans
            st.session_state.step = 12
            st.rerun()

# STEP 12: PRESCRIPTION
if st.session_state.step == 12:
    if "prescription" not in st.session_state:
        with st.spinner("Writing Prescription..."):
            prompt = f"""
            Finalize Case.
            Analysis: {st.session_state.get('analysis')}
            Patient Answer: {st.session_state.case_data.get('DD_Answer')}
            
            Output:
            1. REMEDY NAME & POTENCY (e.g., Nux Vomica 200).
            2. DOSAGE.
            3. REASON (Hindi).
            """
            res = model.generate_content(prompt)
            st.session_state.prescription = res.text
            
            # Save to Sheet
            rx_name = res.text.split('\n')[0][:50]
            save_patient(
                st.session_state.case_data["RegNo"],
                st.session_state.case_data.get("Name","Unknown"),
                st.session_state.case_data.get("Phone","000"),
                rx_name
            )
            
    rx = st.session_state.prescription
    st.markdown(f'<div class="user-text">{rx}</div>', unsafe_allow_html=True)
    speak_text("आपका इलाज तैयार है। " + rx[:100])
    
    if st.button("New Patient"):
        st.session_state.clear()
        st.rerun()
                         
