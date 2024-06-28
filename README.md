# AI Image Analysis with Text-to-Speech

This Streamlit application provides AI-powered image analysis with text-to-speech capabilities. It allows users to upload images or provide image URLs for analysis, leveraging Claude AI for image description and OpenAI's TTS for audio generation.

A working version of this app can be viewed on the Streamlit Community Cloud: [AI Image Analysis](https://ai-image-analysis.streamlit.app/)

## Features

- Image upload and URL input support
- AI-powered image analysis using Claude 3.5 Sonnet
- Text-to-speech conversion of analysis results
- Image metadata extraction (when available)
- Database storage for caching analysis results
- Responsive UI with image resizing

## Requirements

- Python 3.7+
- Streamlit
- Anthropic API key
- OpenAI API key
- Other dependencies listed in `requirements.txt`

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/ai-image-analysis-tts.git
   cd ai-image-analysis-tts
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your API keys:
   - Create a `.streamlit/secrets.toml` file in the project directory
   - Add your API keys to the file:
     ```toml
     [api_keys]
     anthropic = "your_anthropic_api_key"
     openai = "your_openai_api_key"
     ```

## Usage

1. Run the Streamlit app:
   ```
   streamlit run app.py
   ```

2. Open your web browser and navigate to the provided local URL (usually `http://localhost:8501`).

3. Use the application:
   - Upload an image file or provide an image URL
   - Click the "Analyze Image" button to process the image
   - View the analysis results and click "Play Analysis" to hear the text-to-speech version

## How It Works

1. The application resizes the input image to optimize for processing.
2. Image metadata is extracted (if available).
3. The image is sent to Claude AI for analysis, along with any available metadata.
4. The analysis result is stored in a SQLite database for caching.
5. Users can view the analysis and play an audio version generated using OpenAI's text-to-speech model.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [Streamlit](https://streamlit.io/) for the web app framework
- [Anthropic](https://www.anthropic.com/) for the Claude AI model
- [OpenAI](https://openai.com/) for the text-to-speech capabilities
