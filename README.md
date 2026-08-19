# Pokémon GO PvP 隊伍最佳化器

一個實驗性的 Pokémon GO PvP 隊伍最佳化引擎，目標是從排名資料、屬性相剋、招式配置與對戰模擬中，找出 Great League、Ultra League 與 Master League 裡穩定且互補的三隻寶可夢組合。

> [!WARNING]
> V1 只評估 PvPoke 排名與寶可夢的**防守屬性**，尚未考慮實際招式屬性、傷害、能量、對戰模擬、盾數或隊伍出場順序。輸出適合拿來檢查評分模型，不應直接視為實戰勝率排名。

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

預計使用下列資料來源：

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

## Roadmap

- [x] V1：修正 PvPokeTW CSV 欄位、取前 N 名、建立屬性矩陣、窮舉三人組並輸出 Top teams
- [ ] V2：把實際招式屬性與進攻 coverage 納入評分
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
