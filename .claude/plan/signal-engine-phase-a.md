# Implementation Plan: Phase A — Signal Engine (三步法信号引擎)

## Task Type
- [x] Backend (Signal engine + API)
- [x] Frontend (Signal dashboard)
- [x] Fullstack (Parallel)

---

## 1. Design Philosophy

### Core Principle: Cascading Filter Pipeline (级联过滤管道)

**NOT** a parallel scoring model. Signals are generated through a strict three-step cascade:

```
Step 1: 生态门控 (Gate)     ← Pass / Fail / Caution
        │
        │ ONLY if passed
        ▼
Step 2: 题材梯队 (Echelon)  ← Formation analysis per theme
        │
        │ ONLY for themes with complete formation
        ▼
Step 3: 分歧转一致 (Signal)  ← Target stock identification
```

Each step has a **hard gate** — if Step 1 fails, Steps 2 and 3 are NOT executed.
This matches the user's validated trading methodology exactly.

---

## 2. Data Models

### 2.1 New File: `src/data/models_signal.py`

```python
class DailySignal(SQLModel, table=True):
    """每日信号记录 (每个信号标的一行)"""
    __tablename__ = "daily_signals"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(index=True)

    # Step 1: 生态门控
    gate_passed: bool                    # True=通过, False=失败
    gate_level: str                      # "PASS" / "FAIL" / "CAUTION"
    gate_phase: str                      # 当前情绪阶段
    gate_score: int                      # 情绪评分
    gate_reason: str                     # 判定理由文本

    # Step 2: 题材梯队 (仅 gate_passed=True 时有值)
    theme_name: Optional[str] = None     # 所属题材
    theme_formation: Optional[str] = None  # "4321" / "321" / "21" / "scattered"
    theme_completeness: Optional[int] = None  # 梯队完整度 0-100
    theme_strength: Optional[int] = None  # 题材强度 (from ThemeEngine)

    # Step 3: 信号标的 (仅梯队完整时有值)
    code: Optional[str] = Field(default=None, max_length=10, index=True)
    name: Optional[str] = Field(default=None, max_length=20)
    signal_type: Optional[str] = None    # "分歧转一致" / "梯队确认" / "龙头换手"
    board_position: Optional[str] = None  # "1进2" / "2进3" / "3进4" / "首板"
    continuous_count: Optional[int] = None

    # 分歧指标 (JSON)
    divergence_detail: Optional[str] = None  # JSON: 各分歧指标详情
    confidence: Optional[int] = None     # 信号置信度 0-100

    # 龙虎榜补充 (18:40 更新)
    dragon_tiger_match: Optional[bool] = None  # 是否上龙虎榜
    known_player_buy: Optional[str] = None     # 知名游资买入 (JSON)

    UNIQUE(trade_date, code)  -- 同日同股只有一条信号
```

### 2.2 Design Note: Gate-Only Record

When gate fails, only one record per day is saved with `code=None` and gate fields populated.
This preserves the decision log for backtesting ("为什么今天没有信号").

---

## 3. Engine Design

### 3.1 New File: `src/engine/signal.py`

#### Dataclass Outputs (frozen=True, immutable)

```python
@dataclass(frozen=True)
class EcosystemGate:
    """Step 1 output: 生态门控"""
    passed: bool
    level: str          # "PASS" / "FAIL" / "CAUTION"
    phase: str          # 情绪阶段
    score: int          # 情绪评分
    trend: int          # 趋势方向
    max_height: int     # 最高连板
    reason: str         # 中文理由

@dataclass(frozen=True)
class ThemeEchelon:
    """Step 2 output: 单个题材的梯队分析"""
    concept_name: str
    formation: str      # "4321" / "321" / "21" / "scattered"
    board_distribution: dict[int, int]   # {4: 1, 3: 2, 2: 5, 1: 12}
    completeness: int   # 0-100
    strength: int       # from ThemeEngine
    leader_code: Optional[str]
    leader_name: Optional[str]
    leader_continuous: int
    theme_stocks: list[str]  # codes of limit-ups in this theme

@dataclass(frozen=True)
class SignalCandidate:
    """Step 3 output: 单只信号标的"""
    code: str
    name: str
    theme_name: str
    signal_type: str    # "分歧转一致" / "梯队确认" / "龙头换手"
    board_position: str # "1进2" / "2进3" etc.
    continuous_count: int
    divergence_indicators: dict[str, bool]  # 各分歧指标
    quality_score: int  # from LimitUpQuality
    confidence: int     # 0-100

@dataclass(frozen=True)
class SignalSnapshot:
    """信号引擎完整输出"""
    trade_date: date
    gate: EcosystemGate
    echelons: list[ThemeEchelon]       # Top themes with echelon (Step 2)
    candidates: list[SignalCandidate]  # Signal targets (Step 3)
    summary: str                       # 文本总结
```

#### SignalEngine Class

```python
class SignalEngine:
    """三步法信号引擎 — 级联过滤管道。"""

    def generate(
        self,
        trade_date: date,
        emotion: EmotionSnapshot,
        ladder: BoardLadder,
        promotion: PromotionRates,
        theme_summary: ThemeSummary,
        limit_ups: Sequence[DailyLimitUp],
        bursts: Sequence[DailyBurst],
        qualities: list[LimitUpQuality],
        yesterday_limit_ups: Sequence[DailyLimitUp],
    ) -> SignalSnapshot:
        # Step 1
        gate = self._check_gate(emotion, ladder, promotion)

        if not gate.passed:
            return SignalSnapshot(trade_date, gate, [], [],
                                 self._build_summary(gate, [], []))

        # Step 2
        echelons = self._analyze_echelons(theme_summary, limit_ups)

        # Step 3 (only for themes with formation >= "321")
        strong_echelons = [e for e in echelons if e.completeness >= 50]
        candidates = self._detect_signals(
            strong_echelons, limit_ups, bursts, qualities, yesterday_limit_ups
        )

        return SignalSnapshot(
            trade_date, gate, echelons, candidates,
            self._build_summary(gate, echelons, candidates)
        )
```

---

## 4. Algorithm Details

### 4.1 Step 1: Ecosystem Gate (`_check_gate`)

**Input**: EmotionSnapshot, BoardLadder, PromotionRates

**PASS conditions** (all must hold):
```python
# Hard requirements (any violation → FAIL)
if emotion.phase in ("冰点", "退潮"):
    return FAIL("退潮/冰点期, 放弃所有连板接力信号")

if ladder.max_height <= 2 and emotion.trend_direction < 0:
    return FAIL("连板高度压制且趋势下降, 生态恶化")

# Pass conditions
if emotion.phase in ("发酵", "高潮"):
    return PASS("生态健康, 情绪上升期")

if emotion.phase == "修复" and emotion.trend_direction >= 0:
    return PASS("修复期企稳, 可谨慎参与")

# Caution conditions
if emotion.phase == "分歧":
    if ladder.max_height >= 4:
        return CAUTION("分歧期但高度尚存, 需精选")
    else:
        return FAIL("分歧期且高度不足, 风险大于收益")

if emotion.phase == "震荡":
    avg_promotion = _avg_promotion_rate(promotion)
    if avg_promotion > 0.20:
        return CAUTION("震荡但晋级率尚可, 轻仓试错")
    else:
        return FAIL("震荡且晋级率低, 无赚钱效应")
```

**Key thresholds** (configurable constants):
```python
GATE_MIN_HEIGHT = 3           # 最低连板高度 (低于此值倾向FAIL)
GATE_PREMIUM_FLOOR = -3.0     # 昨涨停溢价底线 (低于此值强制FAIL)
GATE_PROMOTION_FLOOR = 0.15   # 平均晋级率底线
```

### 4.2 Step 2: Theme Echelon (`_analyze_echelons`)

**Input**: ThemeSummary, all DailyLimitUp records

For each theme in ThemeSummary.themes (already ranked by strength):

```python
def _analyze_single_echelon(theme: ThemeSnapshot, limit_ups) -> ThemeEchelon:
    # 1. Get all limit-ups belonging to this theme
    theme_stocks = [lu for lu in limit_ups
                    if theme.concept_name in (lu.concept or "").split(",")]

    # 2. Build board distribution
    board_dist = {}  # {continuous_count: count}
    for lu in theme_stocks:
        board_dist[lu.continuous_count] = board_dist.get(lu.continuous_count, 0) + 1

    # 3. Determine formation
    heights = sorted(board_dist.keys(), reverse=True)
    max_h = max(heights) if heights else 0

    if max_h >= 4 and 3 in board_dist and 2 in board_dist and 1 in board_dist:
        formation = "4321"
    elif max_h >= 3 and 2 in board_dist and 1 in board_dist:
        formation = "321"
    elif max_h >= 2 and 1 in board_dist:
        formation = "21"
    else:
        formation = "scattered"

    # 4. Completeness score
    # 4321 → base 80, 321 → base 55, 21 → base 25, scattered → 5
    # Bonus: +3 per extra stock at each filled level (depth)
    # Bonus: +5 if leader_continuous >= 4
    completeness = _calc_completeness(formation, board_dist, max_h)

    return ThemeEchelon(...)
```

**Completeness scoring**:
```python
FORMATION_BASE = {"4321": 80, "321": 55, "21": 25, "scattered": 5}

def _calc_completeness(formation, board_dist, max_h):
    score = FORMATION_BASE[formation]

    # Depth bonus: extra stocks at each level show deeper capital commitment
    for level, count in board_dist.items():
        if count > 1:
            score += min(10, (count - 1) * 3)  # +3 per extra, max +10 per level

    # Height bonus
    if max_h >= 5:
        score += 5

    return min(100, score)
```

### 4.3 Step 3: Divergence-to-Consensus Detection (`_detect_signals`)

**The hardest step.** With daily (not intraday) data, we use proxy indicators.

#### 4.3.1 Theme-Level Divergence Detection

A theme is experiencing **divergence** if ≥2 of these are true:

| Indicator | Data Source | Logic |
|-----------|-----------|-------|
| `leader_opened` | DailyLimitUp.open_count | Leader's open_count > 0 (开过板) |
| `theme_has_burst` | DailyBurst | Any stock in this theme appeared in burst pool today |
| `late_seal` | DailyLimitUp.first_seal_time | Leader sealed after 13:00 (午后封板) |
| `seal_weakened` | DailyLimitUp.seal_amount | Leader's seal_amount / amount < 1.0 (封单弱) |
| `lower_stocks_fell` | DailyBurst + change_pct | ≥2 theme stocks in burst pool OR yesterday's theme stocks dropped today |

```python
def _is_theme_diverging(echelon, limit_ups, bursts) -> tuple[bool, dict]:
    indicators = {}

    leader_lu = _find_stock(limit_ups, echelon.leader_code)
    if leader_lu:
        indicators["leader_opened"] = leader_lu.open_count > 0
        indicators["late_seal"] = _is_late_seal(leader_lu.first_seal_time)
        indicators["seal_weakened"] = _is_seal_weak(leader_lu)

    theme_burst_codes = [b.code for b in bursts
                         if echelon.concept_name in (b.concept or "")]
    indicators["theme_has_burst"] = len(theme_burst_codes) > 0
    indicators["burst_count"] = len(theme_burst_codes)

    true_count = sum(1 for v in indicators.values() if v is True)
    return (true_count >= 2, indicators)
```

#### 4.3.2 Stock-Level Consensus Detection

A stock shows **divergence→consensus** (分歧转一致) if:

```python
def _is_divergence_to_consensus(lu: DailyLimitUp, quality: LimitUpQuality) -> bool:
    # Must be a "turnover seal" (换手板), not a one-word board (一字板)
    if lu.open_count == 0 and (lu.turnover_rate or 0) < 3.0:
        return False  # 一字板, 不是分歧转一致

    # Must have survived divergence (开过板但封回来了)
    if lu.open_count > 0:
        return True   # 开板后回封 = 经典分歧转一致

    # High turnover seal (换手充分的涨停)
    if (lu.turnover_rate or 0) > 8.0 and quality.score >= 50:
        return True   # 虽然没开板, 但换手充分说明有分歧

    return False
```

#### 4.3.3 Signal Type Classification

```python
# 1进2: yesterday_count=1, today_count=2 → "首板晋级, 1进2"
# 2进3: yesterday_count=2, today_count=3 → "连板接力, 2进3"
# 龙头换手: leader with high open_count → "龙头分歧换手"

if lu.continuous_count == 2:
    board_position = "1进2"
elif lu.continuous_count == 3:
    board_position = "2进3"
elif lu.continuous_count >= 4:
    board_position = f"{lu.continuous_count - 1}进{lu.continuous_count}"
else:
    board_position = "首板"
```

#### 4.3.4 Confidence Scoring

```python
def _calc_confidence(
    gate: EcosystemGate,
    echelon: ThemeEchelon,
    quality: LimitUpQuality,
    is_diverging: bool,
    indicators: dict,
) -> int:
    score = 0

    # Gate strength (0-25)
    if gate.level == "PASS":
        score += 20 + min(5, (gate.score - 50) // 10)
    elif gate.level == "CAUTION":
        score += 10

    # Echelon completeness (0-30)
    score += int(echelon.completeness * 0.3)

    # Quality (0-25)
    score += int(quality.score * 0.25)

    # Divergence-to-consensus bonus (0-20)
    if is_diverging:
        score += 15  # Theme diverging = opportunity if stock resists
        if indicators.get("leader_opened"):
            score += 5  # Leader turnover = classic pattern

    return min(100, max(0, score))
```

---

## 5. Repository Layer

### 5.1 New File: `src/data/repo_signal.py`

```python
class SignalRepository:
    """信号数据访问层"""

    def upsert(self, record: DailySignal) -> DailySignal
    def get_by_date(self, trade_date: date) -> list[DailySignal]
    def get_gate_by_date(self, trade_date: date) -> Optional[DailySignal]
    def get_recent(self, trade_date: date, limit: int = 20) -> Sequence[DailySignal]
    def get_by_code(self, code: str, limit: int = 10) -> Sequence[DailySignal]
```

Follow existing UPSERT pattern from `repository.py`.

---

## 6. API Layer

### 6.1 New File: `src/api/routes/signal.py`

| Endpoint | Description |
|----------|-------------|
| `GET /api/signals/today` | 今日完整信号 (gate + echelons + candidates) |
| `GET /api/signals/gate` | 仅门控状态 (轻量, 快速查看生态是否允许) |
| `GET /api/signals/echelons` | 题材梯队分析 (各题材的4321/321结构) |
| `GET /api/signals/history` | 近N日信号历史 (含回测用) |
| `GET /api/signals/{code}/track` | 单只信号标的追踪 (信号发出后的表现) |

### Response Format (signals/today)

```json
{
  "trade_date": "2026-03-14",
  "gate": {
    "passed": true,
    "level": "PASS",
    "phase": "发酵",
    "score": 68,
    "reason": "生态健康, 情绪上升期"
  },
  "echelons": [
    {
      "concept_name": "人工智能",
      "formation": "4321",
      "board_distribution": {"4": 1, "3": 2, "2": 5, "1": 12},
      "completeness": 88,
      "strength": 82,
      "leader": {"code": "000001", "name": "XXX", "continuous": 4}
    }
  ],
  "candidates": [
    {
      "code": "000002",
      "name": "YYY",
      "theme": "人工智能",
      "signal_type": "分歧转一致",
      "board_position": "1进2",
      "confidence": 75,
      "divergence": {
        "leader_opened": true,
        "theme_has_burst": false,
        "late_seal": false
      }
    }
  ],
  "summary": "生态处于发酵期(68分), 人工智能形成4321完整梯队, ..."
}
```

---

## 7. Scheduler Integration

### 7.1 Modify: `src/scheduler/jobs.py`

Add two new scheduled jobs:

```python
# 15:20 - 生成信号 (在 15:15 分析完成后)
scheduler.add_job(
    job_generate_signals,
    "cron", hour=15, minute=20, day_of_week="mon-fri",
    id="generate_signals",
)

# 18:40 - 龙虎榜补充信号 (在 18:30 龙虎榜采集后)
scheduler.add_job(
    job_supplement_signals,
    "cron", hour=18, minute=40, day_of_week="mon-fri",
    id="supplement_signals",
)
```

### 7.2 `job_generate_signals()`

```python
def job_generate_signals():
    """15:20 — 生成三步法信号"""
    today = date.today()
    with get_session() as s:
        # Gather all inputs from already-computed analysis
        emo_repo = EmotionRepository(s)
        lu_repo = LimitUpRepository(s)
        burst_repo = BurstRepository(s)
        theme_repo = ThemeRepository(s)
        signal_repo = SignalRepository(s)

        emotion_record = emo_repo.get_by_date(today)
        history = list(emo_repo.get_recent(today, limit=10))
        limit_ups = lu_repo.get_by_date(today)
        bursts = burst_repo.get_by_date(today)
        yesterday_ups = lu_repo.get_by_date(_prev_trading_day(today))
        themes = theme_repo.get_by_date(today)

        # Build engine inputs
        emo_engine = EmotionEngine()
        lu_engine = LimitUpEngine()
        signal_engine = SignalEngine()

        emotion = emo_engine.analyze(emotion_record, history)
        ladder = lu_engine.build_ladder(limit_ups, bursts, today)
        promotion = lu_engine.calc_promotion_rates(yesterday_ups, limit_ups, today)
        qualities = [lu_engine.assess_quality(lu) for lu in limit_ups]
        theme_summary = ThemeSummary(
            trade_date=today,
            themes=[_theme_record_to_snapshot(t) for t in themes],
            ...
        )

        # Generate signals
        snapshot = signal_engine.generate(
            today, emotion, ladder, promotion,
            theme_summary, limit_ups, bursts, qualities, yesterday_ups
        )

        # Persist
        for record in signal_engine.to_records(snapshot):
            signal_repo.upsert(record)
        s.commit()
```

### 7.3 `job_supplement_signals()`

```python
def job_supplement_signals():
    """18:40 — 龙虎榜补充信号标的的游资信息"""
    today = date.today()
    with get_session() as s:
        signal_repo = SignalRepository(s)
        dt_repo = DragonTigerRepository(s)
        seat_repo = DragonTigerSeatRepository(s)
        player_repo = KnownPlayerRepository(s)

        signals = signal_repo.get_by_date(today)
        dragons = dt_repo.get_by_date(today)
        dragon_codes = {d.code for d in dragons}

        for signal in signals:
            if signal.code and signal.code in dragon_codes:
                signal.dragon_tiger_match = True
                # Check for known player buys
                seats = seat_repo.get_by_code_date(signal.code, today, "BUY")
                known_buyers = [
                    s.player_name for s in seats
                    if s.is_known_player and s.player_name
                ]
                if known_buyers:
                    signal.known_player_buy = json.dumps(known_buyers)
                    signal.confidence = min(100, (signal.confidence or 0) + 10)
        s.commit()
```

---

## 8. Frontend

### 8.1 New File: `frontend/src/views/SignalView.vue`

**Layout (top-to-bottom cascade, mirrors the three steps):**

```
┌──────────────────────────────────────────────────┐
│  Step 1: 生态门控                                  │
│  ┌─────────────────────┐                         │
│  │ 🟢 PASS / 🔴 FAIL   │  情绪: 发酵期 (68分)    │
│  │ 理由: xxxxxxxxxx     │  趋势: ↑ 上升           │
│  └─────────────────────┘  最高板: 5板             │
├──────────────────────────────────────────────────┤
│  Step 2: 题材梯队 (仅 PASS 时显示)                  │
│  ┌──────────┬──────────┬──────────┐              │
│  │ 人工智能  │ 机器人    │ 低空经济  │              │
│  │ [4321]   │ [321]    │ [21]     │              │
│  │ 完整度:88 │ 完整度:62 │ 完整度:30 │              │
│  │ 4板: 1只  │ 3板: 1只  │ 2板: 2只  │              │
│  │ 3板: 2只  │ 2板: 3只  │ 1板: 8只  │              │
│  │ 2板: 5只  │ 1板: 10只 │          │              │
│  │ 1板: 12只 │          │          │              │
│  └──────────┴──────────┴──────────┘              │
├──────────────────────────────────────────────────┤
│  Step 3: 信号标的 (仅强梯队时显示)                   │
│  ┌────┬──────┬────────┬──────┬──────┬────┐       │
│  │ 代码│ 名称  │ 题材    │ 类型  │ 位置  │置信度│       │
│  ├────┼──────┼────────┼──────┼──────┼────┤       │
│  │0002│ YYY  │人工智能  │分歧转一│1进2  │ 75 │       │
│  │0003│ ZZZ  │机器人   │梯队确认│2进3  │ 68 │       │
│  └────┴──────┴────────┴──────┴──────┴────┘       │
│  [龙虎榜补充] 🐉 YYY: 赵老哥买入 3200万            │
└──────────────────────────────────────────────────┘
```

**Key Components:**
- Gate status card: traffic light color (green/red/yellow)
- Echelon pyramid visualization: stacked bar chart per theme
- Signal table: sortable by confidence, filterable by theme
- Dragon-tiger badge: appears after 18:40 supplement

---

## 9. Implementation Steps

### Step A.1: Data Model + Repository
- Create `src/data/models_signal.py` with DailySignal
- Create `src/data/repo_signal.py` with SignalRepository (UPSERT pattern)
- Run database migration (create `daily_signals` table)
- **Deliverable**: Table exists, CRUD works

### Step A.2: Signal Engine Core
- Create `src/engine/signal.py`
- Implement `_check_gate()` — Step 1
- Implement `_analyze_echelons()` — Step 2
- Implement `_detect_signals()` — Step 3
- Implement `_build_summary()` — text generation
- Implement `to_records()` — convert to DailySignal list
- **Deliverable**: Engine generates signals from existing data

### Step A.3: Unit Tests
- Test gate logic with various emotion phases
- Test echelon formation detection (4321/321/21/scattered)
- Test divergence detection with mock data
- Test confidence scoring
- Test full pipeline: gate fail → no signals, gate pass → signals generated
- **Deliverable**: 80%+ coverage on signal.py

### Step A.4: API Routes
- Create `src/api/routes/signal.py`
- Register in `src/api/main.py`
- Endpoints: /today, /gate, /echelons, /history, /{code}/track
- **Deliverable**: API accessible via Swagger

### Step A.5: Scheduler Jobs
- Add `job_generate_signals` (15:20)
- Add `job_supplement_signals` (18:40)
- Wire into `create_scheduler()`
- **Deliverable**: Signals auto-generated daily

### Step A.6: Frontend View
- Create `frontend/src/views/SignalView.vue`
- Add route `/signal` in router.js
- Gate status card + echelon visualization + signal table
- **Deliverable**: Signal page renders correctly

### Step A.7: Backfill + Validation
- Run signal engine on existing 15 trading days of historical data
- Validate gate decisions against known market states
- Verify echelon formations match manual observation
- **Deliverable**: Historical signals make sense

---

## 10. Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `src/data/models_signal.py` | Create | DailySignal SQLModel |
| `src/data/repo_signal.py` | Create | SignalRepository (UPSERT) |
| `src/engine/signal.py` | Create | SignalEngine: 三步法核心 |
| `src/api/routes/signal.py` | Create | Signal API (5 endpoints) |
| `src/api/main.py:L15-L20` | Modify | Register signal router |
| `src/scheduler/jobs.py:L271-L305` | Modify | Add 2 new jobs |
| `frontend/src/views/SignalView.vue` | Create | Signal dashboard |
| `frontend/src/router.js` | Modify | Add /signal route |
| `frontend/src/api/index.js` | Modify | Add signal API calls |
| `tests/test_signal.py` | Create | Signal engine tests |

---

## 11. Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| 日线数据无法精确检测盘中分歧转一致 | 用 open_count + turnover_rate + first_seal_time 作为代理指标; 未来可接入分时数据增强 |
| 题材概念一股多属导致梯队统计重复 | 一只股只归入其 primary concept (连板最高的那个题材); 或按 strength 最高的题材归类 |
| 门控阈值需要调参 | 所有阈值抽为常量, 可通过配置调整; 用历史回填数据验证 |
| 龙虎榜数据18:30才有, 信号15:20就出 | 两阶段: 15:20先出基础信号, 18:40补充龙虎榜信息并更新置信度 |
| 新题材无历史梯队对比 | 新题材默认 consecutive_days=1, 梯队按当日即时数据判断, 不依赖历史 |
| 概念字段可能不含当日最热概念 | concept字段来自AKShare"所属行业", 可能遗漏; 未来可用概念板块成分股反查补全 |

---

## 12. SESSION_ID

- CODEX_SESSION: N/A (codeagent-wrapper not available)
- GEMINI_SESSION: N/A (codeagent-wrapper not available)

> Plan generated by Claude Opus 4.6 direct analysis.
> Focused on cascading filter pipeline architecture per user's validated three-step methodology.
> All algorithms designed for daily-frequency data with proxy indicators for intraday patterns.
