# 検証用フォント

`ipaexm.ttf` は IPAex明朝 004.01 の無改変ファイルです。検証時にこのファイルを
明示して使用します。OSへのインストールは不要です。製品APIの既定書体を決めるもの
ではなく、利用側は使用するフォントファイルを明示します。

## 出所と利用条件

- [公式配布ページ](https://moji.or.jp/ipafont/ipaex00401/)
- [公式配布ZIP](https://moji.or.jp/wp-content/ipafont/IPAexfont/ipaexm00401.zip)
- [IPAフォントライセンスv1.0](https://moji.or.jp/ipafont/license/)

ライセンス第2条6項・第3条2項に従い、名称を保持した無改変フォントとライセンス原文
`IPA_Font_License_Agreement_v1.0.txt` を同梱しています。配布元の
`Readme_ipaexm00401.txt` も無改変で保持しています。PDF内の表示にだけ用いる埋め込み
フォントについては第2条5項に記載されています。

## 再現・検証

通常はリポジトリ内のファイルをそのまま使えるため、テスト時にネットワークは不要です。
復旧が必要な場合は上記ZIPを取得し、`manifest.json` の `archive_sha256` と一致することを
確認してから `ipaexm00401/` 内の3ファイルをこのディレクトリへ展開してください。
フォント、ライセンス、ReadmeのSHA-256もmanifestに固定しています。

```powershell
uv sync --locked --extra dev
uv run --locked --extra dev python -X utf8 .agents/skills/_shared/run_tests.py --target tests/unit/test_font_assets.py --expect pass --label font-assets
```

未配置・改変・必要字形の欠落はテスト失敗です。書体名の一致だけでは同一ファイルと
判定しません。標準のReportLab `TTFont` で読み込めるTrueTypeアウトラインであり、
単独フォントのため `subfontIndex=0` を指定します。`OS/2.fsType=0` を検査します。

指定の日本語、ASCII、ギリシャ文字、数学記号はこの1書体に収録されているため、
これらの検証文字には別書体へのフォールバックは不要です。字形の存在は
`font.face.charToGlyph.get(ord(character), 0)` で調べます。`stringWidth` は欠字にも
`.notdef` の幅を返すため、幅が返ることを字形の存在確認に使用しません。

描画品質・数式の組版・結合文字の配置は、この資産テストとは別に生成PDFで検証します。
