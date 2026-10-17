# Test review: cantilever-p01-37-improvements

2026-10-17、独立 Test Reviewer。最終限定再レビュー: PASS、High / Medium / Low の未解決指摘なし。初回にQ01の連動変更ケースを見逃したが、品質レビューの指摘を受けた修正と追加負例を末尾で再評価した。初回1925件・031210候補と修正後の証拠を区別する。製品・fixture・テストは変更していない。

## Review Scope

- 基準HEAD: `3da8b7cb71803c463029c68e155798f377c62e07`。`.agents/logs/cantilever-improvements-review-scope.json` の全32 changed files と同slugのpatchを対象に、承認計画・実行記録・FR-014/015へ照合した。
- 中心対象: `cell_content.py`、`styles.py`、`tables.py`、`figures.py`、`math.py`、公開exports、fixtureのbuilder/verify/render、それらに対応する変更・新規unit/integrationテスト。既存の明示行高、分割header、37頁原本比較、代表帳票goldenも確認した。
- レビュー開始後に更新された `docs/validation.md` も読み、件数・coverage・wheel・原本比較と自己回帰の区別が証拠と一致することを確認した。開始後の製品/fixture/test入力変更はない。
- Coverage: gather_diffは98.82%、`stale_vs_scope=false`。leadの最終coverage JSONの実数は **2940 / 2975 = 98.82352941176471%**。行coverageであり、branch coverageを測定したとは扱わない。要求90%以上を満たす。

## Findings

None。Medium以上の不足を示す再現例は見つからなかった。

## 検証の評価

| 対象 | 確認した検査と独立性 |
|---|---|
| 原本順序 | immutableな原本PDFの直接抽出とhash固定を確認。数字交換・回転セルの順序交換・符号移動・同字重複、添字role/index/text/重複、方向、glyph二重被覆が負例。描画命令順の反転は正常。原稿とexpectedを同じ誤値へ変えたnative PDFも拒否する。prepareはlayout前、activateはPDF再検証とpointer切替前に拒否する。 |
| Insets・行高診断 | scalarと全辺同値Insetsの結果一致、9通りのalign/valign、左右余白で予約行不変、不正値、rowspan加算とcontroller、明示行高不足を検査。既存の境界一致・局所1行不足・subgrid不足・rowspan/反復headerのテストを維持している。 |
| CellLines | 固定12.8pt、1回丸めと外側paddingによる再丸め、行別styleのcopy、空行/空sequence、min_heightのnextafter境界、0.12pt grid、文字/数式の幅・予約超過と実ink接触を検査。行間や文字サイズを補正して通す検査ではない。独立の破損MathNodeも拒否する。 |
| Image | 物理寸法と予約枠を数値で検査し、9通りの配置、ペア不足、不正値、枠不足、半pixel許容の内外と端点、EXIF後の比率、snapshot/再読込を確認。PDFから小数pt座標、RGB、alpha maskを直接取得する。16図のprovenanceと実snapshotのhashを照合し、検査後のasset差替えを負例にしている。 |
| Script | 明示size/基線offsetの保持、不正値・不要側offset・role・基底接触・上下clearanceを検査。片側autoだけ移動、Fraction/Root/入れ子、既定値一致、MathBlockの予約/overflowを含む。IPAex・MS明朝・MSゴシックのPDFからサイズ6.639ptと基線75.08/81.92ptを観測する。 |
| 不可分Table | header込み1part、重複prefixなし、選択罫線の端点・幅・単一共有境界、連続縦線、結合と0線、全header/空表、不正splitを検査。実PDFでnative pathを調べ、ページ直前の全体移動と容量超過停止を確認。既定split=Trueの二重stroke検査は残る。 |
| 組合せとfixture | p1/p26/p30/p36の829セルを計測し、p26/p30実証の298セルは独立expectedとPDF抽出で照合。入れ子Script・Insets・明示行高・QuarterTurnのtraceとPDFを確認。原本固有SourceCell/SourceScriptは維持する。実証p30の504pt容量を固定37頁へ適用していない。 |

`tmp_path`とmonkeypatchの復元を利用し、テストがcurrentを有効化しないことを確認した。実測PDFを必要とする箇所をモックへ置換しておらず、prepare/activate負例のモックは「その後の処理に到達しない」ことを検査するために限定している。既存テストのassert削除・期待値の緩和・新規skipによる失敗回避は確認されなかった。追加ScriptテストのWindows書体skipは非Windows環境向けで、今回の3書体は全て実行された。

## Test Execution Results

- lead全体: **1925 passed / 135.39秒、失敗0**。`.agents/logs/cantilever-improvements-final.log` と `cantilever-improvements-final-coverage.json` を実読した。レビュー担当による全体再実行はしていない。
- reviewer独立再実行: **25 passed / 7.75秒、失敗0**。共有runnerで `tests/unit/test_cantilever_source_order.py`、`tests/integration/test_cantilever_improvements.py`、`tests/integration/test_equation_layout.py::test_explicit_script_p9_size_and_baselines_survive_pdf`。ログ: `.agents/logs/cantilever-improvements-test-review-independent.log`。coverageの上書きなし。
- reviewerのread-only hash監査: staging `20261017T031210Z-8d17d7f6d15549a2bab7cdc27c9ec982` の129入力・78成果物が現在のbytesと一致。bundle / 目視記録 / golden approvalのartifact mapも一致。通常/gridの全74画像が外観受入版023053と同画素、37 golden PNGが開始HEADと同bytesであることを再確認した。
- wheel受入記録と実ファイルのwheel/sdist hash、全22製品moduleの現ソースhashを再照合。リポジトリ外のPython3.12.12/3.13.11、`-I`、PyMuPDF未導入、公開API出力の両版画素一致を確認するスクリプトと結果を読んだ。レビュー担当がwheel環境を再構築したとは扱わない。
- `.agents/check.ps1`: exit 0、`ok=true`、detect_stack/design-doc/state-docの全exit_code 0。これは文書/スタック検証であり製品機能試験ではない。

## 判定の範囲

このレビュー時点ではstagingを対象とし、currentの切替はleadの最終工程である。全74画像の個別目視はrootの記録に基づき、レビュー担当はhashと画素同一性を独立監査した。任意の分割表の罫線統合、原本固有アンカーの一般API化、全入力組合せの網羅は今回の合格主張に含めない。

## Q01/Q02修正後の追補

初回Testsレビューは、expectedの文字列だけを変えた負例の有効性を確認したが、payloadとsource_bboxを同時交換するケースを見逃した。品質担当が発見したMedium Q01は正当な検証の穴であり、初回PASSをその反証として扱わない。

- **Q01解消**: ID→bboxの組をglyph選択前に独立pinへ照合する修正を確認。reviewerが基準commitの37 expected JSONを `git show` で読み、IDと4float座標だけの正規形を別途算出した。37頁・3345組のSHAが全て固定pinと一致し、現在のexpectedも基準commitと一致した。本文・方向・添字はpin対象外で、元の原本直接照合が引き続き実行される。payload+bbox連動交換、ID交換、選択glyphが変わらない微小bbox変更を拒否し、列挙順とint/float表現変更だけは受理する新テストがある。prepare/activateにも連動交換負例が追加され、旧currentを保つことを検査する。
- **Q02解消**: CellLinesの横/縦別の構造化診断を確認。新8ケースは左右/上下の変位と非対称余白を組み合わせ、部品ID/行番号/軸に加えて実容量と必要extentの数値、`needed > available` を照合する。既存の安全な配置・はみ出し拒否条件を緩和していない。
- reviewer限定再実行: **16 passed /1.90秒、失敗0**。新領域assignment3件、serialization正常1件、prepare2件、activate2件、軸別診断8件。共有runnerのlabel `cantilever-improvements-test-review-q01-q02`、exit 0。全体試験とcoverageはrootの単独実行に任せ、上書きしていない。
- 新候補 `20261017T033209Z-f93e3db55c094beaa28d3b3029fc2b7d` をread-only再監査: **129入力・78成果物hash一致**。bundle/最終目視記録/golden approvalのartifact map一致、37 golden PNGは開始HEADと同bytes。
- 最終74 PNGは個別表示済み031210候補と外観受入023053版の双方に対して **bytes・画素とも完全一致**。初回目視記録の保存ファイルとSHA、74件の画像名/artifact hashを辿って確認した。最終記録は74件の同一画像の目視再利用と10件の新候補spot再表示を明示しており、「新候補を74回再表示した」とは主張していない。
- 再ビルドwheel/sdistの実ファイルhash、22moduleの現在ソースhash、Python3.12.12/3.13.11の結果とPyMuPDF未導入・同画素を再照合。最終wheel SHA-256は `14ac344e68447ef802580824e14b02cf6a719c6d7b04ea0a92dc28125ac02510`。古いwheel結果の流用ではない。

今回の限定再レビューでは新たなHigh/Medium/Low指摘なし。修正後のroot全体試験は追補時点で実行中のため、初回1925件/98.823529%を最終値として転用しない。最終全体結果・有効化・pointer監査はrootの実行記録を正本とする。
