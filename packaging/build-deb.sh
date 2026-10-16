#!/bin/sh
# Pardus/Debian için dys-asistan .deb paketini üretir: dist/dys-asistan_SÜRÜM_all.deb
# Yalnızca dpkg-deb gerekir (Pardus'ta öntanımlı kurulu). Kullanım: sh packaging/build-deb.sh
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/dysasistan/__init__.py")
if [ -z "$VERSION" ]; then
    echo "Sürüm dysasistan/__init__.py dosyasından okunamadı" >&2
    exit 1
fi

BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
PKG="$BUILD/dys-asistan"
LIB="$PKG/usr/lib/python3/dist-packages/dysasistan"
DOC="$PKG/usr/share/doc/dys-asistan"
KIMLIK=io.github.muratgursel.DysAsistan
D="$ROOT/packaging/debian"

install -d "$PKG/DEBIAN" "$PKG/usr/bin" "$LIB" "$DOC/examples" "$PKG/etc/xdg/autostart" \
    "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/scalable/apps"

install -m 644 "$ROOT"/dysasistan/*.py "$LIB/"
install -m 755 "$D/dys-asistan" "$PKG/usr/bin/dys-asistan"
install -m 644 "$D/$KIMLIK.desktop" "$PKG/usr/share/applications/"
install -m 644 "$D/$KIMLIK-autostart.desktop" "$PKG/etc/xdg/autostart/$KIMLIK.desktop"
install -m 644 "$D/$KIMLIK.svg" "$PKG/usr/share/icons/hicolor/scalable/apps/"
install -m 644 "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$ROOT"/docs/*.md "$DOC/"
install -m 644 "$ROOT/tools/sahte_dys.html" "$DOC/examples/"
install -m 644 "$D/copyright" "$DOC/copyright"
install -m 755 "$D/postinst" "$D/prerm" "$PKG/DEBIAN/"
echo "/etc/xdg/autostart/$KIMLIK.desktop" > "$PKG/DEBIAN/conffiles"

SIZE=$(du -sk "$PKG/usr" | cut -f1)
sed -e "s/@VERSION@/$VERSION/" -e "s/@SIZE@/$SIZE/" "$D/control" > "$PKG/DEBIAN/control"
(cd "$PKG" && find usr -type f -exec md5sum {} + > DEBIAN/md5sums)

mkdir -p "$ROOT/dist"
OUT="$ROOT/dist/dys-asistan_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$PKG" "$OUT" >/dev/null
echo "$OUT"
