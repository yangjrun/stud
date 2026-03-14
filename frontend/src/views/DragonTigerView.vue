<template>
  <div>
    <h1 style="margin-bottom: 20px">龙虎榜</h1>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <!-- 知名游资活动 -->
      <div class="card" v-if="data?.player_activities?.length">
        <div class="card-title">游资动向</div>
        <div v-for="act in data.player_activities.slice(0, 15)" :key="`${act.player_alias}-${act.code}-${act.direction}`"
             style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #1e2030; font-size: 13px">
          <div>
            <span class="tag tag-orange">{{ act.player_alias }}</span>
            <span :class="act.direction === 'BUY' ? 'text-red' : 'text-green'" style="margin: 0 8px">
              {{ act.direction === 'BUY' ? '买入' : '卖出' }}
            </span>
            <span>{{ act.name }} ({{ act.code }})</span>
          </div>
          <span style="color: #9ca3af">{{ (act.amount / 10000).toFixed(0) }}万</span>
        </div>
      </div>

      <!-- 上榜个股 -->
      <div class="card">
        <div class="card-title">上榜个股 ({{ data?.total_stocks || 0 }})</div>
        <table>
          <thead>
            <tr>
              <th>代码</th><th>名称</th><th>涨跌幅</th><th>净买入</th>
              <th>知名游资</th><th>机构</th><th>原因</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in stocks" :key="s.code">
              <td>{{ s.code }}</td>
              <td>{{ s.name }}</td>
              <td :class="(s.change_pct || 0) > 0 ? 'text-red' : 'text-green'">
                {{ s.change_pct?.toFixed(2) }}%
              </td>
              <td :class="s.net_amount > 0 ? 'text-red' : 'text-green'" style="font-weight: 600">
                {{ (s.net_amount / 10000).toFixed(0) }}万
              </td>
              <td>
                <span v-if="s.known_player_count > 0" class="tag tag-orange">{{ s.known_player_count }}位</span>
                <span v-else class="tag tag-gray">无</span>
              </td>
              <td>
                <span v-if="s.has_institution" class="tag tag-blue">有</span>
              </td>
              <td style="font-size: 12px; color: #9ca3af; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
                {{ s.reason }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!stocks.length" class="card">暂无龙虎榜数据 (盘后约18:30发布)</div>
    </template>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { getDragonTigerToday } from '../api'

const props = defineProps({ tradeDate: String })
const loading = ref(true)
const data = ref(null)
const stocks = ref([])

async function loadData() {
  loading.value = true
  try {
    const res = await getDragonTigerToday(props.tradeDate)
    data.value = res.data
    stocks.value = res.data?.stocks || []
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

onMounted(loadData)
watch(() => props.tradeDate, loadData)
</script>
