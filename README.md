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

## グループでプリセットを切り替える（ペダルボード化）

グループを切り替えると、ブリッジは **CC 102** を送ります。値はグループ 1 = 0、2 = 16、3 = 32 … 8 = 112 です。
ペダル自体は A+B / C+D で「前へ」「次へ」（CC 2 / CC 3）しか送らないので、ブリッジがグループを数えています。
スイッチを踏むたびに PC 番号から数え直すので、ずれても次に踏んだ時点で正しくなります。
元の CC 2 / CC 3 は Live に渡しません。

1. ギター入力のトラックに Audio Effect Rack を置き、チェーンをプリセットの数だけ作る（例：クリーン、クランチ、リード）。
2. Rack の「Chain」表示でチェーンセレクターのゾーンを出し、右クリック →「範囲を均等に配分」（Distribute Ranges Equally）。
   チェーンが 8 本なら 0–15、16–31 … になり、CC 102 の値と一致します。8 本未満でも、グループ番号 = チェーン番号になるようにゾーンを合わせてください。
3. MIDI マップモードでチェーンセレクターをクリックし、ペダルでグループを切り替える（CC 102 が割り当てられる）。
4. 各チェーンのエフェクトのオン/オフに、そのグループの A〜D を割り当てる。
5. ディレイやリバーブは Return トラックに置くと、プリセットを切り替えても残響が途切れません。

起動直後はグループ 1 として数え始めます。ブリッジ起動時にペダルが別のグループにいた場合は、スイッチを一度踏めば合います。

## Bluetooth

1. 「Audio MIDI 設定」→ ウインドウ → MIDI スタジオを表示 → ツールバーの Bluetooth ボタン。
   通常の Bluetooth 設定画面からは接続できません。
2. 「Bluetooth 構成」ウインドウを開いたままペダルの電源を入れ直し、FootCtrl の「接続」を押す。
3. ブリッジが自動で見つけます。USB と Bluetooth が両方あるときは両方を受信します
   （Bluetooth 接続中のペダルは USB 側に何も送らないことがあるため）。
   同じ信号が両方から届いた場合は 1 回分だけノートを出すので、二重に反応することはありません。

### マップモードでは割り当てられるのに、通常時に反応しない

- `bridge.log` に `PC … -> note …` が出ているか確認します。出ていなければブリッジにペダルの信号が届いていません。
- Live の環境設定で、ペダル本体の入力（`SINCO` / `FootCtrl`）の Remote は Off にし、「Chocolate to Live」だけを On にします。
  ペダル本体の Remote が On のままだと、ブリッジが止まっていても MIDI インジケーターは光るので、原因の切り分けを誤りやすくなります。
- コントロールサーフェスに「Chocolate to Live」を入力とするスクリプトを割り当てないでください（「なし」にする）。

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
