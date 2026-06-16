import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/wizard',
      name: 'wizard',
      component: () => import('../views/WizardView.vue'),
    },
    {
      path: '/read/:sessionId',
      name: 'reader',
      component: () => import('../views/ReaderView.vue'),
    },
    {
      path: '/edit/:plotId',
      name: 'editor',
      component: () => import('../views/EditorView.vue'),
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
    },
    {
      path: '/readme',
      name: 'readme',
      component: () => import('../views/ReadmeView.vue'),
    },
  ],
})

// 首次运行引导：若尚未配置任何 API Key，跳转到管理后台让用户填写。
// 仅在本次会话检查一次，避免每次跳转都打接口。
let _keyChecked = false
router.beforeEach(async (to) => {
  if (_keyChecked || to.name === 'admin') return true
  _keyChecked = true
  try {
    const r = await fetch('/api/admin/providers')
    if (!r.ok) return true
    const p = await r.json()
    // Agnes 内置连接永远有 key，故正常不会触发引导；保留兜底逻辑以防异常配置。
    const hasAnyKey = (p?.providers || []).some(x => x.has_key)
    if (!hasAnyKey) {
      return { name: 'admin', query: { setup: '1' } }
    }
  } catch {
    // 接口异常时不拦截，正常进入
  }
  return true
})

export default router
