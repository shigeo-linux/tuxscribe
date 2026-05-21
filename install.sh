#!/bin/bash
set -e

APP_NAME="tuxscribe"
INSTALL_DIR="/opt/${APP_NAME}"
DESKTOP_DIR="/usr/share/applications"

echo "=== Installing ${APP_NAME} ==="

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install it with: sudo apt install python3"
    exit 1
fi

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    python3-requests \
    python3-reportlab \
    python3-docx \
    python3-ebooklib \
    libgtk-3-dev \
    python3-venv librsvg2-bin

# Create install directory
echo "Copying application files..."
sudo mkdir -p "${INSTALL_DIR}"
sudo cp -r "$(dirname "$0")"/* "${INSTALL_DIR}/"
sudo chmod +x "${INSTALL_DIR}/tuxscribe.py"

echo "Creating virtual environment..."
sudo python3 -m venv --system-site-packages "${INSTALL_DIR}/venv"
sudo "${INSTALL_DIR}/venv/bin/pip" install pypdf ebooklib python-docx reportlab

# Install icon
echo "Installing icon..."
sudo mkdir -p /usr/share/icons/hicolor/scalable/apps
sudo mkdir -p /usr/share/icons/hicolor/48x48/apps
sudo mkdir -p /usr/share/icons/hicolor/256x256/apps
sudo cp "${INSTALL_DIR}/tuxscribe.svg" /usr/share/icons/hicolor/scalable/apps/tuxscribe.svg
rsvg-convert -w 48 -h 48 "${INSTALL_DIR}/tuxscribe.svg" | sudo tee /usr/share/icons/hicolor/48x48/apps/tuxscribe.png > /dev/null
rsvg-convert -w 256 -h 256 "${INSTALL_DIR}/tuxscribe.svg" | sudo tee /usr/share/icons/hicolor/256x256/apps/tuxscribe.png > /dev/null
sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true

# Install desktop entry
echo "Installing desktop entry..."
sudo cp "${INSTALL_DIR}/tuxscribe.desktop" "${DESKTOP_DIR}/"
sudo update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true

# Create a launcher in /usr/local/bin
echo "Creating launcher..."
sudo tee /usr/local/bin/tuxscribe > /dev/null << 'EOF'
#!/bin/bash
exec /opt/tuxscribe/venv/bin/python3 /opt/tuxscribe/tuxscribe.py "$@"
EOF
sudo chmod +x /usr/local/bin/tuxscribe

echo "Creating config directory..."
mkdir -p "$HOME/.config/${APP_NAME}"

echo ""
echo "=== Installation complete! ==="
echo ""
echo "Run tuxscribe:"
echo "  - From the terminal: tuxscribe"
echo "  - From the application menu: search for 'Tuxscribe'"
echo ""
echo "On first launch, open Settings (⚙ button) and enter your OpenRouter API key."
echo "Get a free API key at: https://openrouter.ai/keys"
