<template>
  <div class="learning-path-page">
    <div class="path-toolbar">
      <div class="path-toolbar-copy">
        <h1>项目制学习路径</h1>
        <span>{{ pathData?.phases ? `${allTasks.length} 个递进项目 · 边学边练` : '生成你的第一条 Agent 学习路径' }}</span>
      </div>
      <div class="path-actions">
        <el-popconfirm
          v-if="pathData?.phases"
          title="确定删除当前学习路径吗？"
          confirm-button-text="确认删除"
          cancel-button-text="取消"
          @confirm="deletePath"
        >
          <template #reference><el-button plain>删除路径</el-button></template>
        </el-popconfirm>
        <el-button type="primary" @click="openGenerateDialog">生成/更新路径</el-button>
      </div>
    </div>

    <section v-if="pathData?.personalized_review?.items?.length" class="review-recommendation">
      <div class="review-signal"><el-icon><WarningFilled /></el-icon></div>
      <div class="review-copy">
        <span>PERSONALIZED REVIEW · 次日复习提醒</span>
        <h2>{{ pathData.personalized_review.title }}</h2>
        <p>{{ pathData.personalized_review.message }}</p>
      </div>
      <div class="review-actions">
        <el-button @click="continueTodayLearning">继续今天的学习</el-button>
        <el-button type="warning" @click="reviewWeakProgramming(pathData.personalized_review.items[0])">
          复习昨天的 {{ pathData.personalized_review.items[0].knowledge_tag }} 编程部分
        </el-button>
      </div>
    </section>

    <el-empty v-if="!pathData?.phases" description="尚未生成项目制学习目录">
      <el-button type="primary" @click="openGenerateDialog">生成完整课程目录</el-button>
    </el-empty>

    <div v-else class="course-layout">
      <aside class="course-tree-panel">
        <div class="tree-header">
          <div><span>教程目录</span><b>{{ completedProjectCount }}/{{ allTasks.length }} 个项目完成</b></div>
          <el-progress :percentage="overallPercent" :show-text="false" :stroke-width="5" />
        </div>

        <div class="course-tree" role="tree" aria-label="Agent 学习路径目录">
          <section v-for="(phase, phaseIndex) in pathData.phases" :key="phase.name" class="tree-phase">
            <button class="phase-node" @click="togglePhase(phaseIndex)">
              <span class="phase-index">{{ String(phaseIndex + 1).padStart(2, '0') }}</span>
              <span class="phase-copy"><b>{{ phase.name }}</b><small>{{ phase.personalized_review ? '系统动态推荐' : `${phase.tasks?.length || 0} 个递进项目` }}</small></span>
              <el-icon :class="{ rotated: isPhaseExpanded(phaseIndex) }"><ArrowRight /></el-icon>
            </button>
            <div v-show="isPhaseExpanded(phaseIndex)" class="phase-children">
              <div v-for="task in phase.tasks" :key="task.lab_id" class="task-tree-group">
                <button
                  :class="['task-node', { active: currentLearnTask?.lab_id === task.lab_id, verified: getTaskStatus(task).code }]"
                  @click="selectTask(task, phaseIndex)"
                >
                  <span class="tree-line-dot">{{ getTaskStatus(task).code ? '✓' : task.day }}</span>
                  <span class="task-node-copy"><b>{{ task.topic }}</b><small>{{ task.personalized_review ? `当前掌握度 ${Math.round((task.mastery_score || 0) * 100)}%` : `${task.framework} · ${task.duration}` }}</small></span>
                  <span class="task-stage-count">{{ getLabStages(task).length }}/{{ getTaskTotalStages(task) }}</span>
                </button>
                <nav v-if="currentLearnTask?.lab_id === task.lab_id" class="task-article-tree" aria-label="本节教程目录">
                  <button
                    v-for="item in articleOutline"
                    :key="item.id"
                    :class="[{ active: activeOutlineId === item.id }, `level-${item.level}`]"
                    @click="scrollToOutline(item)"
                  >
                    <span>{{ item.level === 3 ? '·' : '§' }}</span>{{ item.title }}
                  </button>
                  <span v-if="learnDialogLoading" class="tree-outline-loading">正在读取本节目录…</span>
                </nav>
              </div>
            </div>
          </section>
        </div>
      </aside>

      <main class="reader-content-column inline-reader-content">
        <div class="reader-page-nav">
          <button class="reader-page-link previous" :disabled="!previousLearnTask" @click="moveLearning(-1)">
            <small>← 上一节</small><b>{{ previousLearnTask?.topic || '已经是第一节' }}</b>
          </button>
          <div class="reader-progress-strip">
            <span>实验同步</span>
            <div v-for="stage in visibleStages" :key="stage.id" :class="{ passed: isStagePassed(currentLearnTask, stage.id) }" :title="stage.title"></div>
            <b>{{ getLabStages(currentLearnTask).length }}/{{ currentTotalStages }}</b>
          </div>
          <el-button class="reader-lab-button" type="primary" :loading="labLoading[currentLearnTask?.day]" @click="goToCodeLab(currentLearnTask)">
            <el-icon><Monitor /></el-icon>打开配套实验
          </el-button>
          <el-button size="small" text @click="openAIDialog">🤖 AI 生成教程</el-button>
          <button class="reader-page-link next" :disabled="!nextLearnTask" @click="moveLearning(1)">
            <small>下一节 →</small><b>{{ nextLearnTask?.topic || '已经是最后一节' }}</b>
          </button>
        </div>
        <!-- 来源标识 -->
        <div v-if="tutorialMeta.source_type && !learnDialogLoading" class="tutorial-source-badge" :class="'source-' + tutorialMeta.source_type">
          <el-tag v-if="tutorialMeta.source_type === 'seed'" type="success" size="small" effect="plain">📚 系统预置</el-tag>
          <el-tag v-else-if="tutorialMeta.source_type === 'user_modified'" type="warning" size="small" effect="plain">✏️ 我的修改</el-tag>
          <el-tag v-else-if="tutorialMeta.source_type === 'ai_generated'" type="primary" size="small" effect="plain">🤖 AI 生成</el-tag>
          <el-button v-if="tutorialMeta.source_type === 'user_modified'" type="danger" size="small" text @click="restoreSeedTutorial">恢复原始版本</el-button>
          <el-button v-if="tutorialMeta.source_type === 'ai_generated'" type="danger" size="small" text @click="deleteCustomTutorial">删除此教程</el-button>
        </div>

        <div v-if="learnDialogLoading" class="reader-loading"><el-icon class="is-loading" :size="30"><Loading /></el-icon><p>正在加载教程…</p></div>

        <!-- 编辑/预览切换 -->
        <div v-if="learnDialogContent && !learnDialogLoading" class="tutorial-edit-bar">
          <el-button size="small" :type="isEditing ? '' : 'primary'" text @click="toggleEditMode">
            {{ isEditing ? '👁 预览' : '✏️ 编辑' }}
          </el-button>
        </div>

        <div
          v-if="!learnDialogLoading && isEditing"
          class="learn-material-editor"
        >
          <el-input
            v-model="editContent"
            type="textarea"
            :rows="20"
            placeholder="使用 Markdown 格式编辑教程内容…"
            class="tutorial-textarea"
          />
          <div class="editor-actions">
            <el-button @click="isEditing = false">取消</el-button>
            <el-button type="primary" :loading="saveLoading" @click="saveEditedTutorial">保存修改</el-button>
          </div>
        </div>

        <div
          v-else-if="!learnDialogLoading"
          ref="materialRef"
          class="learn-material-content"
          tabindex="0"
          @scroll="handleArticleScroll"
          v-html="learnDialogContent"
        ></div>
      </main>

    </div>

    <el-dialog v-model="showDialog" title="选择学习模块" width="580px" :close-on-click-modal="false">
      <el-alert type="info" :closable="false" title="建议按顺序全选：先完成最小对话，再进入工具 Agent、状态图和端到端工程。" />
      <el-checkbox-group v-model="genForm.selectedModules" class="module-checkbox-group">
        <el-checkbox v-for="module in availableModules" :key="module" :label="module" border size="large" class="module-checkbox">
          <div class="module-label">{{ module }}</div>
          <div class="module-desc">{{ getModuleDesc(module) }}</div>
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading" :disabled="!genForm.selectedModules.length" @click="generateModulePath">生成树状学习目录</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showAIDialog" title="🤖 AI 生成教程" width="550px" :close-on-click-modal="false">
      <el-form :model="aiGenForm" label-position="top">
        <el-form-item label="知识点标识（英文/拼音，用于系统索引）">
          <el-input v-model="aiGenForm.knowledge_tag" placeholder="如: custom-rag-advanced" />
        </el-form-item>
        <el-form-item label="教程主题">
          <el-input v-model="aiGenForm.topic" placeholder="如: RAG高级检索技巧" />
        </el-form-item>
        <el-form-item label="学习目标（可选）">
          <el-input v-model="aiGenForm.goal" type="textarea" :rows="2" placeholder="想通过这篇教程达成什么学习目标？" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAIDialog = false">取消</el-button>
        <el-button type="primary" :loading="aiGenLoading" :disabled="!aiGenForm.knowledge_tag || !aiGenForm.topic" @click="doAIGenerate">开始生成</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useLearningStore } from '../stores/learning'
import { getLearningResource, recordStudyVisit, saveTutorial, deleteTutorial, generateAITutorial } from '../api/learning'
import { getLabProgressOverview, getLabWorkspace } from '../api/workspace'
import { bindCodeBlockActions, renderMarkdown } from '../composables/useCodeBlockRenderer'

const router = useRouter()
const store = useLearningStore()
const pathData = ref(null)
const progressData = ref({})
const labProgress = ref({})
const selectedLabId = ref('')
const expandedPhases = ref([])
const showDialog = ref(false)
const loading = ref(false)
const genForm = reactive({ selectedModules: [] })
const labLoading = reactive({})
const learnLoading = reactive({})
const learnDialogTitle = ref('')
const learnDialogContent = ref('')
const learnDialogLoading = ref(false)
const tutorialMeta = ref({ source_type: '', tutorial_id: null, parent_id: null })
const showAIDialog = ref(false)
const aiGenForm = reactive({ knowledge_tag: '', topic: '', goal: '' })
const aiGenLoading = ref(false)
const isEditing = ref(false)
const editContent = ref('')
const saveLoading = ref(false)
const currentLearnTask = ref(null)
const materialRef = ref(null)
const articleOutline = ref([])
const activeOutlineId = ref('')
let outlineScrollFrame = 0
let lessonLoadToken = 0

const availableModules = [
  '起步：第一段 AI 对话',
  'LangChain：链与工具 Agent',
  'LangGraph：状态与工作流',
  '工程项目：可上线客服 Agent',
]

const moduleDescs = {
  '起步：第一段 AI 对话': '认识模型 → 环境搭建 → 单轮对话 → 记忆与流式输出',
  'LangChain：链与工具 Agent': '提示链 → 工具契约 → create_agent 循环',
  'LangGraph：状态与工作流': 'StateGraph → 条件路由 → 检查点恢复',
  '工程项目：可上线客服 Agent': 'RAG → 有依据回答 → 端到端工程验收',
}

const stageCatalog = [
  { id: 'structure', title: '项目骨架', docHint: '跟教程创建目录与文件' },
  { id: 'environment', title: '虚拟环境', docHint: '建立独立 Python 环境' },
  { id: 'dependencies', title: '框架依赖', docHint: '安装本节 LangChain/LangGraph 包' },
  { id: 'first_llm_call', title: '先跑通再提取', docHint: '在 app.py 中先写出完整调用链，跑通后再提取函数' },
  { id: 'implementation', title: '核心代码', docHint: '边敲代码边理解新增 API' },
  { id: 'integration', title: '小项目运行', docHint: '把本节代码接入可运行程序' },
  { id: 'acceptance', title: '工程验收', docHint: '通过私有场景与能力验证' },
]

const allTasks = computed(() => {
  const tasks = []
  for (const [phaseIndex, phase] of (pathData.value?.phases || []).entries()) {
    for (const task of phase.tasks || []) tasks.push({ ...task, phaseName: phase.name, phaseIndex })
  }
  return tasks
})

const selectedTask = computed(() => allTasks.value.find(task => task.lab_id === selectedLabId.value) || allTasks.value[0] || null)
const completedProjectCount = computed(() => allTasks.value.filter(task => getTaskStatus(task).allDone).length)
const overallPercent = computed(() => allTasks.value.length ? Math.round(completedProjectCount.value / allTasks.value.length * 100) : 0)
const currentLearnIndex = computed(() => allTasks.value.findIndex(task => task.lab_id === currentLearnTask.value?.lab_id))
const previousLearnTask = computed(() => currentLearnIndex.value > 0 ? allTasks.value[currentLearnIndex.value - 1] : null)
const nextLearnTask = computed(() => {
  const index = currentLearnIndex.value
  return index >= 0 && index < allTasks.value.length - 1 ? allTasks.value[index + 1] : null
})
const currentTotalStages = computed(() => {
  const lid = currentLearnTask.value?.lab_id
  if (!lid || !labProgress.value?.[lid]) return 6
  return labProgress.value[lid].total_stages || 6
})
const visibleStages = computed(() => {
  const lid = currentLearnTask.value?.lab_id
  const stageIds = labProgress.value?.[lid]?.stage_ids
  if (!stageIds || !stageIds.length) return stageCatalog
  return stageCatalog.filter(s => stageIds.includes(s.id))
})

onMounted(async () => {
  recordStudyVisit()
  await loadPath()
  if (selectedTask.value) await loadLearningMaterial(selectedTask.value, false)
})

async function loadPath() {
  try {
    const [path, labs] = await Promise.all([store.fetchPath(), getLabProgressOverview().catch(() => ({}))])
    if (path?.path_data?.phases?.length) {
      pathData.value = path.path_data
      progressData.value = path.progress || {}
      labProgress.value = labs || {}
      if (!selectedLabId.value && allTasks.value.length) selectedLabId.value = allTasks.value[0].lab_id
      const phaseIndexes = path.path_data.phases.map((_, index) => index)
      if (!expandedPhases.value.length) expandedPhases.value = phaseIndexes
    } else {
      pathData.value = null
      progressData.value = {}
      labProgress.value = labs || {}
    }
  } catch (_) {
    pathData.value = null
  }
}

function getModuleDesc(name) { return moduleDescs[name] || '' }
function taskKey(task) { return `${task?.day}-${task?.topic}` }

function getTaskStatus(task) {
  if (!task) return { learn: false, code: false, done: 0, allDone: false }
  const completed = progressData.value?.completed_tasks || {}
  if (Array.isArray(completed)) {
    const done = completed.includes(taskKey(task))
    return { learn: done, code: done, done: done ? 2 : 0, allDone: done }
  }
  const status = completed[taskKey(task)] || {}
  const learn = Boolean(status.learn)
  const code = Boolean(status.code) || isStagePassed(task, 'acceptance')
  return { learn, code, done: Number(learn) + Number(code), allDone: learn && code }
}

function getLabStages(task) {
  if (!task?.lab_id) return []
  return labProgress.value?.[task.lab_id]?.completed_stages || []
}
function getTaskTotalStages(task) {
  if (!task?.lab_id) return 6
  return labProgress.value?.[task.lab_id]?.total_stages || 6
}

function isStagePassed(task, stageId) { return getLabStages(task).includes(stageId) }
function isPhaseExpanded(index) { return expandedPhases.value.includes(index) }
function togglePhase(index) {
  expandedPhases.value = isPhaseExpanded(index)
    ? expandedPhases.value.filter(item => item !== index)
    : [...expandedPhases.value, index]
}

async function selectTask(task, phaseIndex) {
  selectedLabId.value = task.lab_id
  if (!isPhaseExpanded(phaseIndex)) expandedPhases.value.push(phaseIndex)
  if (currentLearnTask.value?.lab_id === task.lab_id && learnDialogContent.value) {
    if (materialRef.value) materialRef.value.scrollTo({ top: 0, behavior: 'smooth' })
    return
  }
  await loadLearningMaterial(task, true)
}

async function openGenerateDialog() {
  await loadPath()
  genForm.selectedModules = pathData.value?.modules_selected ? [...pathData.value.modules_selected] : [...availableModules]
  showDialog.value = true
}

async function generateModulePath() {
  if (!genForm.selectedModules.length) return ElMessage.warning('请至少选择一个阶段')
  loading.value = true
  try {
    await store.createPath('', '', '标准', null, [...genForm.selectedModules])
    selectedLabId.value = ''
    await loadPath()
    if (selectedTask.value) await loadLearningMaterial(selectedTask.value, false)
    showDialog.value = false
    ElMessage.success('树状项目课程已生成')
  } finally { loading.value = false }
}

async function deletePath() {
  try {
    await store.removePath()
    pathData.value = null
    progressData.value = {}
    selectedLabId.value = ''
    currentLearnTask.value = null
    learnDialogContent.value = ''
    articleOutline.value = []
    ElMessage.success('学习路径已删除')
  } catch (_) { ElMessage.error('删除失败，请重试') }
}

async function goToCodeLab(task) {
  if (!task) return
  if (!getTaskStatus(task).learn) return ElMessage.warning('请先打开本节教程，再进入配套实验')
  labLoading[task.day] = true
  try {
    await router.push({ name: 'CodeLab', params: { moduleId: task.module_id, taskId: task.lab_id } })
  } finally { labLoading[task.day] = false }
}

async function goToLearning(task) {
  if (!task) return
  await loadLearningMaterial(task, true)
}

function moveLearning(offset) {
  const target = offset < 0 ? previousLearnTask.value : nextLearnTask.value
  if (target) loadLearningMaterial(target, true)
}

async function continueTodayLearning() {
  const task = allTasks.value.find(item => !item.personalized_review) || allTasks.value[0]
  if (task) await selectTask(task, task.phaseIndex)
  materialRef.value?.focus({ preventScroll: true })
}

async function reviewWeakProgramming(item) {
  if (!item?.lab_id) return
  await router.push({ name: 'CodeLab', params: { moduleId: item.module_id, taskId: item.lab_id } })
}

function rebuildArticleOutline() {
  const container = materialRef.value
  if (!container) return
  const labId = currentLearnTask.value?.lab_id || 'lesson'
  articleOutline.value = [...container.querySelectorAll('h2, h3')].map((heading, index) => {
    const id = `lesson-${labId}-section-${index + 1}`
    heading.id = id
    return { id, title: heading.textContent?.trim() || `章节 ${index + 1}`, level: Number(heading.tagName.slice(1)) }
  })
  activeOutlineId.value = articleOutline.value[0]?.id || ''
}

function scrollToOutline(item) {
  const container = materialRef.value
  const target = container?.querySelector(`[id="${item.id}"]`)
  if (!container || !target) return
  const top = target.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop - 22
  container.scrollTo({ top, behavior: 'smooth' })
  activeOutlineId.value = item.id
}

function handleArticleScroll() {
  if (outlineScrollFrame) return
  outlineScrollFrame = window.requestAnimationFrame(() => {
    outlineScrollFrame = 0
    const container = materialRef.value
    if (!container || !articleOutline.value.length) return
    const threshold = container.getBoundingClientRect().top + 90
    let active = articleOutline.value[0]
    for (const item of articleOutline.value) {
      const heading = container.querySelector(`[id="${item.id}"]`)
      if (heading && heading.getBoundingClientRect().top <= threshold) active = item
      else break
    }
    activeOutlineId.value = active.id
  })
}

async function loadLearningMaterial(task, markLearn = false) {
  if (!task) return

  // Guard: warn before discarding unsaved edits
  if (isEditing.value && editContent.value !== '') {
    try {
      await ElMessageBox.confirm('你有未保存的修改，切换教程将丢失这些内容。确定要放弃吗？', '未保存的修改', {
        confirmButtonText: '放弃修改',
        cancelButtonText: '继续编辑',
        type: 'warning'
      })
    } catch {
      return // user cancelled — stay on current content
    }
    isEditing.value = false
  }

  const loadToken = ++lessonLoadToken
  currentLearnTask.value = task
  selectedLabId.value = task.lab_id
  articleOutline.value = []
  activeOutlineId.value = ''
  learnDialogLoading.value = true
  learnLoading[task.day] = true
  try {
    const [resource, workspace] = await Promise.all([
      getLearningResource(task.knowledge || task.topic),
      getLabWorkspace(task.lab_id).catch(() => null),
    ])
    if (loadToken !== lessonLoadToken) return
    if (!resource?.content) throw new Error('该教程尚未准备好')
    const completedStages = workspace?.completed_stages || getLabStages(task) || []
    if (workspace) {
      labProgress.value = {
        ...labProgress.value,
        [task.lab_id]: {
          completed_stages: completedStages,
          total_stages: workspace.course?.stages?.length || 6,
          stage_ids: (workspace.course?.stages || []).map(s => s.id),
        },
      }
    }
    learnDialogTitle.value = resource.matched_tag || task.topic
    tutorialMeta.value = {
      source_type: resource.source_type || 'file',
      tutorial_id: resource.tutorial_id || null,
      parent_id: resource.parent_id || null
    }
    editContent.value = resource.content || ''
    learnDialogContent.value = renderMarkdown(resource.content, {
      completedStages,
      stages: workspace?.course?.stages || stageCatalog,
    })
    // The article is behind v-if/v-else, so reveal it before binding the
    // delegated copy handler to the rendered code blocks.
    learnDialogLoading.value = false
    await nextTick()
    if (materialRef.value) {
      materialRef.value.scrollTop = 0
      bindCodeBlockActions(materialRef.value)
      rebuildArticleOutline()
    }
    if (markLearn && !getTaskStatus(task).learn) {
      await store.updateProgress(taskKey(task), true, 'learn')
      const current = progressData.value.completed_tasks || {}
      progressData.value = {
        ...progressData.value,
        completed_tasks: { ...current, [taskKey(task)]: { ...(current[taskKey(task)] || {}), learn: true } },
      }
    }
  } catch (error) {
    if (loadToken !== lessonLoadToken) return
    ElMessage.error(error.message || '获取教程失败')
  } finally {
    if (loadToken === lessonLoadToken) learnDialogLoading.value = false
    learnLoading[task.day] = false
  }
}

function handleCheckpointClick(stage) {
  if (isStagePassed(selectedTask.value, stage.id)) return ElMessage.success('该检查点已在编程实验室通过')
  goToLearning(selectedTask.value)
}

function openAIDialog() {
  aiGenForm.knowledge_tag = ''
  aiGenForm.topic = ''
  aiGenForm.goal = ''
  showAIDialog.value = true
}

async function doAIGenerate() {
  aiGenLoading.value = true
  try {
    const result = await generateAITutorial({
      knowledge_tag: aiGenForm.knowledge_tag,
      topic: aiGenForm.topic,
      goal: aiGenForm.goal
    })
    showAIDialog.value = false
    ElMessage.success('AI 教程已生成！')
    tutorialMeta.value = {
      source_type: 'ai_generated',
      tutorial_id: result.tutorial_id,
      parent_id: null
    }
    learnDialogTitle.value = result.title
    editContent.value = result.content || ''
    learnDialogContent.value = renderMarkdown(result.content)
    learnDialogLoading.value = false
    await nextTick()
    if (materialRef.value) {
      materialRef.value.scrollTop = 0
      bindCodeBlockActions(materialRef.value)
      rebuildArticleOutline()
    }
  } catch (e) {
    ElMessage.error('AI 生成失败: ' + (e.response?.data?.message || e.message))
  } finally {
    aiGenLoading.value = false
  }
}

async function restoreSeedTutorial() {
  try {
    await ElMessageBox.confirm('将放弃你的修改，恢复为系统预置版本。确定？', '恢复原始版本', { type: 'warning' })
    await deleteTutorial(currentLearnTask.value.knowledge || currentLearnTask.value.topic)
    ElMessage.success('已恢复为系统预置版本')
    tutorialMeta.value = { source_type: 'seed', tutorial_id: null, parent_id: null }
    await loadLearningMaterial(currentLearnTask.value, false)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('恢复失败')
  }
}

async function deleteCustomTutorial() {
  try {
    await ElMessageBox.confirm('将删除此 AI 生成的教程。确定？', '删除教程', { type: 'warning' })
    await deleteTutorial(currentLearnTask.value.knowledge || currentLearnTask.value.topic)
    ElMessage.success('已删除')
    tutorialMeta.value = { source_type: 'seed', tutorial_id: null, parent_id: null }
    await loadLearningMaterial(currentLearnTask.value, false)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

function toggleEditMode() {
  if (!isEditing.value) {
    isEditing.value = true
  } else {
    isEditing.value = false
  }
}

async function saveEditedTutorial() {
  if (!editContent.value.trim()) return ElMessage.warning('内容不能为空')
  saveLoading.value = true
  try {
    const knowledgeTag = currentLearnTask.value.knowledge || currentLearnTask.value.topic
    await saveTutorial(knowledgeTag, {
      title: learnDialogTitle.value,
      content: editContent.value,
      source_type: tutorialMeta.value.source_type || 'ai_generated'
    })
    ElMessage.success('已保存')
    isEditing.value = false
    learnDialogContent.value = renderMarkdown(editContent.value)
    await nextTick()
    if (materialRef.value) {
      materialRef.value.scrollTop = 0
      bindCodeBlockActions(materialRef.value)
      rebuildArticleOutline()
    }
    if (tutorialMeta.value.source_type === 'seed') {
      tutorialMeta.value.source_type = 'user_modified'
    }
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saveLoading.value = false
  }
}

</script>

<style scoped>
.learning-path-page { width:100%;max-width:none;margin:0; }
.path-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:54px;margin:0;padding:8px 16px;border-bottom:1px solid #e2e7f1;background:#f8faff}.path-toolbar-copy{min-width:0}.path-toolbar h1{margin:0;color:#17213a;font-size:18px;letter-spacing:-.02em}.path-toolbar-copy span{display:block;margin-top:3px;color:#8a95a8;font-size:11px}.path-actions{display:flex;gap:8px;flex-shrink:0}.path-actions :deep(.el-button){min-height:34px;padding-inline:13px!important}
.course-layout{height:calc(100vh - 220px);min-height:620px;max-height:860px;display:grid;grid-template-columns:280px minmax(0,1fr) 240px;gap:0;align-items:stretch;overflow:hidden}.course-tree-panel,.inline-reader-content,.inline-reader-outline{min-height:0;border:0;border-radius:0;background:#fff;box-shadow:none}.course-tree-panel{display:flex;overflow:hidden;flex-direction:column;border-right:1px solid #e2e7f1;background:#f4f2ed}.tree-header{flex:0 0 auto;padding:17px 18px;border-bottom:1px solid #dedbd4;background:#fff}.tree-header>div{display:flex;justify-content:space-between;margin-bottom:10px}.tree-header span{color:#536b40;font-weight:800}.tree-header b{color:#7c889e;font-size:10px}.course-tree{min-height:0;flex:1;overflow:auto;overscroll-behavior:contain;padding:8px}.tree-phase{margin-bottom:6px}.phase-node,.task-node{width:100%;display:flex;align-items:center;border:0;background:transparent;text-align:left;cursor:pointer}.phase-node{gap:9px;padding:11px 9px;border-radius:7px}.phase-node:hover{background:#e9ece5}.phase-index{color:#6f945b;font:800 11px/1 monospace}.phase-copy{flex:1;min-width:0}.phase-copy b,.phase-copy small,.task-node-copy b,.task-node-copy small{display:block}.phase-copy b{color:#34432e;font-size:12px}.phase-copy small{margin-top:3px;color:#8b9386;font-size:10px}.phase-node svg{font-size:11px;transition:transform .2s}.phase-node svg.rotated{transform:rotate(90deg)}.phase-children{position:relative;margin-left:20px;padding-left:12px;border-left:1px solid #d6dbd1}.task-tree-group{margin:2px 0}.task-node{position:relative;gap:9px;padding:9px 8px;border-radius:6px}.task-node:hover,.task-node.active{background:#e5eddf}.task-node.active{box-shadow:inset 3px 0 #79a961}.tree-line-dot{display:grid;width:22px;height:22px;flex:0 0 22px;place-items:center;border-radius:7px;color:#71806a;background:#e2e6dd;font-size:10px;font-weight:800}.task-node.verified .tree-line-dot{color:#fff;background:#5f8557}.task-node-copy{flex:1;min-width:0}.task-node-copy b{overflow:hidden;color:#36435d;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.task-node-copy small{margin-top:3px;color:#8c9487;font-size:9px}.task-stage-count{color:#7b8776;font-size:9px}.task-article-tree{margin:2px 0 7px 14px;padding:4px 0 5px 9px;border-left:1px dashed #b9c5b1}.task-article-tree button{display:flex;align-items:flex-start;gap:5px;width:100%;padding:5px 6px;border:0;border-radius:4px;color:#6e786b;background:transparent;font-size:9px;line-height:1.45;text-align:left;cursor:pointer}.task-article-tree button:hover,.task-article-tree button.active{color:#45603b;background:#e3eadf}.task-article-tree button.level-3{padding-left:16px}.task-article-tree button span{color:#83a46f;font-weight:800}.tree-outline-loading{display:block;padding:7px;color:#8a9487;font-size:9px}
.project-detail{padding:26px}.detail-breadcrumb{color:#8994a7;font-size:11px}.detail-breadcrumb span{margin:0 7px}.project-title-row{display:flex;justify-content:space-between;gap:20px;margin-top:18px}.framework-chip{display:inline-flex;padding:5px 9px;border-radius:12px;color:#4c5fd0;background:#eef0ff;font-size:10px;font-weight:750}.project-title-row h2{margin:11px 0 8px;color:#10182f;font-size:25px}.project-title-row p{max-width:650px;margin:0;color:#65728a;line-height:1.65}.project-status-seal{width:80px;height:80px;display:grid;place-content:center;flex:0 0 80px;border:6px solid #e5e8f3;border-radius:50%;text-align:center}.project-status-seal.done{border-color:#a7dfcc}.project-status-seal strong,.project-status-seal span{display:block}.project-status-seal strong{color:#4859cb;font-size:19px}.project-status-seal span{margin-top:2px;color:#8a96aa;font-size:8px}.outcome-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:22px 0}.outcome-grid>div{padding:14px;border:1px solid #e5e9f2;border-radius:12px;background:#fafbfe}.outcome-grid span,.outcome-grid b{display:block}.outcome-grid span{color:#8995a8;font-size:10px}.outcome-grid b{margin-top:6px;color:#283550;font-size:12px;line-height:1.55}.learning-rhythm{margin-top:20px}.section-heading{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:10px}.section-heading span{color:#6576dd;font-size:9px;font-weight:800;letter-spacing:.12em}.section-heading h3{margin:4px 0 0;color:#17213a}.section-heading small{color:#909bad}.checkpoint-list{display:grid;grid-template-columns:1fr 1fr;gap:8px}.checkpoint-row{display:flex;align-items:center;gap:10px;padding:11px;border:1px solid #e3e7f0;border-radius:10px;background:#fff;text-align:left;cursor:pointer}.checkpoint-row:hover{border-color:#c7cdf0}.checkpoint-row.passed{border-color:#bce4d6;background:#f3fbf8}.checkpoint-index{display:grid;width:25px;height:25px;flex:0 0 25px;place-items:center;border-radius:50%;color:#738198;background:#edf0f5;font-size:10px;font-weight:800}.checkpoint-row.passed .checkpoint-index{color:#fff;background:#39b991}.checkpoint-row>span:nth-child(2){flex:1}.checkpoint-row b,.checkpoint-row small{display:block}.checkpoint-row b{color:#34415b;font-size:11px}.checkpoint-row small{margin-top:3px;color:#8a95a8;font-size:9px}.checkpoint-row em{color:#8793a7;font-size:9px;font-style:normal}.checkpoint-row.passed em{color:#249670}.detail-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:22px;padding-top:18px;border-top:1px solid #e8ebf2}
.path-overview{padding:18px}.overview-card{padding:17px;border-radius:14px;background:linear-gradient(140deg,#182344,#293a72);color:#fff}.overview-label{font-size:10px;letter-spacing:.1em;opacity:.65}.overview-card>strong{display:block;margin:7px 0;font-size:34px}.overview-card p{font-size:11px;line-height:1.6;opacity:.75}.overview-section{margin:18px 0}.overview-section h4{color:#25334f}.milestone-item{display:flex;gap:9px;margin:10px 0}.milestone-item>span{display:grid;width:22px;height:22px;flex:0 0 22px;place-items:center;border-radius:7px;color:#596bd7;background:#edf0ff;font-size:10px;font-weight:800}.milestone-item p{margin:2px 0;color:#637088;font-size:11px;line-height:1.45}
.module-checkbox-group{display:flex;flex-direction:column;gap:8px;margin-top:18px}.module-checkbox{width:100%;height:auto!important;margin:0!important;padding:13px 15px}.module-label{color:#273550;font-weight:700}.module-desc{margin-top:4px;color:#8a95a8;font-size:11px}
.reader-content-column{min-width:0;min-height:0;display:flex;overflow:hidden;flex-direction:column;background:#fff}.inline-reader-content{border-right:1px solid #e2e7f1}.reader-page-nav{height:64px;display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:12px;flex:0 0 64px;padding:0 18px;border-bottom:1px solid #e1e5ec;background:#fcfcfd}.reader-page-link{min-width:0;padding:6px 8px;border:0;border-radius:6px;background:transparent;text-align:left;cursor:pointer}.reader-page-link.next{text-align:right}.reader-page-link:hover:not(:disabled){background:#f0f3f8}.reader-page-link:disabled{cursor:default;opacity:.35}.reader-page-link small,.reader-page-link b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.reader-page-link small{color:#78995f;font-size:9px}.reader-page-link b{margin-top:3px;color:#4d586d;font-size:10px}.reader-progress-strip{display:flex;align-items:center;gap:5px;padding:8px 12px;border-radius:16px;background:#f3f5f8}.reader-progress-strip>span{margin-right:2px;color:#68758c;font-size:9px;font-weight:700}.reader-progress-strip>div{width:17px;height:4px;border-radius:9px;background:#d9dee7}.reader-progress-strip>div.passed{background:#72a35b}.reader-progress-strip>b{color:#53617a;font-size:9px}.reader-loading{display:grid;min-height:0;place-content:center;flex:1;color:#7b879a;text-align:center}.learn-material-content{min-height:0;flex:1 1 0;overflow-x:hidden;overflow-y:auto;overscroll-behavior:contain;scroll-behavior:smooth;padding:34px clamp(28px,5vw,68px) 80px;color:#303b53;background:#fff;font-size:15px;line-height:1.85;outline:none}.learn-material-content:focus-visible{box-shadow:inset 0 0 0 2px rgba(83,100,216,.22)}.learn-material-content :deep(h1){margin:0 0 20px;padding-bottom:12px;border-bottom:2px solid #8daf72;color:#111b32;font-size:30px}.learn-material-content :deep(h2){scroll-margin-top:20px;margin:32px 0 13px;padding-left:12px;border-left:4px solid #8daf72;color:#1f2c48;font-size:21px}.learn-material-content :deep(h3){scroll-margin-top:20px;margin:23px 0 10px;color:#5f8557;font-size:17px}.learn-material-content :deep(p){margin:10px 0}.learn-material-content :deep(code:not(pre code)){padding:2px 6px;border-radius:5px;color:#d54f76;background:#f4f0f4}.learn-material-content :deep(table){width:100%;margin:16px 0;border-collapse:collapse;font-size:13px}.learn-material-content :deep(th){padding:10px;border:1px solid #dfe4ed;color:#fff;background:#3d4147;text-align:left}.learn-material-content :deep(td){padding:9px 10px;border:1px solid #e1e5ed}.learn-material-content :deep(blockquote){margin:16px 0;padding:11px 16px;border-left:4px solid #8daf72;background:#f3f7f0;color:#53657a}.learn-material-content :deep(ul),.learn-material-content :deep(ol){padding-left:24px}.reader-outline{min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:14px;background:#f4f2ed}.outline-status-card{padding:15px;border:1px solid #dde2d8;border-radius:8px;background:#fff}.outline-status-card>span{display:block;color:#74806d;font-size:10px}.outline-status-card h3{margin:7px 0 10px;color:#34432e;font-size:14px;line-height:1.45}.outline-status-card>strong{display:block;margin:5px 0 9px;color:#45603b;font-size:28px}.outline-status-card>strong small{font-size:12px}.outline-stage-dots{display:flex;gap:4px;margin-bottom:12px}.outline-stage-dots i{height:5px;flex:1;border-radius:6px;background:#dfe3dc}.outline-stage-dots i.passed{background:#79a961}.outline-status-card .el-button{width:100%}.reader-outline-heading{margin:18px 3px 8px;color:#536b40;font-size:11px;font-weight:800;letter-spacing:.08em}.outline-links{display:flex;flex-direction:column;gap:2px}.outline-links button{display:flex;align-items:flex-start;gap:7px;width:100%;padding:7px 8px;border:0;border-radius:5px;color:#566172;background:transparent;font-size:10px;line-height:1.45;text-align:left;cursor:pointer}.outline-links button:hover,.outline-links button.active{color:#45603b;background:#e3eadf}.outline-links button.level-3{padding-left:20px;color:#7a8492}.outline-links button span{color:#83a46f;font-weight:800}.outline-note{margin-top:18px;padding:12px;border-left:3px solid #8daf72;color:#788174;background:#e9eee5;font-size:9px;line-height:1.6}
@media(max-width:1100px){.course-layout{grid-template-columns:270px minmax(0,1fr)}.inline-reader-outline{display:none}}@media(max-width:900px){.path-toolbar{align-items:flex-start}.path-toolbar-copy span{display:none}.course-layout{height:auto;max-height:none;display:block;overflow:visible}.course-tree-panel{height:360px}.inline-reader-content{height:calc(100dvh - 110px);min-height:600px;margin-top:12px}.reader-page-nav{grid-template-columns:1fr 1fr}.reader-progress-strip{display:none}.learn-material-content{padding:26px 20px 70px}}
.course-layout{grid-template-columns:300px minmax(0,1fr)}
.reader-page-nav{grid-template-columns:minmax(0,1fr) auto auto auto minmax(0,1fr)}
.reader-lab-button{flex-shrink:0}
.learning-path-page{display:flex;height:100%;min-height:0;overflow:hidden;flex-direction:column}
.course-layout{height:auto;min-height:0;max-height:none;flex:1}
.review-recommendation{display:flex;align-items:center;gap:16px;margin:-4px 0 18px;padding:17px 20px;border:1px solid #f1d7a5;border-radius:15px;background:linear-gradient(120deg,#fffaf0,#fff 70%);box-shadow:0 8px 24px rgba(118,85,24,.06)}
.review-signal{display:grid;width:42px;height:42px;flex:0 0 42px;place-items:center;border-radius:13px;color:#b97918;background:#fff0ce;font-size:20px}.review-copy{min-width:0;flex:1}.review-copy span{color:#ad741d;font-size:9px;font-weight:800;letter-spacing:.12em}.review-copy h2{margin:4px 0;color:#42341f;font-size:17px}.review-copy p{margin:0;color:#7d6b4d;font-size:12px}.review-actions{display:flex;gap:8px;flex-shrink:0}
@media(max-width:900px){.learning-path-page{height:auto;overflow:visible}.reader-page-nav{grid-template-columns:1fr auto auto 1fr}.reader-progress-strip{display:none}.reader-lab-button{padding-inline:10px}}
.tutorial-source-badge{display:flex;align-items:center;gap:8px;padding:6px 18px;border-bottom:1px solid #e8ecf1;background:#fafbfd}.tutorial-source-badge .el-button{margin-left:4px;font-size:11px}
.tutorial-edit-bar{display:flex;align-items:center;gap:8px;padding:4px 18px;border-bottom:1px solid #eef1f5;background:#fcfdfe}
.learn-material-editor{min-height:0;flex:1 1 0;display:flex;flex-direction:column;padding:24px clamp(28px,5vw,68px) 24px;overflow-y:auto}.learn-material-editor .tutorial-textarea{flex:1;min-height:400px}.learn-material-editor .tutorial-textarea :deep(textarea){font-family:'JetBrains Mono','Fira Code',monospace;font-size:13px;line-height:1.7;color:#2d3748;background:#fafbfc;border-color:#e2e8f0}.editor-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:14px;padding-top:12px;border-top:1px solid #eef1f5}
@media(max-width:900px){.tutorial-source-badge{flex-wrap:wrap;padding:6px 12px}}
</style>
