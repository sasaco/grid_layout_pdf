# P7 PDF移行 実装記録

2026-10-17「OK GO」で全10工程を承認。正本計画はpier-report-grid-migration.md。

## 工程とゲート

- [x] 1 最新コード・依存・入力・正式出力を固定し既存試験を確認
- [x] 2 独立した内容台帳・見本書式台帳
- [x] 3 微細グリッド・密な長表・数式・図・通常/overlay同一配置の実証
- [x] 4 共通帳票層と描画依存identity
- [x] 5 0500
- [ ] 6 0600と全表示値/動的図
- [ ] 7 0610/0620と全ケース
- [ ] 8 0710/0720と可変ページ
- [ ] 9 CLI/GUI/公開統合・旧描画経路撤去
- [ ] 10 全件・全頁受入、独立レビュー、同一候補の正式公開

## 担当

初期担当はbaseline（移行前結果/表示値/入口台帳）、appearance（原本測定と独立基準）、proof（先行実証と共通公開API層）。rootは統合、独立ゲート、実画像確認、状態記録を担当。公開/計算/入力GUIの既存並行変更を変更前に保全する。後続stageは先行実証合格後に所有を追加する。

## 検証結果

実装開始時GL HEAD: 4f45501d20b3e93e91040f46ad852d5dc720fd1c。その他の結果は実行後に追記する。

2026-10-17 初期環境ゲート:

- APP HEAD744e9389fa69c62906d85d42c823940f924a9251。baseline担当が未コミット状態を含む旧ソース/入力/正式出力/REF/書体をAPP/tmp/reporting-grid-migration/baseline-20261017T035601697852Zへ不変コピー。230ファイル、コピー中変化0。freeze-manifest SHA65852dac070f03b5c3ba5f24420c9b4b1612cbda5af026ae8e662f4688527bf9。
- 既存uv lock --checkは不合格。GLのPillow依存がAPPロックのmetadataへ未反映だった。uv lockで2行のみ追加し、依存version変更0、再check合格。
- GL lead pier-grid-library-baseline: 1939 passed in184.51s、coverage99%、90%ゲート合格。log .claude/logs/pier-grid-library-baseline.log。
- uv build成功、wheel SHA14ac344e68447ef802580824e14b02cf6a719c6d7b04ea0a92dc28125ac02510。APPにuv sync --locked --reinstall-package gridlayoutpdfで強制再導入。
- APP実interpreterによる製品22ファイル集合/SHAがGL sourceとwheel内容に一致。必要API signatureも存在。APP/tmp/reporting-grid-migration/runtime/initial-installed-manifest.jsonへ記録。検証scriptはGL/.claude/logs/verify-p7-grid-install.py。
- .claude/check.ps1はexit0/ok:true（detect_stack/design-doc/state-doc）。製品機能試験とは区別する。

## 未解決事項

先行実証・描画依存identity・0500は合格。0600、0610/0620、0710/0720本体の独立照合と全件統合・独立レビュー・正式公開が残る。過去のライブラリ受入を今回のP7移行完了とは扱わない。

## 内容・書式の独立基準と先行検証

- 移行前の全6計算結果75,260 leafをJSON pointerで固定。旧60ページ本文6,569 span、装飾65を分離。0600の5 sheet全4,601値と3,798表示cellを独立保存した。表示評価全値と実際に印字される内容は区別する。
- 見本4冊69ページを棚卸し、12代表ページを個別目視。明朝/ゴシック9.9pt、添字6.5pt、字下げ14.52pt、本文14.28pt、表役割別12.84/14.28/14.88/23.04pt等を測定した。白黒化を期待変換として記録。
- 0.12pt Gridを公開APIで使用。見本の等号アンカーはglyph左端、GridLayoutPdfのEquationAnchorsは中心であり、初回試作の約2.5pt差を独立確認で発見。共通層で半advanceを変換し、5役割の実glyph左端誤差0.06pt以内と誤変換の負例を追加。添字は見本の上付き4.92pt/下付き1.92ptを指定した。
- lead初回統合試験66 passed/21.56s（内容台帳・書式・旧proof）。新しい等号/添字修正後の最終proofを別に検証する。
- 最終proof: lead独立 p7-grid-lead-proof-final は68 passed/22.04s（proof12+内容/入口34+書式22）。最新版の通常/検査全8PNGを個別目視、欠け/衝突なし。等号全5役割の左端差はASCII+0.045pt/全角-0.030pt、添字実baselineは上付き-4.91998pt/下付き+1.91998pt。長表は現在の320係数、1 Table・20行rowspan×4群を2ページへ分割しheader反復。2026-10-17 13:23 JST頃に後続の0500・runtime・共通図への展開を許可。GL製品拡張は不要だった。
- 共通native骨組の初回root回帰: p7-grid-lead-native-frame は1,044 passed/34.51s。通常/偏心/微小偏心/極端扁平の4頁とoverlay4頁を個別確認した。外形の灰色線を黒へ統一する追加修正は別途確認する。
- 見本0500 p1の一軸圧縮強度見出しは実測MS-Gothic 8.8999996ptだったため、原本の個別roleとして保持する。同単位行9.9pt/上付6.5ptは分離し、便宜的縮小として他の文字へ適用しない。DESIGNへ0.12ptと等号/添字契約の2決定をtyped writerで記録済（applied、decisions_appended=2、skipped_duplicates=0）。
- root p7-protected-drift.pyで230凍結copyのSHAと187保護元fileを再検証、errors=[]。入力・計算器・入力UI・原本・旧正式出力・GL製品sourceに差分なし（2026-10-17 13:31 JST）。
- 親gitルートを用いる所有権helper p7-ownership-check.pyを作成。凍結時の既存変更だけを明示除外し、現在の全changed fileを共有check_ownershipで照合、overlaps=[]/unowned_changes=[]/idle_owners=[]。新tests同名module衝突を避けて新reporting側を*_grid_report.pyへ分離する。
- 最終受入用 p7-held-acceptance.pyをQA領域へ準備した。6stageが実際にstagingへ渡した確定sceneを記録し、その同sceneからoverlay/traceを作成、正式候補PDFをそのままQAコピーする。目視後のdecisionはpublication ID/input SHA/manifest SHAで同一保持候補に束縛し、既存transactionへ一度だけ公開する。まだ最終実行はしていない。

## 移行前アプリ回帰

- 最初の全件実行は600秒の制限で約9%時点にtimeout。試験失敗や合格として扱わない。
- GUIを隔離して再実行: 94 passed, 1 skipped /274.19s。最初の実行中に出たGUI失敗は単独・GUI全件のどちらでも再現しなかった。最終GUI検証も他のUI操作と分離する。
- 非UI既存全件: 3,844 passed, 1 failed /555.67s。唯一の失敗は test_seismic_transverse_cli の「旧PDF読取禁止」ガードが、新規公開済みPDFのtransaction最終hash読取も禁止する既存テスト不整合。生成中の旧/reference PDF禁止を維持し、公開後の検証範囲を限定する修正を担当へ割当。製品PDF入口変更前の観測である。
- 描画依存identity/通常候補公開保護の新Redは16失敗・既存保護2成功。現在の直下globや通常候補の検出不足を捉えている。Kドライブ327依存ファイル19.5MB全文hashはscandir＋8workerで約1.56秒。metadataのみのcacheは使用しない。

## 共通層・公開依存の移行

- root p7-grid-lead-runtime: 57 passed/29.75s（実installed依存/書体、再帰集合追加削除、登録済font変更、通常候補の入力/計算/公開bytes/QA混入/競合/失敗復元、原本書式）。通常候補も全computed辞書をprivate SHAで保持し、JRSNAP公開schemaの0500/0710 two-keyは維持。
- 全app再帰・実installed GridLayoutPdf/ReportLab/Pillow・4実書体ファイルをbyte hashで識別。受入receiptも同じ集合を再確認する。検証境界の重複readを整理し、allのprepare→明示validate→publishでsource hash 9回から5回へ削減（境界末尾で変更検出）。並行試験下の実隔離生成は31.984秒、5回hash計11.762秒、422依存43,789,226bytes。正式outputは未更新。
- 既存CLIの「生成中に入力が変わっても公開する」期待を、入力snapshotで計算各1回を維持しつつ公開拒否・旧成果物保持へ更新。無変更入力の共有SHAと成功公開も別に検証。全6可変頁の承認に伴い旧固定頁assertを意味/出力保護の検査へ置き換える。
- 計算/UIソースを変更せず、描画でLayoutError/FontErrorが発生した場合はCLI境界で既存InputErrorとして扱う。旧Canvas helpersは全stage移行後に最後に撤去する。

## 0500受入と後続実装の進め方

- root p7-grid-lead-foundation-finalは122 passed/33.96s（0500・独立内容台帳・書式・共通proof）。0500-v4の通常2頁・90層と長土質名4頁・長名称3頁、各normal/overlay計18画像を個別確認した。文字や式の欠けはない。長名称の回転ばね方向小節が2頁に分かれるため、見出し・Iv・長短期Krを同頁に保持する最終調整を担当へ依頼した。
- 旧440本文spanを70意味単位へ一回ずつ割り当て、manuscript全leaf→ScenePage→実PDFの1,489 glyphとvectorまで照合する。正しい意味台帳のまま実描画から因子/単位/根号/分数線を削除する負例も拒否する。残りstageにも同じ照合の鎖を求める。
- Tableのhorizontal_rulesは各描画strokeの太さであり、隣接LayoutPart境界では内向き0.12pt strokeが接してpaint bandは0.24ptとなる。原本の単独0.12pt線との差として明記する。機械的な半減はrowspan内/改頁端を細くしすぎるので行わない。各stroke 0.12pt・外枠0.96pt、行高はpaint band中心で14.28pt±0.5ptを検証し、白黒・読みやすさを確認した。
- 共通native骨組の最新版8画像をrootで再確認。標準図の近接寸法1.175/0.225は独立抽出の実glyph間隔4ptで交差なし。視認性のためnative配置の最小間隔を8ptへ広げる確認中。物理geometry/等方尺度は変えない。
- 0500最終受入後、0600・0610/0620・0710/0720を所有分離して並行実装する。先行共通層と0600の独立全値契約が合格済みで、後段rendererは0600 rendererに依存しないための実装順序調整である。0600の数値・図・本文受入を省略せず、全stage完了後に統合ゲートを実行する。
- 2026-10-17 13:47 JST、0500-v5の改ページ変更4画像をroot再確認。残る14PNGはv4とSHA一致。root p7-grid-lead-foundation-groupingは27 passed/16.63s、70unit/1,489glyph監査も再生成済。通常2頁PDF SHA a102544dfe23ecabecf5da36fc1be89bb6069e0d53b2037568963189e47f96cd。0500受入、後続5帳票の実装を許可した。
- native寸法間隔の最終root試験43 passed/19.20s。通常/偏心のnormal/overlay4画像を再目視、字間が改善し物理線は保持。担当全4頁の独立実glyph間隔は最小7.99994pt、物理線等509/874/874/562 segmentの座標/幅/色は変更前と完全一致。

## 作業中に検出した外部並行更新

2026-10-17 13:56頃、保護再検査で4ファイルの外部変更を検出した。migration担当は更新しておらず、各変更を .claude/logs/p7-concurrent-20261017-0456/ へbytes保存・SHA固定し差分確認した。巻き戻しや無制限除外をせず、確認済みSHAに一致する版だけ別枠で受け入れる。

- jrsnap_export.py: native先頭/末尾N行の主筋選択に側面筋が割り込む未対応配筋を拒否する保護追加。SHA3f7830dce0b073d0005235a2be8f70a712991974e0672de9c03782953b4c7bea。
- tests/test_jrsnap_export.py: 対応する側面筋混在拒否、多段主筋、共有隅角筋の試験追加。SHA21d4fd11701fee8c1659946b4c9821e1d40bbcad6caf92dda209771a4aaa805b。
- tests/test_jrsnap_acceptance.py: immutable入力snapshotによる実export oracle照合とreceipt/正式出力衝突拒否の試験追加。SHA56f4b235a230cad3e8141dc4beeefb136232f19e9bcb00b2e4439d08b674f884。
- output/0710_線路方向荷重.json: 変更leafは /provenance/input_sha256 の1件のみ。旧0a17f530…から現在入力7f22b9ca…へ更新され、計算値変更なし。現在SHAa2a4c3529e31e715560c41d23122fdf17d6798f0830b8b719b9172cc2e404f73。今回のmigrationによる正式公開はまだ行っていない。

230凍結copy、入力、計算器、見本、他の正式成果物は変更なし。最終JRSNAP回帰・公開競合検査は上記最新状態を含めて実施する。旧出力を同一だったと表現せず、移行前の証拠と外部更新を分けて保持する。

## 後続stage初稿のQA（未受入）

- 0610-draft通常6頁/overlay6頁をroot全画像確認。8sectionのsemantic一致は担当確認済みだが、短表の合計だけが次頁に出る、matrix見出しが前頁に残る、数値左揃えと罫線際の余白不足、用途列の不要な折返しを指摘した。short table保持/heading連結、数字右揃え/内側余白、用途列拡幅と14.28pt行高、単位/記号のScript化を修正中。
- 0600-firstは未接続のnative19頁初稿。rootが10代表頁を確認し、rich textの暗黙prefix欠落（R_AのR、m²のm等）を発見した。run先頭offset>0のprefixを保持する修正とsource負例が必要。初稿の図寸法は暫定数字リストであり完成扱いにしない。共通見本の階層58.92/73.44/87.96/102.48/117ptおよび等号276.72/436.44ptへ修正し、独立role原点で検査する。
- 0620の凍結display bodyに旧裸頁番号12件（x547/y815/size7）が混在していた。source fixtureは保持し、限定source ID/位置証拠付きpage_counter例外として一度被覆を記録し、新実ページ連番を検査する。本文整数を包括除外しない。
- 0710/0720は初回source→全leaf→scene→PDF検査23件合格（44/71unit、772/1631glyph）、factor/unit/支承式をscene/PDF両方から消す負例も拒否。改ページ・表整列の調整とroot全頁確認は残る。
- 14:08〜14:10 JST頃、0610-v2通常/overlay各6頁と0620-draft各8頁をroot全画像確認。0610の短表・matrix・Scriptと数字整列は改善。低水位の参考式/採用式の2頁分断を追加指摘。0620は風荷重条件末の小見出し孤立とmatrix備考列の不要な折返しを指摘し、内容のまとまりと12.84pt基準行高を保つ修正を依頼した。
- seismic-v2の0710通常2頁・0720通常3頁とoverlay計10画像をroot確認。文字欠け/衝突/短表分断なし。0.010m微小区間、M/F、0720の総高を含む寸法は読める。実埋込face/見本anchor/rowheightの独立監査とsection間隔の適用確認は進行中であり、まだ最終受入ではない。
- 0600は旧3198 body span→205意味単位の一回被覆と値/符号/因子/単位/注記の一致まで担当が確認。暗黙rich-text prefixと階層/等号anchorを修正済み。実scene/PDF監査、実寸法線と結ぶ図、public入口接続の完了を待つ。
