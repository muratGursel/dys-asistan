# Kullanım

## İlk açılış

Kurulumdan sonra DYS Asistan her oturum açılışında kendiliğinden başlar ve
sistem çekmecesinde bir tarayıcı simgesi olarak görünür. Hemen başlatmak için
menüden **DYS Asistan**'ı seçin ya da uçbirimde `dys-asistan &` yazın.

Simgenin menüsü:

| Öğe | İşlev |
|---|---|
| Taranan belgeler klasörü | Taranan PDF'lerin bulunduğu klasörü açar |
| Ayarlar… | Tarayıcı ve tarama ayarları |
| Hakkında | Sürüm bilgisi |
| Çıkış | Yardımcıyı kapatır; DYS taramayı kullanamaz |

## Ayarlar

| Ayar | Açıklama |
|---|---|
| Tarayıcı | DYS tarayıcı belirtmezse kullanılacak cihaz. ↻ ile ağ yeniden aranır. |
| Çözünürlük | 200 dpi evrak için yeterlidir; dosya boyutu çözünürlükle hızla büyür. |
| Renk | Gri (önerilen), Renkli, Siyah-beyaz |
| Sayfa | A4 (önerilen), A5 ya da tarayıcının tüm alanı |
| Kaynak | Boş bırakılırsa cihazın varsayılanı (çoğunlukla cam). Belge besleyiciden taramak için cihazın kaynak adını yazın (`ADF`, `Automatic Document Feeder` vb.); adları `scanimage -d CİHAZ --help` gösterir. |
| "Bir sayfa daha?" | Her sayfadan sonra sorulsun mu |

Ayarlar `~/.config/dys-asistan/ayarlar.json` dosyasında tutulur.

## DYS'de tarama

1. DYS'de **Tara**'ya basın. Tarayıcı listesi gelir; ağdaki cihazlar adı ve
   IP adresiyle görünür.
2. Tarayıcıyı seçip taramayı başlatın.
3. İlk sayfa tarandıktan sonra **"1 sayfa tarandı"** penceresi çıkar:
   sonraki sayfayı cama yerleştirip **Bir sayfa daha tara** ya da
   **Bitir**.
4. Sayfalar tek PDF'te birleşir ve DYS'ye yüklenir.

Taranan PDF'ler `~/.local/share/dys-asistan/Taranan` klasöründe kalır;
DYS'nin dosya listesinden açılıp silinebilir.

## Barkod ve belge yazdırma

DYS'de **Barkod yazdır** ya da yazdırma işlemi başlatıldığında DYS yazıcı
seçimi isterse **Yazdır** penceresi çıkar: yazıcıyı ve kopya sayısını seçin.
Barkod etiketi 72×36 mm'dir; etiket yazıcılarında kağıt boyutu kendiliğinden
ayarlanır, A4 yazıcılarda sayfaya sığdırılır.

## Sorun giderme

**Kurulumda "SSL certificate problem: unable to get local issuer certificate".**
Bilgisayar GitHub'ın sertifikasını doğrulayamıyor. Kurum ağlarında sebep
çoğunlukla güvenlik duvarının HTTPS trafiğini kendi sertifikasıyla yeniden
imzalamasıdır (SSL denetimi); tarayıcılar kurumun sertifikasına güvendiği
için çalışır, uçbirimdeki `curl` ise tanımaz.

- Hemen kurmak için: [Sürümler](https://github.com/muratGursel/dys-asistan/releases/latest)
  sayfasından `dys-asistan_*_all.deb` dosyasını tarayıcıyla indirip
  `sudo apt install ~/İndirilenler/dys-asistan_*_all.deb` ile kurun.
- Kalıcı çözüm: bilgi işlemden kurumun kök sertifikasını alıp sisteme ekleyin:
  `sudo cp kurum-kok.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates`.
- Sertifikayı kimin verdiğini görmek için:
  `echo | openssl s_client -connect api.github.com:443 -servername api.github.com 2>/dev/null | openssl x509 -noout -issuer`.
  GitHub'ın sağlayıcısı yerine bir güvenlik duvarı ya da kurum adı
  görünüyorsa sebep SSL denetimidir.
- Sistem saati yanlışsa da aynı hata görülür; `date` ile denetleyin.

Kurulum betiği bağlantı doğrulamasını hiçbir zaman kapatmaz: doğrulanmamış
bir bağlantıdan yönetici yetkisiyle paket kurmak güvenli değildir.

**Tarayıcı listede yok.**
`dys-asistan --tarayicilari-listele` çıktısına bakın. Boşsa:

- Ağ tarayıcıları için `sane-airscan` kurulu olmalı:
  `sudo apt install sane-airscan`.
- Cihazın aynı ağda olduğundan ve eSCL/AirScan'in açık olduğundan emin olun.
- USB tarayıcılar için `scanimage -L` cihazı göstermiyorsa cihazın SANE
  desteğini kontrol edin (http://www.sane-project.org/sane-supported-devices.html).

**DYS "yardımcı çalışmıyor" diyor.**
Çekmecede simgenin olduğundan emin olun. Windows'tan kopyalanmış eski bir
EbysAsistan aynı portu tutuyorsa onu kapatın.

**Tarama hata veriyor.**
`~/.config/dys-asistan/gunluk.txt` dosyasının son satırlarına bakın;
`dys-asistan --ayrintili` ile daha ayrıntılı günlük alınır. Günlükte DYS
oturum bilgisi bulunmaz. Sebep anlaşılmıyorsa tanılama aracını çalıştırın.

## Tanılama aracı

Tarayıcı görünmüyor ya da tarama hata veriyorsa tanılama aracı bilgileri
toplar, olası sebepleri inceler ve sonucu bir dosyaya yazar.

1. Besleyicili tarayıcılarda (ör. Canon DR-C225) besleyiciye **2 sayfa**
   koyun; araç iki deneme taraması yapar. Camlı tarayıcılarda cama bir sayfa
   koymanız yeterli.
2. Uçbirimde **normal kullanıcı olarak** (`sudo` olmadan) çalıştırın:

   ```sh
   curl -fsSL https://raw.githubusercontent.com/muratGursel/dys-asistan/main/tools/dys-tani.sh | sh
   ```

   İnternete erişimi olmayan bilgisayarlarda `tools/dys-tani.sh` dosyasını
   kopyalayıp `sh dys-tani.sh` ile çalıştırın.
3. Araç ağdaki tarayıcıları da aradığı için 1-2 dakika sürer. Bitince sonuç
   **`~/dys-tani.txt`** dosyasına yazılır ve dosyanın yolu ekranda gösterilir.

### Derin tanılama

Deneme taramalarında **"scanimage çöktü"** görülüyorsa (SANE sürücü hatası),
sebebi daraltmak için derin tanılama çalıştırın. Besleyiciye **10 sayfa**
koyun; araç görüntü biçimini, çözünürlüğü, rengi ve sayfa boyu ayarını tek tek
değiştirerek 9 deneme taraması yapar, sonuçları bir tabloda gösterir ve ilk
çöken denemeyi sürücünün ayrıntılı günlüğüyle yineler:

```sh
curl -fsSL https://raw.githubusercontent.com/muratGursel/dys-asistan/main/tools/dys-tani.sh | sh -s -- --derin
```

Dosyayla çalıştırırken: `sh dys-tani.sh --derin`. Sonuç yine
`~/dys-tani.txt` dosyasına yazılır.

Dosyanın sonundaki **"Özet: olası sebepler"** bölümü bulunan sorunları ve
çözüm önerilerini listeler. Sorunu çözemezseniz dosyayı
[Issues](https://github.com/muratGursel/dys-asistan/issues) sayfasında yeni
bir kayda ekleyin.

Araç şunları inceler:

| Denetim | Ortaya çıkarabileceği sebep |
|---|---|
| USB aygıt listesi | Tarayıcı bağlı değil ya da kapalı |
| USB aygıt izinleri | Kullanıcının tarayıcıya erişim izni yok |
| Aygıtı kullanan işlemler | Tarayıcıyı başka bir uygulama tutuyor |
| SANE sürücü yapılandırması | Sürücü kapalı ya da cihaz bu SANE sürümünde desteklenmiyor |
| SANE'in gördüğü tarayıcılar | Cihaz USB'de var ama SANE görmüyor |
| Cihaz seçenekleri | Tarama alanı A4'ten kısa, sayfa boyu ayarı gerekiyor |
| İki deneme taraması | Kağıt yok, meşgul, izin, sıkışma, kapak açık, USB iletişim hatası |
| DYS Asistan | Çalışmıyor; ayarlar ve günlüğün son satırları |

Sonuç dosyasında DYS oturum bilgisi (token) bulunmaz; kullanıcı adı,
gruplar, sistem ve paket sürümleri ile bağlı cihazların adları bulunur.
