# 図・画像の実装契約

2026-10-16。Step 7の独立モジュール。文書フロー確定後に実装し、既存scene/bounds/renderer/layoutへの画像命令追加は同じ担当が直列に扱う。

## 図

- `Figure(col_span, rows, *items, block_id='')`。枠は整数グリッド列・行、両方正整数。内部座標だけはpt、左上原点。横幅がavailable_widthを超えれば明示エラー、枠を縮小しない。
- itemsは既存Line/Polyline/Rectangle/Text命令、又は`Arrow`/`Label`。入力はtupleへコピーする。図全体は1 LayoutPart、分割禁止。内部の線と文字の重なりは図の意図があるため一律禁止せず、宣言枠からの実字形・線幅の逸脱を検査する。
- `Arrow(x1,y1,x2,y2, *, head_length=6.0, head_width=4.0, width=0.6, color=(0,0,0))`。先端は(x2,y2)、軸方向へhead_lengthだけ戻る開いた2辺の矢印。ゼロ長軸、長さを超えるhead_length、非有限・非正サイズは入力エラー。任意方向を扱い、線幅を含め枠へ収める責任はFigureにある。
- `Label(x,y,text, *, style=None, align='left')`。yは基線、xは実境界を含む左/中央/右アンカー。style未指定は本文。NFCと欠字検査を既存FontRegistryへ委譲する。1行限定、改行とtabは入力エラー。
- 自前の寸法付き荷重図例を作り、柱・梁・荷重矢印・寸法線・日本語ラベルを図枠内で表現する。外部計算や図面解釈を加えない。

## 画像

- `Image(path, *, col_span, rows, align='center', valign='middle', block_id='')`。PNG/JPEGを初期対応とし、静止画1枚。指定グリッド枠内へ縦横比を維持して最大内接させる。alignはleft/center/right、valignはtop/middle/bottom。透明度を保持する。
- 計測時に画像を読込み、検証済み内容を不変bytesとしてsceneに残す。描画までに元ファイルが変わっても寸法・内容は変わらない。壊れたファイル、未対応形式、複数フレームは明示エラー。初期版はEXIF方向を読み取って正規化してから寸法を測る。
- 内部命令`RasterImage(x,y,width,height,data)`は描画する矩形と不変bytesを保持する。幅・高さは正の有限値、boundsはこの矩形。rendererはBytesIO/ImageReader等でbytesから描画し、画像命令を含むページも既存の出力atomic性を維持する。
- scene/layoutの許可命令tuple、Command型、bounds、PDF rendererのpreflightと描画分岐を一貫して更新する。他担当の製品変更と競合させない。

## leadケース

- 図の整数枠高、横幅不足、全4辺で文字・太線・矢印先端の逸脱、移動後の寸法、再計測不変。
- 水平・垂直・斜め矢印、ゼロ長・長過ぎる頭・NaN/inf/不正色、Labelの左右中央と負のleft bearing。
- 横長・縦長画像の内接寸法、上下左右配置、元ファイル差替え後も描画内容保持、透明PNG、EXIF方向、壊れた画像、未対応形式、0サイズ枠。
- 独立PDF抽出で図がvector、画像が所定の位置・縦横比であることを確認。PNG目視で文字や矢印の切断・画像の歪みがないことを確認する。
