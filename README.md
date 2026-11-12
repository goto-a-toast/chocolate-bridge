# chocolate-bridge

Use an **M-VAVE Chocolate** (original, non-Plus) MIDI footswitch with **Ableton Live** in groups,
with no official app running. Mac only.

Live cannot MIDI-map Program Change, and the original Chocolate only has group switching in its
Program Change modes. This bridge converts the pedal's Program Change messages into notes on a
virtual MIDI port, so every switch in every group becomes a separate, mappable toggle in Live.

> Unofficial. The SysEx protocol is community reverse-engineered. Tested on one original
> Chocolate (USB name `SINCO`, Bluetooth name `FootCtrl`) on macOS 14. Use at your own risk.

---

## 概要（日本語）

M-VAVE Chocolate（無印）を Program Change A モードで使い、PC 番号をノートに変換して
仮想 MIDI ポート「Chocolate to Live」へ流します。Live はノートをトグルとしてマップできるので、
グループごとに別々のエフェクトやルーパー操作を割り当てられます。

## インストール

```bash
git clone https://github.com/goto-a-toast/chocolate-bridge.git
cd chocolate-bridge
bash install.sh
```

Python 環境の作成、ログイン時の自動起動の登録、起動までを行います。
Python が無いと言われたら、先に `xcode-select --install` を実行してください。

macOS はデスクトップや書類フォルダを裏で動くプログラムから保護しているため、
実際に動くプログラムは `~/Library/Application Support/chocolate-bridge` に配置されます。
クローンしたフォルダはどこに置いても構いません。
更新するときは `git pull` のあと `bash install.sh` をもう一度実行します。
解除は `bash uninstall.sh` です。

## ペダルの準備（初回のみ、USB 接続で）

```bash
./venv/bin/python -c "from choc import *; c=Choc(); c.discover(); print(c.write(0, 0x00))"   # Program Change A
./venv/bin/python trs.py midi    # 空の TRS ジャックのノイズ（CC 20）を止める
```

設定はペダル本体に保存されるので、別の Mac で繰り返す必要はありません。

## 対応表（Program Change A、NOTE_BASE = 36）

| グループ | A | B | C | D |
|---|---|---|---|---|
| 1 | C1 (36)  | C#1 (37) | D1 (38)  | D#1 (39) |
| 2 | E1 (40)  | F1 (41)  | F#1 (42) | G1 (43)  |
| 3 | G#1 (44) | A1 (45)  | A#1 (46) | B1 (47)  |
| 4 | C2 (48)  | C#2 (49) | D2 (50)  | D#2 (51) |

グループ 5〜8 も同じ規則で続きます。A+B 同時押しで前のグループ、C+D 同時押しで次のグループです。

## Live 側

1. 環境設定 → Link, Tempo & MIDI で、入力「Chocolate to Live」の Remote を On。
2. MIDI マップモード（Cmd+M）で対象のボタンをクリックし、ペダルを踏む。

## Bluetooth

1. 「Audio MIDI 設定」→ ウインドウ → MIDI スタジオを表示 → ツールバーの Bluetooth ボタン。
   通常の Bluetooth 設定画面からは接続できません。
2. 「Bluetooth 構成」ウインドウを開いたままペダルの電源を入れ直し、FootCtrl の「接続」を押す。
3. ブリッジが自動で見つけます。USB と Bluetooth が両方あるときは USB を優先し、片方だけを使います。

ペダルの設定変更（SysEx）は USB で行ってください。

## TRS ジャック

エクスプレッションペダルを使うときは USB で繋いで `./venv/bin/python trs.py expression`、
戻すときは `./venv/bin/python trs.py midi`。

## ファイル

| ファイル | 役割 |
|---|---|
| `bridge.py` | PC → ノート変換の常駐プログラム |
| `choc.py` | ペダルとの SysEx 通信（設定の読み書き） |
| `trs.py` | TRS ジャックの切り替え |
| `install.sh` / `uninstall.sh` | 自動起動の登録と解除 |

ログは `~/Library/Application Support/chocolate-bridge/bridge.log` に出ます。
インストール後はこのフォルダの `bridge.log` からも開けます。

## Credits

Protocol knowledge comes from these community projects:

- [cbix/mvave-chocolate-sysex](https://github.com/cbix/mvave-chocolate-sysex)
- [vctorgab/mvave-chocolate-tui](https://github.com/vctorgab/mvave-chocolate-tui)
- [majabojarska/OpenChocolate](https://github.com/majabojarska/OpenChocolate)

## License

MIT
