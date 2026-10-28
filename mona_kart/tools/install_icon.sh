#!/bin/sh
# Add the Mona Kart kart icon and its drive-in animation to the badge's menu.
# Needs Python 3 and network access once (to install mpy-cross 1.26.1, the
# version that reproduces the badge's own icons.mpy byte for byte).
set -eu

VOLUME="${1:-/Volumes/BADGER}"
MENU="$VOLUME/apps/menu"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${TMPDIR:-/tmp}/mona_kart_icon"
BACKUP="$HERE/../../badge/menu-backup"

[ -f "$MENU/src/icons.py" ] || { echo "Menu not found at $MENU (open Mass Storage first)" >&2; exit 1; }
mkdir -p "$WORK" "$BACKUP"

if ! grep -q '"badger_kart":\|"mona_kart":' "$MENU/src/icons.py"; then
    [ -f "$BACKUP/icons.mpy" ] || cp "$MENU/icons.mpy" "$MENU/src/icons.py" "$BACKUP/"
fi
[ -x "$WORK/venv/bin/mpy-cross" ] || {
    python3 -m venv "$WORK/venv"
    "$WORK/venv/bin/pip" install -q mpy-cross==1.26.1.post2
}

# menu_icon.py replaces any previous entry (including the old badger_kart one)
python3 -I "$HERE/menu_icon.py" --icons-src "$MENU/src/icons.py" --icons-out "$WORK/icons.py" \
    --anim-out "$WORK/mona_kart.bin"
(cd "$WORK" && ./venv/bin/mpy-cross icons.py -o icons.mpy)  # relative name, like the stock build
COPYFILE_DISABLE=1 cp -X "$WORK/icons.mpy" "$MENU/icons.mpy"
COPYFILE_DISABLE=1 cp -X "$WORK/icons.py" "$MENU/src/icons.py"
COPYFILE_DISABLE=1 cp -X "$WORK/mona_kart.bin" "$MENU/anim/mona_kart.bin"
rm -f "$MENU/anim/badger_kart.bin" "$MENU"/._* "$MENU"/src/._* "$MENU"/anim/._*
sync
echo "Kart icon installed. Originals are backed up in $BACKUP"
