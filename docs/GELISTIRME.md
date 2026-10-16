# Geliştirici Notları

## Kaynaktan çalıştırmak

```sh
sudo apt install python3-gi gir1.2-gtk-3.0 python3-pil sane-utils sane-airscan cups-client \
    gir1.2-ayatanaappindicator3-0.1 gir1.2-notify-0.7 python3-pytest
git clone https://github.com/muratGursel/dys-asistan.git && cd dys-asistan
python3 -m dysasistan --tarayicilari-listele
python3 -m dysasistan --ayrintili           # çekmece arayüzüyle
python3 -m dysasistan --sunucu-yalniz       # arayüzsüz
python3 -m pytest -v
```

## Yapı

```text
dysasistan/
  __main__.py   Komut satırı, tek kopya denetimi, başlatma
  sunucu.py     Yerel HTTP sunucusu: uç noktalar, kaynak (Origin) denetimi
  tarama.py     SANE (scanimage) ile listeleme ve tarama
  pdf.py        Sayfaları tek PDF'te birleştirme
  dosyalar.py   Tarama klasörü: listeleme, açma, silme, yol sınırlaması
  dys.py        DYS dosya API'si: yükleme ve indirme
  yazdirma.py   CUPS ile yazdırma, barkod etiketi
  code128.py    Bağımlılıksız Code 128 kodlayıcı
  arayuz.py     GTK 3 çekmece simgesi ve pencereler
  ayarlar.py    Ayarlar ve dizinler
packaging/      .deb paketleme ve temiz kurulum testi
tools/          sahte_dys.html: DYS olmadan deneme sayfası
```

## DYS ile sözleşme

DYS sayfası `http://localhost:62222/<Uç>` adresine `POST` gönderir. Gövde
JSON'dur ama `Content-Type` başlığı `application/x-www-form-urlencoded`
olarak gelir (basit istek; ön uçuş yapılmaz). Bu yüzden gövde, başlığa
bakılmadan JSON olarak okunur. Her istekte `token` alanı vardır. Yanıt her
zaman JSON'dur: başarıda nesne ya da metin, hatada Türkçe ileti metni.

| Uç | Gövde | Başarılı yanıt |
|---|---|---|
| `IsAlive` | `token` | `"alive"` |
| `GetActiveScanners` | `token` | `[{scannerName, isDefault}]` |
| `StartScan` | `token, scannerName` | PDF'in tam yolu |
| `GetAllFileInfos` | `token` | `[{size: "0,07 MB", name, path, creationTime: "gg.aa.yyyy SS:dd:ss"}]` |
| `OpenPdf`, `OpenDirectory`, `DeletePdf` | `token, path` | `"done"` |
| `UploadPdf` | `token, apiUrl, path` | DYS'nin yükleme yanıtı (metin olarak) |
| `GetActivePrinters` | `token` | `[{printerName, isDefault}]` |
| `StartPrint` | aşağıda | `"done"` |

`UploadPdf`, `POST {apiUrl}upload/save` adresine
`{"data": base64, "fileName", "contentType": "application/pdf"}` gönderir;
`Authorization` başlığı token'dır.

`StartPrint` alanları: `contentType` (`barcode`, `application/pdf`,
`application/png`), `fileData` (base64) ya da `fileId` (yoksa
`GET {apiUrl}data/{fileId}/download` ile indirilir), `printerName`,
`printerDialog`, `copyCount`, `fileName` ve barkod için `code`,
`documentNumber`, `documentDate`, `generalDepartmentName`,
`detsisDepartmentName`, `creatorDepartmentName`. **`code` sayı olarak
gelebilir.** Ajan hata dönerse DYS tarayıcının yazdırma penceresine düşer.

DYS, tarama penceresini açarken `GetActiveScanners`'ı birkaç kez aynı anda
çağırır; liste 2 dakika önbellekte tutulur.

## Tarayıcı adları

`scanimage -f "%d\t%v\t%m\t%t\n"` çıktısı ayrıştırılır. Gözlenen tuhaflıklar
(testlerde gerçek örnekleri var):

- `airscan` modele ` ip=…` ekler; üretici yerine `eSCL` ya da `WSD` yazar.
- `escl` bazı cihazlarda stdout'a satır sonu olmadan HTTP hata metni basar;
  bu metin sonraki satırın başına yapışır.
- Aynı cihaz hem `escl:` hem `airscan:` ile görünür; IP'ye göre tekilleştirilir.
- Çoğu ağ cihazı varsayılan olarak tüm camı (Legal) tarar; `-x 210 -y 297`
  ile A4'e kırpılır.

## Ekransız deneme

`--sunucu-yalniz` ile arayüz yoktur: "bir sayfa daha?" sorulmaz, yazıcı
seçimi istenirse DYS'nin gönderdiği yazıcı kullanılır.
`DYS_ASISTAN_YAZICI_ZORLA=KUYRUK` ortam değişkeniyle bu durumda bütün
yazdırma işleri belirtilen CUPS kuyruğuna gider.

Kağıtsız yazdırma denemesi için raw bir CUPS kuyruğu, işi bir TCP alıcıya
aktarabilir:

```sh
sudo lpadmin -p DYS_Deneme -v socket://127.0.0.1:9199 -E -m raw
```

DYS olmadan denemek için:

```sh
python3 -m http.server 8000 -d tools &
python3 -m dysasistan --izin-ver http://localhost:8000
# tarayıcıda http://localhost:8000/sahte_dys.html
```

## Paket

```sh
sh packaging/build-deb.sh                                   # dist/dys-asistan_SÜRÜM_all.deb
sh packaging/temiz-kurulum-testi.sh dist/dys-asistan_*_all.deb debian:12   # Pardus 23 tabanı
sh packaging/temiz-kurulum-testi.sh dist/dys-asistan_*_all.deb debian:13   # Pardus 25 tabanı
```

Sürüm yalnızca `dysasistan/__init__.py` içindeki `__version__`'dadır.
`v*` etiketi gönderildiğinde CI paketi üretip GitHub sürümüne ekler.
