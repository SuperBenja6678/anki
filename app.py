from flask import Flask, render_template, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename
import os
from openai import OpenAI
from dotenv import load_dotenv
import genanki
import random
import tempfile
import json
import base64
from pdf2image import convert_from_path
from PIL import Image
import io
import time
import html
import shutil

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def encode_image_to_base64(image):
    """Convert PIL Image to base64 string"""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# Global variable to store progress
progress_data = {"status": "", "progress": 0}

def update_progress(status, progress):
    global progress_data
    progress_data["status"] = status
    progress_data["progress"] = progress

@app.route('/progress')
def progress_stream():
    def generate():
        global progress_data
        while True:
            # Return progress data in SSE format
            yield f"data: {json.dumps(progress_data)}\n\n"
            time.sleep(0.5)  # Update every 0.5 seconds
    return Response(generate(), mimetype='text/event-stream')

def extract_text_from_image_with_gpt4(image_path):
    """Extract text from an image using GPT-4"""
    try:
        update_progress("Processing image...", 25)
        # Open and encode image
        with Image.open(image_path) as image:
            base64_image = encode_image_to_base64(image)

        update_progress("Analyzing image with AI...", 50)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please extract all the text from this image. Format it as clear, readable paragraphs. Ignore any irrelevant text like page numbers or headers."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4096
        )
        
        update_progress("Extracting text...", 75)
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in extract_text_from_image_with_gpt4: {str(e)}")
        raise

def generate_qa_pairs(images_data):
    try:
        update_progress("Generating flashcards...", 85)
        # Ensure we have images to process
        if not images_data:
            print("Error: No images provided")
            return []

        print("Sending request to OpenAI...")
        
        # Prepare the content array with all images
        content = [
            {
                "type": "text",
                "text": "Convert these multiple choice questions into flashcards. Return ONLY a JSON array where each object has 'front' (question with options) and 'back' (correct answer or 'unanswered') fields. No other text. list the answer choices on thier own line and label them, examle A,B,C"
            }
        ]
        
        # Add all images to the content array
        for image_data in images_data:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_data}"
                }
            })

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI flashcard generator. Your task is to convert multiple choice questions into Anki flashcards. You must ONLY output valid JSON array, nothing else."
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            max_tokens=4000
        )

        # Get the response content
        content = response.choices[0].message.content.strip()
        print(f"Received response from OpenAI: {content[:100]}...")

        update_progress("Processing flashcards...", 90)
        
        # Remove any non-JSON text that might be in the response
        content = content.strip()
        if not content.startswith('['):
            # Try to find the start of the JSON array
            start_idx = content.find('[')
            if start_idx != -1:
                content = content[start_idx:]
            else:
                raise ValueError("No JSON array found in response")

        if not content.endswith(']'):
            # Try to find the end of the JSON array
            end_idx = content.rfind(']')
            if end_idx != -1:
                content = content[:end_idx + 1]
            else:
                raise ValueError("No JSON array end found in response")

        # Parse the JSON response
        try:
            qa_pairs = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            print(f"Content causing error: {content}")
            return []
        
        # Validate the structure
        if not isinstance(qa_pairs, list):
            print("Error: Parsed response is not a list")
            return []

        valid_pairs = []
        for pair in qa_pairs:
            if isinstance(pair, dict) and 'front' in pair and 'back' in pair:
                if isinstance(pair['front'], str) and isinstance(pair['back'], str):
                    valid_pairs.append(pair)

        if not valid_pairs:
            print("Error: No valid Q&A pairs found in response")
            return []

        update_progress("Finalizing flashcards...", 95)
        print(f"Successfully generated {len(valid_pairs)} valid Q&A pairs")
        return valid_pairs

    except Exception as e:
        print(f"Error in generate_qa_pairs: {str(e)}")
        return []

def extract_text_from_pdf_with_gpt4(pdf_path):
    """Extract text from PDF using GPT-4"""
    try:
        print(f"Converting PDF to images: {pdf_path}")
        update_progress("Converting PDF to images...", 10)
        # Convert PDF to images
        pages = convert_from_path(pdf_path, poppler_path=os.getenv('POPPLER_PATH', r'C:\Program Files\poppler-24.08.0\Library\bin'))
        
        # Convert all pages to base64
        base64_images = []
        for i, page in enumerate(pages):
            progress = 10 + (i + 1) * 30 // len(pages)
            update_progress(f"Preparing page {i+1}/{len(pages)}...", progress)
            base64_images.append(encode_image_to_base64(page))

        update_progress("Processing with AI...", 50)
        # Send all images directly to generate_qa_pairs
        qa_pairs = generate_qa_pairs(base64_images)
        
        if not qa_pairs:
            print("Error: Failed to generate flashcards")
            return []
            
        return qa_pairs
        
    except Exception as e:
        print(f"Error in extract_text_from_pdf_with_gpt4: {str(e)}")
        raise

def create_anki_package(qa_pairs, deck_name="AnkiAI Generated Deck"):
    try:
        model_id = random.randrange(1 << 30, 1 << 31)
        deck_id = random.randrange(1 << 30, 1 << 31)

        # Create the model
        model = genanki.Model(
            model_id,
            'Simple Model',
            fields=[
                {'name': 'Question'},
                {'name': 'Answer'},
            ],
            templates=[
                {
                    'name': 'Card 1',
                    'qfmt': '{{Question}}',
                    'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
                },
            ])

        # Create the deck
        deck = genanki.Deck(deck_id, deck_name)

        def clean_text(text):
            # Replace problematic sequences first
            text = text.replace('< ', '&lt; ').replace(' >', ' &gt;')
            text = text.replace('<', '&lt;').replace('>', '&gt;')
            # Convert newlines to <br> tags
            text = text.replace('\n', '<br>')
            return text

        # Add notes to the deck
        for pair in qa_pairs:
            # Clean and format the text
            question = clean_text(pair['front'])
            answer = clean_text(pair['back'])
            
            # Create and add the note
            note = genanki.Note(
                model=model,
                fields=[question, answer]
            )
            deck.add_note(note)

        # Create a temporary directory for the package
        with tempfile.TemporaryDirectory() as temp_dir:
            package_path = os.path.join(temp_dir, f"{deck_name}.apkg")
            # Generate the package
            package = genanki.Package(deck)
            package.write_to_file(package_path)
            
            # Move the package to the uploads folder
            final_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{deck_name}.apkg")
            shutil.copy2(package_path, final_path)
            
        return final_path

    except Exception as e:
        print(f"Error in create_anki_package: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400

        # Reset progress
        update_progress("Starting...", 0)
            
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        update_progress("File uploaded...", 10)
        
        # Process based on file type
        if filename.lower().endswith('.pdf'):
            qa_pairs = extract_text_from_pdf_with_gpt4(filepath)
        else:
            # For single images
            with Image.open(filepath) as img:
                base64_image = encode_image_to_base64(img)
                qa_pairs = generate_qa_pairs([base64_image])
            
        update_progress("Creating Anki deck...", 98)
        # Create Anki package
        if qa_pairs:
            deck_name = os.path.splitext(filename)[0]
            package_path = create_anki_package(qa_pairs, deck_name)
            if package_path:
                update_progress("Done!", 100)
                return jsonify({
                    'success': True,
                    'filename': os.path.basename(package_path),
                    'qa_pairs': qa_pairs
                })
        
        return jsonify({'error': 'Failed to process file'}), 500
        
    except Exception as e:
        print(f"Error in upload_file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<path:filename>')
def download_file(filename):
    try:
        temp_dir = os.path.join(os.getcwd(), 'temp')
        return send_file(os.path.join(temp_dir, filename),
                        as_attachment=True,
                        download_name='anki_flashcards.apkg')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
