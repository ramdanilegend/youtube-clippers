#!/bin/bash
# ╔══════════════════════════════════════════════╗
# ║  SETUP SCRIPT - YouTube Auto Clipper         ║
# ║  Jalankan sekali untuk install dependencies   ║
# ╚══════════════════════════════════════════════╝

echo "🔧 Installing dependencies..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 tidak ditemukan. Install Python 3.8+ dulu."
    exit 1
fi

# Check FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg tidak ditemukan."
    echo ""
    echo "Install FFmpeg:"
    echo "  macOS  : brew install ffmpeg"
    echo "  Ubuntu : sudo apt install ffmpeg"
    echo "  Windows: choco install ffmpeg  (atau download dari https://ffmpeg.org)"
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

# Install dependencies
echo "📥 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ Setup selesai!"
echo ""
echo "📝 LANGKAH SELANJUTNYA:"
echo "   1. Edit config.py → isi API key (OpenAI atau Anthropic)"
echo "   2. Aktifkan venv:  source venv/bin/activate"
echo "   3. Jalankan:       python clipper.py <youtube_url>"
echo ""
