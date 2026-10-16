#!/bin/sh
# Paketi hiçbir şey kurulu olmayan bir Debian konteynerinde üretir, kurar ve dener.
#   sh packaging/temiz-kurulum-testi.sh debian:12   # Pardus 23 tabanı
#   sh packaging/temiz-kurulum-testi.sh debian:13   # Pardus 25 tabanı
# Docker gerekir. Kaynak, depodaki son commit'ten (git archive) alınır.
set -eu

IMAGE=${1:-debian:13}
ROOT=$(cd "$(dirname "$0")/.." && pwd)

git -C "$ROOT" archive --format=tar HEAD | docker run --rm -i "$IMAGE" sh -euc '
mkdir -p /src && tar xf - -C /src
export DEBIAN_FRONTEND=noninteractive
. /etc/os-release
echo "== $PRETTY_NAME"
apt-get update -qq
apt-get install -y -qq --no-install-recommends dpkg-dev curl ca-certificates >/dev/null

echo "== paket"
cd /src && DEB=$(sh packaging/build-deb.sh)
echo "  $(basename "$DEB")"

echo "== kurulum (apt, öntanımlı ayarlarla)"
apt-get install -y -qq "$DEB" >/tmp/apt.log 2>&1 || { tail -30 /tmp/apt.log; exit 1; }
dpkg -s dys-asistan | sed -n "s/^\(Status\|Version\): /  \1: /p"
for p in sane-airscan gir1.2-ayatanaappindicator3-0.1; do
    dpkg -s $p >/dev/null 2>&1 && echo "  önerilen: $p kuruldu"
done

echo "== masaüstü dosyaları"
test -f /usr/share/applications/io.github.muratgursel.DysAsistan.desktop
test -f /etc/xdg/autostart/io.github.muratgursel.DysAsistan.desktop
test -f /usr/share/icons/hicolor/scalable/apps/io.github.muratgursel.DysAsistan.svg
grep -qx "/etc/xdg/autostart/io.github.muratgursel.DysAsistan.desktop" /var/lib/dpkg/info/dys-asistan.conffiles
echo "  tamam"

useradd -m deneme
kullanici() { su deneme -s /bin/sh -c "$*"; }

echo "== komut satırı (kullanıcı olarak)"
kullanici "dys-asistan --version"
kullanici "dys-asistan --tarayicilari-listele" >/tmp/liste.txt 2>&1
echo "  tarayıcı listesi: $(wc -l </tmp/liste.txt) satır (konteynerde cihaz yok)"
! grep -q Traceback /tmp/liste.txt

echo "== yerel sunucu (arayüzsüz)"
kullanici "dys-asistan --sunucu-yalniz >/tmp/sunucu.log 2>&1 &"
for i in 1 2 3 4 5 6 7 8 9 10; do
    curl -s -X POST -d "{\"token\":\"t\"}" http://127.0.0.1:62222/IsAlive >/dev/null 2>&1 && break
    sleep 1
done
iste() { curl -s -o /tmp/yanit -w "%{http_code}" -X POST -H "Origin: $1" --data-binary "$3" "http://127.0.0.1:62222/$2"; }
D=https://dys.saglik.gov.tr
test "$(iste $D IsAlive "{\"token\":\"t\"}")" = 200 && grep -q alive /tmp/yanit
test "$(iste $D IsAlive "")" = 400
test "$(iste https://kotu.example.com IsAlive "{\"token\":\"t\"}")" = 403
test "$(iste $D GetActiveScanners "{\"token\":\"t\"}")" = 200 && test "$(cat /tmp/yanit)" = "[]"
test "$(iste $D GetAllFileInfos "{\"token\":\"t\"}")" = 200
test "$(iste $D DeletePdf "{\"token\":\"t\",\"path\":\"/etc/passwd\"}")" = 400 && test -f /etc/passwd
test "$(iste $D StartScan "{\"token\":\"t\"}")" = 500 && echo "  tarayıcısız tarama: $(cat /tmp/yanit)"
test "$(iste $D GetActivePrinters "{\"token\":\"t\"}")" = 200
test "$(iste $D StartPrint "{\"token\":\"t\",\"contentType\":\"application/pdf\"}")" = 500
echo "  10 uç nokta yanıt verdi; yabancı kaynak 403, klasör dışı yol 400"
kullanici "dys-asistan --sunucu-yalniz" 2>&1 | grep -q "zaten çalışıyor"
echo "  ikinci kopya başlamadı"
pkill -f "^/usr/bin/python3 /usr/bin/dys-asistan" || true
sleep 1
! grep -q Traceback /tmp/sunucu.log

echo "== arayüz (Xvfb, ekransız)"
apt-get install -y -qq xvfb xauth dbus-x11 >/dev/null 2>&1   # yalnızca test için
kullanici "xvfb-run -a dbus-launch --exit-with-session timeout 8 dys-asistan" >/tmp/arayuz.log 2>&1 || true
if grep -q Traceback /tmp/arayuz.log; then cat /tmp/arayuz.log; exit 1; fi
grep -q "dinleniyor" /home/deneme/.config/dys-asistan/gunluk.txt
echo "  çekmece arayüzüyle açıldı, hata yok"

echo "== kaldırma"
apt-get remove -y -qq dys-asistan >/dev/null 2>&1
test ! -e /usr/lib/python3/dist-packages/dysasistan
test ! -e /usr/bin/dys-asistan
apt-get purge -y -qq dys-asistan >/dev/null 2>&1
test ! -e /etc/xdg/autostart/io.github.muratgursel.DysAsistan.desktop
echo "  temiz kaldırıldı"
echo "== BAŞARILI: $PRETTY_NAME"
'
