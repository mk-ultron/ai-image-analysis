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
    
    # Check if the images table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='images'")
    table_exists = c.fetchone()
    
    if not table_exists:
        # If the table doesn't exist, create it with the new schema
        c.execute('''CREATE TABLE images
                     (id INTEGER PRIMARY KEY,
                      image_hash TEXT NOT NULL UNIQUE,
                      make TEXT NOT NULL,
                      model TEXT NOT NULL,
                      datetime TEXT NOT NULL,
                      gps_latitude TEXT,
                      gps_longitude TEXT,
                      analysis TEXT NOT NULL,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    else:
        # If the table exists, check if it needs to be migrated
        c.execute("PRAGMA table_info(images)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'make' not in columns:
            # Perform migration
            c.execute('''CREATE TABLE images_new
                         (id INTEGER PRIMARY KEY,
                          image_hash TEXT NOT NULL UNIQUE,
                          make TEXT NOT NULL,
                          model TEXT NOT NULL,
                          datetime TEXT NOT NULL,
                          gps_latitude TEXT,
                          gps_longitude TEXT,
                          analysis TEXT NOT NULL,
                          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
            # Copy data from the old table to the new table
            c.execute('''INSERT INTO images_new (image_hash, make, model, datetime, gps_latitude, gps_longitude, analysis)
                         SELECT image_hash, 
                                'Unknown' as make, 
                                'Unknown' as model, 
                                'Unknown' as datetime, 
                                'Unknown' as gps_latitude, 
                                'Unknown' as gps_longitude, 
                                analysis 
                         FROM images''')
            
            # Drop the old table and rename the new one
            c.execute("DROP TABLE images")
            c.execute("ALTER TABLE images_new RENAME TO images")
            
            st.success("Database schema has been updated successfully!")
    
    # Create an index on the image_hash column
    c.execute('CREATE INDEX IF NOT EXISTS idx_image_hash ON images(image_hash)')
    
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
            "gps_latitude": str(img.get("gps_latitude", "Unknown")),
            "gps_longitude": str(img.get("gps_longitude", "Unknown")),
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
    3. What text is visible in the image, and what can you infer about the image from it? In 1-2 sentences, describe what do you know about what the text might represent. 
    4. What is the style of the image (e.g., realism, abstract, impressionism, colors and overall mood)

    Additional context from metadata:
    - Camera: {metadata['make']} {metadata['model']}
    - Date taken: {metadata['datetime']}
    - GPS coordinates: {metadata['gps_latitude']}, {metadata['gps_longitude']}

    Provide a comprehensive analysis in about 100-300 words.
    """

    response = anthropic_client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=350,
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
        play_button_key = f"play_{image_hash}"
        if st.button(f"Play Analysis", key=play_button_key):
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

def get_analysis_by_hash(image_hash):
    c.execute("SELECT analysis FROM images WHERE image_hash = ?", (image_hash,))
    result = c.fetchone()
    return result[0] if result else None

def insert_analysis(image_hash, metadata, analysis):
    c.execute("""
        INSERT INTO images (image_hash, make, model, datetime, gps_latitude, gps_longitude, analysis)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        image_hash,
        metadata['make'],
        metadata['model'],
        metadata['datetime'],
        metadata['gps_latitude'],
        metadata['gps_longitude'],
        analysis
    ))
    conn.commit()

def get_or_create_analysis(image_hash, metadata, image_base64):
    existing_analysis = get_analysis_by_hash(image_hash)
    if existing_analysis:
        return existing_analysis
    
    analysis = analyze_image_with_claude(image_base64, metadata)
    insert_analysis(image_hash, metadata, analysis)
    return analysis

def process_image(image, source_type):
    resized_image = resize_image(image)
    
    image_bytes = io.BytesIO()
    resized_image.save(image_bytes, format="JPEG")
    image_bytes = image_bytes.getvalue()
    image_hash = get_image_hash(image_bytes)

    st.image(resized_image, caption='Processed Image (Resized)', use_column_width=True)

    button_key = f"analyze_{source_type}_{image_hash}"

    if st.button("Analyze Image", key=button_key):
        with st.spinner("Analyzing image..."):
            metadata = extract_metadata(image_bytes)
            img_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            analysis = get_or_create_analysis(image_hash, metadata, img_base64)

            st.session_state.analyzed_images.insert(0, {
                'image': resized_image,
                'analysis': analysis,
                'image_hash': image_hash
            })

            st.success("Analysis complete!")
            st.write(analysis)

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
            process_image(image, "upload")

    with tab2:
        url = st.text_input("Enter the URL of an image:")
        if url:
            try:
                image = load_image_from_url(url)
                process_image(image, "url")
            except Exception as e:
                st.error(f"Error loading image from URL: {str(e)}")

    for data in st.session_state.analyzed_images:
        display_analysis_card(data['image'], data['analysis'], data['image_hash'])

if __name__ == "__main__":
    main()
