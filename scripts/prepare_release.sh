#!/bin/bash
# Script to prepare files for GitHub release

set -e

# Get version from version.py
VERSION=$(python3 -c "import version; print(version.__version__)")

echo "Preparing release v${VERSION}..."

# Check if executable exists
if [ ! -f "dist/ChatList-${VERSION}" ]; then
    echo "Error: Executable file dist/ChatList-${VERSION} not found!"
    echo "Please build the executable first with: pyinstaller ChatList.spec"
    exit 1
fi

# Check if .deb package exists
if [ ! -f "chatlist_${VERSION}_amd64.deb" ]; then
    echo "Warning: .deb package chatlist_${VERSION}_amd64.deb not found!"
    echo "Building .deb package..."
    ./build_deb.sh
fi

# Create release directory
RELEASE_DIR="release_v${VERSION}"
rm -rf "${RELEASE_DIR}"
mkdir -p "${RELEASE_DIR}"

# Copy files
echo "Copying release files..."
cp "dist/ChatList-${VERSION}" "${RELEASE_DIR}/"
cp "chatlist_${VERSION}_amd64.deb" "${RELEASE_DIR}/"

# Create release notes
echo "Creating release notes..."
RELEASE_NOTES="${RELEASE_DIR}/RELEASE_NOTES.md"
cp .github/release_template.md "${RELEASE_NOTES}"

# Replace placeholders
sed -i "s/{VERSION}/${VERSION}/g" "${RELEASE_NOTES}"
sed -i "s/YOUR_USERNAME/${GITHUB_USERNAME:-YOUR_USERNAME}/g" "${RELEASE_NOTES}"

# Get previous version from git tags
PREV_TAG=$(git describe --tags --abbrev=0 HEAD~1 2>/dev/null || echo "")
if [ -n "${PREV_TAG}" ]; then
    PREV_VERSION=${PREV_TAG#v}
    sed -i "s/{PREVIOUS_VERSION}/${PREV_VERSION}/g" "${RELEASE_NOTES}"
else
    sed -i "s/{PREVIOUS_VERSION}/initial/g" "${RELEASE_NOTES}"
fi

echo ""
echo "✓ Release files prepared in ${RELEASE_DIR}/"
echo ""
echo "Files:"
ls -lh "${RELEASE_DIR}/"
echo ""
echo "Next steps:"
echo "1. Review and edit ${RELEASE_NOTES}"
echo "2. Create git tag: git tag -a v${VERSION} -m \"Release v${VERSION}\""
echo "3. Push tag: git push origin v${VERSION}"
echo "4. Create release on GitHub using ${RELEASE_NOTES} as description"
echo "5. Upload files from ${RELEASE_DIR}/ to the release"

