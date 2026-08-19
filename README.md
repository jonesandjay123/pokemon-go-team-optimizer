# Pokémon GO PvP 隊伍最佳化器

一個實驗性的 Pokémon GO PvP 隊伍最佳化引擎，目標是從排名資料、屬性相剋、招式配置與對戰模擬中，找出 Great League、Ultra League 與 Master League 裡穩定且互補的三隻寶可夢組合。

> [!IMPORTANT]
> 專案目前只有初始鷹架，尚未產出可用於實戰的隊伍推薦。第一個可驗證版本會先完成純屬性模型，再逐步納入招式與對戰模擬。

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
│   ├── parsing/                    # 排名與 Game Master 資料解析
│   ├── scoring/                    # 隊伍評分函式
│   ├── battle/                     # Matchup 與對戰模擬整合
│   ├── leagues.py                  # 聯盟定義
│   └── optimize.py                 # 最佳化流程入口
└── tests/
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

確認目前的聯盟設定：

```bash
pogo-team-optimizer --league great --top 50
```

目前 CLI 只會顯示即將執行的聯盟與候選池大小，作為專案鷹架的 smoke test；資料解析、評分與排名輸出會在 V1 實作。

## 資料來源

預計使用下列資料來源：

- [PvPoke 排名](https://pvpoke.com/rankings/)：候選寶可夢、排名與建議招式
- [PvPoke Game Master](https://github.com/pvpoke/pvpoke/blob/master/src/data/gamemaster.json)：寶可夢與招式資料
- Pokémon GO 的 18 種屬性相剋關係

下載的排名 CSV 屬於可更新的輸入資料，因此不提交到 Git。請依聯盟放入對應的 `data/<league>/` 目錄；未來會提供明確的檔名規則與匯入指令。

## Roadmap

- [ ] V1：修正 PvPoke CSV 欄位、取前 N 名、建立屬性矩陣、窮舉三人組並輸出 Top teams
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
