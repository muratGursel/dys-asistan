#!/bin/sh
# DYS Asistan tanılama betiği.
#
# Tarayıcıyla ilgili bilgileri toplar, olası sebepleri inceler ve sonucu
# ~/dys-tani.txt dosyasına yazar. Normal kullanıcı olarak çalıştırın (sudo
# gerekmez). Besleyicili tarayıcılarda (ör. Canon DR-C225) çalıştırmadan önce
# besleyiciye 2 sayfa koyun: iki deneme taraması yapılır.
#
#   sh dys-tani.sh
#   sh dys-tani.sh --derin     # tarama çöküyorsa: besleyiciye 10 sayfa koyun;
#                              # sebebi daraltmak için seçenekleri tek tek değiştirerek tarar
#
# Çıktıda DYS oturum bilgisi (token) bulunmaz.

CIKTI="$HOME/dys-tani.txt"
DERIN=0
[ "${1:-}" = "--derin" ] && DERIN=1
sebep() { echo "  >> OLASI SEBEP: $*"; }
baslik() { echo; echo "== $*"; }

{
echo "DYS Asistan tanılama — $(date '+%d.%m.%Y %H:%M:%S')"
[ $DERIN -eq 1 ] && echo "(derin tanılama)"

baslik "Sistem"
. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
uname -r
echo "kullanıcı: $(id -un), gruplar: $(id -Gn)"

baslik "Paketler"
for p in dys-asistan sane-utils libsane1 libsane-common sane-airscan; do
    s=$(dpkg-query -W -f '${Status} ${Version}' "$p" 2>/dev/null)
    case "$s" in
        "install ok installed"*) echo "  $p ${s##* }" ;;
        *) echo "  $p: KURULU DEĞİL" ;;
    esac
done
command -v scanimage >/dev/null || sebep "scanimage yok: sudo apt install sane-utils"

baslik "USB'de görünen tarayıcılar"
# Canon (04a9) ve Canon Electronics (1083: imageFORMULA DR serisi)
USB=$(lsusb 2>/dev/null | grep -i -E "ID (04a9|1083):|canon|scanner")
if [ -n "$USB" ]; then
    echo "$USB"
else
    echo "  (yok)"
    lsusb 2>/dev/null | sed 's/^/  /'
    sebep "Tarayıcı USB'de görünmüyor: kablo, güç düğmesi ya da başka bir USB girişini deneyin."
fi

baslik "USB aygıt dosyası izinleri"
echo "$USB" | while read -r _ bus _ dev _; do
    [ -n "$bus" ] || continue
    dosya="/dev/bus/usb/$bus/${dev%:}"
    [ -e "$dosya" ] || continue
    ls -l "$dosya"
    command -v getfacl >/dev/null && getfacl -p "$dosya" 2>/dev/null | grep -v "^#" | sed 's/^/    /'
    if [ -r "$dosya" ] && [ -w "$dosya" ]; then
        echo "  $dosya: okuma/yazma izni VAR"
    else
        echo "  $dosya: okuma/yazma izni YOK"
        echo "  >> OLASI SEBEP: Kullanıcının tarayıcıya erişim izni yok (udev kuralı). Oturumu kapatıp açın; sürmezse: sudo usermod -aG scanner $(id -un)"
    fi
    if command -v fuser >/dev/null && fuser "$dosya" >/dev/null 2>&1; then
        echo "  aygıtı kullanan işlem(ler): $(fuser "$dosya" 2>/dev/null)"
        echo "  >> OLASI SEBEP: Tarayıcı başka bir uygulama tarafından kullanılıyor (ör. Basit Tarayıcı / simple-scan)."
    fi
done

baslik "SANE sürücü yapılandırması"
if grep -q -E "^\s*canon_dr\b" /etc/sane.d/dll.conf 2>/dev/null; then
    echo "  canon_dr sürücüsü açık (/etc/sane.d/dll.conf)"
else
    echo "  canon_dr sürücüsü dll.conf içinde KAPALI ya da yok"
    echo "$USB" | grep -q -i "1083:" && sebep "canon_dr sürücüsü kapalı: /etc/sane.d/dll.conf dosyasında 'canon_dr' satırının başındaki # işaretini kaldırın."
fi
for m in DR-C225 DR-C225W; do
    if grep -rqs "$m" /usr/share/sane/descriptions/canon_dr.desc /etc/sane.d/canon_dr.conf 2>/dev/null; then
        echo "  $m bu SANE sürümünün canon_dr listesinde var"
    fi
done
grep -rhs -i -E "^\s*usb\s+0x1083" /etc/sane.d/canon_dr.conf 2>/dev/null | head -3 | sed 's/^/  canon_dr.conf: /'

baslik "SANE'in gördüğü tarayıcılar"
echo "  ... tarayıcılar aranıyor (ağdakiler de arandığı için 1-2 dakika sürebilir)"
# scanimage -f kabuğun \t ve \n kaçışlarını yorumlamaz; %n satır sonudur, ayraç '|'
LISTE=$(timeout 90 scanimage -f "%d|%v %m|%t%n" 2>/dev/null)
YEREL=$(echo "$LISTE" | grep -E "^[a-z0-9_]+:" | grep -v -E "(escl|airscan|v4l):")
if [ -n "$YEREL" ]; then echo "$YEREL" | sed 's/^/  /'; else echo "  (USB tarayıcı yok)"; fi
echo "  ağ tarayıcıları (eSCL/AirScan/WSD): $(echo "$LISTE" | grep -c -E "(escl|airscan):")"
D=$(echo "$YEREL" | cut -d'|' -f1 | grep -i "canon_dr" | head -1)
[ -n "$D" ] || D=$(echo "$YEREL" | cut -d'|' -f1 | head -1)
if [ -z "$D" ]; then
    if [ -n "$USB" ]; then
        sebep "Tarayıcı USB'de var ama SANE görmüyor: sürücü kapalı, izin yok ya da bu SANE sürümü cihazı desteklemiyor."
    fi
    echo "  USB tarayıcı bulunamadı; deneme taraması atlanıyor."
else
    echo "  denenecek cihaz: $D"

    baslik "Cihaz seçenekleri (scanimage -A)"
    echo "  ... cihazın seçenekleri okunuyor"
    SECENEK=$(timeout 60 scanimage -d "$D" -A 2>&1)
    echo "$SECENEK" | grep -E "^\s+(--source|--mode|--resolution|-[lxyt]|--page-width|--page-height)\b" | sed 's/^/  /'
    YMAX=$(echo "$SECENEK" | sed -n 's/^\s*-y [0-9.]*\.\.\([0-9.]*\)mm.*/\1/p')
    PHMAX=$(echo "$SECENEK" | sed -n 's/^\s*--page-height [0-9.]*\.\.\([0-9.]*\)mm.*/\1/p')
    if [ -n "$PHMAX" ]; then SAYFA="var (en fazla $PHMAX mm)"; else SAYFA="yok"; fi
    echo "  en fazla tarama boyu: ${YMAX:-?} mm; sayfa boyu seçeneği: $SAYFA"
    if [ -n "$YMAX" ] && [ "${YMAX%.*}" -lt 297 ]; then
        if [ -n "$PHMAX" ]; then
            echo "  NOT: Tarama boyu varsayılan olarak ${YMAX} mm; A4 için önce --page-height 297 verilmeli."
        else
            sebep "Cihazın tarama alanı A4'ten kısa (${YMAX} mm); DYS Asistan ayarlarında Sayfa: 'Tarayıcının tüm alanı' seçilmeli."
        fi
    fi

    COKEN=""   # ilk çöken denemenin biçimi ve seçenekleri (derin kipte sürücü günlüğüyle yinelenir)
    kod=0
    tara() {   # $1 açıklama, $2 biçim (png/pnm/tiff), sonra scanimage seçenekleri
        ad="$1"; bicim="$2"; shift 2
        echo; echo "-- $ad"
        echo "   scanimage -d '$D' $* --format=$bicim"
        echo "   ... taranıyor (en fazla 2 dakika)"
        rm -f /tmp/dys-tani.img
        timeout 120 scanimage -d "$D" "$@" --format="$bicim" -o /tmp/dys-tani.img >/tmp/dys-tani.err 2>&1
        kod=$?
        sed 's/^/   /' /tmp/dys-tani.err
        if [ $kod -eq 0 ] && [ -s /tmp/dys-tani.img ]; then
            echo "   SONUÇ: başarılı ($(stat -c %s /tmp/dys-tani.img) bayt)"
            return
        fi
        echo "   SONUÇ: başarısız (çıkış kodu $kod)"
        case $kod in
            134|136|139)
                case $kod in 134) tur="abort";; 136) tur="kayan nokta hatası";; *) tur="bellek hatası";; esac
                echo "   >> scanimage çöktü ($tur)"
                [ -n "$COKEN" ] || COKEN="$bicim|$*"
                if [ $DERIN -eq 0 ]; then
                    sebep "scanimage tarama sırasında çöküyor (SANE sürücü hatası). Sebebi daraltmak için besleyiciye 10 sayfa koyup derin tanılama çalıştırın (kılavuzda: 'Derin tanılama')."
                else
                    sebep "scanimage tarama sırasında çöküyor (SANE sürücü hatası); hangi seçeneklerde çöktüğü 'Derin tanılama özeti' tablosunda."
                fi
                return ;;
            124)
                sebep "Tarama 2 dakikada bitmedi: tarayıcı yanıt vermiyor; kapatıp açın."
                return ;;
        esac
        hata=$(grep -v -i "rounded value" /tmp/dys-tani.err | tail -1)
        case "$hata" in
            *"out of documents"*|*"No more documents"*|*"no documents"*)
                sebep "Besleyicide kağıt yok ya da kağıt algılanmadı: sayfayı besleyiciye tam oturtun." ;;
            *"busy"*|*"Device busy"*)
                sebep "Tarayıcı meşgul: başka bir tarama uygulamasını kapatıp yeniden deneyin." ;;
            *"denied"*|*"permission"*)
                sebep "Erişim izni yok: oturumu kapatıp açın; sürmezse kullanıcıyı 'scanner' grubuna ekleyin." ;;
            *"jammed"*|*"Jam"*)
                sebep "Kağıt sıkışması: besleyiciyi açıp kağıdı çıkarın." ;;
            *"cover"*|*"Cover"*)
                sebep "Tarayıcının kapağı açık." ;;
            *"I/O"*)
                sebep "Cihazla iletişim hatası (I/O): USB kablosunu çıkarıp takın, tarayıcıyı kapatıp açın." ;;
            *"Invalid argument"*)
                sebep "Cihaz bir seçeneği kabul etmedi: $hata" ;;
        esac
    }

    if [ -n "$PHMAX" ]; then A4="--page-width 210 --page-height 297 -x 210 -y 297"; else A4="-x 210 -y 297"; fi

    if [ $DERIN -eq 0 ]; then
        baslik "Deneme taramaları (her biri besleyiciden 1 sayfa çeker)"
        tara "1) en az seçenekle" png
        # shellcheck disable=SC2086
        tara "2) A4, önce sayfa boyu ayarlanarak (DYS Asistan'ın yöntemi)" png --resolution 200 --mode Gray $A4
    else
        baslik "Derin tanılama: seçenekler tek tek değiştirilerek (her biri 1 sayfa çeker)"
        echo "  Amaç: çökmenin görüntü biçiminden mi, çözünürlükten mi, renkten mi,"
        echo "  sayfa boyu ayarından mı kaynaklandığını ayırmak."
        TABLO=""
        dene() {   # $1 kısa ad, $2 biçim, sonra seçenekler
            kisa="$1"; shift
            tara "$kisa" "$@"
            if [ $kod -eq 0 ] && [ -s /tmp/dys-tani.img ]; then durum="başarılı"
            else case $kod in 134|136|139) durum="ÇÖKTÜ ($kod)";; *) durum="hata ($kod)";; esac; fi
            TABLO="$TABLO
  $(printf '%-44s %s' "$kisa" "$durum")"
        }
        # shellcheck disable=SC2086
        {
        dene "D1  PNM, varsayılan seçenekler"         pnm
        dene "D2  PNG, varsayılan seçenekler"         png
        dene "D3  TIFF, varsayılan seçenekler"        tiff
        dene "D4  PNM, 200 dpi gri"                   pnm --resolution 200 --mode Gray
        dene "D5  PNM, 300 dpi gri"                   pnm --resolution 300 --mode Gray
        dene "D6  PNM, 200 dpi siyah-beyaz"           pnm --resolution 200 --mode Lineart
        dene "D7  PNM, 200 dpi renkli"                pnm --resolution 200 --mode Color
        dene "D8  PNM, 200 dpi gri, A4 sayfa boyu"    pnm --resolution 200 --mode Gray $A4
        dene "D9  PNG, 200 dpi gri, A4 (DYS Asistan)" png --resolution 200 --mode Gray $A4
        }

        baslik "Derin tanılama özeti"
        echo "$TABLO"

        if [ -n "$COKEN" ]; then
            baslik "Sürücü ayrıntılı günlüğü (ilk çöken deneme yineleniyor, 1 sayfa çeker)"
            bicim=${COKEN%%|*}; secenek=${COKEN#*|}
            echo "  seçenekler: $secenek --format=$bicim"
            echo "  ... taranıyor"
            # cihazın sürücüsüne göre: canon_dr:… -> SANE_DEBUG_CANON_DR
            hata_ayiklama="SANE_DEBUG_$(echo "${D%%:*}" | tr 'a-z' 'A-Z')=20"
            echo "  ayrıntı: $hata_ayiklama"
            # shellcheck disable=SC2086
            env "$hata_ayiklama" SANE_DEBUG_DLL=1 timeout 120 scanimage -d "$D" $secenek \
                --format="$bicim" -o /tmp/dys-tani.img >/dev/null 2>/tmp/dys-tani.dbg
            echo "  çıkış kodu: $?; günlüğün son 120 satırı:"
            tail -120 /tmp/dys-tani.dbg | sed 's/^/    /'
            rm -f /tmp/dys-tani.dbg
        fi
    fi
    rm -f /tmp/dys-tani.img /tmp/dys-tani.err
fi

baslik "DYS Asistan"
if pgrep -f '^/usr/bin/python3 /usr/bin/dys-asistan' >/dev/null; then
    echo "  çalışıyor"
else
    echo "  ÇALIŞMIYOR"
    sebep "DYS Asistan çalışmıyor: menüden başlatın ya da oturumu kapatıp açın."
fi
AYAR="$HOME/.config/dys-asistan/ayarlar.json"
[ -f "$AYAR" ] && { echo "  ayarlar:"; grep -v -i token "$AYAR" | sed 's/^/    /'; }
echo "  günlük (son 40 satır):"
tail -40 "$HOME/.config/dys-asistan/gunluk.txt" 2>/dev/null | sed 's/^/    /'

} 2>&1 | tee "$CIKTI"

# alt kabuklarda bulunanlar da dahil, bütün sebepleri dosyadan topla
{
    baslik "Özet: olası sebepler"
    if grep -q "OLASI SEBEP:" "$CIKTI"; then
        grep "OLASI SEBEP:" "$CIKTI" | sed 's/.*OLASI SEBEP: /- /' | awk '!g[$0]++'
    else
        echo "- Belirgin bir sebep bulunamadı; bu dosyayı geliştiriciye iletin."
    fi
} | tee -a "$CIKTI"

echo
echo "Tanılama tamamlandı. Yukarıdaki çıktının tamamı şu dosyaya kaydedildi:"
echo "    $CIKTI"
echo "Sorun çözülmediyse bu dosyayı destek isteğinize ekleyin."
