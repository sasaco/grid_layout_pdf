## Implementation Plan: Cantilever p01-37 Improvements

作成日: 2026-10-17。slug: `cantilever-p01-37-improvements`。状態: 形式・存在・内容レビューPASS、実装未着手。今回の依頼はレビューと計画策定。実装開始は別途ユーザー承認を得る。

### Purpose

片持ち梁p01-37で判明した改善13件を実装に照らして整理し、fixtureが持つ密なセル・原寸図配置の共通責務を安全な公開APIへ移す。原本固有のアンカー・書体・出典管理はfixtureに保持し、固定37頁・文字サイズ・原本表示値・独立検証を保ちながら、余白・行高診断・添字指定・不可分な表の罫線を改善する。

### Scope

根拠は [レビュー結果](../research/cantilever-p01-37-improvements-review.md)、[改善一覧](../research/cantilever-p01-37-improvements.md)、DESIGNのFR-005/008/010/013/014。既存計画 `cantilever-pages-01-37` は完了済みで、本計画の承認とは別である。

**維持する受入条件**: 原本1頁=出力1頁、通常/grid各37頁、595×842pt・Rotate0、全頁番号省略、p30-37の紙面内CCW90度表と18/13ケースの区切り、本文・式・表はnative、登録図16点のみ画像。表示値、`#######`、空欄、桁数、符号を推測修正しない。自動縮小、追加頁、ページ送りによる収容はしない。

| 対象 | 方針 | 優先度 |
|---|---|---|
| IMP-013 | 原本対expectedの順序検査を補強 | P1: API移行前の検証基盤 |
| IMP-003/008/010 | 四辺余白、行高診断、明示行部品を一組として実装 | P1: 共通化の中心 |
| IMP-009 | 原寸指定と予約領域を分離したImage拡張 | P1 |
| IMP-011 | 既定autoを保つScriptの明示style | P2 |
| IMP-007 | 不可分Table内の罫線を統合 | P2: 早期設計実証、実装は独立 |
| IMP-001/002/004/005/006/012 | 実装済み。作り直さず回帰検証 | 全工程の制約 |

P1/P2は着手順であり、P2も本提案の実装範囲に含む。

**新規ファイル（案）**:

- `src/gridlayoutpdf/cell_content.py`: 明示行部品 `CellLines`。原稿JSONやsource IDの解釈を持たない。
- `tests/unit/test_cell_content.py`: pt内側配置、予約行、入力検証、非接触検査。
- `.agents/docs/plans/cantilever-p01-37-improvements-execution.md`: 実装開始後のケース・担当・検証・意図した画素差の記録。

**変更ファイル**:

- `src/gridlayoutpdf/styles.py`, `tables.py`, `__init__.py`: 不変の `Insets`、Cellの四辺余白、行高内訳、Table不可分モード、公開exports。
- `src/gridlayoutpdf/figures.py`, `math.py`: Image物理寸法、Scriptの明示指定。
- `src/gridlayoutpdf/diagnostics.py`: 追加metadataのJSON化に必要な場合のみ。既存座標系・必須キーを変えない。
- `tests/unit/test_tables.py`, `test_table_rules.py`, `test_images.py`, `test_math.py`, `test_diagnostics.py`, `test_rotation.py` と `tests/integration/test_table_pdf.py`, `test_figure_pdf.py`, `test_equation_layout.py`, `test_cantilever_p01_37.py`: 対応する契約・実PDF・独立負例。
- `tests/fixtures/cantilever_p01_37/{builder.py,verify.py,render.py,README.md}`、同 `pages/p*.json`: 公開APIへの移行と原本順序ゲートの呼出しに必要な変更。内容とsource IDを維持する。
- `docs/{api,architecture,validation}.md`, `README.md`, `.agents/docs/research/cantilever-p01-37-improvements.md`: API例、互換性、採用範囲、検証状況。
- `tests/visual/cantilever_p01_37/` とmanifest: Step 8の新出力検証・目視後に限り、意図した差分だけ更新。旧baselineは先に別保存する。representativeの既存goldenは維持。

**依存**: 現在のPython>=3.12、uv.lock、ReportLab/Pillow、開発用PyMuPDF/pytestを再利用。新規依存は不要。`MeasuredBlock.height = rows * row_pitch`、Block protocol、整数行の改ページ、確定sceneをrendererへ渡す構造を維持する。

**並行変更との整合**: 調査開始後にTable.row_heightsと `tests/unit/test_table_row_heights.py` が追加された。続いてfixtureの `appearance.py`、`source-layout.json`、`font-profile.json` と関連テスト2件も検知した。削除・再実装せず、Step 1で合流時点の状態を確認する。明示行高はその値を厳守し、不足時に行を拡大しない。新SourceCellの個別アンカー、SourceScriptの個別書式、PageFrameの47行予約を旧CompactCell経路と同一視しない。この計画は指定bundleと調査開始時点の分析を基準とし、新しいsource appearanceの座標方針を上書きしない。

**範囲外**: 任意の分割可能Tableのページ境界をまたぐ罫線統合、汎用PDF取込、ソルバー、TeXパーサー、GUI、P7移行、PyPI公開、原本修正、QuarterTurnの画像対応。固定頁検査と成果物一式の有効化は既存fixture手順を再利用し、製品APIへ無条件に移さない。

### Implementation Steps

依存順は `1 → 2 → 3 → 4 → 8`、`2 → 5 → 8`、`2 → 6 → 8`、`2+3 → 7 → 8`。4と6の組合せは8で追加検証する。3と7は同じtables.pyを触るので直列、公開exportsとbuilderの合流は担当を一人にする。独立した画像・添字の作業は、実装時に担当を分けられる。

#### Step 1: 受入基準の固定と原本の順序検証（IMP-013）

- [ ] 指定bundle・原本・書体・旧golden・currentのhashを記録。全テストを実装開始時に1回確認し、この計画時の1508 passedと区別する。
- [ ] 並行追加されたrow_heights/source appearanceと関連テストの最終状態を読む。変更後のbuilder、appearance.py、source-layout/font-profile、検証器・goldenの対応を実行記録へ固定し、受入版からの差を整理する。失敗があればAPI移行に混ぜず原因を切り分ける。ソース固有アンカーを残したまま、共通処理だけを新APIへ委ねる移行箇所を確定する。
- [ ] 全37頁のsource bboxに属するglyphを原本から直接読み、方向、基線、本文と添字の関係を使ってexpectedとの順序一致を確認する。元PDFの描画命令順をそのまま読み順と仮定しない。
- [ ] 現行の文字inventory・一回被覆・marker・許可図領域の検査を残す。順序検査は追加とし、expectedやbuilderから正解を再生成しない。
- [ ] 原本順序検査をverify.pyの再利用可能な検証関数へ集約し、render.pyのprepare/activateの既存検証経路からも呼ぶ。テストでしか動かない検査にせず、期待値改変が新bundleの有効化前に停止する負例を確認する。
- [ ] `1530.0→1350.0`（p1）、回転セル内の順序交換（p30）、上下添字役割交換、符号移動、同字重複の負例を用意。通常行、複数行、空欄、同上記号、回転、添字を正常例で網羅する。
- [ ] 原本読み順に曖昧な箇所は、bbox付き原本画像と手作業の局所期待値で根拠を残す。比較をCounterへ戻して通すことはしない。

**Verification**: 37頁の正常例と全負例。既存の3345項目比較、最適化Python拒否、5頁source controlも合格。変更するexpectedがある場合は原本を再確認し、正解を実装へ合わせない。

#### Step 2: 高リスク部分の最小実証とAPI契約の確定

- [ ] API名と下記契約を実行記録へ固定し、以後の担当間で共有する。名称は提案だが、既定値互換・不正値拒否・非縮小は必須。
- [ ] p26とp30の全セル内容で、内側pt配置→余白加算→一度だけ行丸めする部品が成立することを実証。外側Cell.padding=0との組合せを明示する。任意Blockの予約を減らす仕組みは導入しない。
- [ ] p26相当の選択罫線表を全体1partとして描き、同一part内の既存 `_merged` を再利用できることを確認。結合セル、0線、太線、headerのセルIDを含める。
- [ ] p9相当のScriptで明示offsetの安全な受理/拒否条件を実字形で確認。原本の約6.639pt・約4.92ptは参考観察値であり、必須の固定値ではない。

**Verification**: p26/p30の通常/grid、線分端点・実字形・セル対応を測定し目視。指定bundleではp26=45行、p30=46行、p36=47行。並行変更後のPageFrameは47行固定なので、ページ予約行数だけで内部の収容を判断せず、セル枠・実字形・基線の位置も比較する。旧記録の43行へ合わせる必要はない。不成立なら後続の全原稿移行へ進まず、原因・契約をこの工程内で修正して再実証する。

#### Step 3: Cellの四辺余白と行高診断（IMP-010/008）

- [ ] `Insets(top=..., right=..., bottom=..., left=...)` を有限・非負ptの不変値として追加。`Cell.padding: float | Insets` とし、既存floatは全辺同値へ解決する。別名のpadding_x/yを同時に増やさない。
- [ ] Tableの計測・配置・align/valign・結合セルに同じ解決済みInsetsを使う。利用可能幅は `cell_width-left-right`、必要高は `child_reserved_height+top+bottom`。
- [ ] `row_heights=None` では必要高から自動割当し、明示row_heightsでは指定行の合計高と必要高を比較して不足を拒否する。rowspanでも指定行高を変更しない。診断には自動/明示のmode、指定値、必要値、不足量を区別して残す。
- [ ] 子予約高、余白、丸め前pt高、切上げ行数、最終行高、rowspan由来の追加配分をmetadataに追加。行高を支配したセルIDを含め、traceから「小さな余白でも行が増えた理由」を追えるようにする。
- [ ] 旧Block/Paragraphの行丸めは保つ。diagnosticsは計測し直さず、確定metadataだけを出力する。0線でもセル外へ内容を流出させない。

**Verification**: float指定と全辺同値Insetsのcommands/行高一致、左右のみ変更して上下予約不変、幅不足、NaN/Inf/bool/負値、全align/valign、rowspan/colspan、入れ子、分割・反復header、回転、trace JSONを検査。`test_table_row_heights.py`の既存ケースと、Insets/CellLinesを組み合わせた明示行高の不足・境界一致を検査。既定APIの既存goldenは画素不変。

#### Step 4: 明示行の公開部品と密な表の移行（IMP-003/008/010）

- [ ] `CellLines(lines, *, style, line_styles, line_advance, min_height, inner_padding, align, block_id)` をBlockとして追加。linesは文字列またはMathNodeの明示行。MathBoxと描画命令の既存計測を使い、原稿の辞書解釈を含めない。alignは行内のleft/center/rightで、Cell側の部品全体のalignとは区別する。
- [ ] 部品内の基線間隔・内側余白・最低高はptで計算し、最後に `rows_for` を一度呼ぶ。空行や指定min_heightを保持し、全空行も正の予約を持つ。行別styleは行数一致、未指定は既定styleを使う。
- [ ] 外側 `Cell(..., padding=0)` を推奨する。外側余白を指定した場合は従来どおり加算し、二段階の丸めが発生した事実を診断に残す。二重指定を黙って無視しない。
- [ ] 行間は明示値。幅不足、隣接行の実字形接触、予約領域外への流出は部品ID/行番号付きエラーとする。自動改行・自動縮小・自動行間補正を追加しない。
- [ ] 旧CompactCell経路のp1/p26/p30/p36を公開部品の実証ケースへ移し、中央寄せなど行内配置も照合する。line_sizesはline_stylesへ変換する。合流後の実fixtureがSourceCellを使う場合は、個別start_x/baselineを維持し、明示等間隔行として等価な箇所だけCellLinesへ委ねる。非等間隔アンカーのためだけに新しい汎用座標APIを追加せず、原本固有のSourceCellは残せる。

**Verification**: 1行/複数行/空行/大きな式/上下添字/行別書体、min_height、四辺余白、整数境界直前直後、局所0.12ptグリッドを検査。p30の雪係数と次値行は既存の非接触回帰を保持し、採用基線間隔12.8ptを勝手に縮めない。p1/p26/p30/p36が各1頁・47行以内、本文サイズとセル内容が一致すること。

#### Step 5: Imageの物理寸法と予約寸法の分離（IMP-009）

- [ ] `Image` に明示 `width_pt`/`height_pt` のペアを追加。未指定時は従来の必須col_span/rowsへの比率維持fitを完全維持する。
- [ ] 物理寸法だけを指定した場合は描画幅=width_pt、高さ=height_pt、予約幅=width_pt、予約行=`rows_for(height_pt)`。任意のグリッド枠を併記する場合はcol_span/rowsをペアで指定し、その予約枠内へalign/valignで配置する。片方だけの指定・不足枠・過大幅はエラー。
- [ ] 明示した2つのpt値はEXIF補正後の画像比と整合することを求める。許容は各軸±0.5pixelに相当する丸めに限定し、両軸のpixels-per-point許容区間が重なることを確認する。受理時も指定pt値を変更せず、大きな比率不一致は拒否する。登録16図は全てpixel寸法がsource bboxの正確な4倍であり、この条件に適合する。
- [ ] EXIF補正、PNG/JPEG制限、alpha保持、計測時snapshot、再計測時再読込は既存処理を共用。描画時にファイルを再読込しない。
- [ ] SourceFigureは出典・path・hash検査をfixture側に残し、寸法配置をImageへ委ねる。生成されたsnapshot bytes/pixelsもmanifestと照合し、事前のファイル検査だけで同一性を保証したことにしない。非グリッド予約幅とtop/left配置を保持する。

**Verification**: 非整数pt、比率許容内外、EXIFで縦横が入れ替わる画像、透過、壊れた画像、入力変更後のsnapshot不変、枠不足、有限値検証を検査。登録16図すべてでscene/PDFの物理幅高・座標・byte/pixel hash・出典・個数を照合し、PDF実測は既存の精度契約を維持。SourceFigureの単純削除によってprovenanceを失わない。

#### Step 6: Scriptの明示サイズ・offset（IMP-011）

- [ ] 追加keyword-only指定として `scale=0.65`、`superscript_rise=None`、`subscript_drop=None` を提案。rise/dropは基底の基線からの正のpt距離とし、Noneは従来auto計算をそのまま使う。既存の位置引数を変更しない。
- [ ] scaleは有限かつ0より大きく1以下、距離は有限正数とする。使わない側へのoffset指定も誤指定として拒否する。サイズとoffsetの明示値を黙ってclampしない。
- [ ] 明示指定は上付き/下付きの役割、基底との実字形非接触、上下添字同士の間隔を確認する。片側autoならauto側だけ安全に計算できるが、明示値は移動しない。両側明示で衝突した場合はエラー。
- [ ] MathBoxの幅/ascent/descentを新位置から再計算し、MathBlock/EquationGroup/Table/CellLinesの予約へ伝える。Script単独では隣接行を知れないので、行間非接触はCellLinesとレイアウト統合検査で保証する。
- [ ] p9の変更は明示オプションを選択した場合だけ行う。既定式の全出力を原本の座標へ寄せる変更はしない。
- [ ] 合流後にSourceScriptが使われている場合は、水平間隔・字送り・基線を含むその固有契約を確認する。今回の公開scale/rise/dropだけで等価にならない部分はfixtureに残し、既存Scriptへの強制置換を完了条件にしない。

**Verification**: 既定Scriptのcommands・画素一致、片側/両側添字、Fraction/Root/Script入れ子、異なる書体、invalid scale/offset、役割違反、衝突、狭い枠のoverflow、PDF上の基線と文字サイズ。p9・p30と既存の数式折返し・等号列を再確認する。

#### Step 7: 不可分Tableの罫線統合（IMP-007）

- [ ] `Table(..., split=False)` を追加し、既定はTrue。Falseの場合は全行を1つの `_make_part` で組み、1つの不可分MeasuredBlockとして返す。header行はそのpart内に含め、別prefixとして重複させない。
- [ ] 同一part内の既存区間統合を利用し、共有横境界の二重strokeと縦線の行群間の隙間を解消する。元行列番号、セルframe、選択罫線、colspan/rowspanの内側線抑止を保持する。
- [ ] 明示row_heightsも1partへ同じ値で集約し、自動割当へ戻さない。header行も元の高さ・source indexを保持する。
- [ ] Trueの分割・反復header・既定stroke幅の意味は完全維持。Falseはページに収まらなければ既存のoverflow規則で停止する。KeepTogetherで既存Tableを包むだけの実装にしない。
- [ ] p26の6表とp30-37のQuarterTurn内表を適用候補とし、画素差を罫線変化として記録する。renderer全体の重複除去や、任意分割表のfragment生成方式は変更しない。

**Verification**: 共有境界が1本・連続縦線であることをsceneとPDF双方で確認。0線、異なる線幅、短い孤立線分、結合header、全header/空表、rowspan、回転、ページ境界直前、過大表を検査。既定Trueの2本strokeテストは残す。Falseの不分割・セルID/trace対応も検査する。

#### Step 8: 37頁の統合受入・公開API案内・新bundle

- [ ] 3-7の新APIを使う原稿を一つに合流し、全ページの内容・予約行・変更理由を確認。共通化した責務とfixtureに残した原本固有責務を一覧化する。並行source appearanceが採用された場合は、その関連2テストとsource-layout/font-profileの契約も維持する。表示内容・expectedのsource evidenceを自動修正しない。
- [ ] 通常/grid全37頁で、3345項目、114算式行、124ケース、63箇所の`#######`、16図、原本文字の一回被覆と順序、頁数・ページ対応・回転・文字サイズを再検証する。既存の欠落・入替・重複・追加頁・画像変形・最適化起動の負例を維持する。
- [ ] 旧APIの代表帳票goldenは画素不変。新APIに移行した片持ち梁の差分は旧版と比較し、余白/罫線/明示添字など理由を頁別に記録。全74画像を個別目視し、独立した内容検証を通過した後にのみ新goldenへ更新する。失敗回避のための一括更新は禁止。
- [ ] 全製品テスト、製品行coverage90%以上、品質・検証の独立レビューでMedium以上0、sdist→wheel、Python3.12/3.13のクリーン環境で公開API利用を検証する。PyMuPDFをruntime依存へ移さない。
- [ ] API/設計/検証ガイドと改善一覧を更新。IMP-007は「不可分表で対応、任意分割表は対象外」と明記。承認後に採用した設計は型付きwriterでDESIGNへ記録し、STATEにも対応する状態を残す。
- [ ] 既存 `prepare_bundle → 検証 → 目視記録 → activate_bundle` を使い、新しい不変versionだけを有効化。旧versionは保持し、currentを最後に切替。途中失敗時は旧currentのままで、入力・成果物hashとpointerを再検査する。

**Verification**: 上記全ゲートのログ・差分・目視記録・新bundleへのリンクをexecution文書へ記録。既定API互換、公開API移行、固定37頁再現の3つを個別に合格とする。

実装時の製品テストは共有runnerを使用する。対象工程では `--target` を上記該当テストへ絞り、TDD Redは実際のassertion失敗を確認する。

```powershell
$env:PYTHONUTF8='1'
$env:COVERAGE_FILE='.agents/logs/.coverage-cantilever-improvements-final'
uv run --locked --extra dev python -X utf8 .agents/skills/_shared/run_tests.py --target tests --expect pass --cov gridlayoutpdf --min-coverage 90 --label cantilever-improvements-final
```

並行担当ではCOVERAGE_FILEを分け、最終全体coverageはleadが単独で測る。

### Risks & Considerations

- **丸めと余白**: 小さい余白が1行追加するのは既存予約契約の結果。全Blockの行高変更では解決せず、診断とopt-in部品に限定する。p36は現状47行を使い切るため、実証で余裕を仮定しない。
- **空白の意味**: 空行・Spacer・min_heightを実字形がない理由で消さない。新CellLinesも明示空行を保持する。
- **罫線互換**: 独立行群の共有境界2本は既存契約。新不可分モードだけで統合し、任意分割への拡張は別計画とする。
- **原寸画像**: 物理寸法だけでなく予約幅・配置基点・snapshotを照合する。物理pt比とpixel比の差を無断補正しない。
- **添字安全性**: 原本のoffsetは全書体で安全とは限らない。明示値の拒否条件を実証し、外側レイアウトまで確認する。既定autoへ新しい厳しい拒否条件を後付けして互換性を壊さない。
- **期待値独立性**: source-to-expected、generated-to-expected、画素比較を別々に維持する。単純なCounter一致やtraceだけを内容正しさの証拠にしない。
- **変更中の作業ツリー**: 作業開始時から既存の未コミット変更が多数あり、調査中にもrow_heights拡張を検知した。1508件合格は追加前の基準であり、並行変更後の成功を保証しない。担当ファイルと開始差分を記録し、reset/stashや全体整形を行わない。
- **検証の限界**: 計画段階の目視は代表5頁・計10画像、テストは1508件の現状確認。提案APIの成立、最終coverage、新PDFの品質を確認済みとは扱わない。

### Open Questions

- 要件上の未解決事項はない。本計画は既存の固定37頁条件と、今回のレビュー・計画依頼から作成した提案であり、実装承認待ち。
- API名・CellLinesの空行/行内配置の細部・Scriptの安全なrole判定はStep 2でテスト付き契約へ確定する。ユーザーの再回答を前提にした隠れた停止条件にはしない。
- 分割可能な表での罫線統合は今回の完了条件に含めない。必要になった場合は改ページ後のfragment境界と反復headerの責務を扱う別計画とする。

計画検証: plan-doc形式・workspace存在確認はPASS。Codex内容レビューもPASS、Medium/High指摘なし。記録は `.agents/logs/codex/20261017T012817Z-plan-cantilever-p01-37-improvements-validate.md`。これは計画の妥当性の判定であり、提案APIの実装受入ではない。Gate 4の実装承認は未取得。承認後のハンドオフは `/team-execute`、同slug `cantilever-p01-37-improvements`。
