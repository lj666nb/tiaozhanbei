import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { noAuth: true } },
  {
    path: '/',
    component: () => import('../components/AppLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '学习控制台' } },
      { path: 'my-courses', name: 'MyCourses', component: () => import('../views/MyCourses.vue'), meta: { title: '我的课程' } },
      { path: 'diagnosis', name: 'Diagnosis', component: () => import('../views/Diagnosis.vue'), meta: { title: '学情自测' } },
      { path: 'diagnosis/report/:id', name: 'DiagnosisReport', component: () => import('../views/DiagnosisReport.vue'), meta: { title: '诊断报告' } },
      { path: 'qa', name: 'QA', component: () => import('../views/QA.vue'), meta: { title: '智能答疑', workspace: true } },
      { path: 'messaging', name: 'Messaging', component: () => import('../views/Messaging.vue'), meta: { title: '师生通信' } },
      { path: 'learning-path', name: 'LearningPath', component: () => import('../views/LearningPath.vue'), meta: { title: '学习路径', workspace: true } },
      { path: 'task-quiz/:sessionId', name: 'TaskQuiz', component: () => import('../views/TaskQuiz.vue'), meta: { title: '专项练习' } },
      // 编程实验室（三级结构）
      { path: 'join-class', name: 'JoinClass', component: () => import('../views/JoinClass.vue'), meta: { title: '加入班级' } },
      { path: 'my-homework', name: 'MyHomework', component: () => import('../views/MyHomework.vue'), meta: { title: '我的作业' } },
      { path: 'code-lab', name: 'ModuleSelect', component: () => import('../views/ModuleSelect.vue'), meta: { title: '编程实验室' } },
      { path: 'code-lab/:moduleId', name: 'TaskList', component: () => import('../views/TaskList.vue'), meta: { title: '关卡列表', workspace: true } },
      { path: 'code-lab/:moduleId/:taskId', name: 'CodeLab', component: () => import('../views/CodeLab.vue'), meta: { title: 'Agent 项目工作台', fullscreen: true } },
      { path: 'lab-history', name: 'LabHistory', component: () => import('../views/LabHistory.vue'), meta: { title: '编程实验室 · 已完成记录' } },
      // 保留旧路由兼容
      { path: 'code-lab-old/:taskDay', name: 'CodeLabTask', component: () => import('../views/CodeLab.vue'), meta: { title: '编程实验室' } },
      { path: 'code-runner', name: 'CodeRunner', component: () => import('../views/CodeRunner.vue'), meta: { title: '代码运行器', workspace: true } },
      { path: 'error-book', name: 'ErrorBook', component: () => import('../views/ErrorBook.vue'), meta: { title: '错题本' } },
      { path: 'analytics', name: 'Analytics', component: () => import('../views/Analytics.vue'), meta: { title: '学情复盘' } },
      { path: 'resources', name: 'Resources', component: () => import('../views/Resources.vue'), meta: { title: '学习资源' } },
      { path: 'profile', name: 'Profile', component: () => import('../views/Profile.vue'), meta: { title: '个人中心' } },
    ]
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  // 不需要认证的页面直接放行
  if (to.meta.noAuth) {
    next()
    return
  }

  // 无本地 token → 强制去登录
  if (!userStore.token) {
    next('/login')
    return
  }

  // 有 token 但未验证过 → 调后端校验接口确认有效性
  if (!userStore._verified) {
    try {
      await userStore.verifyToken()
      userStore._verified = true
    } catch (e) {
      // token 无效或过期 → 清理并跳转登录
      userStore.logout()
      next('/login')
      return
    }
  }

  // 已登录用户访问 /login → 重定向到主页
  if (to.path === '/login') {
    next('/dashboard')
    return
  }

  next()
})

export default router
