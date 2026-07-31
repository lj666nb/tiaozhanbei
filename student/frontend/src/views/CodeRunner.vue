<template>
  <div class="code-runner-page">
    <div class="runner-header">
      <button type="button" class="runner-back" @click="goBack"><el-icon><ArrowLeft /></el-icon>返回</button>
      <div class="runner-heading">
        <span>QUICK CODE RUNNER</span>
        <h1>代码运行器</h1>
      </div>
      <div class="runner-language">{{ LANG_LABELS[language] || 'Python' }}</div>
    </div>

    <el-row :gutter="16" class="runner-body">
      <!-- 左侧：代码编辑器 -->
      <el-col :span="12">
        <el-card shadow="hover" class="editor-panel">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span><el-icon><Edit /></el-icon> 代码编辑区</span>
              <div style="display:flex;gap:8px">
                <el-button type="primary" @click="runCode" :loading="running">
                  <el-icon><VideoPlay /></el-icon> 运行
                </el-button>
                <el-button type="success" @click="copyCode">
                  <el-icon><CopyDocument /></el-icon> 复制
                </el-button>
                <el-button @click="resetCode">
                  <el-icon><RefreshRight /></el-icon> 重置
                </el-button>
              </div>
            </div>
          </template>
          <div class="editor-wrapper">
            <textarea v-model="code" class="code-editor" spellcheck="false"
              @keydown="handleKeydown" :placeholder="'// 在这里编写你的 ' + (LANG_LABELS[language] || 'Python') + ' 代码...'"></textarea>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：执行结果 -->
      <el-col :span="12">
        <el-card shadow="hover" class="output-panel">
          <template #header>
            <span><el-icon><DataLine /></el-icon> 执行结果</span>
          </template>

          <el-empty v-if="!result && !running" description="点击「运行」查看代码执行结果" :image-size="80" />

          <div v-if="running" class="running-hint">
            <el-icon class="is-loading" :size="24"><Loading /></el-icon>
            <span>代码执行中...</span>
          </div>

          <div v-if="result" class="result-panel">
            <div class="result-summary">
              <el-tag :type="statusTagType" size="large" effect="dark">{{ statusText }}</el-tag>
              <span class="exec-time">耗时 {{ result.execution_time }}s</span>
            </div>

            <div v-if="result.stdout" class="output-block">
              <h4>标准输出</h4>
              <pre class="output stdout">{{ result.stdout }}</pre>
            </div>
            <div v-if="result.stderr" class="output-block">
              <h4>错误输出</h4>
              <pre class="output stderr">{{ result.stderr }}</pre>
            </div>
            <div v-if="!result.stdout && !result.stderr && result.status === 'success'" class="output-block">
              <h4>标准输出</h4>
              <pre class="output stdout" style="color:#909399;font-style:italic">(程序正常退出，无输出内容)</pre>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { runCode as runCodeApi } from '../api/qa'
import { ElMessage } from 'element-plus'
import { copyToClipboard } from '../utils/clipboard'

const router = useRouter()

const code = ref('')
const language = ref('python')
const result = ref(null)
const running = ref(false)

const LANG_LABELS = { python: 'Python', py: 'Python', python3: 'Python', javascript: 'JavaScript', js: 'JavaScript', node: 'JavaScript', c: 'C', cpp: 'C++', 'c++': 'C++', cplusplus: 'C++', java: 'Java' }

onMounted(() => {
  // 从 sessionStorage 读取 QA 传来的代码和语言，读取后立即清除
  const storedCode = sessionStorage.getItem('qa-run-code')
  const storedLang = sessionStorage.getItem('qa-run-lang')
  if (storedCode) {
    code.value = storedCode
    sessionStorage.removeItem('qa-run-code')
  }
  if (storedLang) {
    language.value = storedLang
    sessionStorage.removeItem('qa-run-lang')
  }
})

const statusTagType = computed(() => {
  if (!result.value) return 'info'
  if (result.value.status === 'success') return 'success'
  if (result.value.status === 'timeout') return 'warning'
  return 'danger'
})

const statusText = computed(() => {
  if (!result.value) return ''
  if (result.value.status === 'success') return '执行成功'
  if (result.value.status === 'timeout') return '执行超时'
  return '执行失败'
})

async function runCode() {
  if (!code.value.trim()) {
    ElMessage.warning('请先输入代码')
    return
  }
  running.value = true
  result.value = null
  try {
    const data = await runCodeApi({ code: code.value, language: language.value })
    result.value = data
    if (data.status === 'success') {
      ElMessage.success('代码执行成功')
    } else if (data.status === 'timeout') {
      ElMessage.warning('代码执行超时')
    } else {
      ElMessage.error('代码执行出错，请检查错误输出')
    }
  } catch (e) {
    result.value = {
      stdout: '',
      stderr: e?.response?.data?.message || e?.message || '请求失败',
      exit_code: -1,
      status: 'error',
      execution_time: 0
    }
    ElMessage.error('代码执行失败')
  } finally {
    running.value = false
  }
}

async function copyCode() {
  if (!code.value.trim()) {
    ElMessage.warning('没有可复制的代码')
    return
  }
  const ok = await copyToClipboard(code.value)
  ElMessage[ok ? 'success' : 'warning'](ok ? '代码已复制到剪贴板' : '复制失败，请手动复制')
}

function resetCode() {
  code.value = ''
  result.value = null
}

function handleKeydown(e) {
  if (e.key === 'Tab') {
    e.preventDefault()
    const ta = e.target
    const start = ta.selectionStart
    const end = ta.selectionEnd
    code.value = code.value.substring(0, start) + '    ' + code.value.substring(end)
    setTimeout(() => { ta.selectionStart = ta.selectionEnd = start + 4 }, 0)
  }
}

function goBack() {
  router.push('/qa')
}
</script>

<style scoped>
.code-runner-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  max-width: 1480px;
  margin: 0 auto;
  padding: 14px 16px 18px;
}
.runner-header {
  display: grid;
  grid-template-columns: 110px 1fr 110px;
  align-items: center;
  min-height: 58px;
  margin-bottom: 12px;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255,255,255,.9);
  box-shadow: var(--shadow-sm);
}
.runner-back { display: flex; align-items: center; gap: 5px; width: fit-content; padding: 8px 10px; border: 0; color: var(--ink-600); background: transparent; cursor: pointer; }
.runner-back:hover { color: var(--primary); }
.runner-heading { text-align: center; }
.runner-heading span { color: var(--primary); font-size: 8px; font-weight: 800; letter-spacing: .15em; }
.runner-heading h1 { margin: 3px 0 0; color: var(--ink-950); font-size: 16px; }
.runner-language { justify-self: end; padding: 6px 10px; border-radius: 999px; color: var(--primary); background: #eef0fc; font-size: 10px; font-weight: 700; }
.runner-body {
  flex: 1;
  min-height: 0;
  margin: 0 !important;
}
.runner-body > :deep(.el-col) { height: 100%; }
.editor-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.editor-wrapper {
  flex: 1;
  min-height: 350px;
}
.code-editor {
  width: 100%;
  height: 100%;
  min-height: 350px;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 18px;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  outline: none;
  background: #151c2e;
  color: #d4d4d4;
  tab-size: 4;
}
.code-editor:focus {
  border-color: #409EFF;
}
.code-editor::placeholder {
  color: #6a6a6a;
}
.output-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.output-panel :deep(.el-card__body) {
  flex: 1;
  overflow-y: auto;
}
.running-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px;
  font-size: 15px;
  color: #909399;
}
.result-panel {
  margin-top: 0;
}
.result-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.exec-time {
  font-size: 12px;
  color: #909399;
}
.result-panel h4 {
  font-size: 13px;
  margin-bottom: 8px;
  color: #303133;
}
.output-block {
  margin-top: 12px;
}
.output {
  padding: 12px;
  border-radius: 6px;
  font-family: 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
}
.output.stdout {
  background: #f5f7fa;
  color: #303133;
  border: 1px solid #e8e8e8;
}
.output.stderr {
  background: #fef0f0;
  color: #F56C6C;
  border: 1px solid #fde2e2;
}
@media (max-width: 900px) {
  .code-runner-page { height: auto; min-height: 100%; }
  .runner-body > :deep(.el-col) { height: auto; }
  .runner-body { display: grid; gap: 14px; }
  .runner-header { grid-template-columns: auto 1fr auto; }
  .editor-panel, .output-panel { min-height: 430px; }
}
</style>
