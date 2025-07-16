import streamlit as st
import requests


# Custom CSS to force scrollbars
st.markdown("""
    <style>
    textarea {
        overflow: auto !important;
        white-space: pre !important;
        font-family: monospace !important;
    }
    </style>
    """, unsafe_allow_html=True)


st.title("File Downloader")

# Text area for URLs
urls_input = st.text_area(
    "Enter URLs here (comma-separated):",
    height=150,
    placeholder="https://example.com/file1, https://example.com/file2"
)

# Submit button
if st.button("Submit"):
    if urls_input:
        url_list = [url.strip() for url in urls_input.split(',')]
        st.write("Sending URLs to server:", url_list)
        try:
            response = requests.post("http://localhost:9000/download", json=url_list)
            message = response.json().get("message", "No message returned")
            st.success(message)
        except requests.exceptions.RequestException as e:
            st.error(f"An error occurred: {e}")
    else:
        st.warning("Please enter at least one URL.")
