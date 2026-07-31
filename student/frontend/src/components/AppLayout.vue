<template>
  <el-container class="app-layout">
    <el-aside v-if="!route.meta.fullscreen" :width="sidebarWidth" class="sidebar" :class="{ 'is-collapsed': sidebarCollapsed && !mobileOpen, 'is-mobile-open': mobileOpen }">
      <div class="sidebar-top">
        <div class="brand" @click="router.push('/dashboard')">
        <div class="brand-mark" aria-hidden="true">
          <span class="orbit-dot"></span>
          <span class="brand-core">π</span>
        </div>
        <div class="brand-copy">
          <strong>智学引擎</strong>
          <span>AI LEARNING ATLAS</span>
        </div>
        </div>
        <button
          class="sidebar-toggle"
          :aria-label="sidebarCollapsed ? '展开左侧导航' : '收起左侧导航'"
          :title="sidebarCollapsed ? '展开左侧导航' : '收起左侧导航'"
          @click="toggleSidebar"
        >
          <el-icon><Expand v-if="sidebarCollapsed" /><Fold v-else /></el-icon>
        </button>
      </div>

      <div class="nav-caption">学习空间</div>
      <el-menu :default-active="activeMenu" :collapse="sidebarCollapsed && !mobileOpen" :collapse-transition="false" router>
        <el-menu-item v-for="item in menuItems" :key="item.route" :index="item.route" @click="mobileOpen = false">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>
            {{ item.label }}
            <span v-if="item.badge === 'assignments' && pendingBadgeCount > 0" class="menu-badge-dot"></span>
          </span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer" :class="{ compact: sidebarCollapsed && !mobileOpen }">
        <div class="stage-orbit"><span></span></div>
        <div class="stage-copy">
          <small>{{ userStore.user?.username || '用户' }}</small>
          <strong>{{ userStore.learningStage }}</strong>
        </div>
      </div>

      <div v-if="!sidebarCollapsed || mobileOpen" class="sidebar-logout">
        <button class="logout-btn" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          <span>退出登录</span>
        </button>
      </div>
      <div v-else class="sidebar-logout-icon">
        <button class="logout-btn-icon" @click="handleLogout" title="退出登录">
          <el-icon><SwitchButton /></el-icon>
        </button>
      </div>
    </el-aside>

    <div v-if="mobileOpen && !route.meta.fullscreen" class="sidebar-scrim" @click="mobileOpen = false"></div>
    <el-container class="content-shell">
      <button v-if="!route.meta.fullscreen" class="mobile-nav-launch" aria-label="打开导航" @click="mobileOpen = true">
        <el-icon><Menu /></el-icon>
      </button>
      <el-main class="main-content" :class="{ 'is-fullscreen': route.meta.fullscreen, 'is-workspace': route.meta.workspace }">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { listAssignments, getMySubmissions } from '../api/homework'

function getStudentName() {
  try {
    const raw = localStorage.getItem('user')
    if (raw) {
      const state = JSON.parse(raw)
      const user = state.user || state
      return user.username || user.nickname || '学生'
    }
  } catch { /* */ }
  return '学生'
}

const pendingBadgeCount = ref(0)

async function fetchBadgeCount() {
  try {
    const name = getStudentName()
    const [aRes, sRes] = await Promise.all([
      listAssignments(),
      getMySubmissions(),
    ])
    const assignments = aRes.data?.data?.assignments || aRes.data?.assignments || []
    const submissions = sRes.data?.data?.submissions || sRes.data?.submissions || []
    const subIds = new Set(submissions.map(s => s.assignment_id))
    pendingBadgeCount.value = assignments.filter(
      a => !subIds.has(a.id) && a.status !== 'closed'
    ).length
  } catch { pendingBadgeCount.value = 0 }
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const sidebarCollapsed = ref(localStorage.getItem('sidebar_collapsed') === 'true' || localStorage.getItem('sidebar_hidden') === 'true')
const mobileOpen = ref(false)
const activeMenu = computed(() => route.path)
const sidebarWidth = computed(() => sidebarCollapsed.value && !mobileOpen.value ? '64px' : '252px')

const menuItems = [
  { route: '/dashboard',    label: '学习控制台', icon: 'DataAnalysis' },
  { route: '/my-courses',   label: '我的课程',   icon: 'Reading', badge: 'assignments' },
  { route: '/diagnosis',    label: '学情自测',   icon: 'DocumentChecked' },
  { route: '/qa',           label: '智能答疑',   icon: 'ChatDotRound' },
  { route: '/messaging',    label: '师生通信',   icon: 'ChatLineSquare' },
  { route: '/learning-path',label: '学习路径',   icon: 'Guide' },
  { route: '/error-book',   label: '错题本',     icon: 'EditPen' },
  { route: '/analytics',    label: '学情复盘',   icon: 'TrendCharts' },
  { route: '/resources',    label: '学习资源',   icon: 'Collection' },
  { route: '/code-lab',     label: '编程实验室', icon: 'Monitor' },
  { route: '/profile',      label: '个人中心',   icon: 'User' },
]

onMounted(() => { fetchBadgeCount() })

function toggleSidebar() {
  if (mobileOpen.value) {
    mobileOpen.value = false
    return
  }
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('sidebar_collapsed', String(sidebarCollapsed.value))
  localStorage.removeItem('sidebar_hidden')
}

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-layout { height: 100dvh; min-height: 0; overflow: hidden; }
.sidebar {
  position: relative;
  z-index: 30;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid rgba(255,255,255,.08);
  background:
    radial-gradient(circle at 20% 5%, rgba(86,183,220,.18), transparent 25%),
    linear-gradient(165deg, #151f3c 0%, #10182f 62%, #171b35 100%);
  box-shadow: 12px 0 36px rgba(17, 25, 50, .08);
  transition: width .3s cubic-bezier(.2,.8,.2,1);
}
.sidebar.is-collapsed { box-shadow: 6px 0 20px rgba(17, 25, 50, .08); }
.sidebar-top { display:flex;align-items:center;height:72px;min-height:72px;padding:0 10px 0 16px;border-bottom:1px solid rgba(255,255,255,.07) }
.sidebar-toggle { display:grid;width:34px;height:34px;flex:0 0 34px;place-items:center;border:1px solid rgba(255,255,255,.14);border-radius:9px;color:rgba(255,255,255,.72);background:rgba(255,255,255,.07);cursor:pointer;transition:.2s }
.sidebar-toggle:hover { color:#fff;background:rgba(255,255,255,.14) }
.brand { display: flex; align-items: center; gap: 12px; min-width:0;flex:1;color: #fff; cursor: pointer;overflow:hidden }
.brand-mark { position: relative; display: grid; width: 42px; height: 42px; flex: 0 0 42px; place-items: center; border: 1px solid rgba(255,255,255,.28); border-radius: 50%; }
.brand-mark::before { position: absolute; width: 50px; height: 25px; border: 1px solid rgba(86,183,220,.6); border-radius: 50%; content: ""; transform: rotate(-28deg); }
.brand-core { font-family: Georgia, serif; font-size: 20px; color: #fff; }
.orbit-dot { position: absolute; right: -5px; top: 4px; width: 7px; height: 7px; border-radius: 50%; background: #ff8c73; box-shadow: 0 0 0 4px rgba(255,129,102,.13); }
.brand-copy { min-width: 0; line-height: 1.05; white-space: nowrap; }
.brand-copy strong { display: block; font-size: 17px; letter-spacing: .08em; }
.brand-copy span { display: block; margin-top: 7px; color: rgba(255,255,255,.42); font-size: 9px; letter-spacing: .18em; }
.sidebar.is-collapsed .sidebar-top{padding:0 15px;justify-content:center}.sidebar.is-collapsed .brand{display:none}
.nav-caption { padding: 12px 26px 8px; color: rgba(255,255,255,.36); font-size: 10px; font-weight: 700; letter-spacing: .18em; }
.sidebar.is-collapsed .nav-caption,.sidebar.is-collapsed .stage-copy{display:none}
.el-menu { min-height:0;flex: 1;overflow-x:hidden;overflow-y:auto;border: 0; background: transparent; padding: 4px 12px; }
.el-menu--collapse { width: 64px; padding-inline: 8px; }
.el-menu-item { height: 48px; margin: 4px 0; border-radius: 12px; color: rgba(237,241,255,.64); }
.el-menu-item:hover { color: #fff; background: rgba(255,255,255,.07); }
.el-menu-item.is-active { color: #fff; background: linear-gradient(100deg, rgba(70,87,216,.9), rgba(86,183,220,.6)); box-shadow: 0 9px 24px rgba(28,43,118,.32); }
.el-menu-item.is-active::after { position: absolute; right: 10px; width: 5px; height: 5px; border-radius: 50%; background: #ff9a83; content: ""; }
.el-menu-item .el-icon { font-size: 19px; }
.sidebar-footer { display: flex; align-items: center; gap: 12px; margin: 16px; padding: 14px; border: 1px solid rgba(255,255,255,.09); border-radius: 15px; background: rgba(255,255,255,.055); }
.sidebar-footer.compact { justify-content: center; margin:10px 8px;padding:8px; }
.stage-orbit { display: grid; width: 34px; height: 34px; flex: 0 0 34px; place-items: center; border: 1px dashed rgba(86,183,220,.6); border-radius: 50%; }
.stage-orbit span { width: 9px; height: 9px; border-radius: 50%; background: #56b7dc; box-shadow: 0 0 0 5px rgba(86,183,220,.12); }
.stage-copy small { display: block; color: rgba(255,255,255,.42); font-size: 10px; }
.stage-copy strong { display: block; margin-top: 4px; color: #fff; font-size: 13px; }
.sidebar-logout { margin: 0 16px 16px; }
.logout-btn { display: flex; align-items: center; gap: 10px; width: 100%; padding: 11px 14px; border: 1px solid rgba(255,140,115,.25); border-radius: 12px; color: rgba(255,255,255,.72); background: rgba(255,140,115,.08); cursor: pointer; font-size: 13px; transition: .2s; }
.logout-btn:hover { color: #fff; background: rgba(255,140,115,.18); border-color: rgba(255,140,115,.5); }
.logout-btn .el-icon { font-size: 16px; }
.sidebar-logout-icon { display: flex; justify-content: center; margin: 0 8px 10px; }
.logout-btn-icon { display: grid; width: 36px; height: 36px; place-items: center; border: 1px solid rgba(255,140,115,.25); border-radius: 10px; color: rgba(255,255,255,.64); background: rgba(255,140,115,.08); cursor: pointer; transition: .2s; }
.logout-btn-icon:hover { color: #fff; background: rgba(255,140,115,.18); border-color: rgba(255,140,115,.5); }
.logout-btn-icon .el-icon { font-size: 17px; }
.menu-badge-dot { display: inline-block; width: 7px; height: 7px; margin-left: 6px; border-radius: 50%; background: #ff8166; vertical-align: middle; box-shadow: 0 0 0 3px rgba(255,129,102,.2); }
.content-shell { min-width: 0; min-height:0;height:100dvh;overflow:hidden }
.top-header { display: flex; align-items: center; justify-content: space-between; height: 58px; padding: 0 24px; border-bottom: 1px solid rgba(220,226,238,.85); background: rgba(255,255,255,.82); backdrop-filter: blur(16px); }
.header-left, .header-right { display: flex; align-items: center; gap: 18px; }
.page-identity strong,.page-identity span{display:block}.page-identity strong{color:var(--ink-800);font-size:14px}.page-identity span{margin-top:3px;color:var(--ink-400);font-size:8px;font-weight:800;letter-spacing:.14em}
.menu-trigger { width: 40px; padding: 0 !important; color: var(--ink-600); border: 1px solid var(--line); background: #fff; }
.mobile-trigger { display: none; }
.focus-chip { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid #dfeee9; border-radius: 999px; color: #318b70; background: #f4fbf8; font-size: 12px; font-weight: 650; }
.focus-pulse { width: 7px; height: 7px; border-radius: 50%; background: var(--mint); box-shadow: 0 0 0 4px rgba(57,185,145,.13); }
.user-pill { display: flex; align-items: center; gap: 10px; padding: 6px 9px 6px 7px; border: 1px solid var(--line); border-radius: 14px; color: var(--ink-800); background: #fff; cursor: pointer; box-shadow: 0 4px 14px rgba(30,45,84,.05); }
.avatar { display: grid; width: 36px; height: 36px; place-items: center; border-radius: 11px; color: #fff; background: linear-gradient(145deg, var(--primary), var(--sky)); font-size: 14px; font-weight: 800; }
.user-copy { min-width: 72px; text-align: left; line-height: 1.15; }
.user-copy strong, .user-copy small { display: block; }
.user-copy strong { max-width: 110px; overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.user-copy small { margin-top: 4px; color: var(--ink-400); font-size: 10px; }
.main-content { min-height:0;overflow-x: hidden;overflow-y:auto;padding: 20px 24px 30px; background: transparent;scrollbar-gutter:stable;overscroll-behavior-y:contain }
.main-content.is-fullscreen { overflow: hidden; padding: 0;scrollbar-gutter:auto; }
.main-content.is-workspace { display:flex;overflow:hidden;padding:0;scrollbar-gutter:auto; }
.main-content.is-workspace > * { width:100%;height:auto!important;min-width:0;min-height:0;align-self:stretch; }
.sidebar-scrim { display: none; }
.mobile-nav-launch{display:none}

@media (max-width: 900px) {
  .sidebar { position: fixed; inset: 0 auto 0 0; width: 268px !important; transform: translateX(-105%); transition: transform .28s ease; }
  .sidebar.is-mobile-open { transform: translateX(0); }
  .sidebar-scrim { position: fixed; z-index: 20; inset: 0; display: block; background: rgba(12,18,39,.46); backdrop-filter: blur(3px); }
  .desktop-trigger { display: none; }
  .sidebar-toggle { display:grid; }
  .mobile-trigger { display: inline-flex; }
  .mobile-nav-launch{position:fixed;z-index:18;left:10px;top:10px;display:grid;width:38px;height:38px;place-items:center;border:1px solid rgba(221,226,237,.9);border-radius:10px;color:#33415c;background:rgba(255,255,255,.92);box-shadow:0 7px 20px rgba(24,38,72,.12)}
  .top-header { height: 58px; padding: 0 14px; }
  .focus-chip, .user-copy { display: none; }
  .main-content { padding: 20px 16px 34px; }
  .main-content.is-workspace { overflow:auto; }
}
</style>
