## Implementation Plan: Cantilever Pages 01 37

2026-10-17 / slug: `cantilever-pages-01-37`。計画の状態：形式・存在検査合格、Codex内容レビューPASS、ユーザーが「承認、実装を開始してください」と実装を承認。実行記録は `cantilever-pages-01-37-execution.md`、不足機能・改善候補は `../research/cantilever-p01-37-improvements.md` に継続記録する。

### Purpose

`tests/output/13_片持ち梁照査.pdf` の物理p1〜37を、GridLayoutPdfの公開APIで全文・全表・全図を組み立てる再現テストとして実装する。最新のユーザー指定に従い、原本1ページを出力1ページに対応させたA4縦37ページを必須とし、内容があふれたら「原本再現できず」のエラーで停止する。

### Scope

**確定した受入条件**

- 対象は物理p1〜37（印刷番号13-1〜13-37）。p38から始まる13.3は対象外。各ページの本文・式・表・図を同じ出力ページへ収め、追加頁・欠落頁・内容の他頁送りを許さない。
- 全ページ595×842ptのA4縦、PDFページ自体のrotationは0。右上ページ番号は全37ページで生成しない。原本の印刷番号は対応台帳に残し、欠落検査で除外できるのはこの頁番号装飾だけとする。
- p30〜37の大表は原本どおり紙面内で反時計回り90度、文字方向はPyMuPDF `line.dir=(0,-1)`。各系列のCase1〜18/19〜31の区切りと、p30の水平な節見出しを保持する。A3化・分割パネル化・表の画像化は行わない。
- 文字サイズ・字形を自動縮小しない。原本の表文字約9.959pt、行ピッチ21.60pt、係数/値の行間10.80pt等の実測を基に、表内部の明示スタイル・局所グリッドを決める。本文の標準グリッドは既存設定を使う。原本の全座標やPDFバイト列の一致は要求しない。
- 式は既存の構造化部品、表はTable/Cellを使い、表示値を文字列で保持する。`#######`、符号、桁数、単位、〃、空欄、0、－/―、原本の不整合を推測・再計算・正規化で変更しない。
- 図16パネルは独立した素材として扱える。図だけの切り出し/再描画には出典領域・手法・hash・ラベル確認を残す。原本頁や本文・式・表の画像化、PDFページの取り込みによる代替は禁止。
- 既存の一般的な自動改ページAPI・代表帳票は維持する。今回の固定ページ条件は原稿の組み方と生成前の検証で課す。

**具体的なファイル**

- New files（製品）: `src/gridlayoutpdf/rotation.py`。
- Modified files（製品）: `src/gridlayoutpdf/scene.py`、`src/gridlayoutpdf/bounds.py`、`src/gridlayoutpdf/renderers/reportlab.py`、`src/gridlayoutpdf/diagnostics.py`、`src/gridlayoutpdf/__init__.py`。既存の5種のCommandを維持し、再帰変換ノードや汎用PDF入力を追加しない。
- New files（原稿・期待値）: `tests/fixtures/cantilever_p01_37/README.md`、`manifest.json`、`builder.py`、`render.py`、`pages/p01.json`〜`p37.json`、`expected/p01.json`〜`p37.json`、`assets/`内の図素材とprovenance。JSONは試験用原稿であり製品の新入力形式ではない。
- New files（テスト）: `tests/unit/test_rotation.py`、`tests/unit/test_cantilever_fixture.py`、`tests/integration/test_cantilever_p01_37.py`、`tests/visual/test_cantilever_p01_37_golden.py`、`tests/visual/cantilever_p01_37/manifest.json`および確認済み通常版37枚のPNG。
- Modified files（検証・文書）: `tests/unit/test_scene.py`、`tests/unit/test_bounds.py`、`tests/unit/test_diagnostics.py`、`tests/integration/test_pdf_renderer.py`、`docs/api.md`、`docs/architecture.md`、`docs/validation.md`、`tests/visual/README.md`。必要な場合のみ回転部品の既存容器統合テストを`tests/unit/test_containers.py`へ追加する。
- 先行実証で確定した追加（IMP-006）: p26の上下太線・選択された細線を表すため、`src/gridlayoutpdf/tables.py`に境界ごとの罫線幅指定を追加する。`tests/unit/test_table_rules.py`を新設し、`tests/integration/test_table_pdf.py`で実PDFを検証する。既定の全面罫線・既存goldenは変えず、結合セル・行群分割・実字形の余裕を検査する。
- 計画・決定の記録: 本計画、`.agents/docs/research/cantilever-p01-37-{source-survey,code-findings}.md`、型付きライターによる`.agents/docs/DESIGN.md`・`.agents/STATE.md`、用語集`CONTEXT.md`。
- 生成先: `build/reports/cantilever-p01-37/`。通常PDF、grid PDF、配置JSON、原本/出力対応JSON、通常/grid各37枚のpreview、目視記録、配布物検証結果を置く。完成版は変更しない`versions/<bundle-id>/`単位で保存し、`current.json`が一つの検証済み版だけを指す。一時出力は`.staging/<bundle-id>/`に分離する。
- Dependencies: 既存のReportLab/Pillow、開発用PyMuPDF/pytest/pytest-cov、固定IPAex明朝、uv.lock。新しい実行時依存は不要。原本PDF・書体・既存golden・共有スキルは変更しない。
- 対象外: 構造計算ソルバー、工学的妥当性の判定、P7移行、GUI、TeXパーサー、PyPI公開、p38〜67、任意角度のアフィン変換、回転画像の一般対応。

**調査根拠と開始状態**

- 原本全67頁、SHA-256 `e56bf3ddbe3314ed95517099bedb0e68005df1567b0b3e8f52a2a4066d03393e`は`tests/fixtures/reference_manifest.json`のreport_13と一致。
- 原本全37頁の構成・画像調査は[原本調査](../research/cantilever-p01-37-source-survey.md)、具体的なfile:line根拠は[コード調査](../research/cantilever-p01-37-code-findings.md)。全セル転記や再現の受入は未実施。
- 調査値：p03〜08に114算式行、図16パネル、p30〜37に4系列×31=124ケース行。`#######`はp09=1、p12=6、p13=7、p16=12、p17=12、p18=12、p19=10、p20=3、計63箇所。これらは全項目照合を補う総量チェックであり、代表項目だけの合格判定には使わない。
- HEAD `72de7fa`、開始時作業ツリーはクリーン。今回のbaselineは1269 passed / coverage表示99%（`.agents/logs/cantilever-p01-37-baseline.log`）。
- 工程分解のCodex相談: `.agents/logs/codex/20261016T233650Z-plan-cantilever-pages-01-37-steps.md`。相談中にユーザーが固定37頁・番号省略を追加指定したため、回答の可変頁数・頁番号保持案は採用せず、本計画の受入条件を優先した。内容レビューはこの最新条件で実施した。
- 最新条件での内容レビュー: `.agents/logs/codex/20261016T235437Z-plan-cantilever-pages-01-37-validate-r2.md`（PASS）。初回指摘の出力一式保存、番号不在検査、図の許可一覧、回転metadata/無効入力、先行実証前の転記範囲を修正し、再レビューで全指摘の解消を確認した。

### Implementation Steps

原本と検証契約を固定し、回転・密度・固定ページの難所を先に実証してから全37頁へ展開する。各工程の完了条件を満たしてから依存する工程へ進む。

#### Step 1: 最小の原本台帳・入力契約と先行実証用原稿を固定する

- [x] 原本頁1〜37の最小台帳、ID/schema規約、source issues一覧、期待値の独立性規約を作る。原本頁/領域・種別・原稿/期待値ファイルの対応を定義し、右上頁番号だけを`omitted_page_number`として明示する。
- [x] 先行実証のp30/p36/p16/p17/p26だけは全見出し・本文・式行・表・セル・図のIDと完全な原稿/expectedを用意する。残り32頁の全項目台帳・転記はStep3〜4の成立後、Step5〜8の担当頁群ごとに完成する。実証前に全37頁を転記しない。
- [x] `pages/`を組立用原稿、`expected/`を原本から独立に確認する照合用原稿にする。builderはexpectedを読まない。入力や生成PDFからexpectedを自動生成しない。転記・確認担当と確認済み項目を記録する。
- [x] source issues（63箇所の#######、p17の可視末尾、p26の同値表、単位・節記号の不整合等）をIDごとに記録する。表示値は文字列、空欄は空欄として持つ。
- [x] fixture契約のテストを追加し、頁欠落・重複・対象外p38・ID重複・期待値欠落をassertで検出する。全体fixtureの完成判定と、先行実証用の明示subsetを区別し、subsetを最終37頁の合格に流用しない。

**Verification**: 原本hashと37頁の最小台帳が一致し、先行5頁の全項目oracleが揃う。負例で頁・IDの欠落/重複が検出される。この時点を全文転記完了とは報告しない。最終的な全項目網羅はStep9で検証する。

#### Step 2: 文字の90度回転をscene・境界・描画・診断へ通す

- [x] `Text`へ既定0の`quarter_turns`（整数0〜3）を追加する契約をTDDで実装する。既存4引数の構築・水平文字・translatedを維持し、bool/非整数/範囲外を拒否する。
- [x] 実字形の境界4隅を基線原点周りに回転してboundsを計算する。文字幅だけの推定で張り出しを無視しない。
- [x] ReportLabでは正規直交の文字変換を使い、font size・tracking・100%横倍率・字形正規化・欠字preflightを保つ。描画状態が後続の水平文字へ漏れないようにする。
- [x] diagnosticsは回転文字の向きを記録し、水平文字の既存JSON・goldenを変えない。無効な向き・欠字・回転後の枠外は既存PDFの置換前に失敗させる。

**Verification**: 非対称の実字形境界を用いた手計算矩形、PyMuPDFのline.dir・origin・size・bbox、tracking、後続水平文字、既存ファイル保持をunit/integrationで確認。最初のRedは新APIへの実行時assertまたは挙動assertの失敗で確認し、import/収集失敗をRedにしない。

#### Step 3: 局所グリッドによる回転部品と最大大表を実証する

- [x] 公開`QuarterTurn(block, *, turns, local_grid, block_id="")`を`rotation.py`に追加する。turnsは±1、local_gridは原点0のGridSpec。子の計測に呼出側の書体・スタイルを使い、拡大縮小せず剛体回転する。
- [x] Text/Line/Polyline/Rectangleを扱い、RasterImageや未知の子commandは明示的に拒否する。Textの既存方向との合成、罫線の太さ、rectangleの角を保つ。turnsのbool/非整数/±1以外、GridSpec以外/原点が0でないlocal_grid、無効な子measure結果、空または可視内容のない子をValueErrorで拒否する。寸法不足はLayoutOverflowErrorとする。
- [x] turns=1は紙面の反時計回り90度（右向き文字が下から上へ進む）、turns=-1は逆向き、と定義する。上原点の子座標を外側LayoutPartへ写す`local_to_part`行列をmetadataへ明記する。子のcell frame/content origin/anchorsは局所座標のまま保持し、child各partの累積y offsetとrow_pitchも保存する。任意のmetadataキーを推測で書き換えない。ページ上の座標はpartの配置平行移動とこの行列を一度だけ合成して得る。
- [x] 一つの分割不可なLayoutPartとして外側の整数グリッド行を予約する。local_gridの幅/高さ、回転後の実字形境界、外枠の容量を検査し、足りなければLayoutOverflowErrorにする。入力を変更せず、測定済み内容を描画時に再フローしない。
- [x] 係数/値の密な2段セルが既存部品だけで収まらない場合、fixture内に公開Block/MeasuredBlock/LayoutPart/Text/書体計測を使う小さなセル部品を置く。任意の原本座標から表全体を描く実装にはしない。Table/Cellが列・罫線・結合を管理する。
- [x] p30の14列・2段18ケースとp36の16列・18ケースを、全ヘッダー/全セルを含めて先行実装する。原本の表幅/高さはp30約683.40×422.16pt、p36約712.44×449.28pt。これらは観察値であり、原本座標の完全一致をテスト条件にはしない。

**Verification**: 2枚ともA4縦各1枚、番号なし、p30見出しは水平、表文字方向(0,-1)、全セル/結合/罫線/サイズを独立抽出し、通常/grid計4画像を目視。入れ子のcell frameとcontent origin、太い罫線/張り出す字形、既存Text方向との合成を手計算と照合し、二重変換・文字だけ無変換・metadata破壊・上記無効入力を検出する。小さな回転サンプルだけの成功では通過不可。収まらなければ後続へ進まず、原本の明示スタイル・局所行間の範囲で原因を調べる。縮小・A3化・ケース削除で回避しない。

#### Step 4: 固定ページの公開APIビルダーと生成前ゲートを作る

- [x] 原本各頁の構成をStack/KeepTogetherで原子的にまとめ、明示PageBreakで区切る。Stack内部にPageBreak/At/PageSectionを置かず、改ページはページラッパー間だけに置く。既存Documentの一般自動改ページは変更しない。
- [x] Document.layout完了後、描画前に「37頁」「各source pageの全blockが同番号のoutput pageだけに存在」「空白代替頁なし」「ページ番号装飾なし」を確認する。単に総頁数だけを比較しない。
- [x] あふれは原本頁ID・該当block ID・必要量/使用可能量を持つ「原本再現できず」のエラーとして伝える。38頁を黙って捨てる、空白頁で不足を補う、他頁と内容を交換して37にする実装は禁止。
- [x] `render.py`は原稿検査・全layout・固定頁検査後、通常/grid PDF・JSON・対応表・previewを`.staging/<bundle-id>/`だけに生成する。生成後の独立PDF抽出検査を含む全検査を通すまで有効な出力にしない。
- [x] 全出力とhashをbundle manifestへ保存し、検証済み一式を新しい`versions/<bundle-id>/`へ確定した後、`current.json`を一時ファイル＋原子的置換で切り替える。読出側はpointerを一度解決し、その変更しない版だけを使う。旧版を上書きせず、pointer切替前の失敗は旧currentと旧一式を保持する。初回失敗はcurrentを作らない。pointer切替失敗で残った未参照版を成功扱いにしない。
- [x] 先行subsetは`.staging/`内の実証出力に限定し、37頁のcurrentとして公開しない。全検査コードはStep9までに揃え、最終受入ではStep10の目視記録も同じhashのbundleへ紐付けてから切り替える。この保存方法はfixture用writerの範囲に留め、製品へ汎用公開機能を追加しない。
- [x] 長文導出p16/p17と6表のp26も各1ページの早期実証対象に追加する。通常の本文領域を使い、繰返し文字・値を省略しない。ここで共通の式/表ビルダー、図素材provenance、source IDの追跡契約を固める。

**Verification**: 1頁分の原稿へ行を追加した負例が「原本再現できず」で停止する。grid描画・JSON書込・preview生成・描画後の独立抽出・pointer切替の各段階へ失敗を注入しても旧currentと参照する一式のhashが不変、初回失敗はcurrentなし。成功時は全出力が同じ版を参照する。意図的な欠落頁・同数の内容移動も失敗する。p16/p17/p26の全内容が各1頁で成立し、計6通常/grid画像を確認。固定頁条件に該当しない既存Documentの自動改ページ試験は引き続き合格。

#### Step 5: p30〜37の回転大表8ページを完成する

- [x] 先行実証が通過してから、この頁群の未完了の項目台帳・全原稿・独立oracleを完成する。Step6〜8も同じ順序で進める。
- [x] p30〜37の独立した原稿/expectedを完成し、Md/Vd/Mt内訳と集計の4系列・計124ケースを保持する。
- [x] 係数/値の2段、列見出し・結合、性能/備考/摘要、空欄・ゼロ・－・〃、符号、原本単位をケース×列×役割で照合する。
- [x] 各表を元の18/13ケースのまとまりで1ページに収める。p30だけの節見出しを保持し、右上頁番号は8頁とも省く。

**Verification**: 8頁と124ケース、各セルの全表示を独立期待値と照合。実PDFの文字位置を回転方向に基づき局所軸へ戻し、ケース/列の対応を検査。回転計算のproduction helperを検証側で再使用しない。表の画像が存在せず、抽出可能な文字・ベクター罫線になっていることも確認。

#### Step 6: p01〜08の鉛直荷重・反力・シュー別式を完成する

- [x] 死荷重表、載荷図、RA〜RDの式、単線/複線、B/C/B+C、安全性/使用性、耐震用列車荷重を各原本頁へ転記する。
- [x] 114算式行の総数だけでなく、全行の項順・演算子・値・単位・添字・表示桁数を確認する。`＋-0.575`や0.00、G1〜G4とG1〜G2の区別を保つ。
- [x] 図内寸法・矢印・ラベルを独立素材とラベル台帳で確認する。図内画像の文字をPDFテキスト検証済みと扱わない。

**Verification**: 各頁が元の1頁内で成立し、全項目の期待順序・回数・等号/結果/単位配置・字形サイズが一致。図素材のhashと出典領域が確認できる。

#### Step 7: p09〜20のトルク・水平荷重の導出を完成する

- [x] 図と構造化式を既存Row/Script/Symbol/EquationGroupで組み立てる。原本がslashで書く式を無条件に段分数へ変えて高さを増やさない。必要な改行は原本頁内で式のまとまりを保つ。
- [x] 63箇所の#######、p17の可視末尾、p18の異なる係数表記、負の反力、ρ/α/μ/Σ/∴、原本の空の中間式を保持する。
- [x] p11の埋込み図は素材を抽出して出典hashを記録する。ほかの図も本文・表を巻き込まず、16パネルの該当部分と照合する。

**Verification**: 12頁の全内容を個別の期待値で検証し、#######の頁別回数・式の演算子/添字/符号・単位を確認。どの頁でもあふれを許さない。判読不能な追加箇所が見つかったら推測せず原本領域を示して停止する。

#### Step 8: p21〜29の結合表・断面図・荷重集計を完成する

- [x] p21/p22の結合表、p23の自重表と2図、p24〜29の荷重集計表を、全行・全列の対応を保って作る。
- [x] rowspan/colspan、数式セル、起点/終点、ゴム/ストッパー、合計、空欄とゼロと横線を区別する。p26の6表を重複排除せず、p21(d)→p22(c)等の節記号も保つ。

**Verification**: 9頁の全セルを意味上の行列アドレスで照合し、PDFから結合罫線・セル位置・値・符号を検査する。6表が同じページ内に存在し、ヘッダー再掲や次頁送りでページ境界を変えていないことを確認。

#### Step 9: 全37頁の独立照合と検出能力を検証する

- [x] 全原稿を単一の37頁出力に統合し、37入力頁×37出力頁の一対一対応・全block/式行/セル/図の網羅を確認する。右上頁番号の省略だけを明示的に除外する。
- [x] 通常/gridとも全37頁のMediaBox=(595,842)、/Rotate=0を実PDFで検査する。右上の原本頁番号領域を位置付きで抽出し、13 - n等の頁番号がないことを検証する。ページ番号用のheader/footer装飾が無いことも確認し、右上に頁番号を挿入した負例は両版で失敗させる。p30の水平節見出し・内部provenance・gridの座標目盛とは区別する。
- [x] PyMuPDFで実PDFの文字・方向・size・位置・罫線・画像を抽出し、expectedと照合する。traceは場所の特定を助けるだけにし、traceの返した値をそのまま正解にしない。
- [x] 本文・数値の単純な全文substring集合で終わらず、頁/部品/ケース/列ごとの順序と回数、上下添字の関係、等号・結果・単位位置を検証する。
- [x] 最終scene/PDFの全画像出現を許可済みの図ID一覧と照合する。各図はsource crop・素材bytes hash・デコード画素hash/寸法・配置予定領域・provenance・許可出現回数を持つ。scene上の素材hashと実PDFのデコード画素/配置を照合し、再エンコードによるPNGファイルbytesの差とは区別する。全頁/式/表を覆う画像や未登録画像を拒否し、同じ許可画像の拡大配置・余分な再利用も検出する。
- [x] 欠落、重複、符号/値変更、2セル交換、別頁への内容移動、38頁化、頁番号の再挿入、禁止画像（文字を重ねて抽出を通す例を含む）の小さな負例を作り、検査が実際に失敗することを確認する。汎用ミューテーション基盤は作らない。
- [x] 通常/gridで同じ内容と配置を共有すること、描画前エラーで既存出力を保持すること、フォント・原本hashが維持されることを確認する。

**Verification**: 正しい原稿は37頁で合格、上記の負例はそれぞれ理由付きで失敗。内容不一致をgolden更新で隠さず、未対応頁を残したまま全範囲の成功と報告しない。

#### Step 10: 全ページ目視と画像回帰を確定する

- [x] stagingの通常37頁/grid37頁の計74画像を全て確認し、接触・切断・欠字・意図しない縮小・表の回転方向・余白を修正する。各頁の内容照合と目視は別の検証として記録する。
- [x] 確認者、日時、原稿/expected/図/書体/source PDFのhash、ツール版、通常/grid全画像hashと指摘処置を記録する。
- [x] 内容検査と全頁目視が合格した出力だけ、通常37画像をgoldenとして登録する。生成直後の画像の自動承認や失敗時の自動更新を追加しない。
- [x] 目視済み画像とPDF/JSONのhashを確定したbundleを有効化する。再生成や修正でhashが変わった場合は古い目視記録を流用しない。

**Verification**: goldenの入力・書体・ツール条件を固定して再生成が一致する。未確認画像や未解決指摘がない。既存代表帳票5頁のgoldenも不変。

#### Step 11: 文書・配布物・全体ゲートを完了する

- [x] API/architectureにquarter-turnの角度、対応primitive、局所グリッド、bounds/metadata、分割不可、画像拒否、例外契約を記載する。fixture READMEへ固定37頁の生成方法、エラー時の扱い、対応台帳、source issues、検証コマンドを記載する。
- [x] `docs/validation.md`と`tests/visual/README.md`へ実際に得られた受入証拠を追記する。STATE/DESIGNは型付きライターで更新し、PROGRESSを手書きしない。
- [x] 変更箇所を独立レビューし、Medium以上を修正・再検証する。既存テスト削除・skip・許容値の緩和で合格にしない。
- [x] 全pytest・製品coverage90%以上・原本PDF不変・既存golden・lock検査・共有文書契約を実行する。
- [x] sdist→wheelをビルドし、Python3.12/3.13のクリーン環境から、公開QuarterTurnを使った小さな回転表をリポジトリ外で生成する。PyMuPDFを実行時依存にしない。

**Verification**: 下記最終コマンド、配布物の公開import/生成、git diff確認が成功。37頁対応一覧、通常/grid PDF、テスト、目視記録、再実行方法を納品する。原本再現失敗ならその頁と理由を報告し、合格PDFとして公開しない。

検証コマンド（各Red/Greenは同wrapperの対象・label・COVERAGE_FILEを分ける）:

```powershell
uv sync --locked --extra dev
$env:PYTHONUTF8 = '1'
$env:COVERAGE_FILE = '.agents/logs/coverage-cantilever-p01-37-final'
uv run --locked --extra dev python -X utf8 .agents/skills/_shared/run_tests.py --target tests --expect pass --cov gridlayoutpdf --min-coverage 90 --label cantilever-p01-37-final
uv lock --check
uv build
& .agents/check.ps1
git diff --check
```

Redは`--expect fail`で実際のassert失敗を確認する。収集/import/環境失敗は機能不足の証拠にしない。共有check.ps1は文書・スタック検査であり、製品pytestの代わりにしない。

### Risks & Considerations

#### 2026-10-17 ユーザー指摘による外観修正（承認済み作業の継続）

前の完了チェックは内容・既定グリッドでの検証履歴として保持する。ユーザーが書体・インデント・イコール位置・表行高の不一致を指摘したため、外観受入は再開する。FR-015を追加し、今回のfixtureに原本の書体と意味部品の実測位置を適用する。原本全面画像や文字ごとの座標再生は採用しない。

- [x] 原本全37頁のMS明朝/MSゴシック・インデント・等号・40表の行列境界を独立実測。
- [x] 原本から直接抽出した情報と出力を比較する外観テストを追加し、4項目のRedを確認（4 failed / 原本control 1 passed）。
- [x] Table.row_heightsを明示した整数の局所グリッド行数として追加。不足時はエラーとし、既定挙動を保持する。
- [x] 原本の書体を明示登録し、意味部品単位の配置・式のアンカー・表の寸法をsource-layoutへ記述。builderは原本/expectedを実行時に読まない。
- [x] 原本の添字サイズ/基線と式の折返し・結果位置を保つ明示部品をfixtureで実装し、改善一覧へ汎用API候補を記録。
- [x] p1のD4文字で確認した原本人工斜体をText.shear_xの最小追加で再現。基線字送りを変えずnative文字行列、bounds、回転、traceを揃える。独立した実PDF字形幅比較で傾斜欠落を検出する。
- [x] 全37頁の内容検査と外観検査、通常/grid全頁の原本比較、負例、回帰、独立レビューを実施。
- [x] 新しい全37goldenと検証済みbundleを確定してcurrentを切替。旧版を上書きしない。

外観修正の最終結果: 1738 passed / 107.30秒、行coverage98.923134%（2664/2693）。新候補023053の通常/grid74画像をrootが確認し、独立Tests担当が128入力・78成果物・37goldenを再hashして承認との一致を確認した。全レビュー未解決0。`versions/20261017T023053Z-a954761644604bd1a289b5fcdd9f20d1/`を有効化し、rootがcurrentと両37頁PDFを再検証済み。詳細は実行記録の外観修正完了節。

**Verification**: `tests/integration/test_cantilever_source_appearance.py`、`tests/unit/test_table_row_heights.py`、従来の内容・画像回帰・失敗注入を全て実行。書体は実PDFの埋込みname tableから判定し、入力profileを正解として再利用しない。インデント・等号位置・表境界は原本PDFの文字基線とnative罫線中心から比較する。

- **固定37頁を守れるかが第一の実証課題**: 標準15.48ptの行ピッチのまま2行×18ケースを置くと557.28ptとなり、回転後の高さ482.4ptを超える。p30/p36とp16/p17/p26を全内容で先行検証し、表内部の原本由来の明示ピッチ・セルpadding・不要な余白で調整する。文字の自動縮小や内容省略はしない。
- **再現できない場合の停止**: 保持すべき文字サイズ・内容・向きのまま収まらない頁はエラーで止め、該当頁・部品・超過量を示す。A3化・追加頁・省略を自動選択せず、未完成を成功としない。既存の成果物を保護する。
- **回転の整合性**: Textのbaseline、実字形bounds、罫線、metadata、rendererで同じ向きを扱う。純粋な手計算矩形とPDF抽出を併用し、productionの変換関数だけで正しさを確認しない。
- **出力一式の保存**: rendererの原子的置換は1PDFに限られるため、fixture writerで全一式をstaging検証し、変更しない版へのpointerを最後に原子的に切り替える。normalだけ新しくgrid/JSONが古い混在を許さない。失敗テストは描画後の工程まで含める。
- **局所グリッドと外枠**: 子の行間は明示的に指定するが、外側の位置・占有行数は既存ページグリッドに従う。子をそのままouterのpitchで読み替えたり、別単位のmetadataを同じ座標として報告しない。
- **独立期待値**: 原稿のJSONをexpectedへコピーしただけでは転記ミスを検出できない。原本画像を別途照合する確認担当を置き、全セル/式の独立確認と負例検証を必要条件にする。
- **図と文字抽出**: 図素材の内部ラベルは別に目視/画像確認する。図の外の本文・式・表をcropへ巻き込まない。ページ番号も素材へ混入させない。
- **原本の問題**: #######・切れた原文・不整合な値/単位はsource issuesとして保持し、工学的修正をしない。表示原稿と構造計算を混同しない。
- **作業分担**: Step2〜4の共通API/fixture契約を先に確定する。Step5〜8は`pages/expected/assets`を頁群で所有分離できるが、builder共通部分と最終統合はleadが担当する。期待値の確認担当は同じ入力の自動コピーを行わない。最終coverageは単独で実行する。
- **影響範囲**: 表・数式・Document本体の追加修正は、先行実証で既存APIの不足を具体的な失敗テストで示した場合に限る。追加が必要なら原因とファイルを本計画に追記し、範囲を無制限に広げない。

### Open Questions

- ユーザー判断が必要な未決事項は現時点でなし。大表は原本まま、37頁固定、あふれ時停止、頁番号不要を確認済み。
- 技術的な検証事項はStep3〜4の合否ゲートに置く：local_gridの列幅/行間、compact cellのbaseline、最大表と高密度本文の1頁成立、固定頁wrapperのmetadata保持。これらは実装済みの事実ではない。成立しなければエラーと根拠を示し、条件を変えて続行しない。
- 計画の形式・存在・最新条件によるCodex内容レビューとユーザーの実装承認は完了。`team-execute`、slug `cantilever-pages-01-37` で実行する。今回必要な修正と将来候補を改善項目一覧に記録する。
