<template>
  <div class="profile-page">
    <PageHero
      eyebrow="PERSONAL WORKSPACE"
      title="个人中心"
      description="管理学习画像、AI 记忆和模型能力。配置会用于个性化答疑、学习路径与知识库检索。"
      icon="User"
    >
      <template #meta>
        <el-tag effect="plain">{{ userStore.user?.learning_stage || '入门' }}阶段</el-tag>
        <el-tag :type="deepseekConfigured ? 'success' : 'warning'" effect="plain">{{ deepseekConfigured ? '模型已配置' : '待配置模型' }}</el-tag>
      </template>
    </PageHero>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover" class="profile-identity-card">
          <el-avatar :size="80"><el-icon :size="40"><UserFilled /></el-icon></el-avatar>
          <h2 style="margin:12px 0 4px">{{ userStore.user?.nickname || '未设置' }}</h2>
          <el-tag>{{ userStore.user?.learning_stage || '入门' }} 学习者</el-tag>
          <p style="color:#909399;margin-top:8px">{{ userStore.user?.learning_goal || '未设置学习目标' }}</p>
          <el-divider />
          <el-descriptions :column="1" size="small">
            <el-descriptions-item label="用户名">{{ userStore.user?.username }}</el-descriptions-item>
            <el-descriptions-item label="年级">{{ userStore.user?.grade || '未设置' }}</el-descriptions-item>
            <el-descriptions-item label="技术背景">{{ userStore.user?.programming_background || '未设置' }}</el-descriptions-item>
            <el-descriptions-item label="相关经验">{{ userStore.user?.years_experience || 0 }} 年</el-descriptions-item>
            <el-descriptions-item label="讲解偏好">{{ userStore.user?.answer_preference || '分步清晰' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header><div class="page-title"><el-icon><Setting /></el-icon> 个人信息设置</div></template>
          <el-form :model="form" label-width="100px" style="max-width:500px">
            <el-form-item label="昵称"><el-input v-model="form.nickname" /></el-form-item>
            <el-form-item label="年级/专业"><el-input v-model="form.grade" placeholder="如：大一/计算机科学" /></el-form-item>
            <el-form-item label="技术/职业背景"><el-input v-model="form.programming_background" placeholder="如：Java 业务开发工程师" /></el-form-item>
            <el-form-item label="相关经验">
              <el-input-number v-model="form.years_experience" :min="0" :max="60" />
              <span style="margin-left:8px;color:#909399">年</span>
            </el-form-item>
            <el-form-item label="AI讲解偏好">
              <el-select v-model="form.answer_preference" style="width:100%">
                <el-option label="直观简洁 · 先给结论" value="直观简洁" />
                <el-option label="分步清晰 · 代码配解释" value="分步清晰" />
                <el-option label="工程深入 · 重点讲业务取舍" value="工程深入" />
              </el-select>
            </el-form-item>
            <el-form-item label="学习阶段">
              <el-radio-group v-model="form.learning_stage">
                <el-radio label="入门">入门</el-radio>
                <el-radio label="进阶">进阶</el-radio>
                <el-radio label="高阶">高阶</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="学习目标">
              <el-select v-model="form.learning_goal" style="width:100%">
                <el-option label="课程预习与复习" value="课程预习" />
                <el-option label="期末备考冲刺" value="期末备考" />
                <el-option label="智能体开发实操" value="开发实操" />
                <el-option label="竞赛项目落地" value="竞赛项目" />
                <el-option label="深度学习研究" value="深度学习" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSave" :loading="saving">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="hover" style="margin-top:20px" class="memory-overview-card">
          <template #header><div class="page-title"><el-icon><Connection /></el-icon> AI 个性化记忆</div></template>
          <div class="profile-summary-card">
            <span>整体用户画像</span>
            <p>{{ memoryOverview.profile_summary || '画像仍在形成中' }}</p>
          </div>
          <div class="memory-stats">
            <div><span>短期记忆</span><strong>当前对话</strong><small>{{ memoryOverview.short_term || '即时消息窗口' }}</small></div>
            <div><span>中期记忆</span><strong>{{ memoryOverview.medium_term_sessions || 0 }} 个会话</strong><small>保存多轮对话摘要</small></div>
            <button class="memory-stat-button" type="button" @click="memoryDialogVisible = true">
              <span>长期记忆</span><strong>{{ memoryOverview.long_term_memories?.length || 0 }} 条</strong>
              <small>{{ memoryOverview.vector_store?.enabled ? 'Chroma 向量检索已启用' : '配置嵌入 Key 后启用向量检索' }}</small>
              <em>查看具体记忆 →</em>
            </button>
          </div>
          <div v-if="memoryOverview.long_term_memories?.length" class="memory-facts">
            <el-tag
              v-for="item in memoryOverview.long_term_memories.slice(0, 8)"
              :key="`${item.category}-${item.fact_key}`"
              effect="plain"
              :class="['memory-tag', { 'memory-tag-interest': item.category === 'interest' }]"
              @click="openKnowledgeDetail(item)"
            >
              {{ item.fact_value }} · {{ item.mention_count }} 次
              <em v-if="item.category === 'interest'" style="color:#67C23A">查看讲解 →</em>
            </el-tag>
          </div>
        </el-card>

        <el-dialog v-model="memoryDialogVisible" title="我的长期记忆" width="760px" class="memory-dialog">
          <div class="memory-dialog-toolbar">
            <div class="memory-dialog-note"><el-icon><Connection /></el-icon>记忆会自动新增、冲突更新和过期清理；你始终可以手动修正。</div>
            <el-button type="primary" size="small" @click="beginCreateMemory">新增记忆</el-button>
          </div>
          <el-form v-if="memoryEditing" class="memory-editor" label-width="72px">
            <el-form-item label="分类">
              <el-select v-model="memoryForm.category">
                <el-option label="用户画像" value="profile" />
                <el-option label="兴趣方向" value="interest" />
                <el-option label="学习目标" value="goal" />
                <el-option label="偏好" value="preference" />
                <el-option label="工具环境" value="tooling" />
              </el-select>
            </el-form-item>
            <el-form-item label="记忆名称"><el-input v-model="memoryForm.fact_key" placeholder="如：学校、专业、当前工具" /></el-form-item>
            <el-form-item label="记忆内容"><el-input v-model="memoryForm.fact_value" type="textarea" :rows="2" /></el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="memorySaving" @click="saveMemoryEditor">保存记忆</el-button>
              <el-button @click="memoryEditing = false">取消</el-button>
            </el-form-item>
          </el-form>
          <el-empty v-if="!memoryOverview.long_term_memories?.length" description="还没有形成长期记忆" />
          <div v-else class="memory-detail-list">
            <article
              v-for="item in memoryOverview.long_term_memories"
              :key="`${item.category}-${item.fact_key}`"
              :class="{ selected: selectedMemory === item }"
              @click="openKnowledgeDetail(item)"
            >
              <div class="memory-detail-head">
                <el-tag size="small" effect="plain">{{ memoryCategoryLabel(item.category) }}</el-tag>
                <span>被提及 {{ item.mention_count }} 次 · 调用 {{ item.access_count }} 次</span>
              </div>
              <h4>{{ item.fact_value }}</h4>
              <p>记忆键：{{ item.fact_key }} · 置信度 {{ Math.round((item.confidence || 0) * 100) }}%</p>
              <small>最近确认：{{ formatMemoryTime(item.last_seen_at) }}</small>
              <div class="memory-detail-action">
                <el-button v-if="item.category === 'interest'" type="success" size="small" plain>查看AI详细讲解</el-button>
                <el-button size="small" plain @click.stop="beginEditMemory(item)">编辑</el-button>
                <el-button size="small" type="danger" plain @click.stop="removeMemoryItem(item)">删除</el-button>
              </div>
            </article>
          </div>
        </el-dialog>

        <!-- ── 知识点详细讲解弹窗 ── -->
        <el-dialog
          v-model="knowledgeDetailDialog"
          :title="'📖 ' + (knowledgeDetail.fact_value || knowledgeDetail.fact_key || '知识点讲解')"
          width="800px"
          class="knowledge-detail-dialog"
          destroy-on-close
        >
          <div v-if="knowledgeDetailLoading" class="knowledge-detail-loading">
            <el-icon class="is-loading" :size="28"><Cpu /></el-icon>
            <p>正在从历史对话中总结讲解，请稍候…</p>
          </div>
          <div v-else class="knowledge-detail-body">
            <div v-if="knowledgeDetail.conversation_count > 0" class="knowledge-detail-meta">
              <el-tag type="info" size="small">来源：{{ knowledgeDetail.conversation_count }} 个历史对话</el-tag>
              <el-tag type="info" size="small">共 {{ knowledgeDetail.source_messages_count }} 条相关消息</el-tag>
            </div>
            <div class="knowledge-detail-content" v-html="renderMarkdown(knowledgeDetail.summary)"></div>
            <div v-if="knowledgeDetail.sources.length" class="knowledge-detail-sources">
              <h4>📚 参考对话</h4>
              <ul>
                <li v-for="(s, i) in knowledgeDetail.sources" :key="i">
                  {{ s.title }}（{{ s.msg_count }} 条消息）
                </li>
              </ul>
            </div>
          </div>
        </el-dialog>

        <el-card shadow="hover" style="margin-top:20px" class="deepseek-quick-card">
          <template #header>
            <div class="page-title">
              <el-icon><Cpu /></el-icon> 🔑 DeepSeek API Key 快速配置
              <el-tag v-if="deepseekConfigured" type="success" size="small" style="margin-left:12px">已配置</el-tag>
            </div>
          </template>
          <p style="color:#909399;font-size:13px;margin-bottom:16px">
            输入您的 DeepSeek API Key 即可一键启用，自动配置接口地址和模型。<br/>
            <a href="https://platform.deepseek.com/api_keys" target="_blank" style="color:#409EFF">获取 DeepSeek API Key →</a>
          </p>
          <el-form label-width="80px" style="max-width:500px">
            <el-form-item label="API Key">
              <el-input v-model="deepseekApiKey" type="password" show-password placeholder="sk-..." size="large" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="large" @click="handleSaveDeepSeek" :loading="deepseekSaving" style="width:100%">
                🚀 保存并启用 DeepSeek
              </el-button>
            </el-form-item>
            <el-form-item v-if="deepseekConfigured">
              <el-button type="danger" plain @click="handleResetDeepSeek">重置 DeepSeek 配置</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="hover" style="margin-top:20px" class="embedding-quick-card">
          <template #header>
            <div class="page-title">
              <el-icon><Collection /></el-icon> 📚 知识库嵌入 API Key 快速配置
              <el-tag v-if="embeddingConfigured" type="success" size="small" style="margin-left:12px">已配置</el-tag>
            </div>
          </template>
          <p style="color:#909399;font-size:13px;margin-bottom:16px">
            本地使用 GPU 和 BGE 构建向量库；线上仅调用 SiliconFlow 的同名模型生成 Query 向量。<br/>
            <b>固定模型：BAAI/bge-large-zh-v1.5（1024 维）</b><br/>
            <a href="https://cloud.siliconflow.cn/account/ak" target="_blank" style="color:#409EFF">获取 SiliconFlow API Key →</a>
          </p>
          <el-form label-width="80px" style="max-width:500px">
            <el-form-item label="API Key">
              <el-input v-model="embeddingApiKey" type="password" show-password placeholder="sk-..." size="large" />
            </el-form-item>
            <el-form-item>
              <el-button type="success" size="large" @click="handleSaveEmbedding" :loading="embeddingSaving" style="width:100%">
                📚 保存并启用知识库
              </el-button>
            </el-form-item>
            <el-form-item v-if="embeddingConfigured">
              <el-button type="danger" plain @click="handleResetEmbedding">重置嵌入配置</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="hover" style="margin-top:20px" class="search-quick-card">
          <template #header>
            <div class="page-title">
              <el-icon><Search /></el-icon> 🔍 Tavily 高级搜索配置
              <el-tag v-if="searchApiConfigured" type="success" size="small" style="margin-left:12px">已配置</el-tag>
            </div>
          </template>
          <p style="color:#909399;font-size:13px;margin-bottom:16px">
            输入 Tavily API Key，平台固定使用 <b>advanced</b> 搜索并在结果进入模型前做相关性、语言、来源和重复内容过滤。<br/>
            <span style="font-size:12px;color:#b0b3bb">
              未配置时不会回退到 Bing；AI 若需要联网，会明确提示「Tavily 高级搜索暂不可用」。
            </span>
            <br/><a href="https://app.tavily.com/" target="_blank" style="color:#409EFF">获取 Tavily API Key →</a>
          </p>
          <el-form label-width="80px" style="max-width:500px">
            <el-form-item label="API Key">
              <el-input v-model="searchApiKey" type="password" show-password placeholder="tvly-…" size="large" />
            </el-form-item>
            <el-form-item>
              <el-button type="warning" size="large" @click="handleSaveSearchApi" :loading="searchApiSaving" style="width:100%">
                🔍 保存并启用 Tavily Advanced
              </el-button>
            </el-form-item>
            <el-form-item v-if="searchApiConfigured">
              <el-button type="danger" plain @click="handleResetSearchApi">重置检索配置</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="hover" style="margin-top:20px">
          <template #header><div class="page-title"><el-icon><Cpu /></el-icon> AI大模型配置（高级）</div></template>
          <p style="color:#909399;font-size:13px;margin-bottom:16px">高级自定义配置，支持OpenAI及兼容接口（如Azure、本地模型等）。如仅需使用 DeepSeek，请在上方快速配置。</p>
          <el-form v-if="!llmEditing" label-width="120px" style="max-width:500px">
            <el-form-item label="配置状态">
              <el-tag :type="llmConfig.is_configured ? 'success' : 'info'">
                {{ llmConfig.is_configured ? '已自定义配置' : '使用系统默认（未配置）' }}
              </el-tag>
            </el-form-item>
            <el-form-item v-if="llmConfig.is_configured" label="服务商">
              <el-tag size="small">{{ llmConfig.provider === 'deepseek' ? 'DeepSeek' : llmConfig.provider === 'openai' ? 'OpenAI' : llmConfig.provider || '自定义' }}</el-tag>
            </el-form-item>
            <el-form-item v-if="llmConfig.is_configured" label="模型名称">
              <span>{{ llmConfig.model_name }}</span>
            </el-form-item>
            <el-form-item v-if="llmConfig.is_configured" label="API地址">
              <span style="font-size:12px;color:#909399">{{ llmConfig.base_url }}</span>
            </el-form-item>
            <el-form-item v-if="llmConfig.is_configured" label="API Key">
              <span style="font-size:12px;color:#909399">{{ llmConfig.api_key || '未设置' }}</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="llmEditing = true">修改配置</el-button>
              <el-button v-if="llmConfig.is_configured" type="danger" plain @click="handleResetLLM">重置为默认</el-button>
            </el-form-item>
          </el-form>
          <el-form v-else label-width="120px" style="max-width:500px">
            <el-form-item label="服务商">
              <el-select v-model="llmForm.provider" @change="onProviderChange" style="width:200px">
                <el-option label="OpenAI" value="openai" />
                <el-option label="DeepSeek" value="deepseek" />
                <el-option label="自定义" value="custom" />
              </el-select>
              <el-button v-if="llmForm.provider !== 'deepseek'" size="small" type="success" plain @click="quickSetupDeepSeek" style="margin-left:8px">⚡ 快速填充DeepSeek</el-button>
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="llmForm.api_key" type="password" show-password placeholder="sk-..." />
              <div style="font-size:12px;color:#909399">支持OpenAI、DeepSeek等兼容接口的API Key</div>
            </el-form-item>
            <el-form-item label="接口地址">
              <el-input v-model="llmForm.base_url" placeholder="https://api.openai.com" />
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="llmForm.model_name" placeholder="gpt-4o" />
              <div style="font-size:12px;margin-top:4px">
                <span style="color:#909399">点击快速选择：</span>
                <el-tag v-for="m in currentModelSuggestions" :key="m" size="small" :type="llmForm.model_name === m ? 'primary' : 'info'" @click="llmForm.model_name = m" style="cursor:pointer;margin:2px">{{ m }}</el-tag>
              </div>
            </el-form-item>
            <el-form-item label="嵌入 API Key">
              <el-input v-model="llmForm.embedding_api_key" type="password" show-password placeholder="sk-..." />
              <div style="font-size:12px;color:#909399">
                SiliconFlow · BAAI/bge-large-zh-v1.5，用于线上 Query 向量化。
                <a href="https://cloud.siliconflow.cn/account/ak" target="_blank" style="color:#409EFF">获取 Key →</a>
              </div>
            </el-form-item>
            <el-form-item label="图片生成 Key">
              <el-input v-model="llmForm.image_api_key" type="password" show-password placeholder="r8_..." />
              <div style="font-size:12px;color:#909399">Replicate API Key，用于AI配图生成。<a href="https://replicate.com/account/api-tokens" target="_blank" style="color:#409EFF">免费注册获取 →</a></div>
            </el-form-item>
            <el-form-item label="温度参数">
              <el-slider v-model="llmForm.temperature" :min="0" :max="2" :step="0.1" show-stops style="width:200px" />
              <span style="margin-left:12px;color:#909399;font-size:12px">{{ llmForm.temperature }} (越高越随机)</span>
            </el-form-item>
            <el-form-item label="最大Token数">
              <el-input-number v-model="llmForm.max_tokens" :min="256" :max="32768" :step="256" size="small" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSaveLLM" :loading="llmSaving">保存配置</el-button>
              <el-button @click="llmEditing = false">取消</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="hover" style="margin-top:20px">
          <template #header><div class="page-title"><el-icon><Tools /></el-icon> 自定义学习设置</div></template>
          <el-form label-width="140px" style="max-width:500px">
            <el-form-item label="答疑讲解深度">
              <el-radio-group v-model="settings.explanationLevel">
                <el-radio label="beginner">入门通俗</el-radio>
                <el-radio label="standard">标准分步</el-radio>
                <el-radio label="advanced">拔高拓展</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="每日学习提醒">
              <el-switch v-model="settings.reminder" active-text="开启" inactive-text="关闭" />
            </el-form-item>
            <el-form-item label="学习节奏">
              <el-slider v-model="settings.pace" :min="1" :max="5" :step="1" show-stops style="width:200px" />
              <span style="margin-left:12px;color:#909399">{{ ['轻松','适中','标准','紧凑','冲刺'][settings.pace-1] }}</span>
            </el-form-item>
            <el-form-item><el-button @click="saveSettings">保存偏好</el-button></el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useUserStore } from '../stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getLLMConfig, saveLLMConfig, resetLLMConfig, saveEmbeddingConfig, saveSearchConfig } from '../api/llm'
import { getMemoryOverview, getKnowledgeDetail, createMemory, updateMemory, deleteMemory } from '../api/qa'
import { marked } from 'marked'
import PageHero from '../components/PageHero.vue'

const userStore = useUserStore()
const saving = ref(false)
const llmEditing = ref(false)
const llmSaving = ref(false)
const deepseekSaving = ref(false)
const deepseekApiKey = ref('')
const deepseekConfigured = ref(false)
const embeddingSaving = ref(false)
const embeddingApiKey = ref('')
const embeddingConfigured = ref(false)
const searchApiSaving = ref(false)
const searchApiKey = ref('')
const searchApiConfigured = ref(false)
const memoryOverview = ref({})
const memoryDialogVisible = ref(false)
const selectedMemory = ref(null)
const memoryEditing = ref(false)
const memorySaving = ref(false)
const editingMemoryId = ref(null)
const memoryForm = reactive({ category: 'profile', fact_key: '', fact_value: '' })
const form = reactive({
  nickname: userStore.user?.nickname || '',
  grade: userStore.user?.grade || '',
  learning_stage: userStore.user?.learning_stage || '入门',
  learning_goal: userStore.user?.learning_goal || '',
  programming_background: userStore.user?.programming_background || '',
  years_experience: userStore.user?.years_experience || 0,
  answer_preference: userStore.user?.answer_preference || '分步清晰',
})

function openMemory(item) {
  selectedMemory.value = item
  memoryDialogVisible.value = true
}

function memoryCategoryLabel(category) {
  return ({ preference: '偏好', profile: '画像', goal: '目标', interest: '关注知识点', tooling: '工具环境' })[category] || category || '记忆'
}

async function refreshMemoryOverview() {
  memoryOverview.value = await getMemoryOverview().catch(() => memoryOverview.value || {})
}

function beginCreateMemory() {
  editingMemoryId.value = null
  Object.assign(memoryForm, { category: 'profile', fact_key: '', fact_value: '' })
  memoryEditing.value = true
}

function beginEditMemory(item) {
  editingMemoryId.value = item.id
  Object.assign(memoryForm, {
    category: item.category || 'profile',
    fact_key: item.fact_key || '',
    fact_value: item.fact_value || ''
  })
  memoryEditing.value = true
}

async function saveMemoryEditor() {
  if (!memoryForm.fact_key.trim() || !memoryForm.fact_value.trim()) {
    ElMessage.warning('请填写记忆名称和内容')
    return
  }
  memorySaving.value = true
  try {
    if (editingMemoryId.value) await updateMemory(editingMemoryId.value, memoryForm)
    else await createMemory(memoryForm)
    await refreshMemoryOverview()
    memoryEditing.value = false
    ElMessage.success(editingMemoryId.value ? '记忆已更新' : '记忆已新增')
  } catch (error) {
    ElMessage.error(error?.message || '保存记忆失败')
  } finally {
    memorySaving.value = false
  }
}

async function removeMemoryItem(item) {
  try {
    await ElMessageBox.confirm(`确定删除“${item.fact_key}”这条记忆吗？`, '删除长期记忆', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteMemory(item.id)
    await refreshMemoryOverview()
    ElMessage.success('记忆已删除')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error?.message || '删除失败')
  }
}

function formatMemoryTime(value) {
  if (!value) return '暂无时间'
  return String(value).replace('T', ' ').slice(0, 16)
}

// ── 知识点详细讲解 ──
const knowledgeDetailDialog = ref(false)
const knowledgeDetailLoading = ref(false)
const knowledgeDetail = ref({ summary: '', fact_key: '', fact_value: '', sources: [], conversation_count: 0 })

function renderMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch { return text }
}

async function openKnowledgeDetail(item) {
  if (item.category !== 'interest') {
    // 非知识点类型，保持原有行为：打开记忆列表定位到该项
    selectedMemory.value = item
    memoryDialogVisible.value = true
    return
  }
  // 知识点类型：打开详细讲解弹窗
  knowledgeDetail.value = { summary: '', fact_key: item.fact_key, fact_value: item.fact_value, sources: [], conversation_count: 0 }
  knowledgeDetailDialog.value = true
  knowledgeDetailLoading.value = true
  try {
    const result = await getKnowledgeDetail({
      fact_key: item.fact_key,
      fact_value: item.fact_value,
      category: item.category,
    })
    knowledgeDetail.value = {
      summary: result.summary || '暂无内容',
      fact_key: item.fact_key,
      fact_value: item.fact_value,
      sources: result.sources || [],
      conversation_count: result.conversation_count || 0,
      source_messages_count: result.source_messages_count || 0,
    }
  } catch {
    knowledgeDetail.value.summary = '获取讲解失败，请稍后重试。'
    ElMessage.error('获取讲解失败')
  } finally {
    knowledgeDetailLoading.value = false
  }
}

const settings = reactive({
  explanationLevel: localStorage.getItem('qa_level') || 'standard',
  reminder: localStorage.getItem('reminder') !== 'false',
  pace: parseInt(localStorage.getItem('pace') || '3')
})
const llmConfig = ref({
  provider: 'openai',
  api_key: '',
  base_url: 'https://api.openai.com',
  model_name: 'gpt-4o',
  temperature: 0.7,
  max_tokens: 4096,
  is_configured: false
})
const llmForm = reactive({
  provider: 'openai',
  api_key: '',
  image_api_key: '',
  embedding_api_key: '',
  embedding_provider: 'siliconflow',
  embedding_model: 'BAAI/bge-large-zh-v1.5',
  base_url: 'https://api.openai.com',
  model_name: 'gpt-4o',
  temperature: 0.7,
  max_tokens: 4096
})
const modelSuggestions = {
  openai: ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo', 'o1-mini', 'o1-preview'],
  deepseek: ['deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-reasoner'],
  custom: ['gpt-4o', 'deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-reasoner', 'qwen-turbo', 'glm-4']
}
const currentModelSuggestions = computed(() => modelSuggestions[llmForm.provider] || modelSuggestions.custom)

function onProviderChange(provider) {
  const presets = {
    openai: { base_url: 'https://api.openai.com', model_name: 'gpt-4o' },
    deepseek: { base_url: 'https://api.deepseek.com', model_name: 'deepseek-v4-pro' },
    custom: { base_url: '', model_name: '' }
  }
  const preset = presets[provider]
  if (preset) {
    llmForm.base_url = preset.base_url
    llmForm.model_name = preset.model_name
  }
}

function quickSetupDeepSeek() {
  llmForm.provider = 'deepseek'
  llmForm.base_url = 'https://api.deepseek.com'
  llmForm.model_name = 'deepseek-v4-pro'
  ElMessage.success('已切换到DeepSeek配置，请输入您的API Key后保存')
}

onMounted(async () => {
  refreshMemoryOverview()
  try {
    const data = await getLLMConfig()
    llmConfig.value = data
    // Check if DeepSeek / Embedding are already configured
    deepseekConfigured.value = data.is_configured && data.provider === 'deepseek'
    embeddingConfigured.value = !!(data.embedding_api_key)
    searchApiConfigured.value = !!(data.search_api_key)
    if (data.is_configured) {
      llmForm.api_key = ''
      llmForm.image_api_key = ''
      llmForm.embedding_api_key = ''
      llmForm.provider = data.provider || 'openai'
      llmForm.base_url = data.base_url
      llmForm.model_name = data.model_name
      llmForm.temperature = data.temperature
      llmForm.max_tokens = data.max_tokens
      llmForm.embedding_provider = data.embedding_provider || 'siliconflow'
      llmForm.embedding_model = data.embedding_model || 'BAAI/bge-large-zh-v1.5'
    }
  } catch(e) {}
})

async function handleSave() {
  saving.value = true
  try {
    await userStore.updateUser(form)
    ElMessage.success('保存成功')
  } catch(e) { ElMessage.error('保存失败') }
  finally { saving.value = false }
}

function saveSettings() {
  localStorage.setItem('qa_level', settings.explanationLevel)
  localStorage.setItem('reminder', settings.reminder.toString())
  localStorage.setItem('pace', settings.pace.toString())
  ElMessage.success('偏好设置已保存')
}

async function handleSaveLLM() {
  llmSaving.value = true
  try {
    await saveLLMConfig(llmForm)
    ElMessage.success('大模型配置已保存')
    llmEditing.value = false
    const data = await getLLMConfig()
    llmConfig.value = data
    deepseekConfigured.value = data.is_configured && data.provider === 'deepseek'
    embeddingConfigured.value = !!(data.embedding_api_key)
  } catch(e) { ElMessage.error('保存失败: ' + (e.message || '未知错误')) }
  finally { llmSaving.value = false }
}

async function handleSaveDeepSeek() {
  if (!deepseekApiKey.value.trim()) {
    ElMessage.warning('请输入 DeepSeek API Key')
    return
  }
  if (!deepseekApiKey.value.trim().startsWith('sk-')) {
    ElMessage.warning('API Key 格式不正确，DeepSeek API Key 应以 sk- 开头')
    return
  }
  deepseekSaving.value = true
  try {
    await saveLLMConfig({
      provider: 'deepseek',
      api_key: deepseekApiKey.value.trim(),
      base_url: 'https://api.deepseek.com',
      model_name: 'deepseek-v4-pro',
      temperature: 0.7,
      max_tokens: 4096,
      image_api_key: ''
    })
    deepseekConfigured.value = true
    deepseekApiKey.value = ''
    ElMessage.success('DeepSeek API Key 已保存并启用！')
    // Refresh config display
    const data = await getLLMConfig()
    llmConfig.value = data
  } catch(e) {
    ElMessage.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    deepseekSaving.value = false
  }
}

async function handleResetDeepSeek() {
  try {
    await ElMessageBox.confirm('确认重置 DeepSeek 配置？将恢复为系统默认。', '提示', {
      confirmButtonText: '确认重置',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await resetLLMConfig()
    deepseekConfigured.value = false
    deepseekApiKey.value = ''
    embeddingConfigured.value = false
    llmConfig.value = { provider: 'openai', api_key: '', image_api_key: '', embedding_api_key: '', base_url: 'https://api.openai.com', model_name: 'gpt-4o', temperature: 0.7, max_tokens: 4096, is_configured: false }
    ElMessage.success('DeepSeek 配置已重置')
  } catch(e) {
    if (e !== 'cancel') ElMessage.error('重置失败')
  }
}

async function handleSaveEmbedding() {
  if (!embeddingApiKey.value.trim()) {
    ElMessage.warning('请输入 SiliconFlow API Key')
    return
  }
  if (!embeddingApiKey.value.trim().startsWith('sk-')) {
    ElMessage.warning('API Key 格式不正确，SiliconFlow API Key 应以 sk- 开头')
    return
  }
  embeddingSaving.value = true
  try {
    await saveEmbeddingConfig({
      embedding_api_key: embeddingApiKey.value.trim(),
      embedding_provider: 'siliconflow',
      embedding_model: 'BAAI/bge-large-zh-v1.5'
    })
    embeddingConfigured.value = true
    embeddingApiKey.value = ''
    ElMessage.success('SiliconFlow BGE 已启用，线上查询与本地向量库保持一致。')
    const data = await getLLMConfig()
    llmConfig.value = data
  } catch(e) {
    ElMessage.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    embeddingSaving.value = false
  }
}

async function handleResetEmbedding() {
  try {
    await ElMessageBox.confirm('确认重置嵌入配置？知识库检索将不可用。', '提示', {
      confirmButtonText: '确认重置',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await saveEmbeddingConfig({
      embedding_api_key: '',
      embedding_provider: 'siliconflow',
      embedding_model: 'BAAI/bge-large-zh-v1.5'
    })
    embeddingConfigured.value = false
    embeddingApiKey.value = ''
    const data = await getLLMConfig()
    llmConfig.value = data
    ElMessage.success('嵌入配置已重置')
  } catch(e) {
    if (e !== 'cancel') ElMessage.error('重置失败')
  }
}

async function handleSaveSearchApi() {
  if (!searchApiKey.value.trim()) {
    ElMessage.warning('请输入联网检索 API Key')
    return
  }
  searchApiSaving.value = true
  try {
    await saveSearchConfig({ search_api_key: searchApiKey.value.trim() })
    searchApiConfigured.value = true
    searchApiKey.value = ''
    ElMessage.success('Tavily Advanced 已保存并启用！')
    const data = await getLLMConfig()
    llmConfig.value = data
  } catch(e) {
    ElMessage.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    searchApiSaving.value = false
  }
}

async function handleResetSearchApi() {
  try {
    await ElMessageBox.confirm('确认重置联网检索配置？重置后 QA 中将无法使用联网检索。', '提示', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await saveSearchConfig({ search_api_key: '' })
    searchApiConfigured.value = false
    searchApiKey.value = ''
    const data = await getLLMConfig()
    llmConfig.value = data
    ElMessage.success('联网检索配置已重置')
  } catch(e) {
    if (e !== 'cancel') ElMessage.error('重置失败')
  }
}

async function handleResetLLM() {
  try {
    await ElMessageBox.confirm('确认重置为系统默认配置？', '提示', { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' })
    await resetLLMConfig()
    llmConfig.value = { provider: 'openai', api_key: '', image_api_key: '', embedding_api_key: '', search_api_key: '', base_url: 'https://api.openai.com', model_name: 'gpt-4o', temperature: 0.7, max_tokens: 4096, is_configured: false }
    deepseekConfigured.value = false
    searchApiConfigured.value = false
    llmForm.provider = 'openai'
    llmForm.api_key = ''
    llmForm.image_api_key = ''
    llmForm.embedding_api_key = ''
    llmForm.embedding_provider = 'siliconflow'
    llmForm.embedding_model = 'BAAI/bge-large-zh-v1.5'
    llmForm.base_url = 'https://api.openai.com'
    llmForm.model_name = 'gpt-4o'
    llmForm.temperature = 0.7
    llmForm.max_tokens = 4096
    llmEditing.value = false
    ElMessage.success('已重置为系统默认配置')
  } catch(e) {
    if (e !== 'cancel') ElMessage.error('重置失败')
  }
}
</script>

<style scoped>
.page-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: bold; }
.profile-summary-card{margin-bottom:12px;padding:14px 16px;border:1px solid #dce3f1;border-radius:13px;background:linear-gradient(135deg,#f8faff,#f3f8f6)}.profile-summary-card span{color:#68748a;font-size:10px;font-weight:750;letter-spacing:.06em}.profile-summary-card p{margin:8px 0 0;color:#303d56;font-size:13px;line-height:1.75}.memory-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.memory-stats>div,.memory-stat-button{padding:13px;border:1px solid #e4e9f2;border-radius:12px;background:#fafbfe;text-align:left}.memory-stat-button{font:inherit;cursor:pointer;transition:.18s}.memory-stat-button:hover{border-color:#aeb9ee;background:#f5f7ff;transform:translateY(-1px)}.memory-stats span,.memory-stats strong,.memory-stats small{display:block}.memory-stats span{color:#8792a6;font-size:10px}.memory-stats strong{margin:6px 0;color:#273550;font-size:14px}.memory-stats small{color:#9099aa;font-size:9px;line-height:1.5}.memory-stat-button em{display:block;margin-top:8px;color:#5364d8;font-size:10px;font-style:normal;font-weight:700}.memory-facts{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px}.memory-tag{cursor:pointer}.memory-dialog-toolbar{display:flex;align-items:flex-start;gap:10px;margin-bottom:14px}.memory-dialog-note{display:flex;align-items:center;gap:7px;min-width:0;flex:1;padding:10px 12px;border-radius:10px;color:#66738a;background:#f3f5f9;font-size:12px}.memory-editor{margin-bottom:16px;padding:14px;border:1px solid #dce3f1;border-radius:12px;background:#fafbfe}.memory-detail-list{display:grid;gap:10px;max-height:58vh;overflow-y:auto;padding-right:4px}.memory-detail-list article{padding:14px 16px;border:1px solid #e2e7f1;border-radius:12px;background:#fff}.memory-detail-list article.selected{border-color:#9eaae8;background:#f7f8ff}.memory-detail-head{display:flex;align-items:center;justify-content:space-between;gap:10px}.memory-detail-head>span{color:#98a1b1;font-size:10px}.memory-detail-list h4{margin:10px 0 6px;color:#273550;font-size:14px}.memory-detail-list p,.memory-detail-list small{margin:0;color:#7f899b;font-size:11px;line-height:1.6}@media(max-width:900px){.memory-stats{grid-template-columns:1fr}.memory-dialog-toolbar{align-items:stretch;flex-direction:column}}
.deepseek-quick-card {
  border-left: 4px solid #409EFF;
}
.embedding-quick-card {
  border-left: 4px solid #67C23A;
}
.search-quick-card {
  border-left: 4px solid #E6A23C;
}

/* 知识点标签高亮 */
.memory-tag-interest {
  border-color: #67C23A !important;
  background: #f0f9eb !important;
}
.memory-tag-interest em {
  margin-left: 4px;
  font-size: 10px;
  font-style: normal;
  font-weight: 600;
}

/* 知识点详细操作按钮 */
.memory-detail-action {
  margin-top: 10px;
  text-align: right;
}

/* 知识点讲解弹窗 */
.knowledge-detail-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 48px 0;
  color: #8792a6;
  font-size: 14px;
}
.knowledge-detail-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid #ebeef5;
}
.knowledge-detail-content {
  line-height: 1.8;
  font-size: 14px;
  color: #303133;
}
.knowledge-detail-content :deep(h2),
.knowledge-detail-content :deep(h3) {
  margin: 18px 0 10px;
  color: #273550;
}
.knowledge-detail-content :deep(p) {
  margin: 8px 0;
}
.knowledge-detail-content :deep(ul),
.knowledge-detail-content :deep(ol) {
  padding-left: 20px;
}
.knowledge-detail-content :deep(li) {
  margin: 4px 0;
}
.knowledge-detail-content :deep(code) {
  padding: 2px 6px;
  border-radius: 4px;
  background: #f0f2f5;
  font-size: 13px;
}
.knowledge-detail-sources {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}
.knowledge-detail-sources h4 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #606266;
}
.knowledge-detail-sources ul {
  padding-left: 18px;
  margin: 0;
  font-size: 12px;
  color: #909399;
}
.profile-page { padding-bottom: 32px; }
.profile-identity-card { position: sticky; top: 0; text-align: center; }
.profile-identity-card :deep(.el-card__body) { padding: 28px 22px !important; }
.profile-page :deep(.el-form-item__label) { color: var(--ink-600); font-size: 12px; font-weight: 650; }
.profile-page :deep(.el-card + .el-card) { margin-top: 16px !important; }
@media (max-width: 900px) {
  .profile-identity-card { position: static; margin-bottom: 14px; }
  .profile-page :deep(.el-col) { max-width: 100%; flex: 0 0 100%; }
}
</style>
