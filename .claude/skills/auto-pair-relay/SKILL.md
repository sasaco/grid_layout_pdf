---
name: auto-pair-relay
description: >-
  永続 Navigator と 1 手ごとに起動する Driver で長い Python 実装を進める。Navigator が設計・レビュー・pytest 検証を主導し、lead はユーザーとの橋渡しと最終ゲートを担当する。永続エージェントを利用できない環境では本文の fallback 手順を使う。
---

# Pair Relay（Agent Teams ハイブリッド）

長い実装を **永続 Navigator（teammate）** と **使い捨て Driver（subAgent）** のハイブリッドで回すスキルです。

```text
Human / Owner
  │ 依頼・最終承認・手元 E2E
  ▼
lead（司令塔 = あなた）            ……… team を立て、Human と橋渡しし、最終ゲートを締める
  │ mailbox（永続）
  ▼
Navigator（永続 teammate / 頭脳）  ……… Bash・Skill・Agent をフルに持つ
  │ Agent ツールで 1 手ごとに spawn・報告を直接受領
  ▼
Driver（使い捨て subAgent / 手）   ……… 1 手 = 1 spawn のタイピスト、stateless
```

## なぜハイブリッドか

旧設計は Navigator も Driver も subAgent で、lead が両者の間で**全メッセージを verbatim にリレー**していました。そこから生まれた痛みはすべて subAgent の制約由来です:

- subAgent は毎ターン context を失う → **respawn のたびに外部記憶を貼り直す**（+5-10k token/ターン）。
- subAgent から Bash が剥がれる harness では **lead が pytest を代行**する。
- subAgent は Skill を持たない → **grill を lead が代行**し、回答者の振り分けに苦心する。

**Navigator を永続 teammate にすると、この 3 つが構造的に消えます。** teammate は独立した完全な Claude Code インスタンスで、ターンをまたいで context を保ち、Bash も Skill も Agent ツールも持つ。だから Navigator は自分で grill を回し、自分で Driver を spawn し、自分で pytest を叩けます。lead はもう per-step のリレー係である必要がない。

一方で Driver は **stateless なタイピスト**なので永続させる旨味がなく、1 手ごとに spawn する使い捨て subAgent が最も安い。レビューのセカンドオピニオンも同じく使い捨ての read-only `Explore` で十分かつ安全（破壊的操作が構造的に不可能）。

「永続させる価値のある頭脳は teammate、使い捨てでよい手は subAgent」——これがハイブリッドの分界線です。

## 役割

| 役割 | 種別 | 担当 |
|---|---|---|
| lead（あなた） | team lead | team セットアップ、Human との橋渡し、最終ゲート、respawn/cleanup |
| Navigator | 永続 teammate | grill、設計判断、次の 1 手、Driver の駆動、pytest 検証、差分整理 |
| Driver | 使い捨て subAgent | Navigator の diff を Edit/Write でそのまま反映し、短く報告する |
| Human / Owner | 人間 | 最終承認、手元 E2E、owner 判断 |

役割の指示は spawn prompt に含める。Navigator は対象コードを確認して次の 1 手と検証方法を決め、Driver は指定されたファイル・範囲だけを編集する。利用可能なエージェント機能を使い、専用 agent type の存在を仮定しない。

## セットアップ

1. **Navigator を 1 体 spawn する。** 利用可能なエージェントに Navigator の役割を指示する。lead = あなた、Navigator = 永続の頭脳、の最小構成。
2. **Navigator にゴールを渡す。** 依頼/issue の原文・計画書・既知の制約・「Driver は使い捨て subAgent として自分で 1 手ずつ spawn する方針」「最終承認と手元 E2E は Human が担う」を渡す。
3. **以降は Navigator 主導。** lead は Navigator からの報告・owner 質問・最終ゲート要求が来るまで前に出ない。

### 永続の仕組み（最重要 — ここを誤ると context が消える）

「永続 Navigator」はこのハーネスでは **「最初に spawn した Navigator に対し、以降の全メッセージを SendMessage で継続して送る」** ことで実現する。Agent Teams の teammate も、`Agent` ツールで spawn した subAgent の SendMessage 継続も、lead から見た運用は同じ：**同じ Navigator を生かし続ける**。

ルール:

- **2 回目以降は SendMessage（前回の Navigator 宛て）で継続する。新規 `Agent(pair-relay-navigator, …)` をゴール全文で呼び直さない。** 新規 spawn＋ゴール再貼り付けは **記憶ゼロの Navigator** を生み、grill も状況把握もやり直しになる（context と token の二重消費）。
- 渡すもの（owner 判断の回答・Driver の報告・Human のバグ報告・「次の 1 手の承認」など）は全部、同じ Navigator への SendMessage で送る。SendMessage の本文は**差分だけ**（ゴールや grill 結果を貼り直さない — 継続側は覚えている）。
- **`Done (N tool uses · X tokens · Ys)` は despawn ではない。** これは 1 ターンの完了サマリで、SendMessage すれば同じ context で再開する。"Done" を見て「終わった、次は新しく立て直そう」と新規 spawn してはいけない。
- **Navigator が `[owner-decision]` を返して止まったとき、特に despawn に見えやすい（grill 完了・実装待ち状態）。owner 判断が返ってきたら必ず `SendMessage` で同じ Navigator に返す。** 新規 `Agent(pair-relay-navigator, ...)` を呼ぶと grill 結果が消え、Navigator がコードを再 Read して grill 再現に追加 token を消費する。
- 例外は `[respawn-request: navigator]` が返ってきたとき、または**論理的に別タスク**（実装が一段落して code-review 修正フェーズに入る等）のときだけ。そのときは新個体を spawn し、引き継ぎ block（または新タスクのゴール）を渡す。

#### 健全な継続か despawn かの見分け方（agentId の同一性では判定しない）

継続時の ID やログ形式は実行環境によって異なる。継続側が決定済みの設計を把握しているか、同じスレッドを再開しているかを確認する。記憶を失っている場合は決定事項と最新の検証結果を再度渡す。

Navigator が持つツール（重要）:

- **Bash** — pytest/rg/git status を自分で叩く（lead 代行は不要）。
- **Skill** — grill-with-docs・tdd 等を自分で invoke する。
- **Agent** — Driver subAgent と read-only `Explore` レビュー subAgent を自分で spawn する。
- **Read / Grep / Glob** — コードを当てる。

### 作業に応じたスキルと検証の引き継ぎ

lead は対象範囲と適用するスキルのパスを Navigator の prompt に含める。テストを伴う Python 実装には `.claude/skills/tdd/SKILL.md`、設計の検討には `.claude/skills/grill-with-docs/SKILL.md` を必要に応じて使う。親のスキル内容が自動で引き継がれるとは仮定しない。

挙動や公開 API を変更する場合は、対応する回帰テストと既存利用側への影響を確認する。レイアウト変更は生成 PDF の座標・改ページ・外観も検証し、既存の参照 PDF は保持する。

## 標準ループ

### 0. 着手前 grill（Navigator 主導・ただし lead がゲートを守る）

旧設計では Navigator が Skill を持てず lead が grill を代行していたが、**teammate の Navigator は自分で `grill-with-docs` を invoke できる**。grill は Navigator の永続 context 内で一気通貫に回るので、論点ごとの respawn も外部記憶の貼り直しも不要。

⚠️ **構造ゲートの注意（最重要）**: 旧設計では grill は **Navigator を spawn する前**に lead の context で回っていたので、Navigator がまだ存在しない段階の手順＝**構造的にスキップ不可能**だった。grill を Navigator の中に移すと、grill は Navigator の「self-directed な最初の一歩」になり、Navigator は「次の 1 手」マシンなので**状況把握から即設計に飛んで grill を飛ばす**。だから lead が明示的にゲートを張る必要がある。

**lead のゲート enforcement（必ず行う）:**

1. Navigator の **spawn prompt に「最初の Driver を spawn する前に必ず `grill-with-docs` を完了し、`[grill-done]` + 決定事項サマリを lead に報告せよ。grill を飛ばして実装に入るな」と明記する**。「着手前に grill を回せ」だけでは弱い — Driver spawn の前提条件として書く。
2. Navigator から **`[grill-done]` サマリを受け取って初めて実装フェーズを承認する**。Navigator が grill を飛ばしていきなり「設計方針が固まった、Driver を spawn します」と来たら、**そこで止めて grill をやり直させる**（lead は Navigator の mailbox / 進行を見られる）。
3. owner 判断の論点が grill 中に上がってきたら、その 1 問だけ Human に提示して回答を返す。

Navigator の grill 進め方:

1. `grill-with-docs` を invoke する。
2. 設計論点を **1 問ずつ**立てる。前の論点の答えが次の前提を変えるので、全論点を batch にしない（設計ツリーを依存順に 1 本ずつ解く）。これは実装ループの「1 手ずつ」と同じ禁則で、harness の通信能力に依存しない。
3. **コード/ドメインで答えられる論点は Navigator 自身が Read/Grep で答える**（「既存の型は」「この命名は CONTEXT.md と整合するか」「呼び出し側の期待は」等）。推測で埋めない。
4. **owner 判断が要る論点だけ lead に上げる**（product 意図・要件の曖昧さ・優先順位など、コードからは決まらないもの）。lead はその 1 問だけ Human に提示し、回答を Navigator に返す。コードで答えられる問いまで Human に投げない。

5. 設計ツリーが解決したら、決定事項を CONTEXT.md / ADR にその場で反映する（Navigator が Skill を持つので自分で書ける）。
6. 着手十分か自己レビューし、未解決の急所があれば 2 に戻る。
7. **lead に `[grill-done]` + 決定事項サマリ（分割方針・境界条件・設計の急所）を報告し、実装フェーズの承認を待つ。** ここを飛ばして Driver を spawn しない。

grill 結果（決定事項・境界条件・設計の急所）は実装フェーズの起点にそのまま使う（同一 context なので引き継ぎ不要）。

ユーザーが明示した設計仕様から外れる提案は、既存の承認範囲を確認し、必要な判断だけを lead 経由でユーザーに確認する。

### 1. 開始

grill で固めた設計をもとに、Navigator が作業範囲に適用するスキルと検証方法を確認して実装に入る。

### 2. 次の 1 手 → Driver を spawn

Navigator は「次の 1 手」を具体化したら、**Driver subAgent を 1 体 spawn**してその diff を渡す。1 手 = 1 spawn。複数手順を 1 spawn にまとめない（実装ループの作業単位は 1 手 = 1 往復）。

**前提条件**: 最初の Driver spawn は **grill ゲート（step 0）通過後にのみ**行う。grill 未完了なら、どれだけ設計方針が固まって見えても Driver を spawn しない。

Driver に渡すもの: 対象ファイル / 対象関数・位置 / 変更内容 / 残すべき処理・触らない処理 / 中間状態の注意。

Driver は Read で挿入位置を確認し、Edit/Write で diff をそのまま反映し、1〜3 行で報告して終了する（stateless なので毎回新個体でよい）。

### 3. Driver の報告を直接受ける

Driver の報告は **Navigator が直接受け取る**（lead を経由しない＝直接 mailbox）。報告に「次の手の前提が崩れる事実」（中間状態でコンパイル不能・未定義参照が残る・副作用の波及・「レイアウト計算側だけ変更済みで PDF 描画側は未変更」等）が含まれていれば、Navigator はそれを設計判断に織り込む。Navigator は自分でコードに照合できるので、確認質問に対しても推測で OK を返さず Read/テストで裏を取る。

Driver が指示を**適用せず保留**した（`[review-block]`）場合、Navigator は理由・質問を読んで次の 1 手を起草し直す。質問を丸めず、推測で押し切らない。

### 4. Navigator が検証する

Navigator は自分の Bash で `rg` / `uv run --locked --extra dev python -m pytest` / 旧経路 grep / 差分整理を回す。手元 E2E が必要なものは「何を見れば PASS か」を具体化して lead 経由で Human に渡す。

## lead の残務（薄い）

Navigator が主導するので lead の仕事は限られる:

- **team セットアップ**と Navigator へのゴール受け渡し（slice ごとに要るスキルの invoke 指示を spawn prompt に含める）。
- **Human ⇄ Navigator の橋渡し**: owner 判断の質問を Human に提示し回答を返す／手元 E2E のバグ報告を Navigator に **verbatim** で渡す（仮説を採用して Driver を直接動かさない）。
- **最終ゲート**: 完了宣言の前に「テストを実際に回したか」を締める（下記「Medium 以上なし」節）。
- **完了報告**を Human に短く並べる。
- **respawn / cleanup**: Navigator から context 逼迫の合図が来たら新個体に引き継ぐ。team を畳む。

lead が橋渡しで要約・改変するとき、作業判断に関わる情報は削らない（Human への最終報告での重複ログ圧縮のみ可）。

## 規律（Teams でも効く — 役割に依らない教訓）

通信が直接 mailbox になっても、次の品質規律は変わらず効く。旧設計では lead がリレー時に守らせていたが、**Teams 版では Navigator が自分の Bash/Read で enforce する**。

### Driver の「変更不要 / 既に最終形 / skip した」は事実申告ではなく仮説

Driver が「既に適用済み」「現状が最終形なので変更不要」「差異なしで skip」と返したら、Navigator は **Read で実体を当て、テストで裏を取る**まで確定にしない。「進めて大丈夫ですか？」という確認質問にも、Navigator は推測の GO/NO-GO を返さずコードに照合してから答える。

### 「Medium 以上なし」を確定する前に必ずテストを回す

レビュー＆修正ループで Navigator が**コードレビューだけで「Medium 以上なし」と結論しても、それを最終確定にしない**。コードレビューは静的観察で、落ちるテストを見落とす。

- Navigator が「Medium 以上なし」と返したら、**完了宣言の前に必ず該当範囲の `uv run --locked --extra dev python -m pytest` を回す**（Navigator が自分の Bash で。teammate なので lead 代行は不要）。回す対象は Navigator が起草した検証コマンド、無ければ変更ファイルに対応するユニット/統合テスト。
- テストが赤なら raw 出力を見て「実装バグ（Medium 以上）か / stale テスト（実装は正・テストが誤り）か」を切り分け、次の 1 手を起草する。
- 「コミットメッセージに GREEN と書いてある」「前任が健全と言った」だけで緑とみなさない。実際に回す。
- **lead は最終ゲートとして**、完了報告を受ける前に「Navigator は実際にテストを回したか」を確認する。回した形跡がなければ回させる。

### レビューのセカンドオピニオンは read-only `Explore` で spawn する

独立セカンドオピニオン（codex 代替の Claude レビュー）は **必ず read-only agent type（`Explore`）**で spawn する。`general-purpose` は Bash/Edit/Write を持ち、レビュー中に作業ツリーを触りうる。

Codex によるセカンドオピニオンが usage limit / 未インストールで回せないときは、`Explore` read-only レビューがそのまま正規の代替になり、レビュー＆修正ループは完結させてよい（codex 不在を理由にループを止めない）。完了報告に「codex は usage limit のため Explore で代替」と明記する。必要に応じて観点別にレビューを分担する。

### 破壊的 git を subagent に絶対やらせない

Driver / Explore を spawn する prompt に必ず「`git checkout` / `git reset` / `git restore` / `git stash` 等、作業ツリーを巻き戻すコマンドは実行禁止」と明記する。検証は pytest / Read / Grep / `git status` まで。

subagent はワークツリー全体の文脈を持たないので、`git checkout <file>` でも自分が作っていない未コミット変更を道連れにする（`git reset --hard` だけの問題ではない）。一時 probe は別 throwaway ファイルに書くか Read だけで観測し、消すときも名指しの Edit で消す。長い実装で未コミット差分が積み上がったら、Navigator が節目で WIP コミットして保護する。

### 反幻覚（Driver 指示の前に必ず実在確認）

Navigator は Driver に渡す diff の **ファイルパス / 関数名 / 型名 / フィールド名 / variant 名 / 行番号**を、指示前に必ず `Read` / `rg` で実在確認する。推測で書くと Driver が `[review-block]` を返して 1 往復ロスする。

### `[review-block]` の扱い

Driver が指示を**適用せず保留**した（`[review-block]`）場合、その理由・質問は Navigator が直接受け取り、丸めず・推測で押し切らず、次の 1 手を起草し直す。質問数を変えない。

## バグ報告の扱い

手元 E2E 中にバグが出たら、Human → lead → Navigator へ症状・仮説・再現情報を**そのまま**渡す。lead が仮説を採用して Driver を直接動かさない。Navigator がコードで照合し、1 件だけ修正指示を Driver に出す。

良いバグ報告（このまま Navigator に渡せる粒度）:

```text
生成 PDF で数式の右端が想定したグリッド線からずれています。
同じ入力の数値表示は一致しています。

仮説:
配置計算と PDF 描画で座標変換が重複している可能性があります。

確認済みの事実:
1. 再現入力と生成 PDF を保存した
2. 配置結果の座標を記録した
3. PDF 上の実際の位置と比較した

※ 報告例。実際の調査では対象ファイル・関数名と計測値を添える。

```

## 中間状態の扱い

長い実装では、一時的にビルド不能になる順序を通ることがあります。Driver からその警告が来たら、Navigator はそれを設計判断に織り込み、想定内なら次の 1 手を続ける（Navigator は自分でコードに照合できるので、中間状態の安全性を Read で確かめられる）。

## フォーマットと差分整理

format / restore の判断は Navigator が行う。

教訓:

- 全体整形は無関係ファイルを巻き込むことがあるため、担当範囲に限定する
- 検証で PDF や fixture が生成される場合は、実装差分と区別して `git status` を確認する
- `.claude/docs/research/A4.pdf` と `tests/output/*.pdf` の既存参照ファイルは保持する

Navigator は実装差分・検証副作用・無関係差分を分けて扱い、restore 対象を Human に明示する（破壊的 git は使わず名指しの Edit / 限定 restore で）。

## 完了報告（lead → Human）

完了時、lead は Navigator の検証結果を事実として短く並べる。

```text
完了です。

- pytest: 実行コマンドと結果
- PDF 検証: 対象出力・確認内容・結果（レイアウト変更時）
- 差分: src/gridlayoutpdf/ と tests/ の実際の変更ファイル
- 検証生成物: 保存先と既存参照ファイルを保持したこと
```

## respawn / cleanup

- Navigator から context 逼迫の合図（`[respawn-request: navigator]` + 引き継ぎ block）が来たら、新しい Navigator teammate を spawn し、引き継ぎを**書き換えず・追加せず・要約せず**そのまま渡す。整形は混入であり、Navigator の判断材料を変えてしまう。「引き継ぎを整えてあげたほうが親切」という気持ちが出たら踏みとどまる。
- Driver は stateless なので respawn の概念がない（毎手 spawn し直す）。
- 作業が終わったら team を畳む（cleanup）。

## fallback: Agent Teams が使えない harness

teammate を spawn できない harness（Agent Teams が無効・`/resume` 後に teammate が消えた・split-pane 不可な端末等）では、**Navigator も subAgent に落とす旧リレー設計**で回す。この場合に限り次の workaround が要る:

- **SendMessage 不可 → 毎ターン Navigator を新個体 spawn**。lead が prompt に「直近 commit sha / baseline 数字（passed/failed/errors）/ 確定済み仕様 / 直前の Driver 報告 verbatim」を**外部記憶**として貼り続ける。Navigator の最初の仕事に「Read で SUT 直前状態を確認してから次手を起草」を含める。各ステップを「1 ファイル / 1 関数 / 1 論理修正」まで小さく保てば、新個体でも 15-20+ ターン破綻せず回せる。
- **subAgent から Bash が剥がれる → lead が pytest を代行**し、合否を判定せず raw 出力（「3 passed」「`WinError 10038` で 4 failed」等の事実だけ）を次の Navigator に verbatim で渡す。解釈・次手は Navigator。RED→GREEN は「lead が RED 確認 → Driver が実装 Write → lead が GREEN 確認 → 次 Navigator が解釈」で回す。
- **grill も lead が `grill-with-docs` を代行**し、コードで答えられる論点は Navigator subAgent に Read/Grep で当てさせ（`[owner-decision]` prefix で owner 判断だけ返させる）、owner 判断だけ Human に上げる。

fallback でも「1 論点ずつ・1 手ずつ・batch しない」の規律は崩さない。これは harness の通信能力に依存しない作業単位の話で、Teams でも subAgent でも同じ。**この harness では Navigator/Driver が最初の 1-2 ターンで「Bash を持っていない」「SendMessage が無い」と返して判明する**ので、判明したら即この運用に切り替える。

## 合言葉

頭脳は永続 teammate、手は使い捨て subAgent。  
Navigator には判断と検証を、Driver には 1 手を、Human には事実を渡す。  
lead は運ぶより、Navigator に任せる。混ぜない、削らない、急がせない。
