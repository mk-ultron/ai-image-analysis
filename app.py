import streamlit as st
import anthropic
import openai
from PIL import Image
import io
import sqlite3
import base64
from exif import Image as ExifImage
import tempfile
import os
import hashlib
import requests

# Database setup and migration
def setup_database():
    conn = sqlite3.connect('image_analysis.db')
    c = conn.cursor()
    
    # Create the images table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS images
                 (id INTEGER PRIMARY KEY, image_hash TEXT, metadata TEXT, analysis TEXT)''')
    
    # Check if the image_hash column exists
    c.execute("PRAGMA table_info(images)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'image_hash' not in columns:
        # Add the image_hash column
        c.execute("ALTER TABLE images ADD COLUMN image_hash TEXT")
        st.success("Database schema updated successfully!")
    
    conn.commit()
    return conn, c

# Set up database connection and cursor
conn, c = setup_database()

# Set up API clients
anthropic_client = anthropic.Anthropic(api_key=st.secrets["api_keys"]["anthropic"])
openai_client = openai.OpenAI(api_key=st.secrets["api_keys"]["openai"])

# Initialize session state
if 'analyzed_images' not in st.session_state:
    st.session_state.analyzed_images = []

def extract_metadata(image_bytes):
    try:
        img = ExifImage(image_bytes)
        metadata = {
            "make": img.get("make", "Unknown"),
            "model": img.get("model", "Unknown"),
            "datetime": img.get("datetime", "Unknown"),
            "gps_latitude": img.get("gps_latitude", "Unknown"),
            "gps_longitude": img.get("gps_longitude", "Unknown"),
        }
    except Exception as e:
        metadata = {
            "make": "Unknown",
            "model": "Unknown",
            "datetime": "Unknown",
            "gps_latitude": "Unknown",
            "gps_longitude": "Unknown",
        }
    return metadata

def analyze_image_with_claude(image_base64, metadata):
    prompt = f"""
    Analyze the following image and provide a detailed description. 
    Consider the following aspects:
    1. Main subject(s) of the image
    2. Any pop culture references or recognizable figures?
    3. What text is visible in the image, and what can you infer about the image from it? 
    4. Composition and framing 
    5. Colors and overall mood 
    6. What is the style of the image (e.g., realism, abstract, impressionism)

    Additional context from metadata:
    - Camera: {metadata['make']} {metadata['model']}
    - Date taken: {metadata['datetime']}
    - GPS coordinates: {metadata['gps_latitude']}, {metadata['gps_longitude']}

    Provide a comprehensive analysis in about 100-500 words.
    """

    response = anthropic_client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    )
    
    return response.content[0].text

def text_to_speech(text, voice="alloy"):
    response = openai_client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text
    )
    
    # Save the audio content to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
            temp_audio.write(chunk)
    
    return temp_audio.name

def resize_image(image, max_size=(1568, 1568), max_pixels=1150000):
    width, height = image.size
    num_pixels = width * height
    
    if num_pixels <= max_pixels and width <= max_size[0] and height <= max_size[1]:
        return image
    
    scale = min(
        (max_pixels / num_pixels) ** 0.5,
        max_size[0] / width,
        max_size[1] / height
    )
    
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    return image.resize((new_width, new_height), Image.LANCZOS)

def get_image_hash(image_bytes):
    return hashlib.md5(image_bytes).hexdigest()

def display_analysis_card(image, analysis, image_hash):
    st.write("---")
    col1, col2 = st.columns([1, 3])
    with col1:
        st.image(image, use_column_width=True)
    with col2:
        st.write(analysis)
        if st.button(f"Play Analysis for {image_hash[:8]}", key=f"play_{image_hash}"):
            with st.spinner("Generating audio..."):
                try:
                    audio_file_path = text_to_speech(analysis)
                    st.audio(audio_file_path, format='audio/mp3')
                except Exception as e:
                    st.error(f"An error occurred while generating the audio: {str(e)}")
                finally:
                    if 'audio_file_path' in locals():
                        os.remove(audio_file_path)

def load_image_from_url(url):
    response = requests.get(url)
    image = Image.open(io.BytesIO(response.content))
    return image

def main():
    # Set page configuration
    st.set_page_config(
        page_title="AI Image Analysis with TTS",
        page_icon="🔥",
        layout="centered",
        initial_sidebar_state="auto"
    )
    st.title("AI Image Analysis with TTS")

    # Create tabs for upload and URL input
    tab1, tab2 = st.tabs(["Upload Image", "Enter Image URL"])

    with tab1:
        uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            process_image(image)

    with tab2:
        url = st.text_input("Enter the URL of an image:")
        if url:
            try:
                image = load_image_from_url(url)
                process_image(image)
            except Exception as e:
                st.error(f"Error loading image from URL: {str(e)}")

    # Display all analyzed images
    for data in st.session_state.analyzed_images:
        display_analysis_card(data['image'], data['analysis'], data['image_hash'])

def process_image(image):
    resized_image = resize_image(image)
    
    # Get image hash
    image_bytes = io.BytesIO()
    resized_image.save(image_bytes, format="JPEG")
    image_bytes = image_bytes.getvalue()
    image_hash = get_image_hash(image_bytes)

    st.image(resized_image, caption='Processed Image (Resized)', use_column_width=True)

    if st.button("Analyze Image"):
        with st.spinner("Analyzing image..."):
            metadata = extract_metadata(image_bytes)
            img_base64 = base64.b64encode(image_bytes).decode('utf-8')
            analysis = analyze_image_with_claude(img_base64, metadata)

            # Save to session state
            st.session_state.analyzed_images.insert(0, {
                'image': resized_image,
                'analysis': analysis,
                'image_hash': image_hash
            })

            # Save to database
            c.execute("INSERT INTO images (image_hash, metadata, analysis) VALUES (?, ?, ?)",
                      (image_hash, str(metadata), analysis))
            conn.commit()

if __name__ == "__main__":
    main()
