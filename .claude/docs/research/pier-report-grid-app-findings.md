# P7 pier_design の帳票移行調査

調査日: 2026-10-17。計画 `pier-report-grid-migration` のための読み取り専用調査。実装・計算実行・PDF再生成・テスト実行はしていない。以下の `P7橋脚/` と `Example橋脚/` は `K:/ニュージャパンコンサルタンツ/26_LRT鉄道照査/` 相対。現物の観測と実装提案を区別する。

同日再調査更新: ユーザーは六つのPDF生成の全面移行、計算・UI・I/O維持、全六帳票の可変ページ数を合意済み。0710=3頁・0720=4頁の旧固定条件は今回の移行では解除する。移行計画そのものは作成・レビュー中で、実装は開始していない。初回後にK側でJRSNAP統合の並行実装が進んだため、入口・成果物集合・保護境界を以下で更新した。

## 起動コンテキストと作業状態

- Kドライブの祖先からpier_designまでAGENTS.mdは存在しなかった。K側リポジトリルートはgit実測で `//sasaco-ds218/E6-14-D8/data/ニュージャパンコンサルタンツ/26_LRT鉄道照査`、HEADは調査時 `744e938`。K側の `.claude/rules/`、`.claude/STATE.md`、`.claude/docs/DESIGN.md`、`PROGRESS.md` は不存在。GridLayoutPdfの共有ルールを読んで調査した。K側に欠落するbootstrap文書を新規作成してはいない。
- K側 `CONTEXT.md:7` に線路方向、`:11` / `:15` に地震時の両方向荷重、`:19` に橋脚天端の等価作用、`:23` に検討モデルの骨組図、`:27` に柱下端の微小部材、`:31` に作用の組合せが定義済み。帳票移行を構造応答解析・耐震照査の実装と呼ばない。CONTEXT-MAP.mdとdocs/adrは見当たらない。
- 再調査時HEADは `744e9389fa69c62906d85d42c823940f924a9251` のまま、`pier_design/cli.py`、`editor_calculation.py`、`editor_gui.py` が変更済み。`pier_design/jrsnap_artifacts.py`、`jrsnap_readback.py`、`scripts/accept_jrsnap_ndu.py`、`tests/fixtures/jrsnap_v52_longitudinal_expected.json`、`pre/snapshots/` とK側NDU文書/スキル等が未追跡。別作業の変更を保持する。HEADだけでは調査状態を再現できないため、実装開始前に作業ツリーの再照合が必要。

## 現在の入口と六つの帳票

最新 `P7橋脚/pier_design/cli.py:346` がCLI入口。`:352`〜`:353` にstage/JRSNAP選択、`:184` の `_calculate_stages` が計算、`:218` の `_render_reports` がrenderer境界、`:238` が `(result, staged_pdf)` 呼出し、`:243` が同じresultのJSON保存。`:249` の `prepare_generation` が計算・生成を一度だけ行い、`:86` の `GenerationCandidate` を保持して返す。入力/計算/候補検証を維持し、`_render_reports` 内の描画だけを切替える。初回の「cli.py:99がrenderer境界」という根拠は並行更新により無効になった。

| Stage | 現行rendererと根拠 | 現在保存されているPDF | 指定Example橋脚/outputの見本 |
|---|---|---:|---:|
| 0500 直接基礎 | `pier_design/report.py:387` | 3頁 | 3頁 |
| 0600 上部工反力 | `pier_design/reaction_report.py:58` | 30頁 | 37頁 |
| 0610 線路方向荷重 | `longitudinal_report.py:3` → `longitudinal_example2_report.py:338` | 8頁 | 12頁 |
| 0620 直角方向荷重 | `transverse_report.py:2` → `transverse_report_example2.py:145` | 12頁 | 17頁 |
| 0710 地震時線路方向 | `seismic_longitudinal_report.py:431` | 3頁 | 該当PDFなし |
| 0720 地震時線路直角方向 | `seismic_transverse_report.py:534` | 4頁 | 該当PDFなし |

ページ数は調査時の既存PDFをPyMuPDFで読み取った実測値で、生成確認ではない。全10 PDFが595×842pt。現PDFの頁数は入力内容・現行規則の結果であり、新移行の受入条件にはまだしていない。

現行0610はschema_version=2の正規結果だけを読む8枚のdrawer構成 (`longitudinal_example2_report.py:339`〜`:355`)。0620もschema_version=2を要求し、骨組/材料/荷重/ケースへ分かれる (`transverse_report_example2.py:145`〜`:156`)。旧0610の `longitudinal_report_reference.py` と旧0620の `transverse_report_style.py:151` にもrendererが残るため、名前だけから主経路を判断しない。

`P7橋脚/README.md:251`〜`:259` は初期Example橋脚と現条件Example橋脚2を明確に区別している。現行式・入力・ケースを古い見本へ戻す変更は、ユーザーの「計算内容ではなく体裁」の指示に反する。

## 計算と表示の境界で保持するもの

1. **結果dictとJSONを正本にする。** 最新 `cli.py:272` で全選択段階を計算、`:284` で描画、`:243` で同じresultをJSONに保存する。計算器、入力parser、schema、丸め順、Single/Doubleの引継ぎはユーザー合意により維持する。具体対象は `calculator.py`、`reaction_calculator.py`、`longitudinal_calculator.py`、`transverse_calculator.py`、`seismic_longitudinal_calculator.py`、`seismic_transverse_calculator.py` と各inputs/actions/combinations。
2. **0600の表示式は無条件には削除できない。** `reaction_report_values.py:167`〜`:182` は静的レイアウトJSONのconstants/formulasと現result.cellsを合成し表示セルを評価する。`:103`〜`:164` は循環参照検出、IF/SUM/ROUND等を持つ。`reaction_report.py:60`〜`:66` は表示値の充足を検証する。これを「座標だけの旧実装」と誤認すると表示値・式の因子を失う。現結果から必要表示値を明示抽出する移行境界を先に定義し、既存表示値との同値を照合する必要がある。
3. **表示精度も計算書内容。** `_Page.text` は幅不足時に縮小し、横伸縮も行う (`report.py:88`〜`:105`)。GridLayoutPdfの文字サイズ保持方針へ切替えると改ページ/表幅が変わる。数式因子の精度を落として収めることは不可。既存0710/0720テストは表示因子から結果が再現できることを確認する (`test_seismic_longitudinal_report.py:236`, `:291`; `test_seismic_transverse_report.py:177`)。
4. **図は現在の入力に追従する。** `frame_outline.py:31` は外形、`:89` は寸法、`:188` は配置、`:269` / `:291` はCanvas描画。`frame_model_report.py:104` は節点/部材等の描画。意味的な幾何とCanvas依存を分離して再利用する提案。静的な見本図への置換で現在寸法・節点・微小部材を失わない。
5. **地震帳票の固定頁条件は今回解除する。** K側の旧計画 (`seismic-longitudinal-loads-report.md:13`、`p7-seismic-transverse-report-regeneration.md:13`) と現renderer (`seismic_longitudinal_report.py:432`; `seismic_transverse_report.py:535`〜`:539`) の3/4頁制限は、新しい全六帳票可変頁のユーザー合意で上書きする。意味内容/ケース/精度/失敗時target保護は維持し、固定頁のassertだけを新しい内容被覆・可読性・改頁条件に更新する。0720の原子的出力 (`:559`〜`:569`) を含む公開保護は固定頁解除と無関係に残す。

## 書式と依存の現状

- 日本語書体はWindowsのmsmincho.ttc/msgothic.ttc face0を優先し、不在時CID書体にフォールバックする (`report.py:28`〜`:43`)。GridLayoutPdf側の固定書体供給/字形検証に移す際、フォールバック・再配布の境界を定義する。
- 0600は `reaction_report_layout.py:186` のセル/罫線描画、`reaction_report_pagination.py:53` のsection/band配置、`reaction_report_diagrams.py:439` の動的図、`reaction_report_horizontal.py` と `reaction_report_snow.py` にまたがる。大きな単一置換より意味単位の原稿作成が必要。
- 0610は `longitudinal_example2_report.py`、0620は `transverse_report_example2{,_loads,_cases}.py` と `transverse_report_style.py` に個別Canvas表現がある。共通Page/フォント/表を共有するが、それぞれの責務を新ライブラリへ移す必要がある。
- `tools/build_reaction_report_layout.py:22` / `:65`、`tools/build_longitudinal_report_layout.py:25`〜`:27`、`tools/build_transverse_report_layout.py:16`〜`:17` は旧Excel/PDFから一度抽出したJSONの生成工具。ユーザー指定PDFを体裁の根拠にすることと、これらの計算内容を新しい正本にすることは別。今回工具は実行していない。
- `P7橋脚/pyproject.toml:5` はPython>=3.12、`:7`〜`:10` にgridlayoutpdf/PyMuPDF/ReportLab/tksheet、`:14` にpytest/pypdf/xlrd。`:20`〜`:21` で `C:/Users/sasai/Documents/GridLayoutPdf` の非editableローカルpath依存。`uv.lock:148` も同じdirectory source。P7 .venvのimportlib.metadata実測はgridlayoutpdf 0.1.0、ReportLab 5.0.1、PyMuPDF 1.28.2。pier_design内にgridlayoutpdf参照は検索時0件。既に導入されているが利用は未開始。

## CLI/GUI/外部成果物を壊さない統合条件

- 通常 `--stage all` は6 PDF + 6計算JSON + 両方向FrameWeb入力/付帯JSON4ファイルの計16。`frameweb_artifacts.py:33`〜`:40`、`:62`〜`:76` が既存集合を定義する。最新 `--stage all --jrsnap` はさらに `post/線路方向.ndu` と `.ndu.provenance.json` を加え計18、`--stage 0710 --jrsnap` は0710 PDF/JSONとNDU/付帯JSONの計4 (`cli.py:253`〜`:263`; `jrsnap_artifacts.py:22`〜`:24`)。0710単独でも0500等は内部計算するが、選択外PDF/JSONは公開しない。
- 最新 `cli.py:283`〜`:343` はstaging→帳票/JSON/FrameWeb/NDU→manifest/hash→候補検証→yield。`:358`〜`:359` がcandidate.publishを呼ぶ。FrameWebのschema2 manifest集合は変更せず (`:296`〜`:298`)、JRSNAPは0710 PDF/JSON/NDUの3成果物を独立manifestに持つ (`jrsnap_artifacts.py:66`〜`:69`, `:90`)。all時は両系統のpublication_id/selected_stagesを照合する (`:172`〜`:177`)。PDFだけの個別上書きはどちらの来歴も壊すため、staged pathと候補公開経路を維持する。
- `artifact_publication.py:162`〜`:250` は複数出力の退避/置換/失敗時復元。OS上の一括transactionではなく、未完了journalは再実行を止める (`:44`)。その振る舞いを維持する。
- GUIは最新 `editor_calculation.py:177`〜`:183` でCLIを `--stage all --overwrite`、選択時のみ `--jrsnap` 付きで実行する。main thread検証は`:115`、JRSNAP時は18成果物を照合する (`:129`〜`:148`)。新チェックボックスは `editor_gui.py:519`、startへの伝達は`:706`。既存UIは保持する。`README.md:215`〜`:227` の6帳票/プレビュー説明だけでは追加NDU経路を網羅しないため、並行作業のREADME更新と調整する。

## JRSNAP候補保持と移行の追加リスク

- `GenerationCandidate.validate_unchanged` (`cli.py:136`) は候補の有効期間・再使用、staging内の厳密なファイル集合、全成果物hashを検証する。JRSNAP時は入力/実装source hash (`:122`)、公開先の生成開始時identity/hash (`:146`) も照合する。`publish` (`:167`) は同じ保持bytesを公開し、退避した旧ファイルの競合も確認する (`:153`)。新rendererがstaging内へgrid版・trace・PNGを勝手に追加すると集合照合に失敗する。診断成果物は製品公開候補と別の明示的検証領域に生成するか、成果物契約を正式に拡張する必要がある。
- 外部アプリ受入用 `scripts/accept_jrsnap_ndu.py:258` は `prepare_generation` を一度呼び、NDUのコピーをJRSNAPで検証し、再計算/再描画せず同じ候補をpublishする (`:273`, `:287`, `:306`〜`:307`)。受入receiptは全候補成果物のhash (`:201`) と実装source集合 (`:204`) を結合し、finalizeでも再確認する (`:214`〜`:250`)。新PDFへの切替後に旧receiptを新世代へ使い回すことはできない。通常CLIの出力だけで実アプリ受入済みとはしない (`jrsnap_artifacts.py:92`)。
- **移行に直接関係する追跡漏れ:** `jrsnap_artifacts.py:39`〜`:42` の実装hashは `pier_design/*.py` の直下globのみ。受入receiptの集合確認も `scripts/accept_jrsnap_ndu.py:225` が直下globのみ。新規 `pier_design/reporting/`、外部インストールのgridlayoutpdf、書体/宣言的style等は現状この保護に入らない。移行時は入れ子原稿と実際に読み込むライブラリ/書体を再現可能に固定し、そのidentityをsource/provenance/receiptに一貫して結び付ける方式を決める。単なるバージョン文字列0.1.0は並行変更を区別できない。再帰化または明示台帳を採る場合、上記2実装と検証をそろえ、任意ファイル全量hashで範囲を無制限に広げない。
- **未完成の並行実装:** 再調査時点で `cli.py:276`〜`:277` がimportする `jrsnap_export.py` / `jrsnap_ndu.py` は未存在、`tests/test_*.py` にGenerationCandidate/JRSNAP関連の参照は検索0件。任意経路の設計コードは読めるが、動作完了・テスト成功を示さない。移行の初期ゲートでこの並行実装の合流状態を再確認し、未完を本移行が無断で埋めたり削除したりしない。

## 既存試験と不足

テストファイルは現物65本。今回試験は実行していないため成功数・coverageは主張しない。

- 計算回帰: `test_reaction_calculator.py:56` は独立oracleと全公開値/引継ぎを比較、`test_longitudinal_calculator.py:231`、`test_transverse_calculator.py:233` はExcel oracle。地震系は `test_seismic_longitudinal_calculator.py:101`、`test_seismic_transverse_calculator.py:92` に独立期待値。これらを残し、移行前後の同一入力JSONの全result等値を追加する候補。
- 現行0610: `test_longitudinal_example2_report.py:136` に8頁/順序/footer、`:266` に320係数を物理セルで照合。現行0620: `test_transverse_example2_report.py:34` にsnapshot不変、`:73` に全支承・改頁、`:100` に12頁構成、`:137` に240係数。
- 旧0610/0620試験も残る: `test_longitudinal_report.py:13` はlegacy計算器、`:18` はreference layout。`test_transverse_report.py:16` もlegacy計算器。旧672係数や21×20の試験を現行240/320へ混同しない。旧実装を削除するか互換用途で残すかは実装scopeで明示する。
- 0500: `test_report_cli.py:50` に3頁と計算JSON。0600: `test_reaction_report.py:187` に節/値、`:255` にSingle引継ぎと帳票値の分離、`:301` に以前空欄だった支承、`test_reaction_report_pagination.py:54` にtable収容と継続見出し。
- 0710/0720: `test_seismic_longitudinal_report.py:142`、`test_seismic_transverse_report.py:124` はsnapshot-only、不変性。0720`:209` は20支承/40代入式、`:238` は読めない4頁出力を拒否しtarget保持、`:254` はreplace失敗。
- 公開/GUI: `test_artifact_publication.py:15` / `:80` / `:181` は復元・backup保持・中断journal、`test_editor_calculation.py:107` はworkerコマンドと16成果物、`:304` は帳票改変のmanifest検出、`:425` は隔離出力への実CLI。
- 不足/更新対象: 新GridLayoutPdf原稿と現在のresult各項目を結ぶ網羅台帳、見本の共通書式の実測仕様、見本と生成PDFの直接比較、全6帳票・全頁の通常/grid目視、変動入力のoverflow/no-clipping、native文字/表/図保持、固定書体と配布版の利用検証が必要。固定頁は合意に従って可変頁の被覆試験へ移し、意味内容のassertを弱めない。新ライブラリのgolden一致だけを見本との体裁一致の証拠としない。
- 最新公開経路に対する必須統合試験: 通常all=16、JRSNAP all=18、0710+JRSNAP=4を隔離出力で検証し、6結果JSON・FrameWeb native・NDUの意味内容不変と、新PDF hashを含む両sidecarの世代一致を確認する。新layout/font例外で正式出力が全保持され、復元失敗時journal/backup保護が残ることを確認する。
- 候補保持の必須負例: 候補生成後の新renderer/入れ子原稿/実際のgridlayoutpdf/書体変更、PDF改変、余分なstagingファイル、公開先競合を拒否し、receipt完了処理でも検出する。入力・計算snapshotは変更せずPDFだけ改変しても拒否されること、受入後にrendererを二度呼ばないこと、古いreceiptを新PDFへ転用できないことを検証する。
- GUIの追加回帰: 新JRSNAPチェックボックスoff/onでCLI引数と16/18成果物検証が切替わり、いずれも6 PDFの可変頁をpreviewできること。NDU/sidecar欠落・旧世代混在時に今回成功として扱わないこと。現時点で不足するJRSNAPテストは並行担当の合流を確認して重複実装を避ける。

## 計画用の具体的scope候補（未承認）

- 主な変更先: 上記6公開renderer、0600のlayout/pagination/horizontal/snow/values/diagrams、0610/0620個別描画、`frame_model_report.py` と `frame_outline.py` の描画依存、`P7橋脚/tests/test_*report*.py`、`P7橋脚/README.md`。必要最小限の `cli.py` で新layout例外をユーザー向け失敗へ変換する候補。cliの計算順/公開順は維持する。
- 新規候補: `pier_design/reporting/` 以下の共通style、数値表示adapter、図部品、stage別のGridLayoutPdf原稿と、対応する内容/視覚試験。具体ファイル名は対話後に確定。
- 追加保護対象: `pier_design/jrsnap_artifacts.py` と `scripts/accept_jrsnap_ndu.py` のsource identity契約は、入れ子原稿/外部ライブラリ導入に追従する最小修正候補。NDU計算/serializer/readbackの意味変換自体は維持する。`GenerationCandidate`の一度生成・同一bytes公開・候補外ファイル拒否・競合検出は改造で失わない。
- 原則変更不要: 入力JSON、入力GUI/配筋UI、calculator/actions/combinations、FrameWebの意味変換、artifact_publication、pdf_preview。これらは回帰検証対象。
- GridLayoutPdf側の変更は公開APIで表現できない具体例が判明した場合に限定する。P7固有式・項目・値を汎用ライブラリへ入れない。

## 次のgrillで解く事項

1. 解決済み: 六帳票のPDF生成を全面移行、計算/入力GUI/I/Oは維持。
2. 解決済み: 全六帳票を可変頁とし、0710=3/0720=4の固定制約は解除。現計算節・ケース・式を残す。
3. 書体、インデント、等号位置、表行高、色、ページ番号の詳細は親の最新対話を正とする。片持ち梁37頁の個別固定頁契約を移行へ自動で持ち込まない。
4. 実装上の解決事項: 並行JRSNAP経路の合流状態、旧renderer互換用途、新ライブラリと入れ子原稿を含むsource identityの範囲。通常I/OやNDUの意味内容を変更する根拠にはしない。

