# trimui-chiaki-ng

PS4 / PS5 Remote Play client cho TrimUI Smart Pro S firmware Linux 1.1.1.

**Trang thai**: v0.1.0 - bootstrap. Chay duoc app, scan host PS4/PS5 qua LAN, hien menu va auto-update. Video stream that su se ship o v0.2.0 cung codec H264 / H265.

## Muc tieu phan cung

- **SoC**: Allwinner A523 8-core Cortex-A55 @ 2.0GHz
- **GPU**: ARM Mali-G57 MC1 @ 744MHz
- **RAM**: 1GB LPDDR4
- **Display**: 4.96 inch 1280x720 IPS (native 720p)
- **Wi-Fi**: 802.11 a/b/g/n/ac/ax dual-band
- **Firmware**: TrimUI Linux custom 1.1.1 (TG5050 Smart Pro S)

## Cau hinh video de xuat (muc tieu v0.2.0)

- Resolution: `720p` (native, khong ton scaler)
- FPS: `30`
- Bitrate: `8000-10000` kbps
- Codec: H264 (PS4), H265 (PS5)

## Cai dat vao the nho

1. Copy `files/` len the nho vao `/mnt/SDCARD/Apps/Chiaki/`.
2. File icon `icon.png` nen co trong thu muc.
3. Trong he dieu hanh TrimUI, mo menu -> Apps -> Chiaki.
4. Lan dau khoi dong app se:
   - Kiem tra Python 3, neu thieu se bao loi huong dan.
   - Tu dong kiem tra update tu GitHub release (co the tat qua settings).

## Auto-update (OTA)

App check `https://raw.githubusercontent.com/nlkcodenew/trimui-chiaki-ng/main/manifest.json` luc khoi dong va popup neu co ban moi.

- Bam **CAI NGAY**: app se tai tung file, verify sha256, roi os.replace vao cho that.
- Bam **DE SAU**: dong popup, lan sau se hoi lai.
- Bam **BO QUA**: ghi version vao `settings.json.skipped_versions`, khong hoi nua.

`settings.json` tren may khong bao gio bi ghi de (de bao toan cau hinh nguoi dung).

## Cau truc repo

```
tools/
  make_release.py       # Build manifest.json voi sha256 moi
files/
  app.py                # Entry point
  config.json           # TrimUI launcher manifest
  launch.sh             # Boot script (tim python3, dat env, log)
  settings.json         # Cau hinh nguoi dung
  rh/
    engine.py           # SDL2 engine
    chiaki.py           # Wrapper discovery / wakeup / session
    updater.py          # OTA updater
    modals/update.py    # Modal popup update
    screens/            # UI screens (home, settings, ...)
    state.py            # Runtime state
    version.py          # APP_VERSION single source of truth
.github/workflows/
  release.yml           # Auto build manifest + Release on tag v*
manifest.json           # (chi tool tao ra) sha256 list + version
```

## Build release

Tag phien ban moi:

```
git tag v0.2.0
git push origin v0.2.0
```

GitHub Action chay `tools/make_release.py` -> cap nhat `manifest.json` -> commit nguoc vao `main`. App se tu check va popup update trong vong 30 giay khi nguoi dung mo.

## Luat

`AGPL-3.0` (copy tu chiaki-ng upstream). Khi phat hanh binary phai kem source.