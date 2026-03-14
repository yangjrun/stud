import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/emotion' },
  { path: '/emotion', name: 'Emotion', component: () => import('./views/EmotionView.vue') },
  { path: '/limit-up', name: 'LimitUp', component: () => import('./views/LimitUpView.vue') },
  { path: '/themes', name: 'Themes', component: () => import('./views/ThemeView.vue') },
  { path: '/dragon-tiger', name: 'DragonTiger', component: () => import('./views/DragonTigerView.vue') },
  { path: '/recap', name: 'Recap', component: () => import('./views/RecapView.vue') },
  { path: '/signals', name: 'Signals', component: () => import('./views/SignalView.vue') },
  { path: '/journal', name: 'Journal', component: () => import('./views/JournalView.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
