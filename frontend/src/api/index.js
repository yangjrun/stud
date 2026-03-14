import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export function getEmotionToday(date) {
  return api.get('/emotion/today', { params: { date } })
}

export function getEmotionHistory(days = 60, date) {
  return api.get('/emotion/history', { params: { days, date } })
}

export function getLimitUpToday(date) {
  return api.get('/limit-up/today', { params: { date } })
}

export function getLadder(date) {
  return api.get('/limit-up/ladder', { params: { date } })
}

export function getPromotion(date) {
  return api.get('/limit-up/promotion', { params: { date } })
}

export function getLimitUpQuality(code, date) {
  return api.get(`/limit-up/quality/${code}`, { params: { date } })
}

export function getThemesToday(date, limit = 15) {
  return api.get('/themes/today', { params: { date, limit } })
}

export function getThemeHistory(name, days = 30) {
  return api.get(`/themes/${encodeURIComponent(name)}/history`, { params: { days } })
}

export function getDragonTigerToday(date) {
  return api.get('/dragon-tiger/today', { params: { date } })
}

export function getPlayerHistory(name, limit = 30) {
  return api.get(`/dragon-tiger/player/${encodeURIComponent(name)}`, { params: { limit } })
}

export function getPlayers() {
  return api.get('/dragon-tiger/players')
}

export function getRecapToday(date) {
  return api.get('/recap/today', { params: { date } })
}

export function getRecapByDate(dateStr) {
  return api.get(`/recap/${dateStr}`)
}

export function saveRecapNotes(dateStr, notes) {
  return api.post(`/recap/${dateStr}/notes`, { notes })
}

// 信号引擎
export function getSignalToday(date) {
  return api.get('/signals/today', { params: { date } })
}

export function getSignalGate(date) {
  return api.get('/signals/gate', { params: { date } })
}

export function getSignalEchelons(date) {
  return api.get('/signals/echelons', { params: { date } })
}

export function getSignalCandidates(date) {
  return api.get('/signals/candidates', { params: { date } })
}

export function getSignalSell(date) {
  return api.get('/signals/sell', { params: { date } })
}

export function getSignalHistory(days = 30) {
  return api.get('/signals/history', { params: { days } })
}

export function runSignals(date) {
  return api.post('/signals/run', null, { params: { date } })
}

// 交易日志
export function getTrades(date) {
  return api.get('/journal/trades', { params: { date } })
}

export function getTradesRange(start, end) {
  return api.get('/journal/trades/range', { params: { start, end } })
}

export function addTrade(data) {
  return api.post('/journal/trades', data)
}

export function deleteTrade(id) {
  return api.delete(`/journal/trades/${id}`)
}

export function getPositions() {
  return api.get('/journal/positions')
}

export function getTradeStats() {
  return api.get('/journal/stats')
}

export function getMonthlyStats() {
  return api.get('/journal/stats/monthly')
}
