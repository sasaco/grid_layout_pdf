# 片持ち梁 p01–37 実行記録

2026-10-17、ユーザーの実装開始承認を受領。固定37頁・原本どおりの回転表・全頁番号省略・あふれ時エラーという条件を維持する。

## 担当と依存関係

| 担当 | 所有範囲 | 先行作業 |
|---|---|---|
| rotation | 回転の製品コード、専用unit/integrationテスト | Text方向、bounds、renderer、trace、QuarterTurn |
| fixture | fixture builder/render、pages、assets、fixture unitテスト | 入力契約、p30/36/16/17/26全文、固定頁・出力一式保存 |
| oracle | expected、独立PDF検査・integrationテスト | 原本から先行5頁の期待値を独立転記・確認 |
| root | 文書、台帳、統合ゲート、目視 | 原本との照合、改善一覧、指摘修正の調整 |

初期所有mapは `.claude/logs/ownership-team-execute-cantilever-pages-01-37.json`。先行5頁の成立前に残り32頁の全文転記へ進まない。入力と期待値を別担当で作り、自動コピーを禁止する。

## 必須テストケース

1. Textの既定互換、0〜3方向、bool等の無効値、実字形4隅、tracking、後続水平文字、欠字/枠外失敗時の既存PDF保持。
2. QuarterTurn±1、対応primitive、既存方向との合成、各part累積位置と局所metadata、整数占有行、外枠不足、画像/空/不正measure拒否。
3. 固定37頁と明示subsetの区別、頁/ID欠落・重複、p38拒否、頁対応・空白・頁番号装飾の検査。
4. 全見出し/式/セルを含むp30/36・p16/17/26の各1頁実証。源PDF由来の独立期待値と実PDFを検査。
5. staging以降の各工程失敗（grid、JSON、preview、独立抽出、pointer切替）で旧currentと旧成果物hashを保持。
6. 全37頁の本文・式・セル・図・方向・罫線・画像許可一覧。欠落/重複/値変更/セル交換/別頁移動/38頁/頁番号/禁止画像の負例。
7. 通常/grid全74枚目視の後だけgolden37枚登録。全既存テスト、coverage90%以上、配布物、原本不変。

## 進捗

- [x] 計画レビューPASS・実装承認。
- [x] 最小台帳/先行5頁の原稿と独立期待値。
- [x] Text・QuarterTurnのTDDと対象製品ゲート（全体・配布物ゲートは後続）。
- [x] 先行5頁の固定頁実証と10枚目視。
- [x] 残り32頁、独立照合、全74枚目視、golden。
- [x] 独立レビューMedium以上0・全体/配布物ゲート。

基準: 開始時1269 passed、coverage表示99%。これは今回の再現テストの受入ではない。

## 先行検証の記録

- Text回転: 担当のassert Red18 failed→対象100 passed。leadは描画30件を再実行し合格（cantilever-lead-native）。
- QuarterTurn: 担当146件合格、rotation coverage97%。leadのコード確認と独立46件再実行も合格（cantilever-lead-quarterturn）。docs/api.mdの公開例を実行し1頁18命令の成立を確認。
- 既存通常5頁のgoldenはlead実行3 tests passed（cantilever-lead-existing-golden）、画素変更なし。
- p30/p36の全表入力は各1頁に収まることを確認中。native PDFのMediaBox595×842、Rotate0、表のdir=(0,-1)をleadも確認。全内容・grid・目視のゲート前なので先行実証合格とはまだ扱わない。
- 原本p26の選択罫線が既存Tableでは表現できないとroot/fixtureが確認。IMP-006の最小製品拡張をrotation担当へ追加し、先にassert Redを作る。明示規則の境界は原本Tableの行列番号であり、繰返しヘッダー/分割時に存在しない罫線を勝手に追加しない。

## 先行実証合格と全頁への展開

先行5頁は通常/gridとも795項目の独立照合に合格。lead再実行はintegration35件、fixture unit21件合格。各頁45/42/45/46/47行で、追加頁はない。leadが固定済み成果物の10画像を個別に目視し、式の等号・結果位置、添字、選択罫線、回転表、頁番号不在を確認した。

証拠: `build/reports/cantilever-p01-37/proof5-review.json`。対象bundleは `.staging/20261017T002132Z-fa9f143679b44cec9f8dc10020bd549f/`。これは先行実証であり、37頁のcurrent/golden承認ではない。

この成立を受け、所有mapを更新しpreflight合格。fixtureがp01–08/p30–37と共有builder、rotationがp09–29、oracleが残り32頁の独立expectedと検証、rootが16図素材と文書・最終統合を担当する。既存の先行5頁を保持し、全37頁の成立後に74画像を確認する。

## 展開中の検証

- 原本の図16点を288dpiで切り出し、rootがすべて個別表示して図中ラベル・端部・本文等の混入不在を確認。`assets/metadata.json`と`crop-review.json`で出典領域・物理寸法・hashを固定した。図は原寸のpt寸法で配置する。
- 回転8頁の全124ケースは通常/grid独立照合を通過。P37のLF=1.2と内訳の1.23は個別保持。P18の旧調査誤り「複線(L+I)」は原本の「複線L」へ調査文書を訂正し、値を推測しない。
- sdistからwheelを生成し、21製品moduleのbyte一致・配布物への原本/書体/テスト不混入を検査。リポジトリ外の新規Python3.12.12/3.13.11環境へ導入し、QuarterTurn±1、選択罫線、その後の水平文字を含む各2頁を生成した。PyMuPDF未導入の実行時で成功し、両環境の実PDF方向・10pt・画素一致を確認。証拠は`build/reports/cantilever-p01-37/wheel-acceptance.json`。製品codeが後で変わった場合は再実行する。

## 全37頁の内容・目視・画像回帰

- 通常/gridとも37頁・3345項目、114算式、124ケース、63箇所の#######、許可した16図を独立照合。root再実行は内容/負例63件、fixture unit24件合格。
- 最終候補`20261017T004507Z-3d0e5dc4ee8d43f4a1d8dc260a1d9931`の通常/grid全74画像をrootが個別確認した。文字・図の切れ、添字の接触、罫線・セル結合、回転方向、頁番号不在を確認。原本の表記不整合は維持した。
- 画像/PDF/JSONの78成果物hashと123入力hashを固定し、`build/reports/cantilever-p01-37/full37-visual-review.json`へ目視記録を保存。通常37枚を`tests/visual/cantilever_p01_37/`へ登録し、再生成の全画素一致テスト1件も合格（cantilever-lead-golden37）。
- 最終currentの切替は全体テスト・独立レビューの完了後に実施する。

## 独立レビュー後の修正と最終試験

- SecurityのSEC-001を修正。検証器のassertが最適化起動で消えるため、import時に明示拒否を追加。-O/-OO/PYTHONOPTIMIZEのsubprocessを先にRed3件で再現し、修正後Green67件。Security担当の同一probeと104件再実行でも解消を確認。
- Testレビューの保守改善を採用し、原本37頁・21,232非空白文字を直接再抽出して3,345項目へ一度ずつ割り当てる37ケースを追加。元の検査を保持したまま対象104件合格。
- root最終全件は`cantilever-lead-accepted-all`: **1508 passed、75.96秒、行coverage98.801498%（2638/2670）**。計測JSONは`.claude/logs/cantilever-accepted-coverage.json`。
- verify.pyの入力hash変更に伴い新候補`20261017T005753Z-7952a1f3f915474c8a478f77d40cf9da`を生成。74PNG・trace・mappingは全hash一致。PDFは作成/変更日時等だけ変化し、全描画/画像streamは同一。`regeneration-equivalence.json`に記録し、新PDFhashで目視記録を作成した。登録済み37PNGは不変。

## 完成版の確定

- Security/Quality/Testsの独立レビューは未解決0件。Qualityのread-only Codex補助解析も全文を確認して指摘0。3報告の存在、実装3名+レビュー3名のwork log契約、所有範囲の重複/未割当/未実行なしをrootが確認した。
- 新しい確認記録で画像回帰を再実行し1件合格（cantilever-rebound-golden）。Test reviewerも74画像・78成果物・96入力hashの結び付けを独立再確認した。
- 全検査後に`versions/20261017T005753Z-7952a1f3f915474c8a478f77d40cf9da/`へ確定し、`current.json`を切替。rootがresolve_current、完成status、全78成果物hash、目視記録hash、両PDF37頁・595×842pt・Rotate0を読み直して確認。
- normal.pdf SHA-256: `71df0245ce70d101a2965c2b040210ad76a2f9acaeb0957cdcaa81df4ffe66fa`。grid.pdf: `6c369d1b8dff84d50b9d7e488bda56cd7b2488f18fcf8baad66a3d32dc631564`。
- 原本12PDF・書体・既存golden・uv.lock・pyproject.toml不変。uv lock --check、git diff --check、共有チェックok:true/3checks exit0。既存DESIGNのArchitecture空本文警告は今回の変更に起因しない。
- 改善13項目は今回の対応と将来候補を分離して記録。今回の未完了工程なし。コミット・外部公開はしていない。

## 外観のユーザー指摘による再開

前節は旧版の内部受入履歴である。その後ユーザーから書体・インデント・等号位置・行高の不一致が指摘され、FR-015として修正を開始した。旧版の内容検査・golden自己一致を原本外観一致の証拠にはしない。

- 原本nativeはMS明朝/MSゴシック。ローカルWindows書体のface0を明示登録し、原本10pt本文・回転9.9pt等を保持する。フォントファイルは配布物へ含めない。
- 原本全37頁の433意味部品、276式、40表、16図の配置をsource-layout.jsonへ記述。glyph座標列や原本PDFのページコピーは使わず、既存の意味原稿を部品として計測・配置する。
- 原本比較のRedは4 failed / source control 1 passed。Table.row_heightsを局所整数行数としてTDD追加し、rootの関連75件も合格。既定Table挙動を保持する。
- 全3345項目の原本読み順を追加監査したところ、p1/p2の2反力式で旧expectedが右辺全体→結果の列順へ並べ替えていた。原本の第1行に結果がある物理順へ修正し、source_evidence helperも修正。原本37頁の直接読み順controlは合格した。
- p21/p22の縦括弧8文字も原本の方向へ復元。明示したsource_direction_overridesを追加し、全原本の方向/読み順を照合する。生成版の誤った向きへoracleを合わせない。
- Table.row_heightsを含むsdist→wheelをPython3.12.12/3.13.11のリポジトリ外環境へ導入し、明示行高、過小高の拒否、左右90度表、水平文字、実PDF画素一致を確認。build/reports/cantilever-p01-37/wheel-acceptance.jsonを更新。
- 全37頁layoutは成立。通常/gridの統合内容検査・外観検査、最終目視、golden更新・current切替は作業中。旧currentは保持している。

### 外観比較で見つかった追加差の修正

- Table.row_heightsとText.shear_xの関連105件をrootが再実行して合格。unit全体は1407件合格。shearを含むsdist→wheelもPython3.12.12/3.13.11の別環境でnative PDF生成と画素一致を確認した。
- D4文字の人工斜体を実装。原本subsetの左bboxが基線xでclampされるため、字形前方端と基線原点の差を比較する。許容.20ptは維持し、傾斜0への変異は4件を検出する。D拡大画像も原本との一致をrootが確認した。
- p21/p22の縦用括弧は、抽出bboxの位置に横用字形を置くだけでは「破」に重なった。原本の縦用字形のink中心と通常字形のink中心を合わせる。rootは原本/出力の限定領域を8倍で描画し、黒pixel境界と画素数を比較する回帰を追加。+8pt誤配置を拒否し、正例も合格した。
- 旧oracleの結果右端共通・まとめ線終端の仮定を、原本nativeの実位置との比較へ訂正した。線の重複/重なりを可視区間の和として扱い、p19後半の誤った線区間も修正。旧integration全127件合格、元の負例を維持した。
- 意味行3755件とlhs/result/unitを原本へ一意対応し、有意空白とunit基線を補充。p21荷重式の空白欠落は解消。さらにp3の乗算operand等で8〜20pt、p16等で100pt前後の内部配置差を確認したため、意味operand/operator/Script単位のrun位置を補充中。文字ごとの座標列は保存しない。
- 新しい全37goldenとcurrentは未確定。全頁の最終原本比較を終えてから登録する。

- 再レビューAPP-T01で、横方向の比較だけではp9上付き2の2.52〜3.24ptの縦ずれや、数値を縦へ2ptずらす負例を見逃すことが判明。021112候補は有効化せず、意味run/Script基線の補充と直交方向の独立比較を実装する。原本の基線を保持し、セル内の実字形が罫線を越えないことも検証する。

## 外観修正の完了

- APP-T01を修正し、文字の直交方向を全21,204字で0.20pt許容の独立検査へ追加。最終最大差は0.043419pt。原本に接触する明示8セルの微小補正以外はPDF丸め範囲で一致する。全表を一律移動していた補正は撤去し、fixtureの表局所計測だけ実glyph inkを使用する。製品と元FontRegistryの保守的boundsは保持した。
- QualityのAPP-Q01/Q02/Q03（未対応ASTの黙示省略、relation転記による本文置換、lines/stylesの不一致による行欠落）を明示エラーと負例で修正。Quality28件、Tests外観107件と最終hash監査5件、Security157件の各独立試験が合格。修正後の未解決指摘0件。
- rootの最終対象283件合格に続き、単独全体試験`cantilever-appearance-final-full`は **1738 passed / 107.30秒**。製品行coverage **98.92313405124396%（2664/2693）**、測定JSONは`.claude/logs/cantilever-appearance-final-coverage.json`。既存代表帳票5頁の画像回帰も不変。
- 最終bundle`20261017T023053Z-a954761644604bd1a289b5fcdd9f20d1`を再生成。通常/grid各37頁、各3345内容項目、外観error0。基線最大差0.043419pt、等号0.0000611pt、表罫線0.002pt。全40表は原本の明示行高を保持した。
- rootがこのbundleの通常37枚/grid37枚を個別表示して全74画像を確認し、`appearance-correction-visual-review.json`へ128入力・78成果物・74画像を結び付けた。その後だけ通常37PNGとgolden manifestを更新。独立Tests監査で全hash、実PDFの全外観カテゴリ、fresh原本37枚の来歴、全体試験とcoverageの鮮度を再確認した。
- 旧currentを保持したまま全ゲートを通過後、新bundleを`versions/20261017T023053Z-a954761644604bd1a289b5fcdd9f20d1/`へ確定し、currentを原子的切替。rootがresolve_current・完成status・全128入力/78成果物・目視記録hash・両PDF37頁595×842pt/Rotate0を再監査した。証拠は`build/reports/cantilever-p01-37/appearance-correction-current-audit.json`。
- normal.pdf SHA-256: `73b25b1364573802dcca74e9ff2800cc6f304b6da547d1104f9983f656129942`。grid.pdf: `59616619c5931d2a08d80bec241917da01b9e9c26c999621ba5d5e8b8f04e3c8`。
- Python3.12/3.13の外部wheel検証はrow_heights/shearを含めて合格。原本PDF・書体・旧golden・uv.lock・pyproject.tomlは不変。9担当work log、3レビュー文書、所有reconcile、lock/diff/shared checkも合格。geometry担当は調査結果を他担当へ移管し、製品変更なし。reconcileのcoverage=null警告は保存先探索の限界であり、上記固有JSONで実測済み。
- 改善一覧は24件。原本再現に必要な修正は完了し、汎用のScriptスタイル・辺別padding・物理寸法Image・罫線統合・実ink計測API等は未実装の将来候補として残した。細罫の塗り矩形とstrokeのアンチエイリアス差は残るため、原本との全画素一致は主張しない。コミット・外部公開はしていない。
