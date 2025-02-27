import streamlit as st
import requests
import os
import time
from typing import Optional

# Configure the backend URL
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')

# Set page config
st.set_page_config(
    page_title="LUMI Translation",
    page_icon="🎥",
    layout="wide"
)

# Add custom CSS
st.markdown("""
<style>
.stApp {
    max-width: 1200px;
    margin: 0 auto;
}
.upload-box {
    border: 2px dashed #cccccc;
    padding: 20px;
    text-align: center;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# Title and description
st.title("🎥 LUMI Video Translation")
st.markdown("Translate your videos between multiple languages with AI-powered dubbing")

# File upload section
st.header("Upload Video")
with st.form("upload_form"):
    uploaded_file = st.file_uploader(
        "Choose a video file", 
        type=["mp4", "avi", "mov", "mkv"],
        help="Upload a video file to translate"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        source_lang = st.selectbox(
            "Source Language",
            options=["zh", "en", "ja", "ko", "fr", "de", "es", "it", "ru"],
            index=0,
            help="Select the language of the video"
        )
    
    with col2:
        target_lang = st.selectbox(
            "Target Language",
            options=["en", "zh", "ja", "ko", "fr", "de", "es", "it", "ru"],
            index=0,
            help="Select the language to translate to"
        )
    
    submit_button = st.form_submit_button("Start Translation")

# Handle form submission
if submit_button and uploaded_file is not None:
    with st.spinner("Uploading video..."):
        # Prepare the files and data for the request
        files = {"video": uploaded_file.getvalue()}
        data = {
            "source_lang": source_lang,
            "target_lang": target_lang
        }
        
        # Submit the translation request
        try:
            response = requests.post(
                f"{BACKEND_URL}/v1/translate",
                files=files,
                data=data
            )
            response.raise_for_status()
            result = response.json()
            task_id = result.get("task_id")
            
            if task_id:
                st.success("Video uploaded successfully! Monitoring translation progress...")
                st.session_state["task_id"] = task_id
            else:
                st.error("Failed to start translation task")
                
        except requests.exceptions.RequestException as e:
            st.error(f"Error submitting translation request: {str(e)}")

# Check translation progress
if "task_id" in st.session_state:
    task_id = st.session_state["task_id"]
    status_placeholder = st.empty()
    
    try:
        while True:
            response = requests.get(f"{BACKEND_URL}/status/{task_id}")
            status_data = response.json()
            status = status_data.get("status")
            
            if status == "completed":
                download_url = status_data.get("download_url")
                if download_url:
                    status_placeholder.success("Translation completed!")
                    st.markdown(f"[Download Translated Video]({BACKEND_URL}{download_url})")
                break
            elif status == "failed":
                failure_reason = status_data.get("failure_reason", "Unknown error")
                status_placeholder.error(f"Translation failed: {failure_reason}")
                break
            else:
                status_placeholder.info(f"Translation status: {status}")
                time.sleep(5)
                
    except requests.exceptions.RequestException as e:
        status_placeholder.error(f"Error checking translation status: {str(e)}")

# Add footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>Powered by LUMI Translation | <a href="https://github.com/your-repo/lumi-translation" target="_blank">GitHub</a></p>
</div>
""", unsafe_allow_html=True)