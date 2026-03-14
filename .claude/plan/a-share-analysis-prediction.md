# Implementation Plan: A股超短线复盘与情绪分析系统

## Task Type
- [x] Backend (Data pipeline, sentiment engine, API)
- [x] Frontend (Dashboard visualization)
- [x] Fullstack (Parallel development)

---

## 1. Problem Analysis

### 超短线的核心逻辑

A股超短线交易（持仓1-3天）的本质不是预测价格，而是**读懂市场情绪并跟随合力**。

与中长线完全不同：
- 基本面 → **无关** (1-3天内基本面不会变化)
- 传统技术指标 (MA/MACD/RSI) → **滞后无效** (信号出来行情已走完)
- 北向资金/融资融券 → **关联太弱** (日级别数据对超短线粒度不够)

超短线真正的"指标"是：
1. **情绪周期** — 市场现在处于什么阶段？该进攻还是防守？
2. **连板生态** — 最高板多少？晋级率如何？赚钱效应强不强？
3. **题材主线** — 资金在炒什么？持续性如何？龙头是谁？
4. **龙虎榜/游资** — 知名游资在买什么？卖什么？
5. **涨停质量** — 封单强不强？炸板多不多？几点封的板？

### System Goal

建一个**超短线复盘助手**，帮助散户：
- 每日自动复盘市场情绪状态
- 量化连板生态和赚钱效应
- 追踪题材主线的发酵/退潮
- 分析龙虎榜游资动向
- 评估涨停板质量

**注意：这是分析辅助工具，不是自动交易系统。**

---

## 2. Technical Solution

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  Frontend (Vue 3 + ECharts)                   │
│  情绪仪表盘 │ 连板生态 │ 题材追踪 │ 龙虎榜 │ 涨停复盘       │
└─────────────────────────┬────────────────────────────────────┘
                          │ REST API
┌─────────────────────────┴────────────────────────────────────┐
│                     Backend (FastAPI)                          │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ Data         │  │ Emotion      │  │ Theme            │    │
│  │ Collector    │  │ Cycle Engine │  │ Tracker          │    │
│  │ (AKShare)    │  │ (情绪周期)    │  │ (题材追踪)       │    │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘    │
│         │                 │                    │              │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌────────┴─────────┐   │
│  │ Limit-Up     │  │ Dragon-Tiger │  │ Daily            │   │
│  │ Analyzer     │  │ Analyzer     │  │ Recap            │   │
│  │ (涨停分析)    │  │ (龙虎榜分析)  │  │ Generator        │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │                 │                    │              │
│  ┌──────┴─────────────────┴────────────────────┴─────────┐   │
│  │                  SQLite Database                       │   │
│  └───────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Data Interface | **AKShare** | 免费、涵盖涨停池/龙虎榜/概念板块/行业板块 |
| Backend | **FastAPI** | Async、类型安全、自动API文档 |
| Database | **SQLite** (dev) → **PostgreSQL** (prod) | 轻量启动，后续可迁移 |
| ORM | **SQLModel** | Pydantic + SQLAlchemy 结合 |
| Frontend | **Vue 3 + Vite + ECharts** | 金融图表强项 (K线、热力图、仪表盘) |
| Scheduler | **APScheduler** | 盘后自动采集和复盘 |
| Config | **Pydantic Settings** | 类型安全的配置管理 |

**砍掉的依赖**（相比原计划）：
- ~~pandas-ta~~ (不需要67个技术指标)
- ~~XGBoost / PyTorch~~ (不需要ML预测模型)
- ~~transformers / FinBERT~~ (不需要NLP情绪分析)
- ~~Optuna~~ (不需要超参调优)
- ~~scikit-learn~~ (不需要ML)

---

## 3. 超短线数据模型

### 3.1 Core Data Framework (四维)

```
Dimension 1: 涨停生态 (Limit-Up Ecosystem)
├── 涨停股池 (当日涨停列表 + 封板时间 + 封单量)
├── 炸板股池 (封板失败列表)
├── 跌停股池 (当日跌停列表)
├── 昨日涨停表现 (昨日涨停今日表现 → 溢价率)
├── 连板梯队 (各高度板: 1板/2板/.../N板 数量)
└── 晋级率 (N板→N+1板 的成功比例)

Dimension 2: 情绪周期 (Sentiment Cycle)
├── 涨停家数 / 跌停家数 / 炸板家数
├── 涨跌比 (上涨家数 / 下跌家数)
├── 连板高度 (最高板, 代表市场风险偏好)
├── 昨日涨停溢价率 (次日高开/低开均值)
├── 封板成功率 (涨停 / (涨停+炸板))
├── 市场总成交额 (量能)
└── 情绪周期阶段 (冰点/修复/发酵/高潮/分歧/退潮)

Dimension 3: 题材主线 (Theme Tracking)
├── 概念板块涨幅排名
├── 板块内涨停家数
├── 板块持续天数 (连续几天有涨停)
├── 龙头股识别 (板块内最高连板 + 最大市值涨停)
├── 板块轮动方向 (新题材 vs 老题材延续)
└── 题材催化事件 (政策/新闻, 手动标注或简单关键词)

Dimension 4: 龙虎榜 (Dragon-Tiger List)
├── 上榜原因 (涨幅偏离/换手率/振幅)
├── 买入/卖出前5席位
├── 知名游资识别 (营业部 → 游资映射表)
├── 机构席位 vs 游资席位
├── 净买入排名
└── 游资动向追踪 (某游资近N日买入标的)
```

### 3.2 AKShare 接口映射

| 数据需求 | AKShare 函数 | 说明 |
|---------|-------------|------|
| 当日涨停股池 | `stock_zt_pool_em(date)` | 涨停列表+封单量+封板时间+连板数 |
| 昨日涨停表现 | `stock_zt_pool_previous_em(date)` | 昨日涨停今日开盘价/涨幅 |
| 强势股池 | `stock_zt_pool_strong_em(date)` | 连续多日强势股 |
| 炸板股池 | `stock_zt_pool_zbgc_em(date)` | 封板失败 |
| 跌停股池 | `stock_zt_pool_dtgc_em(date)` | 跌停列表 |
| 龙虎榜详情 | `stock_lhb_detail_em(...)` | 席位买卖明细 |
| 概念板块列表 | `stock_board_concept_name_em()` | 全部概念板块 |
| 概念板块行情 | `stock_board_concept_hist_em(...)` | 板块历史涨幅 |
| 概念板块成分 | `stock_board_concept_cons_em(...)` | 板块内个股 |
| 行业板块 | `stock_board_industry_name_em()` | 行业板块列表 |
| 市场总览 | `stock_zh_a_spot_em()` | 全A股实时行情(算涨跌比) |

### 3.3 Database Schema

```sql
-- ========== 涨停生态 ==========

-- 每日涨停快照
CREATE TABLE daily_limit_up (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date DATE NOT NULL,
    code VARCHAR(10) NOT NULL,
    name VARCHAR(20),
    close_price DECIMAL(10,2),         -- 收盘价(涨停价)
    change_pct DECIMAL(6,2),           -- 涨幅%
    turnover_rate DECIMAL(6,2),        -- 换手率%
    amount DECIMAL(18,2),              -- 成交额(元)
    circulating_mv DECIMAL(18,2),      -- 流通市值(元)
    seal_amount DECIMAL(18,2),         -- 封单金额(元)
    seal_ratio DECIMAL(6,2),           -- 封单金额/成交额
    first_seal_time VARCHAR(10),       -- 首次封板时间 HH:MM:SS
    last_seal_time VARCHAR(10),        -- 最终封板时间
    open_count INTEGER DEFAULT 0,      -- 打开涨停次数
    continuous_count INTEGER DEFAULT 1, -- 连板数
    concept VARCHAR(200),              -- 所属概念/题材
    UNIQUE(trade_date, code)
);

-- 每日炸板记录
CREATE TABLE daily_burst (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date DATE NOT NULL,
    code VARCHAR(10) NOT NULL,
    name VARCHAR(20),
    close_price DECIMAL(10,2),
    change_pct DECIMAL(6,2),
    turnover_rate DECIMAL(6,2),
    amount DECIMAL(18,2),
    first_seal_time VARCHAR(10),       -- 曾经封板时间
    burst_time VARCHAR(10),            -- 炸板时间
    UNIQUE(trade_date, code)
);

-- 每日跌停记录
CREATE TABLE daily_limit_down (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date DATE NOT NULL,
    code VARCHAR(10) NOT NULL,
    name VARCHAR(20),
    close_price DECIMAL(10,2),
    change_pct DECIMAL(6,2),
    amount DECIMAL(18,2),
    UNIQUE(trade_date, code)
);

-- ========== 情绪周期 ==========

-- 每日情绪快照 (每天一行，市场级别)
CREATE TABLE daily_emotion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date DATE NOT NULL UNIQUE,
    limit_up_count INTEGER,            -- 涨停家数(含ST)
    limit_up_count_real INTEGER,       -- 涨停家数(不含ST/新股)
    limit_down_count INTEGER,          -- 跌停家数
    burst_count INTEGER,               -- 炸板家数
    seal_success_rate DECIMAL(4,2),    -- 封板成功率: 涨停/(涨停+炸板)
    advance_count INTEGER,             -- 上涨家数
    decline_count INTEGER,             -- 下跌家数
    advance_decline_ratio DECIMAL(6,2),-- 涨跌比
    max_continuous INTEGER,            -- 最高连板
    max_continuous_code VARCHAR(10),   -- 最高连板股票代码
    max_continuous_name VARCHAR(20),   -- 最高连板股票名称
    yesterday_premium_avg DECIMAL(6,2),-- 昨日涨停今日均溢价%
    yesterday_premium_high DECIMAL(6,2),-- 昨日涨停今日最高溢价%
    yesterday_premium_low DECIMAL(6,2), -- 昨日涨停今日最低溢价%
    total_amount DECIMAL(20,2),        -- 市场总成交额
    emotion_phase VARCHAR(10),         -- 情绪阶段: 冰点/修复/发酵/高潮/分歧/退潮
    emotion_score INTEGER,             -- 情绪评分 0-100
    -- 连板梯队
    board_1_count INTEGER DEFAULT 0,   -- 首板家数
    board_2_count INTEGER DEFAULT 0,   -- 2连板家数
    board_3_count INTEGER DEFAULT 0,   -- 3连板家数
    board_4_count INTEGER DEFAULT 0,   -- 4连板家数
    board_5_plus_count INTEGER DEFAULT 0, -- 5板及以上家数
    -- 晋级率
    promote_1to2_rate DECIMAL(4,2),    -- 1进2晋级率
    promote_2to3_rate DECIMAL(4,2),    -- 2进3晋级率
    promote_3to4_rate DECIMAL(4,2),    -- 3进4晋级率
    notes TEXT                         -- 手动备注
);

-- ========== 题材追踪 ==========

-- 每日热门题材
CREATE TABLE daily_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date DATE NOT NULL,
    concept_name VARCHAR(50) NOT NULL,  -- 概念板块名
    change_pct DECIMAL(6,2),            -- 板块涨幅%
    limit_up_count INTEGER DEFAULT 0,   -- 板块内涨停家数
    total_stocks INTEGER,               -- 板块总股票数
    amount DECIMAL(18,2),               -- 板块成交额
    leader_code VARCHAR(10),            -- 龙头代码
    leader_name VARCHAR(20),            -- 龙头名称
    leader_continuous INTEGER DEFAULT 0,-- 龙头连板数
    consecutive_days INTEGER DEFAULT 1, -- 题材连续活跃天数
    is_new_theme BOOLEAN DEFAULT TRUE,  -- 是否新题材(首日出现)
    catalyst TEXT,                      -- 催化事件(手动标注)
    UNIQUE(trade_date, concept_name)
);

-- ========== 龙虎榜 ==========

-- 龙虎榜每日明细
CREATE TABLE dragon_tiger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date DATE NOT NULL,
    code VARCHAR(10) NOT NULL,
    name VARCHAR(20),
    close_price DECIMAL(10,2),
    change_pct DECIMAL(6,2),
    turnover_rate DECIMAL(6,2),
    amount DECIMAL(18,2),
    reason VARCHAR(100),                -- 上榜原因
    UNIQUE(trade_date, code)
);

-- 龙虎榜席位明细
CREATE TABLE dragon_tiger_seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date DATE NOT NULL,
    code VARCHAR(10) NOT NULL,
    direction VARCHAR(4) NOT NULL,      -- 'BUY' or 'SELL'
    rank INTEGER NOT NULL,              -- 1-5
    seat_name VARCHAR(100),             -- 营业部名称
    buy_amount DECIMAL(18,2),           -- 买入额
    sell_amount DECIMAL(18,2),          -- 卖出额
    net_amount DECIMAL(18,2),           -- 净额
    is_known_player BOOLEAN DEFAULT FALSE, -- 是否知名游资
    player_name VARCHAR(50),            -- 游资别名(如有)
    UNIQUE(trade_date, code, direction, rank)
);

-- 知名游资映射表 (手动维护)
CREATE TABLE known_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seat_name VARCHAR(100) NOT NULL UNIQUE, -- 营业部全称
    player_alias VARCHAR(50),               -- 游资别名 (如 "赵老哥", "佛山无影脚")
    style VARCHAR(50),                      -- 风格标签 (如 "打板", "低吸", "半路")
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- ========== 复盘记录 ==========

-- 每日复盘总结 (系统生成 + 用户补充)
CREATE TABLE daily_recap (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date DATE NOT NULL UNIQUE,
    emotion_summary TEXT,               -- 情绪总结
    theme_summary TEXT,                 -- 题材总结
    dragon_tiger_summary TEXT,          -- 龙虎榜总结
    tomorrow_strategy TEXT,             -- 明日策略建议
    user_notes TEXT,                    -- 用户手动笔记
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. Core Algorithms

### 4.1 情绪周期判定算法

情绪周期是超短线最核心的判断维度。基于以下指标量化：

```python
def classify_emotion_phase(today: DailyEmotion, history: list[DailyEmotion]) -> str:
    """
    判定当日情绪周期阶段

    输入指标:
    - limit_up_count: 涨停家数
    - seal_success_rate: 封板成功率
    - max_continuous: 最高连板
    - yesterday_premium_avg: 昨日涨停溢价率
    - advance_decline_ratio: 涨跌比

    阶段定义:
    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐
    │ 冰点  │ →  │ 修复  │ →  │ 发酵  │ →  │ 高潮  │ →  │ 分歧  │ →  │ 退潮  │ → (循环)
    └──────┘    └──────┘    └──────┘    └──────┘    └──────┘    └──────┘
    """

    score = 0  # 0-100

    # 1. 涨停家数评分 (0-25)
    #    < 30: 冰点区 (0-5)
    #    30-60: 正常 (10-15)
    #    60-100: 活跃 (15-20)
    #    > 100: 极热 (20-25)
    score += score_limit_up_count(today.limit_up_count_real)

    # 2. 封板成功率评分 (0-25)
    #    < 50%: 极弱 (0-5)
    #    50-65%: 偏弱 (5-10)
    #    65-80%: 正常 (10-20)
    #    > 80%: 强势 (20-25)
    score += score_seal_rate(today.seal_success_rate)

    # 3. 连板高度评分 (0-25)
    #    最高板=1 (无连板): (0-5)
    #    最高板=2-3: (5-10)
    #    最高板=4-5: (10-15)
    #    最高板=6-7: (15-20)
    #    最高板>=8: (20-25)
    score += score_max_continuous(today.max_continuous)

    # 4. 昨日涨停溢价评分 (0-25)
    #    < -3%: 亏钱效应 (0-5)
    #    -3% ~ 0%: 弱溢价 (5-10)
    #    0% ~ 3%: 正常溢价 (10-15)
    #    3% ~ 6%: 强溢价 (15-20)
    #    > 6%: 极强 (20-25)
    score += score_premium(today.yesterday_premium_avg)

    # 综合判定
    # 还需要结合趋势方向 (score 连续N日变化方向)
    trend = calculate_score_trend(history[-5:])  # 近5日趋势

    if score <= 20:
        return "冰点"
    elif score <= 35 and trend > 0:
        return "修复"
    elif score <= 60 and trend > 0:
        return "发酵"
    elif score > 75:
        return "高潮"
    elif score > 40 and trend < 0:
        return "分歧"
    elif score <= 40 and trend < 0:
        return "退潮"
    else:
        return "震荡"  # 无明确方向
```

### 4.2 连板晋级率计算

```python
def calculate_promotion_rates(date: str) -> dict:
    """
    计算各高度连板的晋级率

    逻辑:
    - 昨日有 N 只 1 连板 → 今日有 M 只 2 连板 → 1进2 晋级率 = M/N
    - 昨日有 X 只 2 连板 → 今日有 Y 只 3 连板 → 2进3 晋级率 = Y/X

    数据来源: daily_limit_up 表的 continuous_count 字段
    """
    yesterday_boards = count_by_continuous(yesterday)  # {1: 45, 2: 8, 3: 3, 4: 1}
    today_boards = count_by_continuous(today)          # {1: 50, 2: 5, 3: 2, 4: 2}

    rates = {}
    # 今日2板的来源 = 昨日1板晋级
    if yesterday_boards.get(1, 0) > 0:
        rates["1to2"] = today_boards.get(2, 0) / yesterday_boards[1]
    # 今日3板的来源 = 昨日2板晋级
    if yesterday_boards.get(2, 0) > 0:
        rates["2to3"] = today_boards.get(3, 0) / yesterday_boards[2]
    # ...以此类推

    return rates
```

### 4.3 题材强度评分

```python
def score_theme_strength(theme: DailyTheme, history: list[DailyTheme]) -> int:
    """
    题材强度评分 (0-100)

    维度:
    - 板块涨停家数占比 (涨停数/板块总股数)
    - 是否有龙头连板
    - 持续天数
    - 板块整体涨幅
    - 成交额放大
    """
    score = 0

    # 涨停占比 (0-30)
    ratio = theme.limit_up_count / max(theme.total_stocks, 1)
    score += min(30, int(ratio * 300))

    # 龙头连板 (0-25)
    score += min(25, theme.leader_continuous * 5)

    # 持续天数 (0-20)
    score += min(20, theme.consecutive_days * 4)

    # 板块涨幅 (0-15)
    score += min(15, max(0, int(theme.change_pct * 3)))

    # 新题材加分 (0-10)
    if theme.is_new_theme:
        score += 10

    return min(100, score)
```

### 4.4 游资席位识别

```python
# 知名游资席位映射 (初始种子数据, 可通过管理界面维护)
KNOWN_PLAYERS_SEED = [
    # 格式: (营业部名称关键词, 游资别名, 风格)
    ("华泰证券上海武定路", "佛山无影脚", "打板"),
    ("华鑫证券上海宛平南路", "华鑫系", "打板"),
    ("东方财富拉萨团结路", "拉萨系", "接力"),
    ("东方财富拉萨东环路", "拉萨系", "接力"),
    ("中国银河证券绍兴", "赵老哥", "龙头"),
    ("中信证券上海溧阳路", "溧阳路", "打板"),
    ("国泰君安上海江苏路", "章盟主", "低吸"),
    ("华泰证券成都南一环路", "成都系", "打板"),
    # ... 更多可通过管理页面添加
]
```

---

## 5. Implementation Steps

### Phase 1: 项目基础 + 数据采集 (Week 1)

**Step 1.1** - 项目脚手架
- 初始化 Python 项目 (uv + pyproject.toml)
- 目录结构:
  ```
  a-share-short/
  ├── pyproject.toml
  ├── src/
  │   ├── __init__.py
  │   ├── config/
  │   │   ├── __init__.py
  │   │   └── settings.py          # Pydantic Settings
  │   ├── data/
  │   │   ├── __init__.py
  │   │   ├── collector.py         # AKShare 数据采集
  │   │   ├── models.py            # SQLModel ORM
  │   │   └── repository.py        # 数据访问层
  │   ├── engine/
  │   │   ├── __init__.py
  │   │   ├── emotion.py           # 情绪周期引擎
  │   │   ├── limit_up.py          # 涨停分析引擎
  │   │   ├── theme.py             # 题材追踪引擎
  │   │   ├── dragon_tiger.py      # 龙虎榜分析引擎
  │   │   └── recap.py             # 每日复盘生成器
  │   ├── api/
  │   │   ├── __init__.py
  │   │   ├── main.py              # FastAPI 入口
  │   │   └── routes/
  │   │       ├── __init__.py
  │   │       ├── emotion.py       # 情绪相关 API
  │   │       ├── limit_up.py      # 涨停相关 API
  │   │       ├── theme.py         # 题材相关 API
  │   │       ├── dragon_tiger.py  # 龙虎榜 API
  │   │       └── recap.py         # 复盘 API
  │   └── scheduler/
  │       ├── __init__.py
  │       └── jobs.py              # 定时任务
  ├── frontend/                    # Vue 3 app (Phase 3)
  ├── tests/
  ├── data/                        # SQLite 数据库文件
  └── seed/                        # 种子数据 (游资映射等)
  ```
- Expected: 可运行的项目骨架

**Step 1.2** - 数据采集器
- `DataCollector` 类封装所有 AKShare 调用:
  - `fetch_limit_up_pool(date)` → 涨停股池
  - `fetch_limit_up_previous(date)` → 昨日涨停表现
  - `fetch_burst_pool(date)` → 炸板股池
  - `fetch_limit_down_pool(date)` → 跌停股池
  - `fetch_strong_pool(date)` → 强势股池
  - `fetch_dragon_tiger(date)` → 龙虎榜
  - `fetch_concept_boards()` → 概念板块
  - `fetch_market_overview()` → 全A涨跌统计
- AKShare 限流: 每次调用间隔 ≥ 600ms, 失败自动重试 (指数退避)
- Expected: 所有数据源可正常采集

**Step 1.3** - 数据库 + Repository
- SQLModel 定义所有表
- Repository 实现 UPSERT 语义 (幂等写入)
- `LimitUpRepository`, `EmotionRepository`, `ThemeRepository`, `DragonTigerRepository`
- Expected: 数据可持久化存储

**Step 1.4** - 历史数据加载
- 批量加载过去 6 个月的涨停/龙虎榜/板块数据
- 进度条 (tqdm)
- Expected: 有足够历史数据可以验证算法

### Phase 2: 分析引擎 (Week 2-3)

**Step 2.1** - 涨停分析引擎 (`engine/limit_up.py`)
- 连板梯队统计: 按 continuous_count 分组计数
- 晋级率计算: 与昨日对比
- 涨停质量评估:
  - 封单比 = 封单金额 / 成交额 (> 2 为强封)
  - 首封时间 (10:00前为强, 14:00后为弱)
  - 炸板次数 (0次最强, >3次基本废了)
- 涨停按题材归类
- Expected: 完整的涨停生态分析

**Step 2.2** - 情绪周期引擎 (`engine/emotion.py`)
- 情绪评分算法 (0-100, 如上文 4.1)
- 情绪周期阶段判定 (冰点/修复/发酵/高潮/分歧/退潮)
- 历史情绪曲线 (近 60 个交易日)
- 关键转折点检测 (情绪从退潮→冰点→修复的拐点)
- Expected: 每日输出情绪阶段 + 评分

**Step 2.3** - 题材追踪引擎 (`engine/theme.py`)
- 每日热门题材排名 (按涨停家数, 板块涨幅)
- 题材持续性追踪 (连续活跃天数)
- 龙头识别 (板块内最高连板 + 最早涨停)
- 题材生命周期: 新题材/主升期/分歧期/退潮
- 新旧题材切换检测
- Expected: 每日输出 Top10 题材 + 各题材龙头

**Step 2.4** - 龙虎榜分析引擎 (`engine/dragon_tiger.py`)
- 席位解析: 买1-5, 卖1-5
- 知名游资匹配: seat_name 模糊匹配 known_players 表
- 游资买卖方向统计 (近 N 日)
- 机构 vs 游资占比
- 游资协同分析 (多个知名游资同时买入 → 强信号)
- Expected: 每日输出龙虎榜关键信息 + 游资动向

**Step 2.5** - 每日复盘生成器 (`engine/recap.py`)
- 综合所有引擎输出, 生成结构化复盘:
  ```
  ═══ 2026-03-13 复盘 ═══

  【情绪】发酵期 (评分: 68/100) ↑
  涨停 72 家 | 跌停 8 家 | 炸板 15 家 | 封板率 82%
  最高连板: 某某股份 5 板 | 昨日涨停溢价: +2.3%

  【连板梯队】
  5板: 1 只 | 4板: 2 只 | 3板: 5 只 | 2板: 12 只 | 首板: 52 只
  晋级率: 1→2: 26% | 2→3: 38% | 3→4: 40%

  【题材主线】
  1. 人工智能 (涨停12只, 持续第3天) 龙头: XXX (3板)
  2. 机器人   (涨停8只, 持续第5天) 龙头: YYY (5板)
  3. 低空经济 (涨停5只, 新题材!)

  【龙虎榜】
  · 赵老哥 买入 AAA (3200万)
  · 拉萨系 买入 BBB (2800万), 卖出 CCC (1500万)
  · 机构净买入 Top: DDD (+8000万)

  【明日关注】
  · 情绪处于发酵期, 可适度参与
  · 关注 人工智能 方向是否继续发酵
  · 5 板的 YYY 是否能晋级, 决定市场高度
  ```
- Expected: 盘后自动生成可读的复盘报告

### Phase 3: API + Dashboard (Week 3-5)

**Step 3.1** - FastAPI 后端
- Endpoints:
  ```
  GET  /api/emotion/today              → 今日情绪 + 阶段
  GET  /api/emotion/history            → 近 N 日情绪曲线
  GET  /api/limit-up/today             → 今日涨停列表
  GET  /api/limit-up/ladder            → 连板梯队
  GET  /api/limit-up/promotion         → 晋级率
  GET  /api/limit-up/quality/{code}    → 单只涨停板质量评估
  GET  /api/themes/today               → 今日热门题材
  GET  /api/themes/{name}/history      → 题材历史走势
  GET  /api/themes/{name}/leader       → 题材龙头
  GET  /api/dragon-tiger/today         → 今日龙虎榜
  GET  /api/dragon-tiger/player/{name} → 游资近期动向
  GET  /api/recap/today                → 今日复盘
  GET  /api/recap/{date}               → 历史复盘
  POST /api/recap/{date}/notes         → 添加用户笔记
  GET  /api/players                    → 知名游资列表
  POST /api/players                    → 添加/修改游资
  ```
- Expected: 完整 REST API + Swagger 文档

**Step 3.2** - Vue 3 Dashboard
- **Page 1: 情绪总览**
  - 情绪仪表盘 (半圆仪表, 0-100, 当前阶段文字)
  - 近 60 日情绪曲线 (折线图, 标注阶段变化点)
  - 涨停/跌停/炸板 柱状图
  - 涨跌比 面积图
  - 市场成交额 趋势

- **Page 2: 连板生态**
  - 连板梯队可视化 (金字塔/阶梯图)
  - 晋级率趋势 (折线图)
  - 涨停列表 (表格, 可按连板数/封单比/封板时间排序)
  - 涨停质量雷达图 (单只股票: 封单强度/封板时间/炸板次数/换手率/市值)

- **Page 3: 题材追踪**
  - 热门题材排名 (卡片式, 按涨停家数排序)
  - 题材生命周期时间线 (甘特图: 每个题材的活跃天数)
  - 题材内个股涨停地图 (树状图/热力图)
  - 龙头股走势 (迷你K线)

- **Page 4: 龙虎榜**
  - 今日上榜个股列表
  - 买卖席位明细 (展开/折叠)
  - 知名游资标签高亮
  - 游资近期战绩 (选中游资 → 近 30 日买入标的 + 后续涨跌)

- **Page 5: 每日复盘**
  - 复盘报告展示 (Markdown 渲染)
  - 用户笔记输入框
  - 历史复盘日历 (点击日期切换)

- Expected: 可交互的完整 Dashboard

**Step 3.3** - 定时任务
- APScheduler:
  ```
  15:05  采集涨停/炸板/跌停数据 (收盘后)
  15:10  采集全A涨跌统计, 概念板块行情
  15:15  运行分析引擎 (情绪/连板/题材)
  15:20  生成每日复盘
  18:30  采集龙虎榜数据 (盘后延迟发布)
  18:35  运行龙虎榜分析
  18:40  更新复盘报告 (追加龙虎榜部分)
  ```
- Expected: 每日自动化运行

### Phase 4: 优化 + 扩展 (Week 5-6)

**Step 4.1** - 历史回测
- 用历史数据验证情绪周期判定准确性
- 统计: 冰点买入→后续N日收益率 vs 高潮买入→后续N日收益率
- 输出: 各阶段的历史胜率数据

**Step 4.2** - 用户自定义
- 自选股列表 + 涨停提醒
- 自定义游资映射表 (管理页面)
- 复盘模板自定义
- 题材关键词过滤

**Step 4.3** - 数据导出
- CSV 导出 (涨停列表, 龙虎榜, 情绪数据)
- 复盘报告 Markdown/PDF 导出

---

## 6. Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `pyproject.toml` | Create | 项目依赖 (轻量级, 无ML库) |
| `src/config/settings.py` | Create | 配置管理 |
| `src/data/collector.py` | Create | AKShare 数据采集 (8个接口) |
| `src/data/models.py` | Create | SQLModel 表定义 (8张表) |
| `src/data/repository.py` | Create | UPSERT 数据访问层 |
| `src/engine/emotion.py` | Create | 情绪周期引擎 (核心) |
| `src/engine/limit_up.py` | Create | 涨停分析引擎 |
| `src/engine/theme.py` | Create | 题材追踪引擎 |
| `src/engine/dragon_tiger.py` | Create | 龙虎榜分析引擎 |
| `src/engine/recap.py` | Create | 每日复盘生成器 |
| `src/api/main.py` | Create | FastAPI 入口 |
| `src/api/routes/*.py` | Create | API 路由 (5 个模块) |
| `src/scheduler/jobs.py` | Create | 定时任务 |
| `seed/known_players.json` | Create | 知名游资种子数据 |
| `frontend/` | Create | Vue 3 Dashboard |
| `tests/` | Create | 测试用例 |

---

## 7. Dependencies (Python)

```toml
[project]
name = "a-share-short"
requires-python = ">=3.11"
dependencies = [
    "akshare>=1.14.0",        # A股数据接口
    "fastapi>=0.115.0",        # Web API
    "uvicorn[standard]>=0.32.0", # ASGI server
    "sqlmodel>=0.0.22",        # ORM (SQLAlchemy + Pydantic)
    "pandas>=2.2.0",           # 数据处理
    "numpy>=1.26.0",           # 数值计算
    "apscheduler>=3.10.0",     # 定时任务
    "httpx>=0.27.0",           # HTTP client
    "pydantic-settings>=2.6.0", # 配置管理
    "loguru>=0.7.0",           # 日志
    "tqdm>=4.66.0",            # 进度条
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
]
```

**对比原计划砍掉了**: pandas-ta, xgboost, torch, scikit-learn, transformers, optuna — 总依赖体积减少约 **5GB+**。

---

## 8. Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| AKShare 涨停池接口不稳定/变更 | 数据断裂 | 异常捕获+重试; 每次采集前校验字段; 版本锁定 |
| 涨停数据延迟 (盘中数据不完整) | 误判 | 只在收盘后 15:05+ 采集, 不做盘中实时 |
| 龙虎榜数据发布时间不固定 | 复盘不完整 | 分两阶段: 15:20 先出基础复盘, 18:40 追加龙虎榜 |
| 情绪周期阈值需要调参 | 判定不准 | 用历史数据回测验证; 阈值可配置; 逐步迭代 |
| 知名游资席位变更 (换营业部) | 漏识别 | 管理页面支持手动更新; 社区共享 |
| 概念板块名变更 / 新增 | 题材断裂 | 每日自动刷新板块列表; 模糊匹配 |
| SQLite 并发限制 | 多用户慢 | Phase 1 够用; 需要时迁移 PostgreSQL |

---

## 9. Non-Goals (Phase 1)

- ~~ML 预测模型~~ (超短线不需要)
- ~~传统技术指标~~ (MA/MACD/RSI 等)
- ~~基本面分析~~ (PE/PB/ROE)
- ~~北向资金/融资融券~~ (日级别对超短无用)
- ~~自动交易/下单~~ (这是辅助工具, 不是交易系统)
- ~~盘中实时数据~~ (AKShare 延迟大, 且超短线盘中靠肉眼看盘口)
- ~~移动端~~ (先做 Web)

---

## 10. SESSION_ID

- CODEX_SESSION: N/A (codeagent-wrapper not available)
- GEMINI_SESSION: N/A (codeagent-wrapper not available)

> Plan generated by Claude Opus 4.6 direct analysis with web research.
> Focused on ultra-short-term (超短线) trading analysis only.
> All ML/indicator modules removed per user requirement.
