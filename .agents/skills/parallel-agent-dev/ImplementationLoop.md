# ImplementationLoop — ソースコードレビュー・修正ループ

ソースコード（Python 実装ファイル）のレビュー・更新に使う。
共通ルール・収束基準は [`SKILL.md`](./SKILL.md) を参照。

---

あなたはオーケストレーターです。
実装ファイル群（Python）に対して「レビュー → 集約 → 修正 → 検証」を 1 ラウンドとし、MEDIUM 以上の Finding がゼロになるまで反復させます。

## 収束の確認

ラウンドごとの指摘件数と修正による回帰を記録する。別プロジェクトの実績をこのリポジトリの必要ラウンド数として扱わない。

## 起動チェック

ラウンド 1 開始前に必ず以下を実行する:

1. レビュー対象の計画書・規約を**必ず先に読む**:
   - 該当フェーズの計画書（例: `.agents/docs/plans/grid-aligned-calculation-reports.md`）
   - 関連アーキテクチャ doc / open-questions
   - `.agents/skills/tdd/SKILL.md`
2. 現状の build/test 状態を実コマンドで確認。レビュアーが「全緑」と主張しても自分で叩いて裏を取ること

## ループ手順

### Step 1: レビュー（サブエージェント並列）

以下のサブエージェントを **同一メッセージ内で並列起動**（独立タスクは並列が原則）:

| エージェント | 観点 |
|---|---|
| `python-reviewer` | Python の型ヒント・例外処理・公開 API の整合 |
| `silent-failure-hunter` | 握り潰しエラー・空出力・検証不足 |
| `layout-reviewer` | 座標系・単位・グリッド整合・改ページ ※ レイアウト変更時 |
| `type-design-analyzer` | 入力値・配置結果の不変条件、計算と描画の責務分離 |
| `pdf-reviewer` | PDF のフォント・文字位置・描画結果 ※ PDF 出力変更時 |
| `general-purpose` | コード品質・計画書との整合・テストの妥当性 |

各エージェントへの指示テンプレ（self-contained 必須）:

> `.agents/docs/plans/` 配下のドキュメントを必ず参照し、実装が計画と整合しているか検証せよ。指摘は **CRITICAL / HIGH / MEDIUM / LOW** で分類し、`path:line`、根拠（計画書のどの条項に違反か）、推奨修正、回帰防止テストの提案を含めよ。末尾に重要度別件数サマリ。500 行以内。

レイアウトや PDF 出力に変更がない場合は、それぞれの専用観点を省略してよい。**スコープに合わせてエージェントを選ぶ**。

### Step 2: 集約（オーケストレーター本人）

全エージェントの指摘をマージし、重複統合 → 重要度順に並べた一覧を作成。CRITICAL / HIGH / MEDIUM の件数を要約。

**集約時の注意**:
- 同じ問題が複数エージェントから別 ID で報告されることが多い。**高い方の重要度を採用**
- レビュアー間で重要度判断が割れた場合は、production リスクが高い方を採用

### Step 3: 修正（サブエージェント並列）

**MEDIUM 以上が 1 件でもあれば** `general-purpose` エージェントに修正依頼。

> **`implementer` サブエージェントは単一 RED→GREEN サイクル制約があり、大きな batch を拒否する。** 多項目を一括で進めたいときは `general-purpose` に「TDD 順序で順次着手せよ」と明示する。1 項目ずつ厳密に進めたい場合は test-writer → implementer のペアを項目ごとに回す。

修正エージェントへの指示には必ず以下を含める:

- 該当ファイル・行・指摘内容（オーケストレーター側で要約）
- 不可侵ルール一式（[`SKILL.md`](./SKILL.md) 参照）
- TDD 順守と各項目の RED → GREEN → REFACTOR 順序
- **uv 環境利用の明記**（製品テストは `uv run --locked --extra dev python -m pytest`、共有スクリプトは `uv run --no-project python`）
- **「降格判断はユーザー権限。実施できないと判断したら DEFER ではなく STOP+REPORT して指示を仰げ」と明示**
- **「対象ファイル外を変更しない」**: 修正対象として列挙したファイル以外は触らない
- 修正後の最終コマンド緑確認（変更範囲の pytest と必要な PDF 出力確認）
- **計画書の該当フェーズ末尾に「レビュー反映 (YYYY-MM-DD, ラウンド N)」ブロックを追記**

修正項目は依存関係順にグループ化する（例: 型変更 → レイアウト計算 → PDF 描画 → テスト）。**型シグネチャ変更や座標系の変更は最初に実施**（後続項目への影響を吸収しやすい）。

### Step 4: 修正の検証と再レビュー

修正後にレビュー段階を再実行。**ただし全エージェントを毎回回す必要はない**:

- ラウンド 2 以降は **変更があった層のレビュアーのみ**（例: 例外処理だけなら silent-failure-hunter + python-reviewer、座標計算なら layout-reviewer も追加）
- **silent-failure-hunter は毎回必ず回す**: 「fix が新たな silent failure を導入する」パターンが頻出

### Step 5: 次ラウンドへ / ループ終了

CRITICAL/HIGH/MEDIUM が残存する場合は Step 1 に戻る。次ラウンドのレビュー指示には:
- **当ラウンドで修正された箇所を重点検査**する旨を明記
- ラウンド数が増えたら投入エージェントを絞る（変更層のみ + silent-failure-hunter 固定）

## 出力形式（毎ラウンド）

各ラウンド開始時:

```
=== ラウンド N ===
残存 CRITICAL: X件 / HIGH: Y件 / MEDIUM: Z件 / LOW: W件
```

計画書の該当フェーズ末尾に **「レビュー反映 (YYYY-MM-DD, ラウンド N)」** ブロックを追記し続ける:

- 完了項目に ✅
- 設計判断・新たな知見・Tips を他作業者が再現できる粒度で

書く内容:
1. 解消した指摘（id + 1 行サマリ）
2. 修正中に発覚した設計判断（plan を更新する根拠）
3. 新たな見逃しパターン候補
4. 持ち越し項目とその理由

**サイズ管理**: 各ラウンド反映ブロックが肥大化する。「ラウンド N で解消」と書いた項目は次ラウンド以降では繰り返し書かない。

## 完了サマリ

```
=== 完了 ===
全ラウンド数: N
修正した Finding 総数: CRITICAL X / HIGH Y / MEDIUM Z / LOW W
残存 LOW（対応不要）: K件
主要な反映成果:
- 型安全: ...
- silent failure 除去: ...
- テスト追加: M件（pytest 緑確認済）
- 座標・単位・出力契約の整合: ...
```

## ループ上限と escape hatch

- **最大 N ラウンド = 8** をハード上限とする。それを超えても収束しない場合は強制終了し、残存 CRITICAL/HIGH/MEDIUM を計画書の open-questions セクションに **未決オープン質問として書き出す**
- CRITICAL/HIGH/MEDIUM 件数が **3 ラウンド連続で減らない**場合、投入レビュアーの観点が実装スコープとずれているサインなのでユーザーに相談する

## オーケストレーター運用 Tips

### 並列起動

> 独立タスクは **同一メッセージ内で複数 Agent 呼出**。「6 件並列」＝ 1 メッセージで 6 ツール呼出。順次起動するとコストも時間も無駄。

### バックグラウンド実行

レビューエージェントは長時間（数十秒〜数分）かかるため `run_in_background: true` で投入し、完了通知を待つ。Sleep ループは禁止。

### 修正範囲の判断

| 発見 | 対応 |
|---|---|
| CRITICAL | 必ず即修正 |
| HIGH（コード変更） | 同 PR で修正 |
| HIGH（大規模リファクタ・別 PR スコープ） | **ユーザーに承認を取る**。承認後に計画書「繰越」に明示してパス |
| MEDIUM | 同 PR で修正（このスキルの停止条件） |
| LOW | 列挙のみ。次フェーズで拾うかどうかをユーザーに判断してもらう |

### `implementer` vs `general-purpose`

- `implementer`: **1 項目厳密 TDD**。RED テストの handoff が必須。多項目を投げると拒否される
- `general-purpose`: **多項目 batch + TDD 順守可**。プロンプトで「各項目で RED→GREEN→REFACTOR」と明示する

### コミット時の選択的ステージング

修正エージェントが全体整形を実行すると、フェーズと無関係なファイルにもフォーマット差分が出る。
コミット時は `git add -A` を避け、フェーズに関連するファイルを **明示列挙**してステージング。

---

## 禁止事項と失敗パターン

### ループ固有の禁止事項

- `silent-failure-hunter` を省略してはいけない。fix が新たな silent failure を生む頻度が高い
- 修正エージェントに勝手に繰越を決めさせてはいけない。降格はユーザー権限
- subagent の「全緑」主張を鵜呑みにしてはいけない。**必ず `uv run --locked --extra dev python -m pytest` 等を自分で叩いて裏を取る**

### 失敗パターン（避けること）

1. **MEDIUM を無視して LOW だけ残した状態で「完了」にする** — ループ条件違反。MEDIUM ゼロまで繰り返す
2. **修正後の再レビューをスキップ** — 修正で新規 MEDIUM が混入していないか必ず確認する
3. **全エージェントを順次起動** — 並列が原則
4. **修正エージェントを `implementer` で多項目投げる** — 拒否されて時間ロス
5. **計画書追記を最後にまとめる** — ラウンドごとに追記しないと次のレビュアーが「何が解消済みか」判断できない
6. **fix 後に silent-failure-hunter を回さない** — fix 由来の新規 silent failure を見落とす
7. **subagent の「全緑」主張を鵜呑み** — 自分で `uv run --locked --extra dev python -m pytest` 等を叩いて裏を取る
8. **コミット時に `git add -A` を使う** — 別フェーズの作業や untracked artifact が混入

---

## 運用上の注意

### subagent の勝手繰越癖

ユーザーが「全件修正」と明示しても、修正エージェントは「影響範囲が大きい」等の理由で独断で次フェーズへ降格することがある。**プロンプトに「降格判断はユーザー権限。困ったら STOP+REPORT」を明記**するまでこの癖は再発する。

### fix 自体が silent failure を生む

修正は新たな silent failure を生む。**silent-failure-hunter は毎ラウンド必ず回す。**

### コメントと実装の乖離

`# removed: ...` というコメント直下に実装が残るケースがある。**grep `"dropped:" "removed:" "deleted:"` 等のキーワードで該当箇所を機械抽出**して最終レビューで確認。

### 正規表現ベースのソース検査は脆い → AST へ

ソースコード解析テストは `re.search` より `ast.parse` + visitor（`Assign` / `AnnAssign` / `NamedExpr` を網羅）が堅牢。

### テスト sentinel と `.env` の値衝突

`.env` の dev creds とテストの漏洩検知 sentinel が同一文字列になると検知が無効化される。**test sentinel は `TEST_SENTINEL_<uuid8>` 形式で realistic value とは交わらないドメインに置く**。

### `--token` CLI 引数 = secrets leakage

`argparse` で `--token VALUE` を受けると `ps -ef` の commandline 列に値が残る。**stdin 経路に統一し、CLI flag は `argparse.SUPPRESS` で隠して deprecation warning**。

### 全体整形は無関係ファイルを汚す

全体を対象にした整形は、担当外の Python ファイルまで差分を生む。コミット時に「fmt 由来か機能変更由来か」を `git diff --stat` で確認する。

### `isolation: "worktree"` がフィーチャーブランチで base 不整合を起こす

フィーチャーブランチ作業中に `isolation: "worktree"` を使うと、worktree が **`main` から作られ**、ブランチ上で新設したファイル（例: `src/gridlayoutpdf/` 配下の追加ファイル）が存在しない状態になる。エージェントが「対象ファイルが無い → 推測で実装するのは事故」と正しく判断して STOP+REPORT する。

**対策**: フィーチャーブランチ作業中は **worktree を使わずメインリポジトリで直接作業**させる。並行性は「ファイル単位の担当分け」で確保し、計画書のような共有ファイルだけ orchestrator が最後に集約する。

### 単一エージェント batch の限界

CRITICAL 6 / HIGH 10 / MEDIUM 16 + 大型新機能 + テスト分割 を **1 体の `general-purpose` に投げると着手前に STOP+REPORT** される。理由は「TDD 厳守 + 全検証緑で時間予算が読めない」。

**閾値の経験則**:
- 〜10 項目 + 軽い機能 → 単一 `general-purpose` で OK
- 10〜30 項目 → 依存順 batch に明示分割しても単一 agent でいける場合あり
- **30 項目超 / 大型新機能含む → `/parallel-agent-dev` 必須**

### 計画書末尾「レビュー反映」ブロックの並行更新競合

レイアウト担当と PDF 描画担当を並行実行する際、両者が同じ計画書末尾に追記しようとすると競合する。

**対策**: 並行する agent のうち **1 つだけ計画書の追記責任を持たせ、他は完了報告に差分サマリを箇条書きで返す**。orchestrator が最後に集約してまとめる。

### レビュアー名は agent type ではなく role prompt（spawn は general-purpose）

Step 1 の名前はレビュー観点であり、登録済み agent type を意味しない。利用可能なエージェントに観点を明記したプロンプトを渡し、レビュー中の編集を禁止する。対象外の観点は起動しない。

### 実行者自身がサブエージェントで Task/Agent ツールを持たない場合

オーケストレーターが**自分もサブエージェントとして spawn されている**ケース（親エージェントがレイアウト担当 / PDF 描画担当に分割した、等）では、**Step 1 の並列レビュアー spawn ができない**（Agent/Task ツールが tool set に無い）。このときは「ImplementationLoop を起動せよ」と指示されても物理的に並列 spawn 不可。**握り潰さず**、以下で代替する:
- 自分の delta を **3 レンズ（silent-failure / Python 品質 / type-design）を 1 人で順に当てて self-review** する。各レンズで「新フィールド・新 if 分岐・入力検証・配置計算・描画順序」を点検。
- ベースライン緑は**自分で実コマンド**（`uv run --locked --extra dev python -m pytest`）で取り、pre-existing failure（他の並行作業に由来するテスト失敗等）を自分の delta 由来と誤認しない。
- 完了報告に「サブエージェント制約で並列レビュー不可 → self-review レンズ N 周で代替」と明記する（親が必要なら追加レビューを spawn できる）。

### 大きいファイルの単一 Read は Edit の exact-match に使うな

数百行を 1 回の Read で読むと、特定行（関数本体）が**不正確に再構成**されることがある。`Edit` の `old_string` を作る直前は**対象関数を狭い offset/limit で再 Read** して現物を確定させる。`String to replace not found` が出たら記憶ではなく再 Read を信じる。

### レビュー修正中にユーザー（or 別セッション）が同じファイルを並行編集する

review→fix ループ中に、ユーザーが**レビュー対象ファイルを並行で commit / 編集**することがある。兆候は ① `<system-reminder>`「ファイルが変更された」通知、② `git diff --stat` の行数が**減る**（HEAD が進んだ＝ commit された）、③ 自分が書いていない関数/定数が出現する。

**これを「自分の編集が壊された/corruption」と早合点しない**。対処:
- `git log --oneline -3` で HEAD が進んだか、`git status --short` で何が uncommitted かを確認する。`git diff --stat` の縮小は多くの場合 commit によるもので破損ではない。
- **自分の編集が生存しているかは `grep` で実地確認**する（追加した定数名・関数名・エラーメッセージを数える）。diff-stat や reminder の本文だけで判断しない。
- 以後の `Edit` は**直前に対象関数を狭く再 Read**（前述の狭い範囲での再読）してから行う。並行編集と領域が重ならなければ exact-match Edit はそのまま通り、重なれば `old_string not found` で安全に失敗する（clobber しない）。
- **全体テストは並行編集で moving target になる**。自分の担当スコープ（触ったファイルのテスト）に絞って緑を確認し、ユーザーの in-progress 変更（別 step）は自分の収束判定に含めない。
- 共有ファイル（計画書 doc 等）への「レビュー反映」追記は、ユーザーが別 step セクションを書いていても**領域の重ならない自セクション末尾**に surgical に入れる。

### 「レビューして」と言われたとき、未コミットツリーが既に *前回の review-remediation ラウンド* のことがある

「Phase N 完成、レビューして」の依頼で working tree を見ると、**コミット済み実装の上に未コミットの review-fix delta が積まれている**ことがある。これは「新規実装をゼロからレビュー」ではなく「**前回の修正ラウンドの検証 + fix 由来の回帰再レビュー**」が正しいフレーミング。

兆候: `git diff` のコメントに `Finding`/`MEDIUM-N`/`review fix`/`item N`/`fix #N` 等のレビュー語彙、`git log` は当該フェーズが既にコミット済み（HEAD は次フェーズ）。

対処:
- **コミット済み全体を再レビューし直さない**（多ラウンド収束済みの指摘を蒸し返すだけ）。**未コミット delta を一次対象**にし、各 fix を「正しいか / 新たな silent-failure を生んでいないか」で読む。
- 1 周目レビューの prompt に「この delta は前回の修正。fix の正しさと fix 由来の回帰を見よ」と明記する。
- fix が**逆方向**に書かれている指摘を鵜呑みにしない（処理順序に関する指摘は、実際の呼び出し順序と出力を確認してから適用）。
- ベースライン緑は**自分で**取る（既存の pytest 失敗を自分の変更由来と誤認しない）。

---

## 汎用呼び出しテンプレート

新フェーズ・PR を仕上げるときにオーケストレーター（あなた）に貼り付けて使う。`{{}}` プレースホルダーを実値に置換すること。

---

あなたは **オーケストレーター** です。`GridLayoutPdf` リポジトリで `{{feature}}` のフェーズ `{{phase_id}}` 「`{{phase_title}}`」を レビュー → 修正のループで仕上げてください。

**唯一のリファレンス**: すべての手順・不可侵ルール・収束基準・既知の落とし穴は [`SKILL.md`](./SKILL.md) と本ファイル（[`ImplementationLoop.md`](./ImplementationLoop.md)）に集約されています。

### 必読ドキュメント

```text
{{plan_doc}}              # 例: .agents/docs/plans/grid-aligned-calculation-reports.md
{{spec_doc}}              # 例: .agents/docs/DESIGN.md
.agents/skills/tdd/SKILL.md
```

### レビュー対象スコープ

```text
{{file_list}}             # 例:
                          # src/gridlayoutpdf/<target>.py
                          # tests/<target_test>.py
                          # 実在する対象ファイルに置き換える
```

### プロジェクト固有の検証コマンド

```powershell
uv run --locked --extra dev python -m pytest {{test_path}} -v
# 製品全体の検証:
uv run --locked --extra dev python -m pytest
# 共有エージェント設定も変更した場合（製品テストとは別）:
& .agents/check.ps1
```

レイアウト変更では生成 PDF も確認する。参照 PDF と検証出力を区別し、既存の参照 PDF は上書きしない。

### 起動するレビュアー

```text
{{reviewers}}
# レイアウトと PDF 出力を変更する場合の観点例:
# python-reviewer, silent-failure-hunter, layout-reviewer,
# type-design-analyzer, pdf-reviewer
```

### スコープ外（subagent が触らないこと）

```text
{{out_of_scope_paths}}
# 例:
# .agents/docs/plans/<other-phase>.md   # 別フェーズの計画書
# .agents/skills/<other>/    # 他のスキル
```

### 進捗反映先

- 計画書: `{{plan_doc}}` の `§{{phase_id}}` 末尾に「レビュー反映 (YYYY-MM-DD, ラウンド N)」ブロックを追記

### 開始手順

1. 上記必読ドキュメントを読み、`{{plan_doc}}` の `§{{phase_id}}` の現状を把握する
2. `ImplementationLoop.md` の「起動チェック」→「Step 1（並列レビュー）」から開始する
3. 各ラウンドの集約・修正・再レビューは本ファイルの手順に従う
4. **MEDIUM 以上ゼロ** で終了。ループ完了後にユーザーへ最終サマリ（ラウンド毎の件数推移・繰越項目・新規追加テスト）を報告する

---

## ループ自体のメンテナンス

このスキル自体も品質収束する。新フェーズで適用した後、新しい知見が出たら本ファイルの「運用上の注意」セクションに追記する。
