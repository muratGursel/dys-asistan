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
oturum bilgisi bulunmaz.
