<template>
  <div>
    <h1 style="margin-bottom: 20px">每日复盘</h1>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else-if="recap && !recap.error">
      <div class="card">
        <pre class="recap-text">{{ recap.emotion_summary }}</pre>
      </div>
      <div class="card" v-if="recap.theme_summary">
        <pre class="recap-text">{{ recap.theme_summary }}</pre>
      </div>
      <div class="card" v-if="recap.dragon_tiger_summary">
        <pre class="recap-text">{{ recap.dragon_tiger_summary }}</pre>
      </div>
      <div class="card" v-if="recap.tomorrow_strategy">
        <pre class="recap-text">{{ recap.tomorrow_strategy }}</pre>
      </div>

      <!-- 用户笔记 -->
      <div class="card">
        <div class="card-title">我的笔记</div>
        <textarea
          v-model="notes"
          placeholder="记录今天的复盘心得..."
          style="width: 100%; min-height: 100px; background: #1e2030; border: 1px solid #3a3d4a; border-radius: 4px; color: #e0e0e0; padding: 12px; font-size: 14px; resize: vertical"
        ></textarea>
        <button @click="saveNotes" class="save-btn">保存笔记</button>
        <span v-if="saved" style="margin-left: 12px; color: #22c55e; font-size: 13px">已保存</span>
      </div>
    </template>
    <div v-else class="card">暂无复盘数据</div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { getRecapToday, saveRecapNotes } from '../api'

const props = defineProps({ tradeDate: String })
const loading = ref(true)
const recap = ref(null)
const notes = ref('')
const saved = ref(false)

async function loadData() {
  loading.value = true
  saved.value = false
  try {
    const res = await getRecapToday(props.tradeDate)
    recap.value = res.data
    notes.value = res.data?.user_notes || ''
  } catch (e) {
    recap.value = null
  }
  loading.value = false
}

async function saveNotes() {
  try {
    await saveRecapNotes(props.tradeDate, notes.value)
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } catch (e) {
    console.error(e)
  }
}

onMounted(loadData)
watch(() => props.tradeDate, loadData)
</script>

<style scoped>
.recap-text {
  white-space: pre-wrap;
  font-family: "PingFang SC", "Microsoft YaHei", monospace;
  font-size: 14px;
  line-height: 1.8;
  color: #e0e0e0;
}

.save-btn {
  margin-top: 12px;
  padding: 8px 20px;
  background: #ff6b35;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.save-btn:hover { background: #e55a2b; }
</style>
