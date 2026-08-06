<template>
  <div class="module-select-page">
    <section class="lab-hero">
      <div class="hero-copy">
        <span class="hero-eyebrow">AGENT ENGINEERING LAB</span>
        <h1>Agent 工程编程实验室</h1>
        <p>从一段对话代码开始，逐关搭出可恢复、可审计的完整 Agent。建议按阶段顺序学习。</p>
      </div>
      <div class="hero-progress" aria-label="实验室学习进度">
        <div class="progress-value">{{ totalCompleted }}<small>/{{ totalTasks }}</small></div>
        <div class="progress-copy">
          <strong>已完成关卡</strong>
          <span>{{ completionRate }}% 学习进度</span>
        </div>
        <div class="progress-track"><i :style="{ width: `${completionRate}%` }"></i></div>
      </div>
    </section>

    <div class="section-heading">
      <div>
        <span>LEARNING PATH</span>
        <h2>选择学习阶段</h2>
      </div>
      <p>{{ MODULES.length }} 个阶段 · {{ totalTasks }} 个工程关卡</p>
    </div>
    <div class="module-grid">
      <button
        v-for="mod in MODULES"
        :key="mod.id"
        type="button"
        class="module-card"
        @click="enterModule(mod)"
      >
        <div class="module-index">0{{ mod.id }}</div>
        <div class="card-heading">
          <h3 class="card-title">{{ mod.name }}</h3>
          <el-tag size="small" effect="plain">{{ mod.level }}</el-tag>
        </div>
        <p class="card-desc">{{ mod.description }}</p>
        <p class="card-project">阶段项目：{{ mod.project }}</p>
        <div class="module-progress">
          <div class="module-progress-track">
            <i :style="{ width: `${Math.round(getProgress(mod.id) / mod.taskCount * 100)}%` }"></i>
          </div>
          <span>{{ getProgress(mod.id) }}/{{ mod.taskCount }}</span>
        </div>
        <div class="card-footer">
          <span class="card-count">共 {{ mod.taskCount }} 个关卡</span>
          <span class="card-progress" :class="{ done: getProgress(mod.id) >= mod.taskCount, active: getProgress(mod.id) > 0 && getProgress(mod.id) < mod.taskCount }">
            {{ getProgress(mod.id) >= mod.taskCount ? '已完成' : getProgress(mod.id) > 0 ? '进行中 ' + getProgress(mod.id) + '/' + mod.taskCount : '未开始' }}
          </span>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { MODULES } from '../config/flagshipExercises'
import { recordStudyVisit } from '../api/learning'
import { getLabProgressOverview } from '../api/workspace'

const router = useRouter()
const progressData = ref({})
const totalTasks = computed(() => MODULES.reduce((sum, module) => sum + module.taskCount, 0))
const totalCompleted = computed(() => MODULES.reduce((sum, module) => sum + getProgress(module.id), 0))
const completionRate = computed(() => totalTasks.value ? Math.round(totalCompleted.value / totalTasks.value * 100) : 0)

async function loadProgress() {
  try {
    progressData.value = await getLabProgressOverview() || {}
  } catch (_) {
    progressData.value = {}
  }
}

function refreshProgressWhenVisible() {
  if (document.visibilityState === 'visible') loadProgress()
}

onMounted(() => {
  recordStudyVisit()
  loadProgress()
  window.addEventListener('focus', loadProgress)
  window.addEventListener('pageshow', loadProgress)
  document.addEventListener('visibilitychange', refreshProgressWhenVisible)
})

onBeforeUnmount(() => {
  window.removeEventListener('focus', loadProgress)
  window.removeEventListener('pageshow', loadProgress)
  document.removeEventListener('visibilitychange', refreshProgressWhenVisible)
})

/**
 * 获取模块完成进度。服务端是唯一可信来源，保证跨设备一致。
 */
function getProgress(moduleId) {
  const module = MODULES.find(item => item.id === moduleId)
  return (module?.tasks || []).filter(task => Boolean(progressData.value[task.id]?.verified)).length
}

/** 点击模块 → 进入关卡列表页 */
function enterModule(mod) {
  router.push({ name: 'TaskList', params: { moduleId: mod.id } })
}
</script>

<style scoped>
.module-select-page {
  min-height: 100%;
  padding: 4px 0 32px;
  max-width: 1120px;
  margin: 0 auto;
}
.lab-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 44px;
  align-items: center;
  overflow: hidden;
  margin-bottom: 26px;
  padding: 30px 34px;
  border-radius: 22px;
  color: #fff;
  background:
    radial-gradient(circle at 88% 12%, rgba(86, 183, 220, .28), transparent 28%),
    linear-gradient(120deg, #182544, #25345f 65%, #315271);
  box-shadow: 0 18px 42px rgba(24, 36, 76, .16);
}
.hero-eyebrow,
.section-heading span {
  color: #76c7e6;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .16em;
}
.hero-copy h1 {
  margin: 8px 0 9px;
  color: #fff;
  font-size: clamp(24px, 2.5vw, 34px);
  letter-spacing: -.035em;
}
.hero-copy p {
  max-width: 650px;
  margin: 0;
  color: rgba(255, 255, 255, .66);
  font-size: 13px;
  line-height: 1.75;
}
.hero-progress {
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, .12);
  border-radius: 16px;
  background: rgba(255, 255, 255, .07);
  backdrop-filter: blur(8px);
}
.progress-value {
  float: left;
  margin-right: 12px;
  font: 700 28px/1 Georgia, serif;
}
.progress-value small { color: rgba(255,255,255,.42); font-size: 14px; }
.progress-copy strong,
.progress-copy span { display: block; }
.progress-copy strong { font-size: 12px; }
.progress-copy span { margin-top: 4px; color: rgba(255,255,255,.48); font-size: 10px; }
.progress-track,
.module-progress-track {
  overflow: hidden;
  height: 5px;
  border-radius: 999px;
  background: rgba(255,255,255,.12);
}
.progress-track { clear: both; margin-top: 16px; }
.progress-track i,
.module-progress-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ff8166, #63c9e8);
  transition: width .35s ease;
}
.section-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  margin: 0 2px 14px;
}
.section-heading span { color: var(--primary); }
.section-heading h2 {
  margin: 5px 0 0;
  color: var(--ink-950);
  font-size: 19px;
}
.section-heading p { margin: 0 0 2px; color: var(--ink-400); font-size: 11px; }
.module-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.module-card {
  position: relative;
  display: flex;
  min-height: 210px;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
  text-align: left;
  background: #fff;
  border-radius: 16px;
  padding: 22px 24px 20px;
  cursor: pointer;
  border: 1px solid var(--line);
  transition: border-color .2s, box-shadow .2s, transform .2s;
}
.module-card:hover {
  border-color: #c9d0f0;
  box-shadow: 0 14px 30px rgba(30, 45, 84, .1);
  transform: translateY(-3px);
}
.module-card::after {
  position: absolute;
  right: 20px;
  bottom: 18px;
  color: #cbd2e2;
  font-size: 16px;
  content: '→';
}
.module-index {
  position: absolute;
  right: 22px;
  top: 45px;
  color: #f0f2f8;
  font: 700 46px/1 Georgia, serif;
  pointer-events: none;
}
.card-title {
  position: relative;
  z-index: 1;
  font-size: 16px;
  font-weight: 720;
  color: var(--ink-950);
  margin: 0 0 6px;
}
.card-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.card-project { position: relative; z-index: 1; margin: -2px 0 14px; color: var(--ink-800); font-size: 12px; font-weight: 700; }
.card-desc {
  position: relative;
  z-index: 1;
  max-width: 88%;
  font-size: 13px;
  color: var(--ink-400);
  line-height: 1.65;
  margin: 0 0 14px;
}
.module-progress { display: flex; align-items: center; gap: 10px; margin-top: auto; }
.module-progress-track { flex: 1; background: #edf0f7; }
.module-progress span { color: var(--ink-400); font-size: 10px; font-weight: 700; }
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding-right: 28px;
}
.card-count {
  font-size: 11px;
  color: var(--primary);
  font-weight: 700;
}
.card-progress {
  font-size: 12px;
  color: #c0c4cc;
}
.card-progress.active {
  color: #e6a23c;
}
.card-progress.done {
  color: #67C23A;
}
@media (max-width: 820px) {
  .module-select-page { padding: 0 0 24px; }
  .lab-hero { grid-template-columns: 1fr; gap: 20px; padding: 25px 22px; }
  .module-grid { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
  .section-heading p { display: none; }
  .module-card { min-height: 200px; padding: 20px; }
}
</style>
