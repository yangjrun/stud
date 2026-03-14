<template>
  <div>
    <h1 style="margin-bottom: 20px">交易日志</h1>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <!-- 统计卡片 -->
      <div class="grid-3">
        <div class="card" style="text-align: center">
          <div class="stat-label">总盈亏</div>
          <div class="stat-value" :class="stats.total_realized_pnl >= 0 ? 'text-red' : 'text-green'">
            {{ stats.total_realized_pnl?.toFixed(2) || '0.00' }}
          </div>
        </div>
        <div class="card" style="text-align: center">
          <div class="stat-label">胜率</div>
          <div class="stat-value" :style="{ color: winRateColor }">{{ stats.win_rate || 0 }}%</div>
          <div class="stat-label">{{ stats.wins || 0 }}胜 / {{ stats.losses || 0 }}负</div>
        </div>
        <div class="card" style="text-align: center">
          <div class="stat-label">交易次数</div>
          <div class="stat-value">{{ (stats.total_buy_count || 0) + (stats.total_sell_count || 0) }}</div>
          <div class="stat-label">买{{ stats.total_buy_count || 0 }} / 卖{{ stats.total_sell_count || 0 }}</div>
        </div>
      </div>

      <!-- 新增交易表单 -->
      <div class="card">
        <div class="card-title">新增交易</div>
        <div class="form-grid">
          <div>
            <label>日期</label>
            <input type="date" v-model="form.trade_date" />
          </div>
          <div>
            <label>代码</label>
            <input v-model="form.code" placeholder="000001" />
          </div>
          <div>
            <label>名称</label>
            <input v-model="form.name" placeholder="平安银行" />
          </div>
          <div>
            <label>方向</label>
            <select v-model="form.direction">
              <option value="BUY">买入</option>
              <option value="SELL">卖出</option>
            </select>
          </div>
          <div>
            <label>价格</label>
            <input type="number" v-model.number="form.price" step="0.01" />
          </div>
          <div>
            <label>数量</label>
            <input type="number" v-model.number="form.quantity" step="100" />
          </div>
          <div>
            <label>信号类型</label>
            <select v-model="form.signal_type">
              <option value="">无</option>
              <option value="分歧转一致">分歧转一致</option>
              <option value="梯队确认">梯队确认</option>
              <option value="龙头换手">龙头换手</option>
              <option value="龙虎榜关注">龙虎榜关注</option>
            </select>
          </div>
          <div>
            <label>策略</label>
            <input v-model="form.strategy" placeholder="打板/低吸/半路" />
          </div>
        </div>
        <div style="margin-top: 12px">
          <label>原因/备注</label>
          <input v-model="form.reason" placeholder="交易理由" style="width: 100%" />
        </div>
        <button class="btn-submit" @click="submitTrade" :disabled="submitting" style="margin-top: 12px">
          {{ submitting ? '提交中...' : '提交交易' }}
        </button>
      </div>

      <!-- 持仓表格 -->
      <div class="card">
        <div class="card-title">当前持仓 ({{ positions.length }})</div>
        <table v-if="positions.length">
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th>数量</th>
              <th>成本价</th>
              <th>总成本</th>
              <th>首次买入</th>
              <th>已实现盈亏</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in positions" :key="p.code">
              <td>{{ p.code }}</td>
              <td>{{ p.name }}</td>
              <td>{{ p.quantity }}</td>
              <td>{{ p.avg_cost?.toFixed(3) }}</td>
              <td>{{ p.total_cost?.toFixed(2) }}</td>
              <td>{{ p.first_buy_date }}</td>
              <td :class="p.realized_pnl >= 0 ? 'text-red' : 'text-green'">
                {{ p.realized_pnl?.toFixed(2) }}
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else style="color: #9ca3af; text-align: center; padding: 20px">空仓</div>
      </div>

      <!-- 交易历史 -->
      <div class="card">
        <div class="card-title">
          交易历史
          <span style="float: right; font-size: 12px; color: #9ca3af">
            <select v-model="filterDirection" style="background: #1e2030; border: 1px solid #3a3d4a; color: #e0e0e0; padding: 2px 6px; border-radius: 4px;">
              <option value="">全部</option>
              <option value="BUY">买入</option>
              <option value="SELL">卖出</option>
            </select>
          </span>
        </div>
        <table v-if="filteredTrades.length">
          <thead>
            <tr>
              <th>日期</th>
              <th>代码</th>
              <th>名称</th>
              <th>方向</th>
              <th>价格</th>
              <th>数量</th>
              <th>金额</th>
              <th>策略</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in filteredTrades" :key="t.id">
              <td>{{ t.trade_date }}</td>
              <td>{{ t.code }}</td>
              <td>{{ t.name }}</td>
              <td>
                <span class="tag" :class="t.direction === 'BUY' ? 'tag-red' : 'tag-green'">
                  {{ t.direction === 'BUY' ? '买入' : '卖出' }}
                </span>
              </td>
              <td>{{ t.price?.toFixed(2) }}</td>
              <td>{{ t.quantity }}</td>
              <td>{{ t.amount?.toFixed(2) }}</td>
              <td>{{ t.strategy || '-' }}</td>
              <td>
                <span style="color: #ef4444; cursor: pointer; font-size: 12px" @click="removeTrade(t.id)">删除</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else style="color: #9ca3af; text-align: center; padding: 20px">暂无交易记录</div>
      </div>

      <!-- 策略胜率图表 -->
      <div class="card" v-if="Object.keys(stats.strategy_stats || {}).length">
        <div class="card-title">策略统计</div>
        <div ref="chartEl" style="height: 250px"></div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getPositions, getTradeStats, getTradesRange, addTrade, deleteTrade } from '../api'

const props = defineProps({ tradeDate: String })
const loading = ref(true)
const submitting = ref(false)
const positions = ref([])
const trades = ref([])
const stats = ref({})
const filterDirection = ref('')
const chartEl = ref(null)
let chart = null

const today = new Date().toISOString().slice(0, 10)
const form = ref({
  trade_date: today,
  code: '',
  name: '',
  direction: 'BUY',
  price: 0,
  quantity: 0,
  signal_type: '',
  strategy: '',
  reason: '',
})

const winRateColor = computed(() => {
  const r = stats.value?.win_rate || 0
  if (r >= 50) return '#ef4444'
  if (r >= 30) return '#f97316'
  return '#22c55e'
})

const filteredTrades = computed(() => {
  if (!filterDirection.value) return trades.value
  return trades.value.filter(t => t.direction === filterDirection.value)
})

async function loadData() {
  loading.value = true
  try {
    // 最近60天的交易
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - 60)
    const startStr = start.toISOString().slice(0, 10)
    const endStr = end.toISOString().slice(0, 10)

    const [posRes, statsRes, tradesRes] = await Promise.all([
      getPositions(),
      getTradeStats(),
      getTradesRange(startStr, endStr),
    ])
    positions.value = posRes.data?.data || []
    stats.value = statsRes.data || {}
    trades.value = tradesRes.data?.data || []

    await nextTick()
    if (chartEl.value && stats.value?.strategy_stats) {
      renderChart(stats.value.strategy_stats)
    }
  } catch (e) {
    positions.value = []
    stats.value = {}
    trades.value = []
  }
  loading.value = false
}

async function submitTrade() {
  if (!form.value.code || form.value.price <= 0 || form.value.quantity <= 0) {
    alert('请填写完整的交易信息')
    return
  }
  submitting.value = true
  try {
    await addTrade(form.value)
    form.value = { ...form.value, code: '', name: '', price: 0, quantity: 0, reason: '' }
    await loadData()
  } catch (e) {
    alert('提交失败: ' + (e.response?.data?.detail || e.message))
  }
  submitting.value = false
}

async function removeTrade(id) {
  if (!confirm('确认删除此交易?')) return
  try {
    await deleteTrade(id)
    await loadData()
  } catch (e) {
    alert('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

function renderChart(strategyStats) {
  if (!chart) {
    chart = echarts.init(chartEl.value)
  }
  const names = Object.keys(strategyStats)
  const counts = names.map(n => strategyStats[n].count)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#9ca3af' },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#9ca3af' },
    },
    series: [
      {
        name: '交易次数',
        type: 'bar',
        data: counts,
        itemStyle: { color: '#ff6b35', borderRadius: [4, 4, 0, 0] },
      },
    ],
  })
}

onMounted(loadData)
watch(() => props.tradeDate, loadData)
</script>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.form-grid label {
  display: block;
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 4px;
}

.form-grid input,
.form-grid select {
  width: 100%;
  padding: 6px 8px;
  background: #1e2030;
  border: 1px solid #3a3d4a;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 13px;
}

.btn-submit {
  padding: 8px 24px;
  background: #ff6b35;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.btn-submit:hover { background: #e55a2b; }
.btn-submit:disabled { background: #666; cursor: not-allowed; }
</style>
