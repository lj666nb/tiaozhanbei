<template>
  <main class="login-page">
    <section class="login-story">
      <div class="story-top">
        <div class="story-brand"><span class="story-mark">π</span><strong>智学引擎</strong></div>
        <span class="story-edition">AI LEARNING ATLAS · 2026</span>
      </div>

      <div class="story-content">
        <span class="story-kicker">每一次理解，都是新坐标</span>
        <h1>让知识从<br><em>散点</em>连成路径。</h1>
        <p>诊断盲区、规划任务、即时答疑。你的学习节奏，由你掌握，AI 只负责照亮下一步。</p>

        <div class="learning-orbit" aria-hidden="true">
          <div class="orbit orbit-one"><span class="orbit-label label-one">诊断</span></div>
          <div class="orbit orbit-two"><span class="orbit-label label-two">理解</span></div>
          <div class="orbit orbit-three"><span class="orbit-label label-three">实践</span></div>
          <div class="orbit-center"><span>AI</span><small>学习坐标</small></div>
        </div>
      </div>

      <div class="story-foot">
        <span>个性化路径</span><i></i><span>可追踪成长</span><i></i><span>随时答疑</span>
      </div>
    </section>

    <section class="login-panel">
      <div class="panel-inner">
        <div class="mobile-brand"><span>π</span> 智学引擎</div>
        <div class="login-header">
          <span class="panel-kicker">WELCOME BACK</span>
          <h2>{{ activeTab === 'login' ? '继续你的学习旅程' : '建立你的学习坐标' }}</h2>
          <p>{{ activeTab === 'login' ? '登录后，从上次停下的地方继续。' : '告诉我们你的目标，生成专属学习路径。' }}</p>
        </div>

        <el-tabs v-model="activeTab" class="login-tabs" stretch>
          <el-tab-pane label="账号登录" name="login">
            <el-form :model="loginForm" :rules="loginRules" ref="loginFormRef" label-position="top">
              <el-form-item label="用户名" prop="username">
                <el-input v-model="loginForm.username" placeholder="请输入用户名" prefix-icon="User" size="large" />
              </el-form-item>
              <el-form-item label="密码" prop="password">
                <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" prefix-icon="Lock" size="large" show-password @keyup.enter="handleLogin" />
              </el-form-item>
              <el-form-item><el-button type="primary" size="large" @click="handleLogin" :loading="loading" class="submit-button">进入学习空间 <el-icon><Right /></el-icon></el-button></el-form-item>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="创建账号" name="register">
            <el-form :model="regForm" :rules="regRules" ref="regFormRef" label-position="top" class="register-form">
              <div class="form-grid">
                <el-form-item label="用户名" prop="username"><el-input v-model="regForm.username" placeholder="至少 3 个字符" size="large" /></el-form-item>
                <el-form-item label="昵称" prop="nickname"><el-input v-model="regForm.nickname" placeholder="希望如何称呼你" size="large" /></el-form-item>
              </div>
              <el-form-item label="密码" prop="password"><el-input v-model="regForm.password" type="password" placeholder="至少 6 位" size="large" show-password /></el-form-item>
              <div class="form-grid">
                <el-form-item label="技术/职业背景">
                  <el-input v-model="regForm.programming_background" placeholder="如：Java 业务开发工程师" size="large" />
                </el-form-item>
                <el-form-item label="相关经验（年）">
                  <el-input-number v-model="regForm.years_experience" :min="0" :max="60" size="large" style="width:100%" />
                </el-form-item>
              </div>
              <el-form-item label="希望 AI 如何讲解">
                <el-select v-model="regForm.answer_preference" size="large" style="width:100%">
                  <el-option label="直观简洁 · 先给结论" value="直观简洁" />
                  <el-option label="分步清晰 · 代码配解释" value="分步清晰" />
                  <el-option label="工程深入 · 重点讲业务取舍" value="工程深入" />
                </el-select>
              </el-form-item>
              <div class="form-grid">
                <el-form-item label="学习阶段" prop="learning_stage">
                  <el-select v-model="regForm.learning_stage" placeholder="选择阶段" size="large" style="width:100%">
                    <el-option label="入门 · 零基础开始" value="入门" /><el-option label="进阶 · 已有基础" value="进阶" /><el-option label="高阶 · 深度学习" value="高阶" />
                  </el-select>
                </el-form-item>
                <el-form-item label="学习目标" prop="learning_goal">
                  <el-select v-model="regForm.learning_goal" placeholder="选择目标" size="large" style="width:100%">
                    <el-option label="课程预习与复习" value="课程预习" /><el-option label="期末备考冲刺" value="期末备考" /><el-option label="智能体开发实操" value="开发实操" /><el-option label="竞赛项目落地" value="竞赛项目" /><el-option label="深度学习研究" value="深度学习" />
                  </el-select>
                </el-form-item>
              </div>
              <el-form-item><el-button type="primary" size="large" @click="handleRegister" :loading="loading" class="submit-button">创建学习账号 <el-icon><Right /></el-icon></el-button></el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
        <div class="trust-note"><el-icon><Lock /></el-icon> 学习记录仅用于生成你的个性化建议</div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()
const activeTab = ref('login')
const loading = ref(false)

const loginForm = reactive({ username: '', password: '' })
const loginRules = { username: [{ required: true, message: '请输入用户名' }], password: [{ required: true, message: '请输入密码' }] }
const regForm = reactive({
  username: '', password: '', nickname: '', learning_stage: '入门', learning_goal: '课程预习',
  programming_background: '', years_experience: 0, answer_preference: '分步清晰'
})
const regRules = {
  username: [{ required: true, message: '请输入用户名', min: 3 }],
  password: [{ required: true, message: '请输入密码', min: 6 }],
  nickname: [{ required: true, message: '请输入昵称' }],
  learning_stage: [{ required: true, message: '请选择学习阶段' }],
  learning_goal: [{ required: true, message: '请选择学习目标' }]
}
const loginFormRef = ref(null)
const regFormRef = ref(null)

async function handleLogin() {
  if (!loginForm.username.trim() || !loginForm.password.trim()) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await userStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch(e) { ElMessage.error(e.response?.data?.detail || e.message || '登录失败，请检查网络连接') }
  finally { loading.value = false }
}

async function handleRegister() {
  if (!regForm.username.trim() || !regForm.password.trim() || !regForm.nickname.trim()) {
    ElMessage.warning('请填写完整的注册信息')
    return
  }
  if (regForm.password.length < 6) {
    ElMessage.warning('密码至少需要6位')
    return
  }
  loading.value = true
  try {
    await userStore.register(regForm)
    ElMessage.success('注册成功，请登录')
    // 清空登录表单并切换到登录 tab
    loginForm.username = regForm.username
    loginForm.password = ''
    regForm.username = ''
    regForm.password = ''
    regForm.nickname = ''
    regForm.programming_background = ''
    regForm.years_experience = 0
    regForm.answer_preference = '分步清晰'
    activeTab.value = 'login'
  } catch(e) { ElMessage.error(e.response?.data?.detail || e.message || '注册失败，请稍后重试') }
  finally { loading.value = false }
}
</script>

<style scoped>
.login-page { display: grid; min-height: 100vh; grid-template-columns: minmax(430px, 46%) 1fr; background: #fff; }
.login-story { position: relative; display: flex; min-height: 100vh; flex-direction: column; overflow: hidden; padding: 42px 52px 34px; color: #fff; background: radial-gradient(circle at 72% 38%, rgba(86,183,220,.2), transparent 25%), linear-gradient(150deg, #172345, #11182f 66%, #242044); }
.login-story::after { position: absolute; inset: 0; opacity: .13; background-image: linear-gradient(rgba(255,255,255,.12) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.12) 1px, transparent 1px); background-size: 36px 36px; content: ""; mask-image: linear-gradient(to bottom, black, transparent 80%); }
.story-top, .story-content, .story-foot { position: relative; z-index: 2; }
.story-top { display: flex; align-items: center; justify-content: space-between; }
.story-brand { display: flex; align-items: center; gap: 11px; font-size: 16px; letter-spacing: .08em; }
.story-mark, .mobile-brand span { display: grid; width: 38px; height: 38px; place-items: center; border: 1px solid rgba(255,255,255,.3); border-radius: 50%; font-family: Georgia, serif; font-size: 19px; }
.story-edition { color: rgba(255,255,255,.4); font-size: 9px; font-weight: 700; letter-spacing: .18em; }
.story-content { width: min(570px, 100%); margin: auto 0; padding: 64px 0 20px; }
.story-kicker, .panel-kicker { display: block; margin-bottom: 18px; color: #79c7e5; font-size: 11px; font-weight: 750; letter-spacing: .18em; }
.story-content h1 { font-size: clamp(44px, 5vw, 72px); font-weight: 720; line-height: 1.08; letter-spacing: -.06em; }
.story-content h1 em { color: #ff927a; font-family: Georgia, "Songti SC", serif; font-weight: 500; }
.story-content > p { width: min(480px, 90%); margin-top: 24px; color: rgba(239,243,255,.62); font-size: 15px; line-height: 1.9; }
.learning-orbit { position: relative; width: 330px; height: 205px; margin: 40px 0 0 36px; }
.orbit { position: absolute; inset: 50% auto auto 50%; border: 1px solid rgba(121,199,229,.34); border-radius: 50%; transform: translate(-50%,-50%) rotate(-12deg); }
.orbit-one { width: 150px; height: 72px; }.orbit-two { width: 235px; height: 116px; }.orbit-three { width: 330px; height: 166px; }
.orbit-label { position: absolute; display: grid; width: 40px; height: 40px; place-items: center; border: 1px solid rgba(255,255,255,.25); border-radius: 50%; color: #fff; background: #263766; box-shadow: 0 0 0 7px rgba(255,255,255,.035); font-size: 10px; transform: rotate(12deg); }
.label-one { right: -20px; top: 12px; }.label-two { left: 5px; bottom: -4px; }.label-three { right: 36px; bottom: -8px; background: #9a4f56; }
.orbit-center { position: absolute; left: 50%; top: 50%; display: grid; width: 86px; height: 86px; place-items: center; border-radius: 50%; background: linear-gradient(145deg, #5368ea, #3f4fc6); box-shadow: 0 16px 40px rgba(22,33,95,.45); transform: translate(-50%,-50%); }
.orbit-center span { font-family: Georgia, serif; font-size: 24px; }.orbit-center small { margin-top: -22px; color: rgba(255,255,255,.55); font-size: 9px; }
.story-foot { display: flex; align-items: center; gap: 13px; color: rgba(255,255,255,.4); font-size: 10px; letter-spacing: .08em; }.story-foot i { width: 3px; height: 3px; border-radius: 50%; background: #ff8166; }
.login-panel { display: grid; min-width: 0; place-items: center; padding: 46px 7vw; background: radial-gradient(circle at 100% 0%, #f0f2ff, transparent 30%), #fff; }
.panel-inner { width: min(520px, 100%); }
.mobile-brand { display: none; }
.login-header { margin-bottom: 20px; }.panel-kicker { margin-bottom: 12px; color: var(--primary); }.login-header h2 { color: var(--ink-950); font-size: clamp(28px, 3vw, 38px); line-height: 1.2; letter-spacing: -.045em; }.login-header p { margin-top: 10px; color: var(--ink-400); font-size: 14px; }
.login-tabs { margin-top: 24px; }.login-tabs :deep(.el-tabs__nav-wrap::after) { height: 1px; background: var(--line); }.login-tabs :deep(.el-tabs__item) { height: 48px; font-size: 14px; }.login-tabs :deep(.el-tabs__content) { overflow: visible; padding-top: 20px; }
.login-tabs :deep(.el-form-item__label) { color: var(--ink-600); font-size: 12px; font-weight: 680; }.login-tabs :deep(.el-input__wrapper), .login-tabs :deep(.el-select__wrapper) { min-height: 46px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }.submit-button { width: 100%; height: 48px; margin-top: 4px; }.submit-button .el-icon { margin-left: 8px; }
.trust-note { display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 10px; color: var(--ink-400); font-size: 11px; }
@media (max-width: 980px) { .login-page { grid-template-columns: 1fr; }.login-story { display: none; }.login-panel { min-height: 100vh; padding: 38px 22px; }.mobile-brand { display: flex; align-items: center; gap: 10px; margin-bottom: 54px; color: var(--ink-950); font-weight: 800; letter-spacing: .08em; }.mobile-brand span { width: 34px; height: 34px; color: #fff; border: 0; background: var(--primary); }.panel-inner { width: min(500px, 100%); } }
@media (max-width: 560px) { .form-grid { grid-template-columns: 1fr; gap: 0; }.mobile-brand { margin-bottom: 38px; }.login-header h2 { font-size: 27px; } }
</style>
