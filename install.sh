#!/bin/sh
# DYS Asistan kurulum betiği (Pardus ve Debian tabanlı sistemler).
#
#   curl -fsSL https://raw.githubusercontent.com/muratGursel/dys-asistan/main/install.sh | sudo sh
#
# GitHub'daki son sürümün .deb paketini indirir ve bağımlılıklarıyla kurar.
set -eu

REPO="muratGursel/dys-asistan"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bu betik yönetici yetkisi ister. Şöyle çalıştırın: ... | sudo sh" >&2
    exit 1
fi
if ! command -v apt-get >/dev/null 2>&1; then
    echo "Bu betik Pardus ve Debian tabanlı sistemler içindir (apt bulunamadı)." >&2
    exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
    apt-get update -q && apt-get install -y -q curl
fi

elle_kur() {
    cat >&2 <<EOF

Paketi tarayıcıyla indirip elle kurabilirsiniz:
  1. https://github.com/$REPO/releases/latest adresinden
     dys-asistan_*_all.deb dosyasını indirin.
  2. sudo apt install ~/İndirilenler/dys-asistan_*_all.deb
     (klasör adı ~/Downloads da olabilir)
EOF
}

# curl'ün hata koduna göre anlaşılır ileti; bağlantı doğrulaması asla kapatılmaz
curl_hatasi() {
    case $1 in
        60|77|35)
            cat >&2 <<EOF
GitHub'ın sertifikası doğrulanamadı (curl hata $1).
Kurum ağlarında bunun sebebi çoğunlukla güvenlik duvarının HTTPS trafiğini
kendi sertifikasıyla yeniden imzalamasıdır (SSL denetimi). Bilgi işlemden
kurumun kök sertifikasını alıp sisteme ekleyin:
  sudo cp kurum-kok.crt /usr/local/share/ca-certificates/
  sudo update-ca-certificates
Sertifikayı kimin verdiğini görmek için:
  echo | openssl s_client -connect api.github.com:443 -servername api.github.com 2>/dev/null | openssl x509 -noout -issuer
Sistem saati yanlışsa da bu hata görülür: date
EOF
            ;;
        5|6|7|28)
            echo "GitHub'a bağlanılamadı (curl hata $1): internet bağlantısını ya da vekil sunucu (proxy) ayarını denetleyin." >&2 ;;
        22)
            echo "GitHub isteği reddetti (curl hata 22): https://github.com/$REPO/releases" >&2 ;;
        *)
            echo "İndirme başarısız (curl hata $1)." >&2 ;;
    esac
    elle_kur
    exit 1
}

echo "Son sürüm aranıyor..."
KOD=0
YANIT=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest") || KOD=$?
[ $KOD -eq 0 ] || curl_hatasi $KOD
URL=$(printf '%s\n' "$YANIT" | sed -n 's/.*"browser_download_url": *"\([^"]*_all\.deb\)".*/\1/p' | head -n 1)
if [ -z "$URL" ]; then
    echo "İndirilecek paket bulunamadı: https://github.com/$REPO/releases" >&2
    exit 1
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
DEB="$TMP/$(basename "$URL")"
echo "İndiriliyor: $URL"
curl -fsSL -o "$DEB" "$URL" || curl_hatasi $?
chmod 644 "$DEB"

apt-get update -q
apt-get install -y -q "$DEB"

echo
echo "DYS Asistan kuruldu: $(dys-asistan --version)"
echo "Oturum açılışında kendiliğinden başlar; şimdi başlatmak için: dys-asistan &"
