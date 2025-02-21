# AnkiAI - Flashcard Creator

AnkiAI is a web application that automatically creates Anki flashcards from uploaded images and PDFs using OCR and AI-powered question generation.

## Features

- Upload images (PNG, JPG, JPEG) and PDFs
- OCR text extraction
- AI-powered question and answer generation
- Automatic Anki deck creation
- Modern, responsive UI with drag-and-drop support
- Multiple language support

## Prerequisites

- Python 3.7+
- Tesseract OCR
- OpenAI API key

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Tesseract OCR:
- Windows: Download and install from https://github.com/UB-Mannheim/tesseract/wiki
- Make sure Tesseract is in your system PATH

3. Configure OpenAI API:
- Copy your OpenAI API key to the `.env` file:
```
OPENAI_API_KEY=your_openai_api_key_here
```

## Usage

1. Start the Flask server:
```bash
python app.py
```

2. Open your browser and navigate to `http://localhost:5000`

3. Upload an image or PDF file:
   - Drag and drop files into the upload zone
   - Or click to browse and select files

4. Wait for processing:
   - The application will extract text using OCR
   - Generate questions and answers using AI
   - Create an Anki deck

5. Download the generated `.apkg` file

6. Import the downloaded file into Anki

## Project Structure

```
anki/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env               # Environment variables
├── README.md          # Documentation
├── templates/         # HTML templates
│   └── index.html    # Main page template
└── uploads/          # Temporary file storage
```

## License

MIT License
