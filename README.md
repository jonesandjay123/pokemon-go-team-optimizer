# Pokémon GO PvP 隊伍最佳化器

一個實驗性的 Pokémon GO PvP 隊伍最佳化引擎，目標是從排名資料、屬性相剋、招式配置與對戰模擬中，找出 Great League、Ultra League 與 Master League 裡穩定且互補的三隻寶可夢組合。

> [!WARNING]
> V2 已加入實際招式屬性與進攻 coverage，但仍不是戰鬥模擬器；尚未計算傷害量、出招時間、盾、CMP、IV 或隊伍順序。輸出適合比較透明的隊伍結構，不應直接視為實戰勝率排名。

## 為什麼做這個專案

直接選排名最高的三隻寶可夢，不一定會得到最穩定的隊伍。這個專案會窮舉候選池中的所有三人組，並用透明、可重現的評分方式衡量：

- 隊伍是否存在共同弱點或雙重弱點
- 成員能否互相補足防守與進攻屬性
- 面對主流環境時的平均表現與最差情境
- Lead、Safe Swap、Closer 等角色是否合理
- 0、1、2 盾情境下的穩定度

以前 50 名為例，三隻一組只有 `C(50, 3) = 19,600` 種組合，可以直接完整搜尋，不需要用黑箱模型猜答案。

## 專案結構

```text
pokemon-go-team-optimizer/
├── config/                         # 各聯盟的 CP 上限與資料設定
│   ├── great_league.toml
│   ├── ultra_league.toml
│   └── master_league.toml
├── data/                           # 本機輸入資料，不提交大型 CSV
│   ├── great_league/
│   ├── ultra_league/
│   └── master_league/
├── results/                        # 最佳化器輸出的分析結果
│   ├── great_league/
│   ├── ultra_league/
│   └── master_league/
├── src/pogo_team_optimizer/
│   ├── parsing/                    # PvPoke／PvPokeTW 排名資料解析
│   ├── scoring/                    # 可拆解的 V1 評分函式
│   ├── battle/                     # Matchup 與對戰模擬整合
│   ├── leagues.py                  # 聯盟定義
│   ├── models.py                   # 標準化內部資料模型
│   ├── type_chart.py               # 完整 18 屬性倍率
│   ├── search.py                   # 三人組窮舉與排序
│   ├── output.py                   # 結果 CSV 輸出
│   ├── sensitivity.py              # V1.1 五模型比較與穩定度分析
│   └── optimize.py                 # 最佳化流程入口
└── tests/
    └── fixtures/                   # 可提交的小型壞 header 測試資料
```

同一套引擎會透過聯盟設定執行，不會為三個聯盟複製三套程式。

## 開發環境

- Python 3.11 以上
- 專案管理採用標準 `pyproject.toml`
- 初始測試只使用 Python 標準函式庫

建立開發環境並執行測試：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

把排名 CSV 放到指定位置後執行：

```bash
pogo-team-optimizer --league great --top 50
```

CLI 會讀取前 50 名、窮舉 `19,600` 個不分順序的三人組，在終端顯示 Top 10，並把 Top 50 寫入 `results/great_league/top_teams.csv`。

開發或測試時也可以覆寫路徑：

```bash
pogo-team-optimizer \
  --league great \
  --top 6 \
  --input tests/fixtures/pvpoketw_rankings_malformed_cp.csv \
  --output /tmp/top_teams.csv
```

## V2：招式感知的進攻 Coverage

V2 保留全部 V1／V1.1 指令與公式，另外用獨立的 `--scoring v2` 模型加入：

- 進攻招式屬性的種類數
- 對 18 種單屬性目標的效果絕佳／普通／抵抗分類
- 快速招式與蓄力招式各自的效果絕佳 coverage
- 每位隊員是否至少有一個 STAB 招式
- 隊友招式屬性的 pairwise Jaccard 重複度
- 防守分數與進攻 coverage 的平衡度

每一項都會個別寫入 CSV；總分只是這些公開元件的固定加權，不會執行完整 PvPoke 對戰模擬。

先下載並快取 PvPoke 的 GameMaster 與排名 JSON（`data/cache/` 已由 Git 排除）：

```bash
python -m pogo_team_optimizer.data_sources --league great
```

執行真實 Great League Top 50：

```bash
pogo-team-optimizer \
  --league great \
  --top 50 \
  --input data/cache/rankings-1500.json \
  --scoring v2 \
  --diagnostics
```

`--diagnostics` 會另外寫出 `v2_diagnostics.json`，包含 V2 Top 10、和五個 V1/V1.1 模型的重疊、寶可夢頻率變化、Steel/Flying 出現率、coverage 分布，以及成員最佳隊伍名次升降。

GameMaster 是招式 ID、英文顯示名稱、屬性、快速／蓄力分類、power、energy、energy gain 與 buff/debuff 的權威來源。資料匯入模組與最佳化器分離。若使用中文排名 CSV，可用 `--aliases aliases.json` 提供可驗證的本地化名稱對照；無法解析或招式不屬於該形態時會逐列報告，不會靜默刪除。

### 理論模式與庫存模式

理論模式使用 PvPoke 的建議 moveset。庫存模式則把**完整排名池**先和使用者實際擁有的個體取交集，再枚舉這個縮小後的可行組合；因此即使可用寶可夢在第 50 名之後，也不會因 `--top 50` 而停止尋找。`--top` 只界定用來比較的理論候選池。

```bash
pogo-team-optimizer \
  --league great \
  --top 50 \
  --input data/cache/rankings-1500.json \
  --inventory data/inventory/great_league.csv \
  --scoring v2 \
  --results 10
```

庫存模式會用 CSV 中的**實際招式**評分，不會假設擁有該寶可夢就等於擁有 PvPoke 建議招式。它會分別回報 battle-ready、招式不同、缺少招式、形態不符與不在排名中；一個只解鎖第一蓄力招式的個體也可評分。

庫存 CSV 每一列代表一個實際個體：

```csv
instance_id,pokemon_name,form,shadow,cp,fast_move,charged_move_1,charged_move_2,notes
my-001,Bulbasaur,,false,1498,Vine Whip,Seed Bomb,,only one charged move
```

可複製 [data/inventory/great_league.example.csv](data/inventory/great_league.example.csv) 開始填寫。請將真實檔案命名為 `great_league.csv`；該檔會被 Git 忽略，避免提交個人庫存。

### V2 限制

目前 coverage 只回答「招式屬性最多能打到何種倍率」，不考慮招式傷害、能量效率、出招節奏、盾、CMP、Lead／Safe Swap／Closer、TM 經濟、星塵糖果成本或 IV-specific matchup。同樣具有 coverage 的兩個招式不代表實戰價值相等，這些屬於後續 battle-simulation 里程碑。

## V2.1：庫存正確性強化

V2.1 不改寫 V1／V1.1／V2，而是在庫存模式補上兩項正確性保證：

1. **GBL species clause**：同一圖鑑 species 不能同隊。合法性使用 GameMaster 的 `dex` 作 canonical key，因此兩個不同個體、Normal + Shadow，以及同圖鑑的其他 form 都不能同時進隊。理論與庫存搜尋使用同一規則。
2. **實際 moveset 品質修正**：庫存實際招式仍完整參與 V2 coverage，並額外衡量快速招式 DPT、EPT、出招回應性，以及蓄力招式 power、energy、DPE、費用與 buff/debuff utility。

Moveset quality 的公開公式為：

```text
fast_quality = 0.40 × normalized_DPT
             + 0.50 × normalized_EPT
             + 0.10 × timing_responsiveness

charged_quality = 0.20 × normalized_power
                + 0.55 × normalized_DPE
                + 0.25 × affordability
                + 0.10 × signed_buff_utility

moveset_quality = 0.40 × fast_quality
                + 0.45 × mean(charged_quality)
                + 0.15 × charged_slot_completeness
```

所有 normalization 都是固定且不依 species 調整：`DPT / 5`、`EPT / 5`、`power / 150`、`DPE / 2.5` 會 clamp 到 `0..1`；`timing_responsiveness = 1 / turns`；`affordability = clamp((100 - energy) / 65)`。Buff utility 依 self buff 或 opponent debuff 的方向、stage 總和與觸發機率計算並 clamp 到 `-1..1`，因此自我 debuff 也會反映為成本。

PvPoke ranking quality 原本就是以推薦 moveset 算出的整體結果，因此 V2.1 **不再把絕對招式品質重複加分**。它只套用以下相對修正：

```text
move_quality_adjustment = 20 × (actual_quality - recommended_quality)
V2.1_total = V2_total + move_quality_adjustment
```

理論候選的 actual 等於 recommended，所以分數不變；庫存實際招式較差時會透明扣分。只有一個蓄力招式仍然合法，但 slot completeness 為 `0.5`，且 coverage 也只使用該招式。

```bash
pogo-team-optimizer \
  --league great \
  --top 50 \
  --input data/cache/rankings-1500.json \
  --inventory data/inventory/great_league.csv \
  --scoring v2.1 \
  --results 10
```

庫存執行會產生 `inventory_diagnostics.csv`，每個個體包含：

- 實際與 PvPoke 推薦招式
- `exact`／`partial`／`different` 比對
- actual／recommended move-quality 與 delta
- 是否缺少第二蓄力招式
- battle-ready、合法但招式不同、招式無效或 form 不符等狀態

建立可直接填寫的繁體中文庫存範本：

```bash
python -m pogo_team_optimizer.inventory_template
```

預設輸出 `data/inventory/great_league.csv`，不會覆寫既有檔案；需要覆寫時必須明確加 `--force`。每列是一隻實際個體，目前不要求 IV。

## V2.2：Battle Readiness／強化差距

V2.2 在 V2.1 上增加獨立的庫存準備度分類，不改動 V1、V1.1、V2 理論排名或 V2.1 move-quality：

- `ready-now`：CP 已達 target CP 的設定比例，今晚可列入即戰隊伍。
- `power-up-needed`：species、form 與招式都合法，但 CP 仍明顯低於目標；不會被當成未擁有。
- `ineligible-over-cap`：CP 超過聯盟上限，不能參賽。
- `invalid/missing-move`：缺少必要招式或招式不屬於該 form。
- `missing-species/form`：無法可靠解析或排名中沒有正確 form。

Target CP 優先使用排名輸入中的 optimized CP。PvPoke machine-readable ranking JSON 沒有該欄時，會明確使用聯盟 CP cap 作 `league-cap-fallback`。預設 ready threshold 集中定義為 `0.95`，即：

```text
readiness_ratio = actual_cp / target_cp
ready-now       = readiness_ratio >= 0.95
cp_gap          = max(0, target_cp - actual_cp)
```

`95%` 容許少量 CP／IV build 差異，但可把 CP 900／1500 這類明顯尚未強化完成的個體分開。可用 CLI 集中覆寫，不會散落 hard-code：

```bash
pogo-team-optimizer \
  --league great \
  --top 50 \
  --input data/cache/rankings-1500.json \
  --inventory data/inventory/great_league.csv \
  --scoring v2.2 \
  --ready-threshold 0.95 \
  --results 10
```

庫存結果會清楚分成三組：

- `top_teams_v2_2_ready.csv`：三名成員全部為 ready-now 的目前可玩隊伍。
- `top_teams_v2_2_power_up.csv`：至少一名 owned member 尚需強化的潛力隊伍，附 actual CP、target CP 與 gap。
- `top_teams_v2_2_theoretical.csv`：不受庫存限制的理論隊伍。

`inventory_diagnostics.csv` 也會對每個個體增加 actual CP、target CP、CP gap、readiness ratio、readiness status 與 target source，同時保留 V2.1 的 actual/recommended moves、move-quality delta 與第二蓄力招狀態。

CP ratio **不是**精確戰力模型，也不是 IV-specific battle simulation。它只用來判斷「已接近預定 build」或「還需要強化」；實際 IV、Stardust／糖果成本、盾、對戰模擬與出場順序仍屬未來里程碑。

## V2.2a：Inventory Scout Mode

Scout Mode 讓尚未逐隻抄完招式的真實庫存先用於候選探索，不會改動任何 V1～V2.2 評分或 Ready Now 規則。

庫存招式狀態分為：

- `moves-known`：fast move 與 charged move 1 已填寫，使用實際招式嚴格驗證與評分。
- `moves-unknown`：招式尚未檢查；只有 Scout Mode 可以暫用 PvPoke recommended moveset。
- `moves-invalid`：已填入的招式名稱無法解析、不是正確類別，或不屬於該 form；Scout 不會替換這種錯誤。

CSV 可增加選填欄位 `move_state`，值為 `known`、`unknown` 或留白。留白時，fast move 或 charged move 1 空白會推斷為 unknown；charged move 2 單獨留白仍表示「已知只有一個蓄力招式」，維持 V2.1 的合法語意。

```bash
pogo-team-optimizer \
  --league great \
  --top 50 \
  --input data/cache/rankings-1500.json \
  --inventory data/inventory/great_league.csv \
  --scoring v2.2 \
  --scout \
  --results 15
```

Scout 使用推薦招式建立的候選與隊伍都會明確標記 `PROVISIONAL`／`assumed-pvpoke-recommended`，不會寫回庫存，也永遠不會混入 Ready Now。填入實際招式後，下次執行會自動回到 V2.1/V2.2 的 actual-move scoring。

額外輸出：

- `inventory_scout_teams.csv`：至少含一個 moves-unknown 個體的 provisional teams，分為 `needs-move-check` 與 `power-up+move-check`。
- `inventory_move_check_priority.csv`：最值得先打開 Pokémon GO 檢查招式的個體排序。

Move-inspection priority 使用固定、可拆解公式，沒有 species-specific bonus：

```text
priority = 0.40 × frequency_in_top_50_provisional_teams
         + 0.30 × best_provisional_team_placement
         + 0.20 × normalized_PvPoke_source_rank
         + 0.10 × CP_readiness
```

Priority 報表包含 instance、species/form/Shadow、CP、PvPoke source rank、readiness、Top provisional team 出現次數、最佳 provisional score／rank，以及 actual moves 是否已知。用途只是在回答「下一批先檢查哪 10～15 隻」，provisional score 不是實際 moveset 的承諾。

## V1 資料管線

```text
PvPoke／PvPokeTW CSV
        ↓ parsing（包含明確的 CP header 修復）
標準化 RankingEntry
        ↓ top-N selection
不分順序的三人組 combinations
        ↓ 18 屬性防守矩陣 + V1 scoring
固定 tie-break 的完整排序
        ↓
終端 Top 10 + top_teams.csv
```

解析器與最佳化器彼此分離。後續即使改用 PvPoke JSON，搜尋與評分程式也不需要知道原始資料格式。

## 資料來源

使用下列資料來源：

- [PvPoke 排名](https://pvpoke.com/rankings/)：候選寶可夢、排名與建議招式
- [PvPoke Game Master](https://github.com/pvpoke/pvpoke/blob/master/src/data/gamemaster.json)：寶可夢與招式資料
- Pokémon GO 的 18 種屬性相剋關係

下載的完整排名 CSV 屬於可更新的本機輸入，因此不提交到 Git。V1 驗證用的 Great League 檔案必須放在：

```text
data/great_league/cp1500_all_overall_rankings.csv
```

若檔案不存在或資料筆數少於 `--top`，CLI 會指出預期位置與錯誤原因。目前不會自動操作 PvPokeTW 網頁或下載資料。

### PvPokeTW CP header 修復

已知 PvPokeTW CSV 的 header 在「等級」後漏掉 `CP`，但每一筆資料仍有輸出 CP，導致後方欄位整體錯位。解析器只會在以下條件**全部成立**時插入 `CP` header：

1. 每筆資料剛好多出一欄。
2. header 內有「等級」與「一般招式」。
3. 「一般招式」緊接在「等級」後。
4. header 尚未包含 `CP`。

其他欄數異常不會被猜測或靜默修正，而會直接報錯。`tests/fixtures/` 保留一份六筆小型測試資料，完整原始 CSV 仍由 `.gitignore` 排除。

## V1 評分公式

所有原始元件都先正規化到 `0..1`，再套用集中於 `ScoreWeights` 的固定權重：

```text
total_score =
    35 × ranking_quality
  + 25 × resistance_coverage
  + 25 × teammate_weakness_coverage
  + 15 × defensive_diversity
  - 20 × shared_weakness_penalty
  - 15 × severe_weakness_penalty
```

各元件定義如下：

- `ranking_quality`：三隻的 PvPoke score 平均值除以 100。
- `resistance_coverage`：18 種攻擊屬性中，至少有一名隊員能抵抗的比例。
- `teammate_weakness_coverage`：所有個別弱點暴露中，至少有另一名隊友能抵抗該屬性的比例。
- `defensive_diversity`：隊員對每種攻擊屬性的「弱／普通／抗」反應多樣性平均值。
- `shared_weakness_penalty`：18 種攻擊屬性中，同時打到至少兩名隊員弱點的比例。
- `severe_weakness_penalty`：全隊共同弱點率與個別雙重弱點暴露率的平均。

屬性倍率與 PvPoke 一致：效果絕佳 `1.6`、抗性 `0.625`、主系列免疫在 Pokémon GO 中為 `0.390625`；雙屬性會將兩個倍率相乘。

權重目前是刻意固定的第一版基準。若結果不符合直覺，應先記錄原因，再由人工決定是否建立 V1.1；程式不會為了產生「看起來合理」的答案自動調權重。

## 輸出格式

`top_teams.csv` 使用 UTF-8 BOM，方便直接以試算表開啟，包含：

- 隊伍總排名與三名成員
- `total_score`
- 六個未加權的正規化評分元件
- 共同弱點與受影響隊員數
- 至少有一名隊員能抵抗的屬性摘要

相同輸入會使用成員原始 rank 與名稱作為 tie-break，確保每次輸出順序一致。

## V1.1 評分敏感度實驗

真實 Great League V1 結果的 Top 50 全部含有 Steel 與 Flying，而且 teammate coverage 全部達到 100%。V1.1 的目的不是調出「看起來合理」的隊伍，而是用固定、可重現的實驗判斷：這種結構究竟來自特定評分公式，還是純防守屬性最佳化本身就會導向相近答案。

### Baseline 保證

`baseline` 完整保留 V1 的公式、權重與 tie-break。以下兩個指令使用相同模型：

```bash
pogo-team-optimizer --league great --top 50
pogo-team-optimizer --league great --top 50 --scoring baseline
```

V1.1 的 regression test 會固定檢查 baseline 結果；實驗變體不會覆寫或暗中調整 baseline。

### 實驗變體

#### `diminishing-resistance`

將原始 resistance coverage `c`（抵抗屬性數除以 18）轉換為：

```text
transformed_resistance = c ^ exponent
exponent = 0.5
```

平方根是單調且正規化的凹函數。早期 coverage 仍有價值，但從 16 → 17 → 18 的邊際差距會縮小。`exponent` 是 `ScoringConfig` 的顯式參數，不包含針對特定隊伍的例外。

#### `exposure-aware`

baseline 只要有一名隊友抵抗，就會把每個 weakness exposure 視為完整 cover。實驗模型改為對每種攻擊屬性計算：

```text
type_coverage = min(1, (resistant / (vulnerable + resistant)) / (2 / 3))
team_coverage = 依 vulnerable 數加權的 type_coverage 平均
```

`2/3` 是三人隊伍在至少一名成員有弱點時，抵抗成員所能占的最大比例。代表性結果：

- weak／neutral／resist：`0.75`
- weak／weak／resist：`0.50`
- weak／resist／resist：`1.00`
- weak／weak／neutral：`0.00`

因此兩名隊員同時有弱點、只有一人抵抗時，不再和單一弱點得到相同分數。

#### `combined`

同時使用平方根 resistance coverage 與 exposure-aware teammate coverage，其他公式與權重不變。

#### `severe-penalty`

只把 severe weakness penalty 權重從 baseline 的 `15` 提高為 `45`（固定 3 倍），其餘 coverage 邏輯不變。這個數值在執行實驗前即固定，不會依 Top 10 結果調整。

### 執行單一模型

```bash
pogo-team-optimizer --league great --top 50 --scoring diminishing-resistance
pogo-team-optimizer --league great --top 50 --scoring exposure-aware
pogo-team-optimizer --league great --top 50 --scoring combined
pogo-team-optimizer --league great --top 50 --scoring severe-penalty
```

baseline 維持輸出 `top_teams.csv`；實驗模型預設輸出 `top_teams_<scoring>.csv`。

### 執行完整比較

```bash
pogo-team-optimizer --league great --top 50 --compare-scoring
```

比較流程會讓五個模型各自評估同一批 19,600 個 unordered teams，並在 `results/great_league/` 產生：

- `top_teams_<scoring>.csv`：每個模型的 Top 50
- `v1_1_comparison.csv`：五模型的結構與穩定度摘要
- `v1_1_summary.json`：Top 10、個別／合併暗影頻率、coverage 分布、Jaccard、頻率變化與 ranking movement

所有結果檔都由 `.gitignore` 排除。V1.1 模型只是敏感度實驗，**不代表真實勝率更高**，也沒有加入招式 coverage、傷害、能量、盾或戰鬥模擬。

## Roadmap

- [x] V1：修正 PvPokeTW CSV 欄位、取前 N 名、建立屬性矩陣、窮舉三人組並輸出 Top teams
- [x] V1.1：比較五種固定防守評分模型的敏感度、結構偏誤與 ranking stability
- [x] V2：把實際招式屬性、進攻 coverage 與庫存限制納入評分
- [x] V2.1：實施 GBL species clause、實際 moveset 品質修正與庫存診斷
- [x] V2.2：區分 ready-now 與 power-up-needed，輸出 CP 強化差距
- [x] V2.2a：以 provisional recommended moves 探索未完成招式盤點的庫存
- [ ] V3：建立或匯入 Pokémon 之間的 matchup matrix
- [ ] V4：以平均值、最差情境與變異程度衡量隊伍 robustness
- [ ] V5：分析 Lead、Safe Swap、Closer 的排列方式
- [ ] V6：比較 0、1、2 盾情境並提供缺角替代方案

## 設計原則

- **可解釋**：每個分數都要能拆解，避免只輸出無法驗證的「最佳隊伍」。
- **可重現**：輸入資料、設定與結果要能被版本化或追溯。
- **聯盟無關**：Great、Ultra、Master League 共用核心演算法。
- **資料與程式分離**：平衡調整後只需更新資料，不應重寫演算法。
- **先驗證再加深**：先完成透明的 V1，再加入招式與戰鬥模擬。

## 授權

本專案使用 [MIT License](LICENSE)。Pokémon、Pokémon GO 與相關名稱和素材的權利屬於其各自權利人；本專案與 Niantic、The Pokémon Company 或 PvPoke 無官方關聯。
