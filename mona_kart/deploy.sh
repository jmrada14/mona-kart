#!/bin/sh
# Copy Mona Kart onto the badge while it is in USB disk mode (Mass Storage app).
set -eu

VOLUME="${1:-/Volumes/BADGER}"
SOURCE="$(cd "$(dirname "$0")" && pwd)/app"
TARGET="$VOLUME/apps/mona_kart"

if [ ! -d "$VOLUME/apps" ]; then
    echo "Badge not found at $VOLUME (open Mass Storage on the badge first)" >&2
    exit 1
fi

# the app was called Badger Kart before; drop that copy so the menu has one tile
rm -rf "$VOLUME/apps/badger_kart"
mkdir -p "$TARGET"
for file in "$SOURCE"/*.py; do
    COPYFILE_DISABLE=1 cp -X "$file" "$TARGET/"
done
rm -f "$TARGET"/._* "$VOLUME/apps/._mona_kart"
sync
echo "Copied $(ls "$SOURCE"/*.py | wc -l | tr -d ' ') files to $TARGET. Eject the disk, then reboot the badge."
