<template>
  <div class="app">
    <nav class="sidebar">
      <h2 class="logo">超短复盘</h2>
      <div class="date-picker">
        <input type="date" v-model="currentDate" @change="onDateChange" />
      </div>
      <router-link to="/emotion" class="nav-item" active-class="active">情绪周期</router-link>
      <router-link to="/limit-up" class="nav-item" active-class="active">连板生态</router-link>
      <router-link to="/themes" class="nav-item" active-class="active">题材追踪</router-link>
      <router-link to="/dragon-tiger" class="nav-item" active-class="active">龙虎榜</router-link>
      <router-link to="/recap" class="nav-item" active-class="active">每日复盘</router-link>
      <div style="border-top: 1px solid #2a2d3a; margin: 8px 0;"></div>
      <router-link to="/signals" class="nav-item" active-class="active">信号引擎</router-link>
      <router-link to="/journal" class="nav-item" active-class="active">交易日志</router-link>
    </nav>
    <main class="content">
      <router-view :trade-date="currentDate" />
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const today = new Date().toISOString().slice(0, 10)
const currentDate = ref(today)

function onDateChange() {
  // router-view will reactively update via prop
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #0f1117;
  color: #e0e0e0;
}

.app {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 200px;
  background: #161822;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #2a2d3a;
  position: fixed;
  top: 0;
  bottom: 0;
}

.logo {
  color: #ff6b35;
  font-size: 20px;
  padding: 0 20px 20px;
  border-bottom: 1px solid #2a2d3a;
}

.date-picker {
  padding: 15px 20px;
  border-bottom: 1px solid #2a2d3a;
}

.date-picker input {
  width: 100%;
  padding: 6px 8px;
  background: #1e2030;
  border: 1px solid #3a3d4a;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 13px;
}

.nav-item {
  display: block;
  padding: 12px 20px;
  color: #9ca3af;
  text-decoration: none;
  font-size: 14px;
  transition: all 0.2s;
}

.nav-item:hover { color: #e0e0e0; background: #1e2030; }
.nav-item.active { color: #ff6b35; background: #1e2030; border-left: 3px solid #ff6b35; }

.content {
  flex: 1;
  margin-left: 200px;
  padding: 24px;
}

/* Shared styles */
.card {
  background: #161822;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
  border: 1px solid #2a2d3a;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #f0f0f0;
}

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }

.stat-value {
  font-size: 28px;
  font-weight: 700;
}

.stat-label {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.tag-red { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
.tag-green { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
.tag-orange { background: rgba(249, 115, 22, 0.2); color: #f97316; }
.tag-blue { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
.tag-gray { background: rgba(156, 163, 175, 0.2); color: #9ca3af; }

.text-red { color: #ef4444; }
.text-green { color: #22c55e; }
.text-orange { color: #f97316; }

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid #2a2d3a;
  color: #9ca3af;
  font-weight: 500;
}

td {
  padding: 8px 12px;
  border-bottom: 1px solid #1e2030;
}

tr:hover { background: #1e2030; }

.loading {
  text-align: center;
  padding: 40px;
  color: #9ca3af;
}
</style>
