# Cai dat trimui-chiaki-ng vao TrimUI Smart Pro S

## Buoc 1: Copy file

Copy `files/` vao the nho theo duong dan `/mnt/SDCARD/Apps/Chiaki/`:

```
Apps/Chiaki/
  app.py
  config.json
  launch.sh
  settings.json
  rh/
    engine.py
    chiaki.py
    updater.py
    ...
```

## Buoc 2: Icon

Dat file `icon.png` (toa 256x256, PNG transparent) vao `Apps/Chiaki/icon.png`.

## Buoc 3: Khoi dong

Tren may Smart Pro S:

1. Vao menu Apps.
2. Chon **Chiaki-ng**.
3. App se khoi dong, hien menu chinh, quet may PS4/PS5 qua Wi-Fi.

## Luu y

- Can Python 3.10+. Firmware TrimUI Linux 1.1.1 da co san.
- Can SDL2 + SDL2_ttf. Co san trong `/usr/lib64` cua firmware.
- Muon auto-update, can Wi-Fi ket noi Internet.
- Lan dau tien nen tat Bluetooth de tranh nhieu Wi-Fi (khuyen cao hang).

## Auto-update

Sau khi cai, app se tu check GitHub release moi khi khoi dong. Neu co ban moi se hien popup cho phep cap nhat.