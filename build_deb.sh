#!/bin/bash
# Script to build .deb package for ChatList

set -e

# Get version from version.py
VERSION=$(python3 -c "import version; print(version.__version__)")
PACKAGE_NAME="chatlist"
ARCH="amd64"
DEB_NAME="${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"

echo "Building .deb package for ChatList v${VERSION}..."

# Check if executable exists
if [ ! -f "dist/ChatList-${VERSION}" ]; then
    echo "Error: Executable file dist/ChatList-${VERSION} not found!"
    echo "Please build the executable first with: pyinstaller ChatList.spec"
    exit 1
fi

# Clean previous build
echo "Cleaning previous build..."
rm -rf deb_package
rm -f ${PACKAGE_NAME}_*_${ARCH}.deb

# Create directory structure
echo "Creating package structure..."
mkdir -p deb_package/DEBIAN
mkdir -p deb_package/usr/bin
mkdir -p deb_package/usr/share/applications
mkdir -p deb_package/usr/share/doc/${PACKAGE_NAME}

# Copy executable
echo "Copying executable..."
cp dist/ChatList-${VERSION} deb_package/usr/bin/${PACKAGE_NAME}
chmod +x deb_package/usr/bin/${PACKAGE_NAME}

# Create control file
echo "Creating control file..."
cat > deb_package/DEBIAN/control << EOF
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: libc6 (>= 2.31), libqt5core5a (>= 5.15.0), libqt5gui5 (>= 5.15.0), libqt5widgets5 (>= 5.15.0)
Maintainer: alexor86-test <alexor86-test@example.com>
Description: AI Model Comparison Tool
 ChatList — это Python-приложение с графическим интерфейсом (PyQt5),
 которое позволяет отправлять один промт в несколько AI-моделей
 одновременно и сравнивать их ответы.
 .
 Основные возможности:
  - Отправка промтов в несколько AI моделей одновременно
  - Сравнение ответов в удобной таблице
  - Сохранение промтов и результатов
  - AI-ассистент для улучшения промтов
  - Экспорт результатов в Markdown и JSON
  - Настройка темы и размера шрифта
EOF

# Create desktop file
echo "Creating desktop file..."
cat > deb_package/usr/share/applications/${PACKAGE_NAME}.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=ChatList
Name[ru]=ChatList
Comment=AI Model Comparison Tool
Comment[ru]=Инструмент сравнения AI моделей
Exec=/usr/bin/${PACKAGE_NAME}
Icon=${PACKAGE_NAME}
Terminal=false
Categories=Utility;Development;
StartupNotify=true
EOF

# Copy documentation
echo "Copying documentation..."
if [ -f "LICENSE" ]; then
    cp LICENSE deb_package/usr/share/doc/${PACKAGE_NAME}/copyright
fi
if [ -f "README.md" ]; then
    cp README.md deb_package/usr/share/doc/${PACKAGE_NAME}/README.md
    gzip -9 -n deb_package/usr/share/doc/${PACKAGE_NAME}/README.md 2>/dev/null || true
fi

# Create postinst script
echo "Creating postinst script..."
cat > deb_package/DEBIAN/postinst << 'POSTINST_EOF'
#!/bin/bash
# Post-installation script for chatlist

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi

# Update icon cache
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

exit 0
POSTINST_EOF
chmod +x deb_package/DEBIAN/postinst

# Build .deb package
echo "Building .deb package..."
dpkg-deb --build deb_package ${DEB_NAME}

echo ""
echo "✓ Package built successfully: ${DEB_NAME}"
echo "  Size: $(du -h ${DEB_NAME} | cut -f1)"
echo ""
echo "To install: sudo dpkg -i ${DEB_NAME}"
echo "To check: dpkg-deb -I ${DEB_NAME}"

