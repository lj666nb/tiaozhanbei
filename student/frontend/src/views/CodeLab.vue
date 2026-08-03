<template>
  <div class="ide-page" v-loading="loading" element-loading-background="rgba(8, 13, 24, .86)">
    <header class="ide-topbar">
      <div class="brand-area">
        <button class="icon-button" title="返回关卡列表" @click="goBack"><el-icon><ArrowLeft /></el-icon></button>
        <div class="brand-mark">A</div>
        <div class="project-heading">
          <strong>{{ workspace?.project_name || 'Agent Lab' }}</strong>
          <span>{{ course.module || 'Agent 工程实战' }} · {{ course.title || '加载中' }}</span>
        </div>
      </div>
      <div class="top-actions">
        <div class="layout-switcher" role="group" aria-label="工作台布局">
          <button :class="{ active: layoutMode === 'standard' }" title="标准布局：文件、编辑器和编程搭档" @click="setLayout('standard')"><span class="layout-glyph standard"></span></button>
          <button :class="{ active: layoutMode === 'project' }" title="项目布局：只显示资源管理器和代码区域" @click="setLayout('project')"><span class="layout-glyph project"></span></button>
          <button :class="{ active: layoutMode === 'focus' }" title="专注布局：只显示编辑器" @click="setLayout('focus')"><span class="layout-glyph focus"></span></button>
          <button :class="{ active: layoutMode === 'pair' }" title="搭档布局：编辑器和 Agent 双栏" @click="setLayout('pair')"><span class="layout-glyph pair"></span></button>
        </div>
        <button
          class="environment-pill"
          :class="{ ready: workspace?.virtual_env }"
          :disabled="terminalRunning || workspace?.virtual_env"
          :title="workspace?.virtual_env ? '当前项目环境可用' : '点击为当前项目创建 .venv'"
          @click="setupEnvironment"
        >
          <i :class="{ online: workspace?.virtual_env }"></i>
          {{ workspace?.virtual_env ? '.venv 已就绪' : terminalRunning ? '正在创建环境…' : '一键创建环境' }}
        </button>
        <div class="project-state-actions" aria-label="项目状态跳转">
          <button class="ghost-action" :disabled="capabilityBusy" @click="switchProjectState('initial')">
            <el-icon><RefreshRight /></el-icon> 初始化项目
          </button>
          <button
            class="ghost-action passed-state"
            :disabled="capabilityBusy || !canSwitchToPassed"
            :title="canSwitchToPassed ? '恢复到此前全部测试点通过的项目状态' : '需要先亲自通过一次实验推进'"
            @click="switchProjectState('passed')"
          >
            <el-icon><CircleCheck /></el-icon> 全测试通过
            <span v-if="!canSwitchToPassed">未解锁</span>
          </button>
        </div>
      </div>
    </header>

    <nav class="capability-progress" aria-label="实验能力验证进度">
      <div class="flow-title">
        <small>能力验证闭环</small>
        <b>{{ flowHeadline }}</b>
      </div>
      <div class="flow-track">
        <div class="flow-line"><i :style="{ width: `${flowProgressPercent}%` }"></i></div>
        <button
          v-for="step in capabilitySteps"
          :key="step.id"
          :class="['flow-step', step.state]"
          :disabled="step.state === 'upcoming'"
          @click="openCapabilityStep(step.id)"
        >
          <span class="flow-node">{{ step.state === 'done' ? '✓' : step.index }}</span>
          <span class="flow-copy">
            <b>{{ step.label }}</b>
            <small>{{ step.detail }}</small>
          </span>
          <em v-if="step.score !== null">{{ step.score }} 分</em>
        </button>
      </div>
      <button class="flow-action" :disabled="capabilityBusy || !!checkingStage" @click="handleTopAction">
        <el-icon><CircleCheck /></el-icon>
        <span><small>当前任务</small><b>{{ topActionLabel }}</b></span>
      </button>
    </nav>

    <main :class="['workbench', `layout-${layoutMode}`]" :style="workbenchGridStyle">
      <aside class="activity-bar">
        <button :class="{ active: ['standard', 'project'].includes(layoutMode) && leftMode === 'files' }" title="项目文件" @click="showLeftPanel('files')"><el-icon><FolderOpened /></el-icon></button>
        <button :class="{ active: layoutMode === 'standard' && leftMode === 'guide' }" title="引导教程" @click="showLeftPanel('guide')"><el-icon><Reading /></el-icon></button>
        <button title="运行终端" @click="showTerminal"><el-icon><Monitor /></el-icon></button>
      </aside>

      <aside class="side-panel">
        <template v-if="leftMode === 'files'">
          <div class="panel-title">
            <span>项目资源管理器</span>
            <div>
              <button title="新建文件" @click="createFile()"><el-icon><DocumentAdd /></el-icon></button>
              <button title="新建文件夹" @click="createDirectory()"><el-icon><FolderAdd /></el-icon></button>
              <button title="保存并刷新项目" :disabled="refreshing" @click="refreshWorkspace"><el-icon :class="{ 'is-loading': refreshing }"><Refresh /></el-icon></button>
            </div>
          </div>
          <div class="project-root"><el-icon><ArrowDown /></el-icon><el-icon><FolderOpened /></el-icon><b>{{ workspace?.project_name }}</b></div>
          <div class="file-list">
            <LabFileTree
              :entries="explorerChildren[''] || []"
              :children="explorerChildren"
              :expanded="expandedDirectories"
              :active-path="activePath"
              :dirty-paths="dirtyFiles"
              @activate="entry => entry.is_directory ? toggleExplorerDirectory(entry) : openExplorerFile(entry.path)"
              @contextmenu="openExplorerContextMenu"
            />
            <div v-if="!visibleExplorerEntries.length" class="empty-files">点击右上角 + 创建第一个文件</div>
          </div>
          <div class="explorer-hint">每题一个 .venv · 右键管理文件 · 自动保存</div>
        </template>

        <template v-else>
          <div class="panel-title"><span>项目引导</span><em>{{ completedStages.length }}/{{ stages.length }}</em></div>
          <div class="lesson-intro">
            <div class="lesson-labels">
              <span>{{ course.framework }}</span>
              <em v-for="skill in course.skills || []" :key="skill">{{ skill }}</em>
            </div>
            <h3>{{ course.title }}</h3>
            <p>{{ course.description }}</p>
            <div class="learning-contract">
              <div>
                <small>开始前建议会</small>
                <b>{{ (course.prerequisites || []).join(' · ') || 'Python 基础' }}</b>
              </div>
              <div>
                <small>完成的标准</small>
                <b>{{ (course.acceptance || []).join(' · ') || '通过本关全部检查' }}</b>
              </div>
            </div>
            <details v-if="course.input_output" class="contract-details">
              <summary>查看输入输出示例与验收标准</summary>
              <pre>{{ course.input_output }}</pre>
              <ul>
                <li v-for="item in course.acceptance || []" :key="item">{{ item }}</li>
              </ul>
            </details>
          </div>
          <div class="stage-list">
            <article
              v-for="(stage, index) in stages"
              :key="stage.id"
              :class="['stage-card', { open: currentStage === stage.id, current: currentStage === stage.id, done: completedStages.includes(stage.id) }]"
            >
              <button class="stage-heading" @click="toggleStage(stage)">
                <span class="stage-number">{{ completedStages.includes(stage.id) ? '✓' : index + 1 }}</span>
                <span>
                  <b>{{ stage.title }} <em v-if="currentStage === stage.id && !completedStages.includes(stage.id)">当前</em></b>
                  <small>{{ stage.checks.join(' · ') }}</small>
                </span>
                <el-icon><ArrowDown /></el-icon>
              </button>
              <div v-if="currentStage === stage.id" class="stage-body">
                <p>{{ stage.instruction }}</p>
                <div v-if="stage.micro_steps?.length" class="micro-step-plan">
                  <strong>按小步实现，不要一次写完整函数</strong>
                  <ol>
                    <li v-for="(micro, microIndex) in stage.micro_steps" :key="micro.id">
                      <span>{{ microIndex + 1 }}</span>
                      <p><b>{{ micro.title }}</b><small>{{ micro.description }}</small></p>
                    </li>
                  </ol>
                </div>
                <div v-if="stage.command" class="command-chip">
                  <code>{{ stage.command }}</code>
                  <button @click="sendStageCommand(stage.command)">运行</button>
                </div>
                <button v-if="stage.id === 'implementation'" class="outline-button full" @click="insertStarter">插入本关函数骨架</button>
                <button class="check-button" :disabled="checkingStage === stage.id" @click="checkStage(stage)">
                  <el-icon v-if="checkingStage === stage.id" class="is-loading"><Loading /></el-icon>
                  <el-icon v-else><MagicStick /></el-icon>{{ stage.id === 'implementation' ? `运行 ${stage.test_count || ''} 个测试点` : 'AI 检查本阶段' }}
                </button>
                <div v-if="stageResults[stage.id]" :class="['check-result', { passed: stageResults[stage.id].passed }]">
                  <div v-for="item in stageResults[stage.id].checks" :key="item.label" class="check-result-item">
                    <span>{{ item.passed ? '✓' : '!' }}</span><p><b>{{ item.label }}</b><small>{{ item.detail }}</small></p>
                    <ul v-if="item.cases?.length" class="test-case-list">
                      <li v-for="testCase in item.cases" :key="testCase.label" :class="{ passed: testCase.passed }">
                        <span>{{ testCase.passed ? '✓' : '×' }}</span>
                        <div class="test-case-content">
                          <div class="test-case-header">
                            <b>{{ testCase.label }} <em v-if="!testCase.passed && testCase.category">{{ testCase.category }}</em></b>
                            <small v-if="testCase.duration_ms != null" class="test-duration">{{ testCase.duration_ms }}ms</small>
                          </div>
                          <small class="test-detail">{{ testCase.detail }}</small>
                          <div v-if="!testCase.passed && (testCase.input_args || testCase.expected_value || testCase.actual_value)" class="test-debug-info">
                            <div v-if="testCase.input_args" class="debug-row">
                              <span class="debug-label">📥 输入参数</span>
                              <code>{{ testCase.input_args }}</code>
                            </div>
                            <div v-if="testCase.expected_value" class="debug-row expected">
                              <span class="debug-label">✅ 期望输出</span>
                              <code>{{ testCase.expected_value }}</code>
                            </div>
                            <div v-if="testCase.actual_value" class="debug-row actual">
                              <span class="debug-label">❌ 实际输出</span>
                              <code>{{ testCase.actual_value }}</code>
                            </div>
                          </div>
                          <small v-if="testCase.next_action" class="next-action">💡 下一步：{{ testCase.next_action }}</small>
                        </div>
                      </li>
                    </ul>
                  </div>
                </div>
                <div v-if="stage.hints?.length" class="hint-ladder">
                  <button
                    class="hint-reveal"
                    :disabled="visibleHintCount(stage) >= stage.hints.length"
                    @click="revealNextHint(stage)"
                  >
                    <el-icon><MagicStick /></el-icon>
                    {{
                      visibleHintCount(stage) >= stage.hints.length
                        ? '已查看本步全部提示'
                        : visibleHintCount(stage)
                          ? `继续查看提示 ${visibleHintCount(stage) + 1}`
                          : '我卡住了，给我一级提示'
                    }}
                  </button>
                  <div
                    v-for="hint in visibleStageHints(stage)"
                    :key="hint.level"
                    class="hint-card"
                  >
                    <span>提示 {{ hint.level }}</span>
                    <b>{{ hint.title }}</b>
                    <p>{{ hint.content }}</p>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </template>
      </aside>

      <div class="side-panel-resize-handle" @mousedown="startSidePanelResize"></div>

      <section class="editor-column">
        <div v-if="capabilityStatus === 'repair_pending'" class="stage-submit-banner">
          <div>
            <small>当前阶段 · 故障修复</small>
            <b>修复 solution.py 后，填写根因说明并提交判题</b>
          </div>
          <button class="primary-action" :disabled="capabilityBusy" @click="openRepairStage">
            <el-icon><CircleCheck /></el-icon>
            {{ projectState === 'repair' ? '填写说明并提交' : '切换到故障项目' }}
          </button>
        </div>
        <div v-else-if="capabilityStatus === 'variant_pending'" class="stage-submit-banner variant">
          <div>
            <small>当前阶段 · 变式迁移</small>
            <b>完成 solution.py 中的变式代码后，从这里提交</b>
          </div>
          <button class="primary-action" :disabled="variantBusy || capabilityBusy" @click="openVariantSubmission">
            <el-icon><MagicStick /></el-icon>
            {{ projectState === 'variant' ? '提交变式迁移' : '切换到变式项目' }}
          </button>
        </div>
        <div class="editor-tabs">
          <button
            v-for="path in openTabs"
            :key="path"
            :class="{ active: path === activePath }"
            @click="openFile(path)"
          >
            <span :class="['tab-dot', fileKind(path)]"></span>{{ path.split('/').pop() }}
            <i v-if="dirtyFiles.has(path)">●</i>
            <el-icon class="tab-close" @click.stop="closeTab(path)"><Close /></el-icon>
          </button>
          <div class="editor-spacer"></div>
          <button v-if="isMarkdownFile" class="preview-toggle-btn" :class="{ active: markdownPreview }" @click="toggleMarkdownPreview">
            <el-icon><component :is="markdownPreview ? 'Edit' : 'View'" /></el-icon>{{ markdownPreview ? '编辑' : '预览' }}
          </button>
          <span v-if="activePath" class="editor-engine-badge">CodeMirror · {{ languageFor(activePath) }} · Ctrl+Space 补全</span>
          <button v-if="activePath?.endsWith('.py')" class="editor-hint-button" title="显示 Python 代码提示" @click="editor?.showCompletions()">
            <el-icon><MagicStick /></el-icon>代码提示
          </button>
          <button class="save-button" :disabled="!activePath" @click="saveActiveFile"><el-icon><DocumentChecked /></el-icon>保存</button>
        </div>
        <div v-show="activePath && !markdownPreview" ref="editorRef" class="code-editor-host"></div>
        <div v-if="activePath && markdownPreview && isMarkdownFile" class="markdown-preview" v-html="renderMarkdown(markdownPreviewContent)"></div>
        <div v-if="!activePath" class="welcome-editor">
          <div class="welcome-logo">A</div>
          <h2>开始搭建你的 Agent 项目</h2>
          <p>从左侧创建文件，或打开“项目引导”逐步完成环境、依赖与代码。</p>
          <button class="primary-action" @click="leftMode = 'guide'">打开项目引导</button>
        </div>

        <div class="terminal-resize-handle" @mousedown.stop.prevent="startTerminalResize">
          <div class="terminal-resize-bar"></div>
        </div>

        <section class="terminal-panel" :style="{ height: terminalHeight + 'px', flex: '0 0 ' + terminalHeight + 'px' }">
          <div class="terminal-tabs">
            <button class="active"><el-icon><Monitor /></el-icon>终端</button>
            <span :class="{ running: terminalRunning }">{{ terminalRunning ? `● 正在执行 ${terminalElapsed}s` : '项目终端 · 实时输出 · 可选中复制' }}</span>
            <button v-if="terminalRunning" class="stop-terminal" title="停止当前命令" @click="stopTerminal">■ 停止</button>
            <button title="清空终端" @click="terminalLines = []"><el-icon><Delete /></el-icon></button>
          </div>
          <div ref="terminalOutputRef" class="terminal-output" @click="handleTerminalOutputClick">
            <div class="terminal-welcome">Agent Lab Terminal · 支持常用命令、管道、重定向与虚拟环境</div>
            <div v-for="(line, index) in terminalLines" :key="index" :class="['terminal-line', line.type]">
              <template v-if="line.type === 'command'"><span v-if="line.activeEnv" class="prompt-env">({{ line.activeEnv.split('/').pop() }})</span><span class="prompt-symbol">➜</span></template><pre>{{ line.text }}</pre>
            </div>
            <div class="terminal-input-row">
              <span v-if="terminalActiveEnv" class="prompt-env">({{ terminalActiveEnv.split('/').pop() }})</span><span class="prompt-symbol">➜</span><span class="prompt-path">~/{{ workspace?.project_name }}{{ terminalCwd ? `/${terminalCwd}` : '' }}</span>
              <input
                ref="terminalInputRef"
                v-model="terminalCommand"
                :disabled="terminalRunning"
                autocomplete="off"
                spellcheck="false"
                @keydown="handleTerminalKeydown"
              />
              <el-icon v-if="terminalRunning" class="is-loading"><Loading /></el-icon>
            </div>
          </div>
        </section>
      </section>

      <aside class="agent-panel">
        <div class="agent-header">
          <div class="agent-avatar"><el-icon><MagicStick /></el-icon></div>
          <div>
            <b>{{ assistantTitle }}</b>
            <span :class="['assistant-runtime', assistantRuntime.status]"><i></i>{{ assistantRuntimeLabel }}</span>
          </div>
          <button title="清空对话" @click="resetChat"><el-icon><Delete /></el-icon></button>
        </div>
        <div ref="chatRef" class="chat-list" @click="handleAgentBlockAction">
          <div v-for="(message, index) in chatMessages" :key="index" :class="['chat-message', message.role]">
            <div v-if="message.role === 'assistant'" class="mini-avatar">A</div>
            <div :class="['message-bubble', { 'runtime-message': message.runtimeStatus }]">
              <div v-if="message.toolCalls?.length" class="tool-calls-inline">
                <div v-for="(tc, tcIdx) in message.toolCalls" :key="tcIdx" :class="['tool-call-chip', tc.status]">
                  <span class="tool-call-icon">{{ tc.status === 'running' ? '⏳' : '✅' }}</span>
                  <span class="tool-call-name">{{ tc.tool }}</span>
                  <span v-if="tc.args?.path" class="tool-call-arg">{{ tc.args.path }}</span>
                  <span v-if="tc.args?.stage_id" class="tool-call-arg">{{ tc.args.stage_id }}</span>
                  <span v-if="tc.status === 'completed' && tc.detail" class="tool-call-arg">{{ tc.detail }}</span>
                </div>
              </div>
              <div v-if="message.role === 'assistant'" class="assistant-markdown" v-html="renderAssistantMarkdown(message.content)"></div>
              <div v-else>{{ message.content }}</div>
              <details v-if="message.observations?.length" class="agent-observations">
                <summary>Agent 已观察 {{ message.observations.length }} 项</summary>
                <div v-for="item in message.observations" :key="`${item.tool}-${item.label}`">
                  <span :class="item.status">●</span>
                  <p><b>{{ item.label }}</b><small>{{ item.detail }}</small></p>
                </div>
              </details>
              <small v-if="message.notice">{{ message.notice }}</small>
            </div>
          </div>
          <div v-if="assistantLoading" class="chat-message assistant"><div class="mini-avatar">A</div><div class="message-bubble typing"><i></i><i></i><i></i></div></div>
        </div>
        <div class="quick-prompts">
          <template v-if="assistantRuntime.available">
            <button @click="askQuick(`解释为什么要完成“${currentStageRecord?.title || '当前步骤'}”，先不要给代码`)">为什么做</button>
            <button @click="askQuick('根据当前项目和最近的检查结果，给我下一层提示，不要给完整答案')">渐进提示</button>
            <button @click="askQuick('针对当前步骤问我一个自测问题，等我回答后再反馈')">自测一下</button>
          </template>
          <button v-else class="setup-model-button" @click="goToModelSetup">配置模型以启用 Agent</button>
        </div>
        <div class="agent-composer">
          <div class="assistant-mode-switch" role="group" aria-label="编程搭档模式">
            <button :class="{ active: assistantMode === 'chat' }" title="仅问答，不读取整个项目" @click="assistantMode = 'chat'">Chat</button>
            <button :class="{ active: assistantMode === 'agent' }" title="结合当前项目进行分析" @click="assistantMode = 'agent'">Agent</button>
          </div>
          <textarea
            v-model="assistantQuestion"
            rows="3"
            :disabled="!assistantRuntime.available"
            :placeholder="assistantRuntime.available ? '问项目、依赖、报错或框架 API…' : '配置模型后启用动态引导'"
            @keydown="handleAssistantKeydown"
          ></textarea>
          <div>
            <span>{{ assistantRuntime.available ? 'Enter 发送 · Ctrl + Enter 换行' : '当前仅提供左侧静态课程引导' }}</span>
            <button :disabled="assistantLoading || !assistantRuntime.available || !assistantQuestion.trim()" @click="sendAssistant"><el-icon><Promotion /></el-icon></button>
          </div>
        </div>
      </aside>
    </main>

    <div
      v-if="explorerMenu.visible"
      class="explorer-context-menu"
      :style="{ left: `${explorerMenu.x}px`, top: `${explorerMenu.y}px` }"
      @click.stop
    >
      <button v-if="!explorerMenu.entry?.is_directory" @click="contextOpen"><span>打开</span><kbd>Enter</kbd></button>
      <button v-if="explorerMenu.entry?.is_directory" @click="contextNewFile"><span>新建文件…</span><kbd>Ctrl+N</kbd></button>
      <button v-if="explorerMenu.entry?.is_directory" @click="contextNewDirectory"><span>新建文件夹…</span></button>
      <div class="menu-separator"></div>
      <button @click="contextOpenInTerminal"><span>在集成终端中打开</span></button>
      <button v-if="isPythonEntry(explorerMenu.entry)" @click="contextRunPython"><span>运行 Python 文件</span><kbd>Ctrl+F5</kbd></button>
      <div class="menu-separator"></div>
      <button @click="contextCopy"><span>复制</span><kbd>Ctrl+C</kbd></button>
      <button @click="contextCopyPath(false)"><span>复制路径</span><kbd>Shift+Alt+C</kbd></button>
      <button @click="contextCopyPath(true)"><span>复制相对路径</span></button>
      <button :disabled="explorerMenu.entry?.path === '.venv'" @click="contextDuplicate"><span>创建副本…</span></button>
      <div class="menu-separator"></div>
      <button :disabled="explorerMenu.entry?.path === '.venv'" @click="contextRename"><span>重命名…</span><kbd>F2</kbd></button>
      <button class="danger" :disabled="explorerMenu.entry?.path === '.venv'" @click="contextDelete"><span>删除</span><kbd>Delete</kbd></button>
    </div>

    <!-- 答辩回顾对话框 -->
    <el-dialog v-model="reviewDialog" width="820px" class="dark-dialog review-dialog" :close-on-click-modal="false">
      <template #header><div class="dialog-title"><span>答辩评审已保存</span><b>查看评分、点评与标准答案</b></div></template>
      <div v-if="reviewLoading" class="knowledge-detail-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <p>正在读取已保存的答辩评审...</p>
      </div>
      <div v-else class="review-body">
        <div class="review-overview">
          <div :class="['review-total-score', reviewSummary.defense_score >= 60 ? 'passed' : 'retry']">
            <strong>{{ reviewSummary.grading_status === 'completed' ? (reviewSummary.defense_score || 0) : '--' }}</strong><span>/ 100</span>
          </div>
          <div>
            <small>原理答辩总分</small>
            <b>{{ reviewSummary.grading_status === 'completed' ? '三道题均已完成 AI 评分' : '原理答辩已完成，AI 正在后台评分' }}</b>
            <p>{{ reviewSummary.grading_status === 'completed' ? '每题评分与评语已写入学习档案。' : '评分不会阻塞故障修复；分析完成后这里会自动更新。' }}</p>
          </div>
        </div>
        <div v-for="(item, index) in reviewItems" :key="item.question_id" class="review-card">
          <div class="review-question-header">
            <span class="review-q-num">{{ index + 1 }}</span>
            <div>
              <b>{{ item.prompt }}</b>
              <small>考察重点：{{ item.focus }}</small>
            </div>
            <span :class="['review-score-tag', item.user_score >= 70 ? 'good' : item.user_score >= 50 ? 'ok' : 'low']">
              {{ item.grading_status === 'completed' ? `${item.user_score}分` : '评分中' }}
            </span>
          </div>
          <div class="review-compare">
            <div class="review-col">
              <div class="review-col-title">你的回答</div>
              <div class="review-answer user">{{ item.user_answer || '（未作答）' }}</div>
              <div v-if="item.feedback" class="review-feedback">
                <b>{{ item.graded_by === 'ai' ? '🤖 AI' : '⚙️ 系统' }}反馈：</b>{{ item.feedback }}
              </div>
              <div v-if="item.hit_points?.length" class="review-points hit">
                ✓ {{ item.hit_points.join(' · ') }}
              </div>
              <div v-if="item.missing_points?.length" class="review-points miss">
                ✗ 遗漏：{{ item.missing_points.join(' · ') }}
              </div>
            </div>
            <div class="review-col">
              <div class="review-col-title reference">📖 标准参考答案</div>
              <div class="review-answer reference" v-html="renderMarkdown(item.reference_answer || '（正在生成...）')"></div>
            </div>
          </div>
        </div>
        <div v-if="repairReview.explanation || reviewSummary.repair_score" class="repair-review-card">
          <div class="repair-review-heading">
            <div>
              <small>故障修复评分详情</small>
              <b>{{ repairReview.tests_passed ? '测试已恢复' : '测试仍有未通过项' }}</b>
            </div>
            <span>{{ reviewSummary.repair_score || 0 }}分</span>
          </div>
          <div class="repair-score-grid">
            <div><small>测试恢复</small><b>{{ repairReview.test_score || 0 }} / 80</b></div>
            <div><small>根因说明</small><b>{{ repairReview.explanation_score || 0 }} / 20</b></div>
            <div><small>通过用例</small><b>{{ repairReview.passed_count || 0 }} / {{ repairReview.total || 0 }}</b></div>
          </div>
          <p v-if="repairReview.description"><b>注入故障：</b>{{ repairReview.description }}</p>
          <p v-if="repairReview.explanation"><b>你的修复说明：</b>{{ repairReview.explanation }}</p>
        </div>
        <p class="review-tip">对比你的回答和标准答案，先理解差异，再进入下一阶段。</p>
        <button class="primary-action review-next-action" @click="finishDefenseReview">
          {{ reviewNextAction === 'repair' ? '我已看完，进入故障修复' : reviewNextAction === 'retry' ? '根据点评补充答辩' : '关闭' }}
        </button>
      </div>
    </el-dialog>

    <!-- 变式迁移对话框 -->
    <el-dialog v-model="variantDialog" width="760px" class="dark-dialog" :close-on-click-modal="false">
      <template #header><div class="dialog-title"><span>🔀 变式迁移</span><b>在新场景中检验真实掌握程度</b></div></template>
      <div class="variant-form">
        <div class="variant-meta">
          <span>新业务场景</span>
          <span>新输入输出契约</span>
          <span>独立测试评分</span>
          <b v-if="capabilityStatus === 'verified'">{{ capabilitySession?.variant_score || 0 }} 分</b>
        </div>
        <div class="variant-scenario-card">
          <h4>📖 变式场景</h4>
          <div class="variant-scenario-content" v-html="renderMarkdown(capabilitySession?.variant_scenario || '正在加载变式场景...')"></div>
        </div>
        <div v-if="capabilityStatus === 'verified'" class="variant-result-card">
          <b>{{ variantEvidence.tests_passed ? '全部迁移测试通过' : '迁移任务已评分' }}</b>
          <span>通过 {{ variantEvidence.passed_count || 0 }} / {{ variantEvidence.total || 0 }} 个测试点</span>
          <p>本次结果已经写入能力报告。你仍可查看场景要求和最终得分，用于复盘不同业务约束下的实现取舍。</p>
        </div>
        <p v-else class="variant-instruction">
          请在 <b>solution.py</b> 中实现上述变式函数。你可以复用原有代码，但必须适应新的输入/输出契约。
          完成后点击下方按钮提交判题。
        </p>
        <div v-if="capabilityStatus !== 'verified'" class="variant-actions">
          <button class="primary-action dialog-submit" :disabled="variantBusy" @click="handleVariantSubmit">
            <el-icon v-if="variantBusy" class="is-loading"><Loading /></el-icon>
            <el-icon v-else><MagicStick /></el-icon>
            提交变式代码并判题
          </button>
          <button class="outline-button dialog-submit" style="margin-left:8px;" @click="variantDialog = false">
            回到编辑器继续
          </button>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="defenseDialog" width="760px" class="dark-dialog" :close-on-click-modal="false">
      <template #header>
        <div class="dialog-title">
          <span>{{ capabilityStatus === 'defense_pending' ? '功能验收通过' : '能力验证闭环' }}</span>
          <b>{{ capabilityStatus === 'defense_pending' ? '继续完成原理答辩' : capabilityStatus === 'repair_pending' ? '提交故障修复' : '查看能力报告' }}</b>
        </div>
      </template>
      <div v-if="capabilityStatus === 'defense_pending'" class="defense-form">
        <p>请结合你刚写的项目回答。重点说明框架接口的作用，不考查基础 Python 语法。</p>
        <label v-for="(question, index) in defenseQuestions" :key="question.id">
          <span>{{ index + 1 }}. {{ question.prompt }}</span>
          <el-input v-model="defenseAnswers[question.id]" type="textarea" :rows="3" placeholder="结合具体函数、文件或调用流程回答" />
        </label>
        <button class="primary-action dialog-submit" :disabled="capabilityBusy" @click="submitDefenseAnswers">提交答辩</button>
      </div>
      <div v-else-if="capabilityStatus === 'repair_pending'" class="repair-form">
        <h3>故障已经写入 repair_target.py</h3>
        <p>{{ capabilitySession?.mutation_description }}</p>
        <p>请先在编辑器中完成修复，再填写根因说明。提交后系统保存真实评分{{ hasVariant ? '并直接解锁变式迁移' : '并完成能力验证' }}，测试分数不会阻塞流程。</p>
        <el-input v-model="repairExplanation" type="textarea" :rows="4" placeholder="至少20字：故障根因是什么，你修改了哪里？" />
        <div class="repair-actions">
          <button class="primary-action dialog-submit" :disabled="capabilityBusy" @click="submitRepairCode">
            <el-icon v-if="capabilityBusy" class="is-loading"><Loading /></el-icon>
            <el-icon v-else><CircleCheck /></el-icon>
            {{ capabilityBusy ? '正在判题…' : '提交故障修复并判题' }}
          </button>
          <button class="outline-button dialog-submit" :disabled="capabilityBusy" @click="defenseDialog = false">返回编辑器继续修复</button>
          <button class="outline-button dialog-submit" :disabled="capabilityBusy" @click="openReviewDialog">📋 查看答辩回顾</button>
        </div>
      </div>
      <div v-else-if="capabilityStatus === 'skipped'" class="verified-report">
        <div class="score-ring low">{{ capabilitySession?.report?.total_score || capabilitySession?.total_score || 0 }}</div>
        <h2>关卡完成（仅测试分）</h2>
        <p>{{ capabilitySession?.report?.summary || '你选择跳过能力验证，仅获得测试点分数。可以随时重做本题完成能力验证。' }}</p>
        <div class="score-dimensions">
          <div class="dim-row"><span>测试点</span><span class="pass">100分</span></div>
          <div class="dim-row"><span>原理答辩</span><span class="skip">未参与</span></div>
          <div class="dim-row"><span>故障修复</span><span class="skip">未参与</span></div>
        </div>
      </div>
      <div v-else-if="capabilityStatus === 'variant_pending'" class="verified-report">
        <div :class="['score-ring', repairEvidence.tests_passed ? 'ok' : 'low']">{{ capabilitySession?.repair_score || 0 }}</div>
        <h2>{{ repairEvidence.tests_passed ? '故障已修复并完成评分' : '本次修复仍有未通过项' }}</h2>
        <p>无论本次是否修好，都可以重新挑战故障修复，或带着当前得分继续变式迁移。</p>
        <div class="repair-result-grid">
          <div><small>测试恢复</small><b>{{ repairEvidence.test_score || 0 }} / 80</b></div>
          <div><small>根因说明</small><b>{{ repairEvidence.explanation_score || 0 }} / 20</b></div>
          <div><small>通过用例</small><b>{{ repairEvidence.passed_count || 0 }} / {{ repairEvidence.total || 0 }}</b></div>
        </div>
        <div class="repair-choice-actions">
          <button class="outline-button" :disabled="capabilityBusy" @click="retryRepairAttempt">
            <el-icon><RefreshRight /></el-icon> 重新进行故障修复
          </button>
          <button class="primary-action" :disabled="capabilityBusy" @click="continueToVariant">
            <el-icon><MagicStick /></el-icon> 继续变式迁移
          </button>
        </div>
        <button class="text-review-button" @click="openReviewDialog">📋 查看评分详情与答辩回顾</button>
      </div>
      <div v-else class="verified-report">
        <div class="score-ring">{{ capabilitySession?.report?.total_score || 100 }}</div>
        <h2>能力验证完成</h2><p>{{ capabilitySession?.report?.summary || '项目、理解与故障修复证据均已成立。' }}</p>
        <div v-if="capabilitySession?.report?.dimensions" class="score-dimensions">
          <div class="dim-row" v-for="(val, key) in capabilitySession.report.dimensions" :key="key">
            <span>{{ key }}</span><span :class="val >= 70 ? 'pass' : val >= 50 ? 'ok' : 'low'">{{ val }}分</span>
          </div>
        </div>
        <div v-if="capabilitySession?.report?.process_evidence" class="process-evidence-summary">
          <span>编辑快照 <b>{{ capabilitySession.report.process_evidence.edit_snapshots || 0 }}</b></span>
          <span>运行尝试 <b>{{ capabilitySession.report.process_evidence.run_attempts || 0 }}</b></span>
          <span>阶段检查 <b>{{ capabilitySession.report.process_evidence.stage_checks || 0 }}</b></span>
          <span>最高提示 <b>{{ capabilitySession.report.process_evidence.max_hint_level || 0 }} 级</b></span>
        </div>
        <button class="outline-button" style="margin-top:14px;" @click="openReviewDialog">📋 查看答辩回顾与标准答案</button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { basicSetup } from 'codemirror'
import { autocompletion, completeFromList, snippetCompletion, startCompletion } from '@codemirror/autocomplete'
import { indentWithTab } from '@codemirror/commands'
import { Compartment, EditorState } from '@codemirror/state'
import { keymap, EditorView } from '@codemirror/view'
import { python } from '@codemirror/lang-python'
import { markdown } from '@codemirror/lang-markdown'
import { json } from '@codemirror/lang-json'
import { javascript } from '@codemirror/lang-javascript'
import { oneDark } from '@codemirror/theme-one-dark'
import {
  askLabAssistant, checkLabStage, createLabDirectory, deleteLabEntry, duplicateLabEntry,
  getLabWorkspace, listLabEntries, moveLabEntry, readLabFile, saveLabFile, streamLabTerminal,
  streamLabAssistant, resetLabAssistant,
} from '../api/workspace'
import { bindCodeBlockActions, renderMarkdown } from '../composables/useCodeBlockRenderer'
import LabFileTree from '../components/LabFileTree.vue'
import {
  getCapabilitySession, markCapabilityCodePassed, recordCapabilityEvents, startCapabilitySession,
  submitCapabilityDefense, submitCapabilityRepair, retryCapabilityRepair,
  switchCapabilityProjectState,
  getSessionReview,
  generateVariant, submitVariant,
} from '../api/capability'

const route = useRoute()
const router = useRouter()
const exerciseId = computed(() => String(route.params.taskId || '1-1'))
const moduleId = computed(() => String(route.params.moduleId || '1'))
const loading = ref(true)
const refreshing = ref(false)
const workspace = ref(null)
const course = computed(() => workspace.value?.course || {})
const stages = computed(() => course.value.stages || [])
const files = ref([])
const directories = ref([])
const completedStages = ref([])
const currentStage = ref('structure')
const stageResults = reactive({})
const checkingStage = ref('')
const leftMode = ref('guide')
const layoutMode = ref(['standard', 'project', 'focus', 'pair'].includes(localStorage.getItem('lab_layout')) ? localStorage.getItem('lab_layout') : 'standard')
const visibleHints = reactive({})

const editorRef = ref(null)
let editor = null
const models = new Map()
const activePath = ref('')
const openTabs = ref([])
const dirtyFiles = reactive(new Set())
let autoSaveTimer = null
const AUTO_SAVE_DELAY = 1500 // 1.5 秒无操作后自动保存

const terminalCommand = ref('')
const terminalLines = ref([])
const terminalRunning = ref(false)
const terminalInputRef = ref(null)
const terminalOutputRef = ref(null)
const terminalHistory = ref([])
const terminalHistoryIndex = ref(-1)
const terminalActiveEnv = ref('')
const terminalCwd = ref('')
const terminalElapsed = ref(0)
const terminalHeight = ref(225)
let terminalTimer = null
let terminalAbortController = null
let terminalResizeState = null
const sidePanelWidth = ref(300)
let sidePanelResizeState = null
const explorerChildren = reactive({})
const expandedDirectories = reactive(new Set())
const explorerMenu = reactive({ visible: false, x: 0, y: 0, entry: null })

const assistantQuestion = ref('')
const assistantLoading = ref(false)
let assistantAbortController = null
const chatRef = ref(null)
const chatMessages = ref([])
const assistantMode = ref(localStorage.getItem('lab_assistant_mode') === 'chat' ? 'chat' : 'agent')
const assistantRuntime = ref({ status: 'loading', available: false, model: '', provider: '' })
const assistantTitle = computed(() => {
  if (!assistantRuntime.value.available) return '项目静态引导'
  return assistantMode.value === 'agent' ? 'Agent 引导导师' : 'Chat 编程问答'
})
const assistantRuntimeLabel = computed(() => {
  if (assistantRuntime.value.status === 'loading') return '正在确认模型状态'
  if (assistantRuntime.value.status === 'ready') {
    const model = assistantRuntime.value.model || '已配置模型'
    return assistantMode.value === 'agent'
      ? `${model} · 当前：${currentStageRecord.value?.title || '查看项目'}`
      : `${model} · 仅问答`
  }
  if (assistantRuntime.value.status === 'error') return '模型连接异常'
  return '未启用 Agent'
})
const markdownPreview = ref(false)
const isMarkdownFile = computed(() => activePath.value && activePath.value.toLowerCase().endsWith('.md'))
const markdownPreviewContent = computed(() => {
  if (!isMarkdownFile.value || !activePath.value) return ''
  const model = models.get(activePath.value)
  return model ? model.getValue() : ''
})

const capabilitySession = ref(null)
const capabilityBusy = ref(false)
const defenseDialog = ref(false)
const reviewDialog = ref(false)
const reviewLoading = ref(false)
const reviewItems = ref([])
const reviewSummary = reactive({ defense_score: 0, repair_score: 0, status: '', grading_status: '' })
const repairReview = reactive({})
const reviewNextAction = ref('')
const defenseAnswers = reactive({})
const repairExplanation = ref('')
const variantCode = ref('')
const variantBusy = ref(false)
const variantDialog = ref(false)
const capabilityStatus = computed(() => capabilitySession.value?.status || 'coding')
const hasVariant = computed(() => Boolean(capabilitySession.value?.has_variant))
const projectState = computed(() => workspace.value?.project_state || 'initial')
const canSwitchToPassed = computed(() => Boolean(
  workspace.value?.state_options?.can_switch_to_passed
  || (capabilitySession.value?.original_code && Number(capabilitySession.value?.code_score) >= 100),
))
const repairEvidence = computed(() => capabilitySession.value?.report?.repair_evidence || {})
const variantEvidence = computed(() => capabilitySession.value?.report?.variant_evidence || {})
const defenseGradingStatus = computed(() => capabilitySession.value?.defense_grading_status || 'not_started')
const defenseQuestions = computed(() => capabilitySession.value?.defense_questions || [])
const acceptancePassed = computed(() => completedStages.value.includes('acceptance'))
const currentStageIndex = computed(() => Math.max(0, stages.value.findIndex(item => item.id === currentStage.value)))
const currentStageRecord = computed(() => stages.value[currentStageIndex.value] || null)
const workbenchGridStyle = computed(() => {
  const panelCol = `${sidePanelWidth.value}px`
  if (layoutMode.value === 'project') return { gridTemplateColumns: `46px ${panelCol} 5px minmax(0,1fr)` }
  if (layoutMode.value === 'standard') return { gridTemplateColumns: `46px ${panelCol} 5px minmax(470px,1fr) 330px` }
  return {}
})
const visibleExplorerEntries = computed(() => {
  const result = []
  const visit = (parent, depth) => {
    for (const entry of explorerChildren[parent] || []) {
      result.push({ ...entry, depth })
      if (entry.is_directory && expandedDirectories.has(entry.path)) visit(entry.path, depth + 1)
    }
  }
  visit('', 0)
  return result
})
const topActionLabel = computed(() => {
  if (capabilityStatus.value === 'verified') return '查看能力报告'
  if (capabilityStatus.value === 'skipped') return '查看分数（已跳过验证）'
  if (capabilityStatus.value === 'variant_pending') return '提交变式迁移'
  if (capabilityStatus.value === 'repair_pending') return '填写说明并提交修复'
  if (capabilityStatus.value === 'defense_pending') return '继续原理答辩'
  if (acceptancePassed.value) return '开始原理答辩'
  if (checkingStage.value) return `正在检查：${currentStageRecord.value?.title || '当前步骤'}`
  return currentStage.value === 'acceptance'
    ? '运行最终验收'
    : `检查：${currentStageRecord.value?.title || '当前步骤'}`
})

const capabilityStepIndex = computed(() => {
  if (!hasVariant.value) {
    return ({
      coding: 0,
      defense_pending: 1,
      repair_pending: 2,
      verified: 3,
      skipped: 0,
    }[capabilityStatus.value] ?? 0)
  }
  return ({
    coding: 0,
    defense_pending: 1,
    repair_pending: 2,
    variant_pending: 3,
    verified: 4,
    skipped: 0,
  }[capabilityStatus.value] ?? 0)
})

const capabilitySteps = computed(() => {
  const activeIndex = capabilityStepIndex.value
  const scoreOrNull = (value, completed = false) => completed || Number(value) > 0
    ? Math.round(Number(value) || 0)
    : null
  const stageTotal = Math.max(stages.value.length, 1)
  const definitions = [
    {
      id: 'coding',
      label: '实验推进',
      detail: capabilityStatus.value === 'coding'
        ? `${completedStages.value.length}/${stageTotal} 个步骤完成`
        : '功能验收已完成',
      score: scoreOrNull(capabilitySession.value?.code_score),
    },
    {
      id: 'defense',
      label: '原理答辩',
      detail: defenseGradingStatus.value === 'completed'
        ? '评分与点评已保存'
        : capabilityStatus.value !== 'defense_pending' && capabilityStatus.value !== 'coding'
          ? '已完成，AI 后台评分中'
        : '解释你的实现依据',
      score: defenseGradingStatus.value === 'completed'
        ? scoreOrNull(capabilitySession.value?.defense_score)
        : null,
    },
    {
      id: 'repair',
      label: '故障修复',
      detail: repairEvidence.value.tests_passed !== undefined
        ? '故障定位证据已保存'
        : '定位并修复注入故障',
      score: scoreOrNull(
        capabilitySession.value?.repair_score,
        repairEvidence.value.tests_passed !== undefined,
      ),
    },
    ...(hasVariant.value ? [{
      id: 'variant',
      label: '变式迁移',
      detail: variantEvidence.value.tests_passed !== undefined
        ? '新场景验证已完成'
        : '在新约束下独立实现',
      score: scoreOrNull(
        capabilitySession.value?.variant_score,
        variantEvidence.value.tests_passed !== undefined,
      ),
    }] : []),
  ]
  return definitions.map((step, index) => ({
    ...step,
    index: index + 1,
    state: capabilityStatus.value === 'skipped'
      ? (index === 0 ? 'done' : 'skipped')
      : activeIndex > index
        ? 'done'
        : activeIndex === index
          ? 'current'
          : 'upcoming',
  }))
})

const flowProgressPercent = computed(() => {
  if (capabilityStatus.value === 'verified') return 100
  if (capabilityStatus.value === 'skipped') return 0
  if (capabilityStatus.value === 'coding') {
    return Math.round((completedStages.value.length / Math.max(stages.value.length, 1)) * 22)
  }
  const totalSteps = hasVariant.value ? 4 : 3
  return Math.round((capabilityStepIndex.value / (totalSteps - 1)) * 100)
})

const flowHeadline = computed(() => {
  if (capabilityStatus.value === 'verified') return hasVariant.value ? '四项能力证据已完成' : '三项能力证据已完成'
  if (capabilityStatus.value === 'variant_pending') return '最后一步：完成变式迁移'
  if (capabilityStatus.value === 'repair_pending') return '原理答辩已完成，开始故障修复'
  if (capabilityStatus.value === 'defense_pending') return '功能通过，等待原理答辩'
  return acceptancePassed.value ? '实验已验收，开始能力验证' : '先完成当前实验步骤'
})

function languageFor(path) {
  if (path.endsWith('.py')) return 'python'
  if (path.endsWith('.json')) return 'json'
  if (path.endsWith('.md')) return 'markdown'
  if (path.endsWith('.yml') || path.endsWith('.yaml')) return 'yaml'
  if (path.endsWith('.env') || path.endsWith('.txt') || path.includes('requirements')) return 'plaintext'
  return 'plaintext'
}

function fileKind(path) {
  if (path.endsWith('.py')) return 'python'
  if (path.endsWith('.md')) return 'markdown'
  if (path.includes('.env')) return 'env'
  if (path.endsWith('.json')) return 'json'
  return 'text'
}

function fileLabel(path) {
  const kind = fileKind(path)
  return { python: 'Py', markdown: 'M↓', env: '⚙', json: '{}', text: '≡' }[kind]
}

watch(assistantMode, value => localStorage.setItem('lab_assistant_mode', value))
watch(visibleHints, value => {
  localStorage.setItem(`lab_hint_progress:${exerciseId.value}`, JSON.stringify(value))
}, { deep: true })

const learningEventQueue = []
let learningEventFlushTimer = null
let lastEditSnapshotAt = 0
let defenseGradingPollTimer = null

function queueLearningEvent(type, payload = {}) {
  learningEventQueue.push({ type, payload })
  if (learningEventQueue.length >= 8) {
    flushLearningEvents()
    return
  }
  if (!learningEventFlushTimer) {
    learningEventFlushTimer = window.setTimeout(flushLearningEvents, 3000)
  }
}

async function flushLearningEvents() {
  if (learningEventFlushTimer) window.clearTimeout(learningEventFlushTimer)
  learningEventFlushTimer = null
  const sessionId = capabilitySession.value?.id
  if (!sessionId || !learningEventQueue.length) return
  const events = learningEventQueue.splice(0, learningEventQueue.length)
  try {
    await recordCapabilityEvents(sessionId, events)
  } catch (_) {
    learningEventQueue.unshift(...events.slice(-40))
  }
}

async function ensureCapabilitySession() {
  const session = await startCapabilitySession(exerciseId.value)
  capabilitySession.value = session
  if (['pending', 'grading'].includes(session.defense_grading_status)) {
    startDefenseGradingPolling()
  }
  await flushLearningEvents()
  return session
}

function stopDefenseGradingPolling() {
  if (defenseGradingPollTimer) window.clearInterval(defenseGradingPollTimer)
  defenseGradingPollTimer = null
}

async function pollDefenseGrading() {
  const sessionId = capabilitySession.value?.id
  if (!sessionId) return
  try {
    const latest = await getCapabilitySession(sessionId)
    const previousStatus = defenseGradingStatus.value
    capabilitySession.value = { ...capabilitySession.value, ...latest }
    if (latest.defense_grading_status === 'completed') {
      stopDefenseGradingPolling()
      if (previousStatus !== 'completed') ElMessage.success('AI 已完成原理答辩评分，结果已自动更新')
    }
  } catch (_) {
    // 后台评分失败不会影响学生继续故障修复，下次轮询会自动重试。
  }
}

function startDefenseGradingPolling() {
  if (defenseGradingPollTimer) return
  pollDefenseGrading()
  defenseGradingPollTimer = window.setInterval(pollDefenseGrading, 4000)
}

function restoreHintProgress() {
  Object.keys(visibleHints).forEach(key => delete visibleHints[key])
  try {
    Object.assign(visibleHints, JSON.parse(localStorage.getItem(`lab_hint_progress:${exerciseId.value}`) || '{}'))
  } catch (_) { /* ignore invalid local progress */ }
}

function visibleHintCount(stage) {
  return Math.min(Number(visibleHints[stage.id] || 0), stage.hints?.length || 0)
}

function visibleStageHints(stage) {
  return (stage.hints || []).slice(0, visibleHintCount(stage))
}

function revealNextHint(stage) {
  const next = Math.min(visibleHintCount(stage) + 1, stage.hints?.length || 0)
  visibleHints[stage.id] = next
  queueLearningEvent('hint', { stage_id: stage.id, level: next, source: 'guide', visible: next })
}

function toggleStage(stage) {
  currentStage.value = stage.id
  const target = stage.target_file
  if (target && models.has(target)) openFile(target)
}

function setLayout(mode) {
  if (mode === 'project') leftMode.value = 'files'
  layoutMode.value = mode
  localStorage.setItem('lab_layout', mode)
  nextTick(() => editor?.layout())
}

function showLeftPanel(mode) {
  leftMode.value = mode
  if (mode === 'guide' || !['standard', 'project'].includes(layoutMode.value)) setLayout('standard')
}

function showTerminal() {
  if (layoutMode.value === 'focus') setLayout('standard')
  focusTerminal()
}

class LabTextModel {
  constructor(value = '', language = 'text') {
    this.value = String(value)
    this.language = language
  }
  getValue() { return this.value }
  getValueLength() { return this.value.length }
  setValue(value) {
    this.value = String(value)
    if (models.get(activePath.value) === this) editor?.setModel(this)
  }
  dispose() {}
}

const languageCompartment = new Compartment()
let currentEditorModel = null
let suppressEditorChange = false

const pythonCompletionSource = completeFromList([
  snippetCompletion('def ${name}(${params}):\n\t${pass}', { label: 'def', detail: '定义函数', type: 'keyword' }),
  snippetCompletion('class ${Name}:\n\tdef __init__(self${params}):\n\t\t${pass}', { label: 'class', detail: '定义类', type: 'keyword' }),
  snippetCompletion('if ${condition}:\n\t${pass}', { label: 'if', detail: '条件分支', type: 'keyword' }),
  snippetCompletion('for ${item} in ${items}:\n\t${pass}', { label: 'for', detail: '遍历循环', type: 'keyword' }),
  snippetCompletion('try:\n\t${pass}\nexcept ${Exception} as exc:\n\t${pass}', { label: 'try', detail: '异常处理', type: 'keyword' }),
  snippetCompletion('with ${expression} as ${name}:\n\t${pass}', { label: 'with', detail: '上下文管理', type: 'keyword' }),
  ...['return', 'raise', 'import', 'from', 'as', 'elif', 'else', 'while', 'break', 'continue', 'True', 'False', 'None']
    .map(label => ({ label, type: 'keyword' })),
  ...['len', 'range', 'enumerate', 'zip', 'sorted', 'sum', 'min', 'max', 'isinstance', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'print']
    .map(label => ({ label, type: 'function', apply: `${label}()` })),
])

function languageExtension(path = '') {
  const language = languageFor(path)
  if (language === 'python') {
    const support = python()
    return [support, support.language.data.of({ autocomplete: pythonCompletionSource })]
  }
  if (language === 'markdown') return markdown()
  if (language === 'json') return json()
  if (language === 'javascript' || language === 'typescript') {
    return javascript({ typescript: language === 'typescript' })
  }
  return []
}

function handleEditorContentChange() {
  if (!activePath.value || !currentEditorModel) return
  dirtyFiles.add(activePath.value)
  if (autoSaveTimer) window.clearTimeout(autoSaveTimer)
  autoSaveTimer = window.setTimeout(() => {
    if (activePath.value && dirtyFiles.has(activePath.value)) saveActiveFile(true)
  }, AUTO_SAVE_DELAY)
  const now = Date.now()
  if (now - lastEditSnapshotAt >= 10_000) {
    lastEditSnapshotAt = now
    queueLearningEvent('edit', {
      length: currentEditorModel.getValueLength(),
      source: activePath.value,
    })
  }
}

function createEditor() {
  if (editor || !editorRef.value) return
  const view = new EditorView({
    parent: editorRef.value,
    state: EditorState.create({
      doc: '',
      extensions: [
        basicSetup,
        oneDark,
        languageCompartment.of(languageExtension('')),
        autocompletion({
          activateOnTyping: true,
          override: [context => activePath.value.endsWith('.py') ? pythonCompletionSource(context) : null],
        }),
        keymap.of([
          indentWithTab,
          { key: 'Ctrl-Space', run: startCompletion },
          { key: 'Mod-Space', run: startCompletion },
          { key: 'Mod-s', run: () => { saveActiveFile(); return true } },
        ]),
        EditorState.tabSize.of(4),
        EditorView.lineWrapping,
        EditorView.theme({
          '&': { height: '100%', fontSize: '14px', backgroundColor: '#0b111d' },
          '.cm-scroller': {
            fontFamily: "'JetBrains Mono', 'Cascadia Code', Consolas, monospace",
            lineHeight: '1.65',
            padding: '12px 0 40px',
          },
          '.cm-content': { caretColor: '#f4f7ff' },
          '.cm-gutters': { backgroundColor: '#0b111d', borderRight: '1px solid #1f2a3b' },
          '.cm-activeLine': { backgroundColor: 'rgba(104, 91, 255, .08)' },
          '.cm-activeLineGutter': { backgroundColor: 'rgba(104, 91, 255, .12)' },
          '.cm-tooltip-autocomplete': { border: '1px solid #3a4962' },
        }),
        EditorView.domEventHandlers({
          paste: event => {
            queueLearningEvent('paste', {
              length: event.clipboardData?.getData('text/plain')?.length || 0,
              source: activePath.value,
            })
          },
        }),
        EditorView.updateListener.of(update => {
          if (!update.docChanged || suppressEditorChange || !currentEditorModel) return
          currentEditorModel.value = update.state.doc.toString()
          handleEditorContentChange()
        }),
      ],
    }),
  })

  editor = {
    layout: () => view.requestMeasure(),
    focus: () => view.focus(),
    setModel(model) {
      currentEditorModel = model || null
      suppressEditorChange = true
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: model?.getValue() || '' },
        effects: languageCompartment.reconfigure(languageExtension(activePath.value)),
        selection: { anchor: 0 },
      })
      suppressEditorChange = false
    },
    getSelection: () => ({
      from: view.state.selection.main.from,
      to: view.state.selection.main.to,
    }),
    executeEdits(_source, edits) {
      const edit = edits?.[0]
      if (!edit) return
      view.dispatch({
        changes: { from: edit.range.from, to: edit.range.to, insert: edit.text },
        selection: { anchor: edit.range.from + edit.text.length },
      })
    },
    showCompletions: () => {
      view.focus()
      return startCompletion(view)
    },
    dispose: () => view.destroy(),
  }
}

function disposeModels() {
  models.forEach(model => model.dispose())
  models.clear()
}

function syncFiles(payload) {
  files.value = payload.files || []
  directories.value = payload.directories || []
  completedStages.value = payload.completed_stages || []
  Object.keys(stageResults).forEach(key => delete stageResults[key])
  Object.assign(stageResults, payload.stage_results || {})
  terminalActiveEnv.value = payload.active_env || ''
  terminalCwd.value = payload.terminal_cwd || ''
  assistantRuntime.value = {
    status: payload.assistant?.status || 'setup_required',
    available: Boolean(payload.assistant?.available),
    model: payload.assistant?.model || '',
    provider: payload.assistant?.provider || '',
  }
  disposeModels()
  for (const file of files.value) {
    models.set(file.path, new LabTextModel(file.content, languageFor(file.path)))
  }
  dirtyFiles.clear()
}

function hydrateAssistant(payload, force = false) {
  if (!force && chatMessages.value.length) return
  const assistant = payload.assistant || {}
  const history = Array.isArray(assistant.history) ? assistant.history : []
  if (history.length) {
    chatMessages.value = history.map(item => ({ role: item.role, content: item.content }))
    return
  }
  chatMessages.value = [{
    role: 'assistant',
    content: assistant.welcome || '当前课程引导已就绪。',
    runtimeStatus: assistant.available ? '' : (assistant.status || 'setup_required'),
  }]
}

async function loadExplorerDirectory(path = '', force = false) {
  if (!force && explorerChildren[path]) return
  const payload = await listLabEntries(exerciseId.value, path)
  explorerChildren[path] = payload.entries || []
}

async function resetExplorer() {
  Object.keys(explorerChildren).forEach(key => delete explorerChildren[key])
  expandedDirectories.clear()
  await loadExplorerDirectory('', true)
}

async function toggleExplorerDirectory(entry) {
  if (expandedDirectories.has(entry.path)) {
    expandedDirectories.delete(entry.path)
    return
  }
  try {
    await loadExplorerDirectory(entry.path)
    expandedDirectories.add(entry.path)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '文件夹无法打开')
  }
}

async function openExplorerFile(path) {
  if (!models.has(path)) {
    try {
      const file = await readLabFile(exerciseId.value, path)
      if (file.binary) return ElMessage.info(file.message || '该文件无法作为文本预览')
      files.value.push({ path, content: file.content })
      models.set(path, new LabTextModel(file.content, languageFor(path)))
    } catch (error) {
      return ElMessage.error(error.response?.data?.detail || '文件读取失败')
    }
  }
  openFile(path)
}

async function loadWorkspace(reset = false) {
  loading.value = true
  try {
    const payload = await getLabWorkspace(exerciseId.value, reset)
    workspace.value = payload
    syncFiles(payload)
    hydrateAssistant(payload, reset || !chatMessages.value.length)
    restoreHintProgress()
    const nextStage = stages.value.find(stage => !completedStages.value.includes(stage.id))
    currentStage.value = nextStage?.id || stages.value.at(-1)?.id || 'structure'
    leftMode.value = 'guide'
    if (payload.removed_virtual_envs?.length) {
      terminalLines.value.push({ type: 'output', text: `每道题只保留一个 .venv，已清理重复环境：${payload.removed_virtual_envs.join('、')}` })
    }
    await resetExplorer()
    const stageTarget = currentStageRecord.value?.target_file
    const preferred = files.value.find(file => file.path === stageTarget)
      || files.value.find(file => file.path === activePath.value)
      || files.value.find(file => file.path.endsWith('.py')) || files.value[0]
    if (preferred) openFile(preferred.path)
    await ensureCapabilitySession()
    return true
  } catch (error) {
    const detail = error.response?.data?.detail || error.message || '工作区加载失败'
    terminalLines.value.push({ type: 'error', text: `工作区刷新失败：${detail}` })
    return false
  } finally {
    loading.value = false
  }
}

async function refreshWorkspace() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await saveAll()
    const refreshed = await loadWorkspace(false)
    if (refreshed) ElMessage.success('项目已刷新')
  } finally {
    refreshing.value = false
  }
}

function openFile(path) {
  const model = models.get(path)
  if (!model || !editor) return
  // 切换文件前自动保存当前文件
  if (autoSaveTimer) window.clearTimeout(autoSaveTimer)
  if (activePath.value && dirtyFiles.has(activePath.value)) {
    saveActiveFile(true)
  }
  activePath.value = path
  markdownPreview.value = false
  if (!openTabs.value.includes(path)) openTabs.value.push(path)
  editor.setModel(model)
  editor.focus()
}

function closeTab(path) {
  const index = openTabs.value.indexOf(path)
  openTabs.value = openTabs.value.filter(item => item !== path)
  if (path === activePath.value) {
    const next = openTabs.value[Math.max(0, index - 1)] || ''
    activePath.value = ''
    markdownPreview.value = false
    editor?.setModel(null)
    if (next) openFile(next)
  }
}

function toggleMarkdownPreview() {
  if (!isMarkdownFile.value) return
  markdownPreview.value = !markdownPreview.value
  if (!markdownPreview.value) {
    // 切回编辑模式时刷新编辑器布局
    nextTick(() => editor?.layout())
  }
}

async function saveActiveFile(silent = false) {
  if (!activePath.value || !models.get(activePath.value)) return
  await saveLabFile(exerciseId.value, activePath.value, models.get(activePath.value).getValue())
  dirtyFiles.delete(activePath.value)
  const item = files.value.find(file => file.path === activePath.value)
  if (item) item.content = models.get(activePath.value).getValue()
  if (!silent) ElMessage.success(`${activePath.value} 已保存`)
}

async function saveAll() {
  for (const path of [...dirtyFiles]) {
    const model = models.get(path)
    if (model) await saveLabFile(exerciseId.value, path, model.getValue())
    dirtyFiles.delete(path)
  }
}

function parentPath(path = '') {
  return path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : ''
}

function joinProjectPath(parent, name) {
  return [parent, name].filter(Boolean).join('/')
}

async function createFile(basePath = '') {
  try {
    const { value } = await ElMessageBox.prompt(basePath ? `在 ${basePath} 中创建文件。` : '文件将创建在项目内，也可以输入 src/tools.py 这样的子路径。', '新建文件', {
      confirmButtonText: '创建', cancelButtonText: '取消', inputPlaceholder: '例如：solution.py',
      inputPattern: /^(?!\/)(?!.*\.\.)(?!.*[<>:"|?*])[\w.\-/]+$/,
      inputErrorMessage: '请输入安全的项目相对路径',
    })
    const path = joinProjectPath(basePath, value)
    if (files.value.some(file => file.path === path)) return ElMessage.warning('该文件已经存在')
    await saveLabFile(exerciseId.value, path, '')
    const file = { path, content: '' }
    files.value.push(file)
    files.value.sort((a, b) => a.path.localeCompare(b.path))
    models.set(path, new LabTextModel('', languageFor(path)))
    const parent = parentPath(path)
    await loadExplorerDirectory(parent, true)
    if (parent) expandedDirectories.add(parent)
    openFile(path)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close' && error?.message) console.warn(error)
  }
}

async function createDirectory(basePath = '') {
  try {
    const { value } = await ElMessageBox.prompt(basePath ? `在 ${basePath} 中创建文件夹。` : '文件夹将创建在当前项目内，也可以输入 src/services 这样的多级路径。', '新建文件夹', {
      confirmButtonText: '创建', cancelButtonText: '取消', inputPlaceholder: '例如：src/tools',
      inputPattern: /^(?!\/)(?!.*\.\.)(?!.*[<>:"|?*])[\w\-/]+$/,
      inputErrorMessage: '请输入安全的项目相对路径',
    })
    const path = joinProjectPath(basePath, value)
    await createLabDirectory(exerciseId.value, path)
    const parent = parentPath(path)
    await loadExplorerDirectory(parent, true)
    if (parent) expandedDirectories.add(parent)
    ElMessage.success(`文件夹 ${path} 已创建`)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close' && error?.message) console.warn(error)
  }
}

async function refreshAfterEntryMutation(preferredPath = '') {
  activePath.value = ''
  openTabs.value = []
  editor?.setModel(null)
  await loadWorkspace(false)
  if (preferredPath) await openExplorerFile(preferredPath)
}

async function removeEntry(entry) {
  if (!entry?.path) return
  try {
    await ElMessageBox.confirm(`确定删除 ${entry.path}？${entry.is_directory ? '文件夹中的内容也会一并删除。' : ''}此操作不可恢复。`, '删除', { type: 'warning' })
    await deleteLabEntry(exerciseId.value, entry.path)
    await refreshAfterEntryMutation()
  } catch (_) { /* cancelled */ }
}

function closeExplorerMenu() { explorerMenu.visible = false }

function openExplorerContextMenu(event, entry) {
  const width = 260
  const height = entry.is_directory ? 390 : 410
  explorerMenu.entry = entry
  explorerMenu.x = Math.min(event.clientX, window.innerWidth - width - 8)
  explorerMenu.y = Math.min(event.clientY, window.innerHeight - height - 8)
  explorerMenu.visible = true
}

function takeContextEntry() {
  const entry = explorerMenu.entry ? { ...explorerMenu.entry } : null
  closeExplorerMenu()
  return entry
}

function isPythonEntry(entry) { return Boolean(entry && !entry.is_directory && entry.path.toLowerCase().endsWith('.py')) }

async function contextOpen() {
  const entry = takeContextEntry()
  if (entry) await openExplorerFile(entry.path)
}

async function contextNewFile() {
  const entry = takeContextEntry()
  if (entry?.is_directory) await createFile(entry.path)
}

async function contextNewDirectory() {
  const entry = takeContextEntry()
  if (entry?.is_directory) await createDirectory(entry.path)
}

async function copyText(value, message) {
  await navigator.clipboard.writeText(value)
  ElMessage.success(message)
}

async function contextCopy() {
  const entry = takeContextEntry()
  if (!entry) return
  if (entry.is_directory) return copyText(entry.path, '文件夹路径已复制')
  const file = await readLabFile(exerciseId.value, entry.path)
  if (file.binary) return ElMessage.info('二进制文件不能复制为文本')
  await copyText(file.content, '文件内容已复制')
}

async function contextCopyPath(relative) {
  const entry = takeContextEntry()
  if (!entry) return
  const value = relative ? entry.path : `/${workspace.value?.project_name || 'agent-lab'}/${entry.path}`
  await copyText(value, relative ? '相对路径已复制' : '项目路径已复制')
}

function defaultCopyName(entry) {
  const name = entry.name
  if (entry.is_directory || !name.includes('.')) return `${name}-copy`
  const dot = name.lastIndexOf('.')
  return `${name.slice(0, dot)}-copy${name.slice(dot)}`
}

async function contextDuplicate() {
  const entry = takeContextEntry()
  if (!entry || entry.path === '.venv') return
  try {
    const parent = parentPath(entry.path)
    const { value } = await ElMessageBox.prompt('输入副本名称。', '创建副本', {
      confirmButtonText: '复制', cancelButtonText: '取消', inputValue: defaultCopyName(entry),
      inputPattern: /^(?!\.?\.?$)(?!.*[\\/<>:"|?*])[^\\/<>:"|?*]+$/,
      inputErrorMessage: '请输入有效名称',
    })
    const destination = joinProjectPath(parent, value)
    await duplicateLabEntry(exerciseId.value, entry.path, destination)
    await refreshAfterEntryMutation(entry.is_directory ? '' : destination)
  } catch (_) { /* cancelled */ }
}

async function contextRename() {
  const entry = takeContextEntry()
  if (!entry || entry.path === '.venv') return
  try {
    await saveAll()
    const parent = parentPath(entry.path)
    const { value } = await ElMessageBox.prompt('输入新名称。', '重命名', {
      confirmButtonText: '重命名', cancelButtonText: '取消', inputValue: entry.name,
      inputPattern: /^(?!\.?\.?$)(?!.*[\\/<>:"|?*])[^\\/<>:"|?*]+$/,
      inputErrorMessage: '请输入有效名称',
    })
    const destination = joinProjectPath(parent, value)
    if (destination === entry.path) return
    await moveLabEntry(exerciseId.value, entry.path, destination)
    await refreshAfterEntryMutation(entry.is_directory ? '' : destination)
  } catch (_) { /* cancelled */ }
}

async function contextDelete() {
  const entry = takeContextEntry()
  if (entry?.path !== '.venv') await removeEntry(entry)
}

function shellQuote(value) { return `'${String(value).replaceAll("'", "'\\''")}'` }

async function moveTerminalToProjectPath(path) {
  await executeTerminal('cd')
  if (path) await executeTerminal(`cd ${shellQuote(path)}`)
}

async function contextOpenInTerminal() {
  const entry = takeContextEntry()
  if (!entry) return
  showTerminal()
  const directory = entry.is_directory ? entry.path : parentPath(entry.path)
  await moveTerminalToProjectPath(directory)
}

async function contextRunPython() {
  const entry = takeContextEntry()
  if (!isPythonEntry(entry)) return
  showTerminal()
  await moveTerminalToProjectPath('')
  await executeTerminal(`python ${shellQuote(entry.path)}`)
}

async function resetProject() {
  await switchProjectState('initial')
}

const projectStateCopy = {
  initial: {
    title: '切换到初始化项目',
    message: '项目文件将恢复到本关最初状态；历史成绩和“曾经通过”记录会保留，但当前工作区文件会被替换。',
    confirm: '恢复初始化状态',
  },
  passed: {
    title: '切换到全测试通过项目',
    message: '将恢复你此前亲自通过时的完整项目文件、solution.py 和每个阶段的测试结果；本地 .env 与 .venv 会保留。',
    confirm: '恢复通过状态',
  },
  repair: {
    title: '进入故障修复项目',
    message: '系统会将代表性故障写入 repair_target.py（不会影响你已经写好的 solution.py）。请在 repair_target.py 中定位并修复故障，然后提交评分。',
    confirm: '切换并开始修复',
  },
  variant: {
    title: '进入变式迁移项目',
    message: '系统会把项目切换到新的业务场景，生成独立的 solution.py 骨架和 VARIANT_TASK.md；如果本关已经完成，也会重新打开变式迁移阶段供你再次提交评分。',
    confirm: '切换到变式项目',
  },
}

async function switchProjectState(targetState, options = {}) {
  if (projectState.value === targetState && ['repair', 'variant'].includes(targetState) && !options.force) return true
  if (targetState === 'passed' && !canSwitchToPassed.value) {
    ElMessage.warning('请先亲自完成并通过一次实验推进，才能使用“全测试通过”状态')
    return false
  }
  const copy = projectStateCopy[targetState]
  if (!copy) return false
  try {
    if (!options.confirmed) {
      await ElMessageBox.confirm(copy.message, copy.title, {
        type: targetState === 'initial' ? 'warning' : 'info',
        confirmButtonText: copy.confirm,
        cancelButtonText: '保持当前项目',
      })
    }
    capabilityBusy.value = true
    await saveAll()
    const session = capabilitySession.value?.id
      ? capabilitySession.value
      : await ensureCapabilitySession()
    const result = await switchCapabilityProjectState(session.id, targetState)
    capabilitySession.value = { ...capabilitySession.value, ...(result.session || {}) }
    activePath.value = ''
    openTabs.value = []
    terminalLines.value = []
    Object.keys(stageResults).forEach(key => delete stageResults[key])
    if (targetState === 'initial') localStorage.removeItem(`lab_hint_progress:${exerciseId.value}`)
    await loadWorkspace(false)
    terminalLines.value.push({
      type: 'status',
      text: `✓ 项目已刷新为“${copy.title.replace('切换到', '')}”状态`,
    })
    if (targetState === 'repair') {
      if (files.value.some(f => f.path === 'repair_target.py')) {
        openFile('repair_target.py')
      }
      terminalLines.value.push({ type: 'status', text: '请运行 python -m lab_test，依据失败用例定位故障。' })
      showTerminal()
    }
    if (targetState === 'variant') {
      terminalLines.value.push({ type: 'status', text: '请先阅读 VARIANT_TASK.md，再在全新的 solution.py 中完成迁移任务。' })
    }
    ElMessage.success(`项目已切换并刷新：${copy.title.replace('切换到', '')}`)
    return true
  } catch (error) {
    if (error === 'cancel' || error === 'close') return false
    ElMessage.error(error.response?.data?.detail || error.message || '项目状态切换失败')
    return false
  } finally {
    capabilityBusy.value = false
  }
}

async function insertStarter() {
  const existing = models.get('solution.py')
  if (existing?.getValue().trim()) {
    try { await ElMessageBox.confirm('solution.py 已有内容，是否用本关函数骨架覆盖？', '插入骨架', { type: 'warning' }) }
    catch (_) { return }
  }
  await saveLabFile(exerciseId.value, 'solution.py', course.value.starter_code || '')
  if (existing) existing.setValue(course.value.starter_code || '')
  else {
    files.value.push({ path: 'solution.py', content: course.value.starter_code || '' })
    models.set('solution.py', new LabTextModel(course.value.starter_code || '', 'python'))
  }
  dirtyFiles.delete('solution.py')
  openFile('solution.py')
}

async function checkStage(stage) {
  checkingStage.value = stage.id
  try {
    await saveAll()
    const result = await checkLabStage(exerciseId.value, stage.id)
    stageResults[stage.id] = result
    completedStages.value = result.completed_stages || []
    if (stage.id === 'acceptance' && result.passed && workspace.value) {
      workspace.value.project_state = 'passed'
      workspace.value.state_options = {
        ...(workspace.value.state_options || {}),
        can_switch_to_passed: true,
        acceptance_ever_passed: true,
      }
    }
    queueLearningEvent('stage_check', {
      stage_id: stage.id,
      passed: result.passed,
      failed: (result.checks || []).filter(item => !item.passed).length,
      source: 'guide',
    })
    ElMessage[result.passed ? 'success' : 'warning'](result.summary)
    if (result.passed) {
      const index = stages.value.findIndex(item => item.id === stage.id)
      if (stages.value[index + 1]) toggleStage(stages.value[index + 1])
    }
  } finally { checkingStage.value = '' }
}

async function executeTerminal(forcedCommand = '') {
  const command = (forcedCommand || terminalCommand.value).trim()
  if (!command || terminalRunning.value) return
  terminalCommand.value = ''
  if (terminalHistory.value.at(-1) !== command) terminalHistory.value.push(command)
  terminalHistory.value = terminalHistory.value.slice(-80)
  terminalHistoryIndex.value = terminalHistory.value.length
  terminalLines.value.push({ type: 'command', text: command, activeEnv: terminalActiveEnv.value, cwd: terminalCwd.value })
  terminalRunning.value = true
  terminalElapsed.value = 0
  const startedAt = Date.now()
  terminalTimer = window.setInterval(() => { terminalElapsed.value = Math.floor((Date.now() - startedAt) / 1000) }, 1000)
  terminalAbortController = new AbortController()
  scrollTerminal()
  let liveLine = null
  let result = null
  try {
    await saveAll()
    result = await streamLabTerminal(exerciseId.value, command, event => {
      if (event.type === 'output') {
        if (!liveLine) {
          liveLine = { type: 'output', text: '' }
          terminalLines.value.push(liveLine)
        }
        // 按换行拆分，每行独立展示，防止 pip 大量输出挤在一个 DOM 元素中
        const parts = (event.data || '').split('\n')
        liveLine.text += parts[0]
        for (let i = 1; i < parts.length; i++) {
          liveLine = { type: 'output', text: parts[i] }
          terminalLines.value.push(liveLine)
        }
        // 限制终端行数，防止大量输出导致页面卡顿
        if (terminalLines.value.length > 5000) {
          terminalLines.value.splice(0, terminalLines.value.length - 5000)
        }
        scrollTerminal()
      } else if (event.type === 'clear') {
        terminalLines.value = []
        liveLine = null
      }
    }, terminalAbortController.signal)
    terminalActiveEnv.value = result.active_env || ''
    terminalCwd.value = result.cwd || ''
    if (liveLine) liveLine.type = result.exit_code === 0 ? 'output' : 'error'
    else if (result.output !== '__CLEAR__') terminalLines.value.push({ type: result.exit_code === 0 ? 'status' : 'error', text: result.exit_code === 0 ? `✓ 执行完成（${terminalElapsed.value}s）` : `命令退出，状态码 ${result.exit_code}` })
    if (result.exit_code === 0) {
      const payload = await getLabWorkspace(exerciseId.value, false)
      workspace.value = { ...workspace.value, ...payload }
      await loadExplorerDirectory('', true)
      for (const path of [...expandedDirectories]) await loadExplorerDirectory(path, true)
    }
    queueLearningEvent('run', {
      duration: Math.max(0, Math.round((Date.now() - startedAt) / 1000)),
      exit_code: result.exit_code,
      passed: result.exit_code === 0,
      source: 'terminal',
    })
  } catch (error) {
    const stopped = error.name === 'AbortError'
    terminalLines.value.push({ type: stopped ? 'status' : 'error', text: stopped ? '■ 命令已停止' : (error.response?.data?.detail || error.message) })
  } finally {
    if (terminalTimer) window.clearInterval(terminalTimer)
    terminalTimer = null
    terminalAbortController = null
    terminalRunning.value = false
    scrollTerminal()
    nextTick(focusTerminal)
  }
  return result
}

function stopTerminal() { terminalAbortController?.abort() }

function startTerminalResize(event) {
  terminalResizeState = {
    startY: event.clientY,
    startHeight: terminalHeight.value,
  }
  const wb = document.querySelector('.workbench')
  if (wb) wb.classList.add('resizing-terminal')
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'ns-resize'
  document.addEventListener('mousemove', handleTerminalResize)
  document.addEventListener('mouseup', stopTerminalResize)
  event.preventDefault()
}

function handleTerminalResize(event) {
  if (!terminalResizeState) return
  event.preventDefault()
  const dy = terminalResizeState.startY - event.clientY
  const newHeight = Math.max(80, Math.min(600, terminalResizeState.startHeight + dy))
  terminalHeight.value = newHeight
}

function stopTerminalResize() {
  terminalResizeState = null
  const wb = document.querySelector('.workbench')
  if (wb) wb.classList.remove('resizing-terminal')
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  document.removeEventListener('mousemove', handleTerminalResize)
  document.removeEventListener('mouseup', stopTerminalResize)
  nextTick(() => editor?.layout())
}

function startSidePanelResize(event) {
  sidePanelResizeState = {
    startX: event.clientX,
    startWidth: sidePanelWidth.value,
  }
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', handleSidePanelResize)
  document.addEventListener('mouseup', stopSidePanelResize)
  event.preventDefault()
}

function handleSidePanelResize(event) {
  if (!sidePanelResizeState) return
  event.preventDefault()
  const dx = event.clientX - sidePanelResizeState.startX
  const newWidth = Math.max(200, Math.min(500, sidePanelResizeState.startWidth + dx))
  sidePanelWidth.value = newWidth
}

function stopSidePanelResize() {
  sidePanelResizeState = null
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  document.removeEventListener('mousemove', handleSidePanelResize)
  document.removeEventListener('mouseup', stopSidePanelResize)
  nextTick(() => editor?.layout())
}

function handleTerminalKeydown(event) {
  if (event.key === 'Enter') {
    event.preventDefault()
    executeTerminal()
    return
  }
  if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
    if (!terminalHistory.value.length) return
    event.preventDefault()
    const delta = event.key === 'ArrowUp' ? -1 : 1
    terminalHistoryIndex.value = Math.max(0, Math.min(terminalHistory.value.length, terminalHistoryIndex.value + delta))
    terminalCommand.value = terminalHistoryIndex.value === terminalHistory.value.length ? '' : terminalHistory.value[terminalHistoryIndex.value]
    nextTick(() => terminalInputRef.value?.setSelectionRange(terminalCommand.value.length, terminalCommand.value.length))
    return
  }
  if (event.key !== 'Tab') return
  event.preventDefault()
  const value = terminalCommand.value
  const commandCandidates = [
    'ls', 'tree', 'pwd', 'cd', 'clear', 'python --version', 'python -m venv .venv',
    'source .venv/bin/activate', 'deactivate', 'pip install', 'pip install -r requirements.txt',
    'python -m py_compile solution.py', 'python solution.py', 'lab-test', 'python -m lab_test', 'pytest', 'git status',
  ]
  const lastToken = value.split(/\s+/).pop() || ''
  const pathCandidates = [
    ...visibleExplorerEntries.value.map(item => `${item.path}${item.is_directory ? '/' : ''}`),
  ]
  const matches = value.includes(' ')
    ? pathCandidates.filter(item => item.toLowerCase().startsWith(lastToken.toLowerCase()))
    : commandCandidates.filter(item => item.toLowerCase().startsWith(value.toLowerCase()))
  if (!matches.length) return
  if (value.includes(' ')) terminalCommand.value = `${value.slice(0, value.length - lastToken.length)}${matches[0]}`
  else terminalCommand.value = matches[0]
}

function sendStageCommand(command) {
  terminalCommand.value = command
  executeTerminal(command)
}

function setupEnvironment() {
  if (workspace.value?.virtual_env || terminalRunning.value) return
  leftMode.value = 'guide'
  currentStage.value = 'environment'
  executeTerminal('python -m venv .venv')
}

function focusTerminal() { nextTick(() => terminalInputRef.value?.focus()) }
function handleTerminalOutputClick() {
  if (window.getSelection?.().toString()) return
  focusTerminal()
}
function scrollTerminal() { nextTick(() => { if (terminalOutputRef.value) terminalOutputRef.value.scrollTop = terminalOutputRef.value.scrollHeight }) }
function scrollChat() { nextTick(() => { if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight }) }

function renderAssistantMarkdown(content) {
  const terminalLanguages = new Set(['bash', 'sh', 'shell', 'zsh', 'cmd', 'bat', 'powershell', 'terminal', 'console'])
  return renderMarkdown(content).replace(
    /(<div class="code-block-wrapper">[\s\S]*?<span class="code-lang-tag">([^<]*)<\/span>[\s\S]*?<div class="code-toolbar-actions">)/g,
    (_match, toolbar, language) => `${toolbar}<button class="code-toolbar-btn" data-action="${terminalLanguages.has(language.toLowerCase()) ? 'fill-terminal' : 'insert-editor'}">${terminalLanguages.has(language.toLowerCase()) ? '填入终端' : '插入编辑器'}</button>`,
  )
}

function handleAgentBlockAction(event) {
  const button = event.target.closest?.('[data-action="insert-editor"], [data-action="fill-terminal"]')
  if (!button) return
  const code = button.closest('.code-block-wrapper')?.querySelector('code')?.textContent || ''
  if (!code.trim()) return
  if (button.dataset.action === 'fill-terminal') {
    const command = code.split(/\r?\n/).map(line => line.trim()).find(line => line && !line.startsWith('#'))?.replace(/^[$>]\s*/, '') || ''
    terminalCommand.value = command
    showTerminal()
    ElMessage.success('命令已填入终端，确认后按 Enter 执行')
    return
  }
  if (!editor || !activePath.value) return ElMessage.warning('请先打开要插入代码的文件')
  const selection = editor.getSelection()
  editor.executeEdits('agent-manual-insert', [{ range: selection, text: code, forceMoveMarkers: true }])
  editor.focus()
  ElMessage.success(`代码已插入 ${activePath.value}，将自动保存`)
}

async function resetChat() {
  if (assistantAbortController) { assistantAbortController.abort(); assistantAbortController = null }
  if (chatMessages.value.length > 1) {
    try {
      await ElMessageBox.confirm(
        '确定要清空当前对话记录吗？',
        '清空对话',
        { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' }
      )
    } catch (_) {
      return  // 用户取消
    }
  }
  try {
    const result = await resetLabAssistant(exerciseId.value)
    assistantRuntime.value = {
      status: result.status,
      available: Boolean(result.available),
      model: result.model || '',
      provider: result.provider || '',
    }
    chatMessages.value = [{
      role: 'assistant',
      content: result.welcome,
      runtimeStatus: result.available ? '' : result.status,
    }]
  } catch (_) {
    ElMessage.error('导师对话暂时无法重置')
  }
}

function askQuick(text) { assistantQuestion.value = text; sendAssistant() }

function handleAssistantKeydown(event) {
  if (event.isComposing || event.key !== 'Enter') return
  if (event.ctrlKey) return
  event.preventDefault()
  sendAssistant()
}

async function sendAssistant() {
  const question = assistantQuestion.value.trim()
  if (!assistantRuntime.value.available) return goToModelSetup()
  if (!question || assistantLoading.value) return
  // Cancel any existing stream
  if (assistantAbortController) assistantAbortController.abort()
  assistantAbortController = new AbortController()
  const signal = assistantAbortController.signal

  chatMessages.value.push({ role: 'user', content: question })
  assistantQuestion.value = ''
  assistantLoading.value = true
  scrollChat()
  // Push a placeholder assistant message for streaming
  // Keep the streamed message itself reactive. Mutating the raw object after it
  // was inserted into a reactive array can otherwise delay the UI until "done".
  const streamMsg = reactive({ role: 'assistant', content: '', toolCalls: [], observations: [] })
  chatMessages.value.push(streamMsg)
  let workspaceChanged = false

  try {
    await saveAll()
    await streamLabAssistant(
      exerciseId.value, question, activePath.value,
      assistantMode.value, currentStage.value,
      (event) => {
        if (signal.aborted) return
        switch (event.type) {
          case 'text':
            streamMsg.content += event.content
            scrollChat()
            break
          case 'tool_call':
            streamMsg.toolCalls.push({
              tool: event.tool,
              args: event.args,
              status: 'running',
              result: '',
              preview: '',
            })
            scrollChat()
            break
          case 'tool_result':
            const tc = streamMsg.toolCalls.find(
              t => t.tool === event.tool && t.status === 'running'
            )
            if (tc) {
              tc.status = event.status || 'completed'
              tc.detail = event.detail || ''
              tc.preview = event.preview || ''
            }
            if (event.workspace_changed) workspaceChanged = true
            scrollChat()
            break
          case 'done':
            const hasAvailability = typeof event.available === 'boolean'
            assistantRuntime.value = {
              ...assistantRuntime.value,
              status: event.status || 'ready',
              // A failed model call does not mean the configured model vanished.
              // Keep the composer usable so the student can retry or continue.
              available: hasAvailability
                ? event.available
                : assistantRuntime.value.available,
            }
            if (event.observations) streamMsg.observations = event.observations
            if (event.notice) streamMsg.notice = event.notice
            if (event.status === 'error') {
              streamMsg.runtimeStatus = 'error'
              // Always append error message when it occurs, even if there's existing content
              if (event.error) {
                streamMsg.content = (streamMsg.content || '') + '\n\n⚠️ ' + event.error
              }
            } else if (event.error && !streamMsg.content) {
              streamMsg.content = event.error
            }
            break
        }
      },
      signal,
    )
  } catch (error) {
    if (error.name === 'AbortError') return
    streamMsg.content = streamMsg.content || error.response?.data?.detail || error.message || '导师请求失败，本次没有生成回答。'
    streamMsg.runtimeStatus = 'error'
  } finally {
    assistantLoading.value = false
    assistantAbortController = null
    // Remove empty placeholder if no content was received
    if (!streamMsg.content && !streamMsg.toolCalls.length) {
      chatMessages.value = chatMessages.value.filter(m => m !== streamMsg)
    }
    if (workspaceChanged && !signal.aborted) {
      const previousLeftMode = leftMode.value
      const previousActivePath = activePath.value
      await loadWorkspace(false)
      leftMode.value = previousLeftMode
      if (previousActivePath && models.has(previousActivePath)) openFile(previousActivePath)
    }
    scrollChat()
  }
}

function goToModelSetup() {
  router.push({ name: 'Profile', query: { section: 'llm' } })
}

async function handleTopAction() {
  if (capabilityStatus.value === 'verified' || capabilityStatus.value === 'skipped') {
    defenseDialog.value = true
    return
  }
  if (capabilityStatus.value === 'variant_pending') {
    await openVariantSubmission()
    return
  }
  if (capabilityStatus.value === 'defense_pending') {
    defenseDialog.value = true
    return
  }
  if (capabilityStatus.value === 'repair_pending') {
    await openRepairStage()
    return
  }
  if (!acceptancePassed.value) {
    leftMode.value = 'guide'
    const stage = currentStageRecord.value
      || stages.value.find(item => !completedStages.value.includes(item.id))
    if (stage) await checkStage(stage)
    return
  }
  await beginCapability()
}

// ── 变式迁移 ──
async function ensureVariantScenario() {
  if (capabilitySession.value?.variant_scenario) return
  capabilityBusy.value = true
  try {
    const result = await generateVariant(capabilitySession.value.id)
    capabilitySession.value = { ...capabilitySession.value, ...result.data || result }
  } catch (e) {
    ElMessage.warning(e.response?.data?.detail || '无法生成变式场景')
  } finally {
    capabilityBusy.value = false
  }
}

async function openVariantSubmission() {
  await ensureVariantScenario()
  const reopening = capabilityStatus.value === 'verified'
  if (projectState.value !== 'variant' || reopening) {
    const switched = await switchProjectState('variant', { force: reopening })
    if (!switched) return
  }
  variantDialog.value = true
}

async function continueToVariant() {
  defenseDialog.value = false
  await openVariantSubmission()
}

async function openRepairStage() {
  const reopening = capabilityStatus.value === 'verified'
  if (projectState.value !== 'repair' || reopening) {
    await switchProjectState('repair', { force: reopening })
    // 切换到 repair 后，自动打开 repair_target.py
    if (files.value.some(f => f.path === 'repair_target.py')) {
      openFile('repair_target.py')
    }
    return
  }
  defenseDialog.value = true
}

async function retryRepairAttempt() {
  capabilityBusy.value = true
  try {
    const result = await retryCapabilityRepair(capabilitySession.value.id)
    repairExplanation.value = ''
    capabilitySession.value = { ...capabilitySession.value, ...result, status: 'repair_pending' }
    defenseDialog.value = false
    await switchProjectState('repair', { confirmed: true, force: true })
    terminalLines.value.push(
      { type: 'status', text: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' },
      { type: 'status', text: `🔁 已开始第 ${result.retry_attempt || 2} 次故障修复` },
      { type: 'status', text: `上次得分：${result.previous_repair_score || 0} 分（评分记录已保留）` },
      { type: 'status', text: `故障描述：${result.mutation_description || capabilitySession.value?.mutation_description || ''}` },
      { type: 'status', text: '👉 代表性故障已写入 repair_target.py（solution.py 未受影响），请定位并修复后重新提交' },
      { type: 'status', text: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' },
    )
    showTerminal()
    ElMessage.success('已保留上次得分并重新注入故障，可以开始下一次修复')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '重新开始故障修复失败')
  } finally {
    capabilityBusy.value = false
  }
}

async function handleVariantSubmit() {
  if (projectState.value !== 'variant') {
    return ElMessage.warning('请先确认切换到变式迁移项目状态，再提交代码')
  }
  const code = variantCode.value.trim() || models.get('solution.py')?.getValue() || ''
  if (!code.trim()) return ElMessage.warning('请先在编辑器中编写变式代码')
  variantBusy.value = true
  try {
    await saveAll()
    const result = await submitVariant(capabilitySession.value.id, code)
    if (!result.variant_passed) {
      const evaluation = result.evaluation || {}
      const failedCases = (evaluation.results || []).filter(c => !c.passed)
      if (failedCases.length) {
        terminalLines.value.push(
          { type: 'error', text: `变式仍有 ${failedCases.length} 个测试点失败:` },
          ...failedCases.map(c => ({ type: 'error', text: `  ✗ ${c.description}: ${c.error || '未满足预期'}` })),
        )
      }
      ElMessage.warning(`变式已完成评分：通过 ${evaluation.passed_count || 0}/${evaluation.total || '?'}，本阶段不再阻塞后续流程`)
    }
    capabilitySession.value = { ...capabilitySession.value, ...result, status: 'verified', report: result.report }
    variantDialog.value = false
    defenseDialog.value = true
    ElMessage.success(result.variant_passed ? '🎉 变式迁移通过！完整能力验证完成。' : '变式迁移已评分并保存，完整能力验证完成。')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '变式迁移提交失败，请稍后重试')
  } finally {
    variantBusy.value = false
  }
}

async function beginCapability() {
  const solution = models.get('solution.py')
  if (!solution) return ElMessage.warning('没有找到 solution.py')
  capabilityBusy.value = true
  try {
    await saveAll()
    let session = capabilitySession.value?.id ? capabilitySession.value : await ensureCapabilitySession()
    if (session.status === 'coding') {
      session = { ...session, ...await markCapabilityCodePassed(session.id, solution.getValue()) }
    }
    capabilitySession.value = session
    for (const question of session.defense_questions || []) defenseAnswers[question.id] = ''
    defenseDialog.value = true
  } finally { capabilityBusy.value = false }
}

async function openCapabilityStep(stepId) {
  if (stepId === 'coding') {
    leftMode.value = 'guide'
    if (!['standard', 'project'].includes(layoutMode.value)) setLayout('standard')
    return
  }
  if (stepId === 'defense') {
    if (capabilityStatus.value === 'defense_pending') {
      defenseDialog.value = true
    } else if (capabilityStatus.value !== 'coding') {
      await openReviewDialog()
    }
    return
  }
  if (stepId === 'repair') {
    if (['repair_pending', 'variant_pending', 'verified'].includes(capabilityStatus.value)
        && capabilitySession.value?.mutation_code) {
      await openRepairStage()
    } else if (Number(capabilitySession.value?.repair_score) > 0) {
      await openReviewDialog()
    }
    return
  }
  if (stepId === 'variant' && ['variant_pending', 'verified'].includes(capabilityStatus.value)) {
    await openVariantSubmission()
  }
}

async function openReviewDialog() {
  if (!capabilitySession.value?.id) return ElMessage.warning('没有找到能力验证记录')
  reviewNextAction.value = ''
  reviewDialog.value = true
  reviewLoading.value = true
  reviewItems.value = []
  try {
    const data = await getSessionReview(capabilitySession.value.id)
    reviewItems.value = data.review_items || []
    reviewSummary.defense_score = Number(data.defense_score || 0)
    reviewSummary.repair_score = Number(data.repair_score || 0)
    reviewSummary.status = data.status || ''
    reviewSummary.grading_status = data.defense_grading_status || ''
    Object.keys(repairReview).forEach(key => delete repairReview[key])
    Object.assign(repairReview, data.repair_review || {})
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '获取回顾数据失败')
  } finally {
    reviewLoading.value = false
  }
}

function finishDefenseReview() {
  const nextAction = reviewNextAction.value
  reviewDialog.value = false
  reviewNextAction.value = ''
  if (nextAction === 'retry') {
    defenseDialog.value = true
    return
  }
  if (nextAction === 'repair') {
    showTerminal()
    leftMode.value = 'guide'
    ElMessage.success('已进入故障修复：请先运行 python -m lab_test，再结合失败信息定位问题')
  }
}

async function submitDefenseAnswers() {
  const unanswered = defenseQuestions.value.filter(item => !String(defenseAnswers[item.id] || '').trim())
  if (unanswered.length) return ElMessage.warning(`还有 ${unanswered.length} 个问题未回答`)
  capabilityBusy.value = true
  try {
    const answers = defenseQuestions.value.map(item => ({ question_id: item.id, answer: defenseAnswers[item.id] }))
    const result = await submitCapabilityDefense(capabilitySession.value.id, answers, 'AI提供了提示')
    capabilitySession.value = result

    if (result.defense_passed) {
      terminalLines.value.push(
        { type: 'status', text: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' },
        { type: 'status', text: '🔧 故障修复阶段已解锁，当前项目尚未改变' },
        { type: 'status', text: `故障描述：${result.mutation_description}` },
        { type: 'status', text: '' },
        { type: 'status', text: '👉 点击顶部“故障修复”，确认后系统才会切换并刷新故障项目' },
        { type: 'status', text: '👉 切换完成后运行 python -m lab_test 查看哪些测试失败' },
        { type: 'status', text: '👉 阅读 test 输出中的「输入/期望/实际」信息来定位故障' },
        { type: 'status', text: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' },
      )
    }
    defenseDialog.value = false
    startDefenseGradingPolling()
    ElMessage.success('原理答辩已完成；点击“故障修复”确认切换项目后再开始修复')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '答辩提交失败，请稍后重试')
  } finally { capabilityBusy.value = false }
}

async function submitRepairCode() {
  if (projectState.value !== 'repair') {
    defenseDialog.value = false
    return openRepairStage()
  }
  if (repairExplanation.value.trim().length < 20) {
    defenseDialog.value = true
    return ElMessage.warning('请先在能力验证窗口用至少20字说明故障根因')
  }
  capabilityBusy.value = true
  try {
    await saveAll()
    const code = models.get('repair_target.py')?.getValue() || models.get('solution.py')?.getValue() || ''
    const result = await submitCapabilityRepair(capabilitySession.value.id, code, repairExplanation.value)
    const evaluation = result.evaluation || {}
    const failedCases = (evaluation.results || []).filter(c => !c.passed)
    if (failedCases.length) {
      terminalLines.value.push(
        { type: 'error', text: `故障修复已提交，本次仍有 ${failedCases.length} 个测试点未通过，结果已计入评分：` },
        ...failedCases.map(c => ({ type: 'error', text: `  ✗ ${c.description}: ${c.error || '未满足预期'}` })),
      )
    }
    // 提交即完成本阶段；测试结果只影响评分，不再阻塞变式迁移。
    const newStatus = result.status || 'verified'
    capabilitySession.value = { ...capabilitySession.value, ...result, status: newStatus, report: result.report }
    defenseDialog.value = true
    ElMessage.success(
      newStatus === 'variant_pending'
        ? `故障修复已提交并完成评分（${Math.round(result.repair_score || 0)}分），变式迁移已解锁`
        : '故障修复已提交并完成评分',
    )
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '故障修复提交失败，请稍后重试')
  } finally { capabilityBusy.value = false }
}

function goBack() { router.push({ name: 'TaskList', params: { moduleId: moduleId.value } }) }

function handleGlobalKeydown(event) {
  if (!explorerMenu.visible) return
  if (event.key === 'Escape') closeExplorerMenu()
  if (event.key === 'F2') { event.preventDefault(); contextRename() }
  if (event.key === 'Delete') { event.preventDefault(); contextDelete() }
}

onMounted(async () => {
  document.addEventListener('click', closeExplorerMenu)
  window.addEventListener('keydown', handleGlobalKeydown)
  createEditor()
  await loadWorkspace()
  bindCodeBlockActions(chatRef.value)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeExplorerMenu)
  window.removeEventListener('keydown', handleGlobalKeydown)
  terminalAbortController?.abort()
  if (terminalTimer) window.clearInterval(terminalTimer)
  if (learningEventFlushTimer) window.clearTimeout(learningEventFlushTimer)
  if (autoSaveTimer) window.clearTimeout(autoSaveTimer)
  if (assistantAbortController) assistantAbortController.abort()
  stopDefenseGradingPolling()
  flushLearningEvents().catch(() => {})
  document.removeEventListener('mousemove', handleTerminalResize)
  document.removeEventListener('mouseup', stopTerminalResize)
  document.removeEventListener('mousemove', handleSidePanelResize)
  document.removeEventListener('mouseup', stopSidePanelResize)
  saveAll().catch(() => {})
  editor?.dispose()
  editor = null
  disposeModels()
})
</script>

<style scoped>
.ide-page { --bg:#080d18; --panel:#0e1524; --panel2:#111a2b; --line:#243044; --muted:#8693a8; --text:#dce5f4; --accent:#6d5dfc; height:100%; min-height:0; color:var(--text); background:var(--bg); overflow:hidden; box-shadow:0 18px 48px rgba(5,10,20,.22); }
button { font:inherit; }
.ide-topbar { height:58px; display:flex; align-items:center; justify-content:space-between; padding:0 14px; background:#0c1321; border-bottom:1px solid var(--line); }
.brand-area,.top-actions,.brand-area>div,.environment-pill,.ghost-action,.primary-action { display:flex; align-items:center; }
.brand-area { gap:10px; min-width:0; }.icon-button { width:34px;height:34px;border:0;border-radius:8px;color:#9aa9bd;background:transparent;cursor:pointer;font-size:18px }.icon-button:hover{background:#1b2639;color:#fff}
.brand-mark,.welcome-logo { display:grid;place-items:center;background:linear-gradient(135deg,#8b75ff,#4c7dff);color:white;font-weight:900;box-shadow:0 0 24px rgba(109,93,252,.35) }.brand-mark{width:31px;height:31px;border-radius:9px}
.project-heading { flex-direction:column;align-items:flex-start!important;min-width:0}.project-heading strong{font-size:14px}.project-heading span{font-size:11px;color:var(--muted);max-width:430px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.top-actions { gap:9px }.project-state-actions{display:flex;align-items:center;gap:5px}.project-state-actions .ghost-action{padding:7px 9px;font-size:11px}.project-state-actions .passed-state{border-color:#2b5a49;color:#a7ddc5}.project-state-actions .passed-state span{padding:1px 4px;border-radius:6px;color:#7b8799;background:#1a2433;font-size:8px}.project-state-actions button:disabled{opacity:.5;cursor:not-allowed}.layout-switcher{display:flex;align-items:center;gap:2px;padding:3px;border:1px solid #2b3749;border-radius:7px;background:#0a111d}.layout-switcher button{display:grid;width:30px;height:26px;place-items:center;border:0;border-radius:5px;color:#8794a7;background:transparent;cursor:pointer}.layout-switcher button:hover,.layout-switcher button.active{color:#eef3fb;background:#202c40}.layout-glyph{position:relative;display:block;width:16px;height:13px;border:2px solid currentColor}.layout-glyph::before,.layout-glyph::after{position:absolute;top:0;bottom:0;width:2px;background:currentColor;content:""}.layout-glyph.standard::before{left:3px}.layout-glyph.standard::after{right:3px}.layout-glyph.project::before{left:4px}.layout-glyph.project::after{display:none}.layout-glyph.focus::before,.layout-glyph.focus::after{display:none}.layout-glyph.pair::before{left:6px}.layout-glyph.pair::after{display:none}.environment-pill{gap:7px;color:#e8c27d;font-size:12px;padding:7px 10px;background:#1e1b19;border:1px solid #55452e;border-radius:7px;cursor:pointer}.environment-pill:hover:not(:disabled){color:#ffe0a3;border-color:#8d6d38;background:#2a241c}.environment-pill.ready,.environment-pill:disabled.ready{color:#a9b6ca;background:#111c2d;border-color:#26354c;cursor:default}.environment-pill:disabled:not(.ready){cursor:wait}.environment-pill i,.agent-header span i{width:7px;height:7px;background:#f0a948;border-radius:50%}.environment-pill i.online,.agent-header span i{background:#4bd39b;box-shadow:0 0 8px #4bd39b}
.ghost-action,.primary-action,.outline-button{gap:7px;border-radius:7px;padding:8px 12px;cursor:pointer;border:1px solid #34435a}.ghost-action{color:#c3cede;background:#111a29}.primary-action{color:#fff;border-color:#7768ff;background:linear-gradient(135deg,#725fff,#526dff);box-shadow:0 5px 18px rgba(86,91,255,.22)}.primary-action:disabled{opacity:.55;cursor:not-allowed}
.capability-progress{height:70px;box-sizing:border-box;display:grid;grid-template-columns:155px minmax(500px,1fr) 190px;align-items:center;gap:16px;padding:8px 14px;border-bottom:1px solid #2a3850;background:linear-gradient(90deg,#0d1626,#10192a 58%,#0b1422)}
.flow-title{display:flex;flex-direction:column;padding-right:15px;border-right:1px solid #27344a}.flow-title small{color:#6f7f98;font-size:9px;letter-spacing:.12em}.flow-title b{margin-top:4px;color:#dce5f4;font-size:11px;line-height:1.35}
.flow-track{position:relative;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));align-items:center}.flow-line{position:absolute;z-index:0;top:15px;left:12.5%;right:12.5%;height:2px;overflow:hidden;background:#29364b}.flow-line i{display:block;height:100%;background:linear-gradient(90deg,#48c993,#7a68ff);box-shadow:0 0 10px rgba(90,211,166,.55);transition:width .35s ease}
.flow-step{position:relative;z-index:1;min-width:0;display:grid;grid-template-columns:30px minmax(0,1fr) auto;align-items:center;gap:7px;padding:0 6px;border:0;color:#66758c;background:transparent;text-align:left}.flow-step:not(:disabled){cursor:pointer}.flow-step.current{color:#e4e9f3}.flow-step.done{color:#94d7bd}.flow-step.skipped{color:#56647a}.flow-node{width:28px;height:28px;display:grid;place-items:center;border:2px solid #34425a;border-radius:50%;color:#7f8da2;background:#111b2b;font:700 10px 'Cascadia Code',Consolas,monospace}.flow-step.current .flow-node{border-color:#7a6cff;color:#fff;background:#332d78;box-shadow:0 0 0 4px rgba(116,103,239,.12),0 0 18px rgba(116,103,239,.28)}.flow-step.done .flow-node{border-color:#47bd8f;color:#07130f;background:#59d4a4}.flow-step:not(:disabled):hover .flow-node{transform:translateY(-1px)}
.flow-copy{min-width:0}.flow-copy b,.flow-copy small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.flow-copy b{font-size:11px}.flow-copy small{margin-top:3px;color:#65748b;font-size:8px}.flow-step.current .flow-copy small{color:#929eb1}.flow-step em{align-self:start;margin-top:1px;padding:2px 5px;border:1px solid #2f5b4b;border-radius:8px;color:#65d4a6;background:#102b22;font-size:8px;font-style:normal;white-space:nowrap}
.flow-action{height:44px;display:flex;align-items:center;gap:9px;padding:0 12px;border:1px solid #6659df;border-radius:9px;color:#fff;background:linear-gradient(135deg,#332c78,#263a7b);box-shadow:0 7px 20px rgba(35,34,105,.3);cursor:pointer;text-align:left}.flow-action:disabled{opacity:.55;cursor:not-allowed}.flow-action>svg{font-size:18px}.flow-action span{min-width:0}.flow-action small,.flow-action b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.flow-action small{color:#9e97df;font-size:8px}.flow-action b{margin-top:2px;font-size:11px}
.workbench { height:calc(100% - 128px);min-height:0;display:grid;grid-template-columns:46px 272px 5px minmax(470px,1fr) 330px;background:var(--bg) }
.workbench.layout-project{grid-template-columns:46px 272px 5px minmax(0,1fr)}.workbench.layout-project .agent-panel{display:none}.workbench.layout-focus{grid-template-columns:46px minmax(0,1fr)}.workbench.layout-focus .side-panel,.workbench.layout-focus .agent-panel,.workbench.layout-focus .side-panel-resize-handle{display:none}.workbench.layout-pair{grid-template-columns:46px minmax(0,1fr) 360px}.workbench.layout-pair .side-panel,.workbench.layout-pair .side-panel-resize-handle{display:none}
.activity-bar{display:flex;flex-direction:column;align-items:center;background:#0a101c;border-right:1px solid var(--line);padding-top:7px}.activity-bar button{width:45px;height:45px;border:0;border-left:2px solid transparent;background:transparent;color:#77859b;font-size:21px;cursor:pointer}.activity-bar button:hover,.activity-bar button.active{color:#fff;background:#131d2e}.activity-bar button.active{border-left-color:#7c6cff}
.side-panel{min-width:0;background:var(--panel);border-right:1px solid var(--line);display:flex;flex-direction:column;overflow:hidden}
.side-panel-resize-handle{width:5px;min-width:5px;cursor:col-resize;background:transparent;transition:background .15s;z-index:10}
.side-panel-resize-handle:hover,.side-panel-resize-handle:active{background:#5b6cf0}.panel-title{height:43px;padding:0 12px;display:flex;align-items:center;justify-content:space-between;text-transform:uppercase;letter-spacing:.08em;color:#aab6c8;font-size:11px;border-bottom:1px solid var(--line)}.panel-title div{display:flex}.panel-title button,.agent-header>button,.terminal-tabs>button:last-child{border:0;background:transparent;color:#8b99ae;padding:5px;cursor:pointer}.panel-title button:hover{color:#fff}.panel-title em{font-style:normal;color:#7f70ff}
.project-root{height:36px;padding:0 10px;display:flex;align-items:center;gap:5px;border-bottom:1px solid #263247;font-size:12px;color:#d5ddeb;background:#111a29}.project-root>.el-icon:nth-child(2){color:#d5b46d}.file-list{flex:1;overflow:auto;padding:0}.file-badge.python,.tab-dot.python{color:#59a9ff}.file-badge.markdown,.tab-dot.markdown{color:#9aa8ff}.file-badge.env,.tab-dot.env{color:#f1c45a}.file-badge.json,.tab-dot.json{color:#e6a75f}.file-badge.text,.tab-dot.text{color:#a6b0c0}.empty-files,.explorer-hint{padding:18px;color:#68768c;font-size:11px;text-align:center}.explorer-hint{padding:8px;border-top:1px solid var(--line)}
.lesson-intro{padding:16px;border-bottom:1px solid var(--line)}.lesson-intro>span{font-size:10px;color:#a99fff;background:#27224c;padding:4px 7px;border-radius:10px}.lesson-intro h3{font-size:15px;margin:11px 0 7px}.lesson-intro p{font-size:12px;line-height:1.65;color:#8795aa;margin:0;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.stage-list{overflow:auto;padding:8px}.stage-card{margin-bottom:7px;border:1px solid #232f42;border-radius:8px;background:#101827;overflow:hidden}.stage-card.open{border-color:#554ca0}.stage-card.done{border-color:#265443}.stage-heading{width:100%;display:flex;align-items:center;gap:9px;padding:10px;border:0;color:#d2dbe9;background:transparent;text-align:left;cursor:pointer}.stage-heading>span:nth-child(2){flex:1;min-width:0}.stage-heading b,.stage-heading small{display:block}.stage-heading b{font-size:12px}.stage-heading small{margin-top:3px;font-size:10px;color:#75839a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.stage-heading>svg{font-size:11px}.stage-number{width:23px;height:23px;display:grid;place-items:center;border-radius:50%;background:#25304a;color:#a9b4c6;font-size:11px}.stage-card.done .stage-number{background:#174a38;color:#65e0ac}.stage-body{padding:0 11px 12px}.stage-body>p{font-size:11px;color:#9ba8bb;line-height:1.65}.command-chip{display:flex;align-items:center;padding:7px 8px;border:1px solid #26354b;border-radius:6px;background:#080f1b}.command-chip code{flex:1;color:#8fd5b7;font-size:10px;overflow:hidden;text-overflow:ellipsis}.command-chip button{border:0;color:#a99fff;background:transparent;font-size:10px;cursor:pointer}.full{width:100%;justify-content:center;margin-top:8px;color:#bbb5ff;background:transparent}.check-button{width:100%;display:flex;justify-content:center;align-items:center;gap:6px;margin-top:8px;padding:8px;border:0;border-radius:6px;color:#fff;background:#5c52d9;font-size:11px;cursor:pointer}.check-result{margin-top:9px;padding:7px;border-radius:6px;background:#2b1920}.check-result.passed{background:#122d26}.check-result>div{display:flex;gap:7px;padding:4px}.check-result>div>span{color:#ff8797}.check-result.passed>div>span{color:#57d9a1}.check-result p{margin:0}.check-result b,.check-result small{display:block;font-size:10px}.check-result small{color:#8b97aa;margin-top:2px;line-height:1.4}
.lesson-labels{display:flex;flex-wrap:wrap;gap:5px}.lesson-labels span,.lesson-labels em{padding:3px 6px;border-radius:10px;font-size:9px;font-style:normal}.lesson-labels span{color:#a99fff;background:#27224c}.lesson-labels em{color:#8fcdb2;background:#153127}.lesson-intro>p{font-size:11px}.learning-contract{display:grid;gap:6px;margin-top:10px}.learning-contract>div{padding:7px 8px;border:1px solid #243149;border-radius:6px;background:#0b1321}.learning-contract small,.learning-contract b{display:block}.learning-contract small{color:#69778d;font-size:8px;text-transform:uppercase;letter-spacing:.05em}.learning-contract b{margin-top:3px;color:#bac6d7;font-size:9px;line-height:1.45}.contract-details{margin-top:8px;border-top:1px solid #253149;padding-top:7px}.contract-details summary{color:#9e95ff;font-size:9px;cursor:pointer}.contract-details pre{max-height:130px;margin:7px 0;padding:7px;overflow:auto;border-radius:5px;color:#b8c5d7;background:#080f1b;font:9px/1.5 'Cascadia Code',Consolas,monospace;white-space:pre-wrap}.contract-details ul{margin:5px 0 0;padding-left:16px;color:#8997ab;font-size:9px;line-height:1.55}.stage-list{flex:1;min-height:0}.stage-card.current{border-color:#554ca0}.stage-heading b em{display:inline-block;margin-left:4px;padding:1px 4px;border-radius:5px;color:#c8c2ff;background:#332c79;font-size:8px;font-style:normal}.micro-step-plan{margin:9px 0;padding:8px;border:1px solid #2b3850;border-radius:7px;background:#0b1321}.micro-step-plan>strong{display:block;margin-bottom:7px;color:#c5c0ff;font-size:9px}.micro-step-plan ol{margin:0;padding:0;list-style:none}.micro-step-plan li{display:flex;align-items:flex-start;gap:7px;padding:5px 0;border-top:1px solid rgba(255,255,255,.05)}.micro-step-plan li:first-child{border-top:0}.micro-step-plan li>span{width:17px;height:17px;display:grid;flex:0 0 17px;place-items:center;border-radius:50%;color:#aaa3ff;background:#282253;font-size:8px}.micro-step-plan p{margin:0}.micro-step-plan b,.micro-step-plan small{display:block;font-size:9px}.micro-step-plan small{margin-top:2px;color:#6f7e94;line-height:1.4}.hint-ladder{display:grid;gap:6px;margin-top:9px}.hint-reveal{width:100%;display:flex;align-items:center;justify-content:center;gap:5px;padding:7px;border:1px dashed #4b4778;border-radius:6px;color:#b8b1ff;background:#171630;font-size:9px;cursor:pointer}.hint-reveal:disabled{color:#68738a;border-color:#30394a;background:#111823;cursor:default}.hint-card{padding:8px;border-left:2px solid #7467ef;border-radius:5px;background:#171b30}.hint-card span{float:right;color:#6f7c91;font-size:8px}.hint-card b{display:block;color:#bcb7ff;font-size:9px}.hint-card p{margin:4px 0 0;color:#9aa7ba;font-size:9px;line-height:1.55}.reflection-card{margin:10px 8px 14px;padding:10px;border:1px solid #34415a;border-radius:8px;background:#101a2a}.reflection-heading{display:flex;align-items:center;justify-content:space-between}.reflection-heading span{color:#d7def0;font-size:11px;font-weight:700}.reflection-heading em{padding:2px 6px;border-radius:8px;color:#e5b96c;background:#3a2d18;font-size:8px;font-style:normal}.reflection-heading em.done{color:#8cd6af;background:#173526}.reflection-card>p{margin:7px 0;color:#7f8da2;font-size:9px;line-height:1.5}.reflection-card label{display:block;margin-top:9px}.reflection-card label>span{display:block;margin-bottom:5px;color:#abb6c8;font-size:9px;line-height:1.45}.reflection-card textarea{width:100%;resize:vertical;box-sizing:border-box;padding:7px;border:1px solid #303e56;border-radius:6px;color:#dbe4f2;background:#09111e;font:9px/1.5 inherit;outline:none}.reflection-card textarea:focus{border-color:#6d5dfc}.reflection-card textarea:disabled{opacity:.7}.reflection-card .check-button{margin-top:10px}
.process-evidence-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:12px;text-align:left}.process-evidence-summary span{padding:7px 9px;border:1px solid #dfe5ef;border-radius:7px;color:#7a8494;background:#f7f9fc;font-size:11px}.process-evidence-summary b{float:right;color:#465066}
.editor-column{min-width:0;display:flex;flex-direction:column;overflow:hidden;background:#0b111d}.editor-tabs{flex:0 0 38px;display:flex;min-width:0;background:#0c1320;border-bottom:1px solid var(--line);overflow:hidden}.editor-tabs>button:not(.save-button){height:38px;display:flex;align-items:center;gap:6px;padding:0 10px;border:0;border-right:1px solid #202b3d;color:#8794a7;background:#101826;font-size:11px;cursor:pointer;white-space:nowrap}.editor-tabs>button.active{color:#e9eef7;background:#0b111d;border-top:1px solid #7464ff}.tab-dot{width:7px;height:7px;border-radius:50%;background:currentColor}.tab-close{font-size:12px;opacity:0}.editor-tabs button:hover .tab-close{opacity:1}.editor-tabs button i{font-style:normal;color:#887aff}.editor-spacer{flex:1}.editor-engine-badge{align-self:center;margin-right:8px;color:#65758c;font:9px 'Cascadia Code',Consolas,monospace;white-space:nowrap}.editor-tabs>.editor-hint-button{height:28px!important;align-self:center;margin-right:5px;border:1px solid #3d4a65!important;border-radius:6px;color:#b4adff!important;background:#1b2038!important}.editor-tabs>.editor-hint-button:hover{border-color:#7467ee!important;color:#fff!important}.save-button{border:0;border-left:1px solid var(--line);background:#0e1726;color:#9aa8bc;padding:0 11px;cursor:pointer;display:flex;gap:5px;align-items:center;font-size:11px}.code-editor-host{min-width:0;min-height:200px;flex:1;overflow:hidden}.code-editor-host :deep(.cm-editor){height:100%}.code-editor-host :deep(.cm-scroller){overflow:auto}.code-editor-host :deep(.cm-tooltip-autocomplete){z-index:50;min-width:240px;border-radius:7px;overflow:hidden;background:#121c2c}.code-editor-host :deep(.cm-tooltip-autocomplete ul li[aria-selected]){background:#4d43a6;color:#fff}.welcome-editor{grid-row:auto;flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#8190a7}.welcome-logo{width:60px;height:60px;border-radius:18px;font-size:29px;opacity:.75}.welcome-editor h2{font-size:18px;color:#c9d3e2;margin:18px 0 6px}.welcome-editor p{font-size:12px;margin:0 0 20px}.terminal-panel{min-height:80px;overflow:hidden;border-top:1px solid var(--line);background:#090f1a}.terminal-resize-handle{flex:0 0 24px;position:relative;z-index:10;display:flex;align-items:center;justify-content:center;height:24px;cursor:ns-resize;user-select:none;margin:-2px 0}.terminal-resize-handle:hover .terminal-resize-bar,.workbench.resizing-terminal .terminal-resize-bar{height:6px;background:#5b6cf0;box-shadow:0 0 8px rgba(91,108,240,.35)}.terminal-resize-bar{width:100%;height:5px;border-radius:3px;background:#2a3a54;transition:all .15s}.workbench.resizing-terminal .agent-panel,.workbench.resizing-terminal .side-panel,.workbench.resizing-terminal .activity-bar,.workbench.resizing-terminal .side-panel-resize-handle{pointer-events:none}.workbench.resizing-terminal,.workbench.resizing-terminal *{user-select:none!important}.terminal-tabs{height:35px;display:flex;align-items:center;border-bottom:1px solid #1e293a}.terminal-tabs button{height:35px;border:0;color:#8997aa;background:transparent;font-size:11px;padding:0 12px;cursor:pointer}.terminal-tabs button.active{color:#e4eaf3;border-bottom:1px solid #796bff}.terminal-tabs span{margin-left:auto;color:#526077;font-size:10px}.terminal-tabs span.running{color:#5ed5a4}.terminal-tabs .stop-terminal{height:24px;margin-left:9px;padding:0 8px;border:1px solid #633844;border-radius:5px;color:#ff9aaa;background:#28141b}.terminal-output{height:calc(100% - 36px);overflow:auto;padding:9px 13px;color:#bfcbda;font:12px/1.55 'Cascadia Code',Consolas,monospace;cursor:text;user-select:text}.terminal-output *{user-select:text}.terminal-welcome{color:#687891;margin-bottom:6px}.terminal-line{display:flex;gap:8px}.terminal-line pre{margin:0;white-space:pre-wrap;font:inherit}.terminal-line.command pre{color:#e7ecf4}.terminal-line.error pre{color:#ff7f8f}.terminal-line.output pre{color:#a6b8ca}.terminal-line.status pre{color:#6fd2a8}.prompt-symbol{color:#58d5a2;font-weight:800}.prompt-env{color:#67d5a4;font-weight:700}.terminal-input-row{display:flex;align-items:center;gap:7px}.prompt-path{color:#8075ff}.terminal-input-row input{flex:1;border:0;outline:0;color:#fff;background:transparent;font:inherit;user-select:text}
.stage-submit-banner{display:flex;flex:0 0 auto;align-items:center;justify-content:space-between;gap:16px;padding:9px 12px;border-bottom:1px solid #315543;background:linear-gradient(90deg,#10251f,#111d28)}.stage-submit-banner.variant{border-bottom-color:#4d4389;background:linear-gradient(90deg,#1b1838,#111d28)}.stage-submit-banner>div{min-width:0}.stage-submit-banner small,.stage-submit-banner b{display:block}.stage-submit-banner small{color:#66d5a6;font-size:9px;letter-spacing:.06em}.stage-submit-banner.variant small{color:#9c91ff}.stage-submit-banner b{margin-top:3px;overflow:hidden;color:#dce5f4;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.stage-submit-banner .primary-action{flex:0 0 auto;justify-content:center;min-width:150px}
.agent-panel{min-width:0;min-height:0;background:var(--panel);border-left:1px solid var(--line);display:grid;grid-template-rows:58px minmax(0,1fr) auto 142px}.agent-header{display:flex;align-items:center;gap:9px;padding:0 12px;border-bottom:1px solid var(--line)}.agent-avatar,.mini-avatar{display:grid;place-items:center;border-radius:10px;color:white;background:linear-gradient(135deg,#7a65ff,#4d7cff)}.agent-avatar{width:34px;height:34px}.agent-header>div:nth-child(2){flex:1;min-width:0}.agent-header b,.agent-header span{display:block}.agent-header b{font-size:12px}.agent-header span{max-width:235px;margin-top:3px;overflow:hidden;color:#7f8ea5;font-size:9px;text-overflow:ellipsis;white-space:nowrap}.agent-header span i{display:inline-block;width:6px;height:6px;margin-right:5px;border-radius:50%;background:#66748a}.agent-header span.ready i{background:#51d39a;box-shadow:0 0 7px rgba(81,211,154,.45)}.agent-header span.setup_required i{background:#e8aa52}.agent-header span.error i{background:#ff7184}.chat-list{min-height:0;overflow-x:hidden;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;padding:14px 12px}.chat-message{display:flex;gap:8px;margin-bottom:13px}.chat-message.user{justify-content:flex-end}.mini-avatar{width:24px;height:24px;flex:0 0 24px;font-size:10px}.message-bubble{max-width:88%;min-width:0;padding:9px 10px;border-radius:4px 11px 11px 11px;background:#182236;color:#c5d0df;font-size:11px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere}.message-bubble.runtime-message{border:1px solid #59492e;background:#211c16}.chat-message.assistant .message-bubble{white-space:normal}.chat-message.user .message-bubble{background:#4c43a2;color:white;border-radius:11px 4px 11px 11px}.message-bubble small{display:block;margin-top:7px;padding-top:6px;border-top:1px solid rgba(255,255,255,.08);color:#7f8da2;font-size:9px}.agent-observations{margin-top:8px;padding-top:7px;border-top:1px solid rgba(255,255,255,.08)}.agent-observations summary{color:#9c94ff;font-size:9px;cursor:pointer}.agent-observations>div{display:flex;align-items:flex-start;gap:6px;margin-top:6px}.agent-observations>div>span{color:#718099;font-size:8px}.agent-observations>div>span.completed,.agent-observations>div>span.passed{color:#54d59d}.agent-observations>div>span.attention{color:#efb35c}.agent-observations p{margin:0}.agent-observations p b,.agent-observations p small{display:block;margin:0;padding:0;border:0;font-size:9px}.agent-observations p small{margin-top:1px;color:#6f7d91}.assistant-markdown :deep(p){margin:0 0 8px}.assistant-markdown :deep(p:last-child){margin-bottom:0}.assistant-markdown :deep(ul),.assistant-markdown :deep(ol){margin:7px 0;padding-left:20px}.assistant-markdown :deep(h1),.assistant-markdown :deep(h2),.assistant-markdown :deep(h3){margin:12px 0 7px;color:#eef3fb;font-size:13px}.assistant-markdown :deep(code:not(pre code)){padding:2px 5px;border-radius:4px;color:#9fe0c2;background:#0b1321}.assistant-markdown :deep(.code-block-wrapper){margin:9px 0;border:1px solid #2b3850;border-radius:7px;background:#080f1b;overflow:hidden}.assistant-markdown :deep(.code-toolbar){display:flex;align-items:center;justify-content:space-between;gap:4px;padding:5px 7px;border-bottom:1px solid #273349;background:#111a29}.assistant-markdown :deep(.code-lang-tag){color:#8998ae;font-size:9px}.assistant-markdown :deep(.code-toolbar-actions){display:flex;gap:3px}.assistant-markdown :deep(.code-toolbar-btn){width:auto;height:auto;padding:3px 5px;border:0;border-radius:4px;color:#9ba9bd;background:#1b273a;font-size:8px;cursor:pointer}.assistant-markdown :deep(.code-toolbar-btn:hover){color:#fff;background:#34425b}.assistant-markdown :deep(pre){margin:0;padding:9px;overflow:auto;color:#c9d6e7;font:10px/1.55 'Cascadia Code',Consolas,monospace;white-space:pre}.typing{display:flex;gap:4px;padding:12px}.typing i{width:5px;height:5px;border-radius:50%;background:#8f83ff;animation:blink 1s infinite}.typing i:nth-child(2){animation-delay:.16s}.typing i:nth-child(3){animation-delay:.32s}@keyframes blink{50%{opacity:.25;transform:translateY(-2px)}}
.tool-calls-inline{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px;padding-bottom:7px;border-bottom:1px solid rgba(255,255,255,.06)}.tool-call-chip{display:inline-flex;align-items:center;gap:5px;padding:4px 8px;border-radius:6px;font-size:10px;background:#1a2438;border:1px solid #2b3850;color:#a9b6ca}.tool-call-chip.running{border-color:#5b4fc4;color:#c5bfff;background:#1e1850}.tool-call-chip.completed{border-color:#265443;color:#62d4a5;background:#0f2620}.tool-call-icon{font-size:11px}.tool-call-name{font-weight:650;color:#c9d4e8}.tool-call-arg{color:#7889a5;font-family:'Cascadia Code',Consolas,monospace;font-size:9px;margin-left:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px}.quick-prompts{display:flex;flex-wrap:wrap;gap:5px;padding:7px 10px}.quick-prompts button{padding:5px 7px;border:1px solid #2a3850;border-radius:12px;color:#8998ae;background:#101a2a;font-size:9px;cursor:pointer}.quick-prompts button:hover{color:#c7c1ff;border-color:#6156bb}.quick-prompts .setup-model-button{width:100%;border-color:#6758d7;color:#c9c3ff;background:#282252}.agent-composer{margin:0 10px 10px;padding:8px;border:1px solid #34425b;border-radius:9px;background:#0a111e}.agent-composer:focus-within{border-color:#6c5fe7}.assistant-mode-switch{display:flex!important;justify-content:flex-start!important;gap:3px;margin:-2px 0 6px}.assistant-mode-switch button{width:auto!important;height:23px!important;padding:0 9px!important;border:1px solid #2c3950!important;border-radius:6px!important;color:#7f8da3!important;background:transparent!important;font-size:9px!important}.assistant-mode-switch button.active{color:#fff!important;border-color:#6658e9!important;background:#332c79!important}.agent-composer textarea{width:100%;resize:none;border:0;outline:0;color:#dce5f2;background:transparent;font:11px/1.5 inherit}.agent-composer textarea:disabled{color:#66748a;cursor:not-allowed}.agent-composer>div{display:flex;align-items:center;justify-content:space-between}.agent-composer span{color:#56647a;font-size:9px}.agent-composer button{width:27px;height:27px;border:0;border-radius:7px;color:white;background:#6658e9;cursor:pointer}.agent-composer button:disabled{opacity:.4}
.dialog-title{display:flex;flex-direction:column}.dialog-title span{color:#7b6eff;font-size:11px}.dialog-title b{font-size:18px;margin-top:4px}.defense-form>p,.repair-form p{color:#6c7789;font-size:13px}.defense-form label{display:block;margin:15px 0}.defense-form label>span{display:block;margin-bottom:7px;font-size:13px;font-weight:600}.dialog-submit{margin-top:12px}.repair-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px}.repair-actions .dialog-submit{margin-left:0}.verified-report{text-align:center;padding:25px}.score-ring{width:95px;height:95px;display:grid;place-items:center;margin:auto;border:7px solid #59d7a3;border-radius:50%;color:#30b981;font-size:28px;font-weight:900}.score-ring.low{border-color:#e6a817;color:#b8860b}
@media(max-width:1200px){.capability-progress{grid-template-columns:minmax(500px,1fr) 180px}.flow-title{display:none}.flow-step{grid-template-columns:30px minmax(0,1fr)}.flow-step em{display:none}.workbench.layout-standard{grid-template-columns:46px 240px 5px minmax(430px,1fr) 290px}.project-heading span,.environment-pill{display:none}}@media(max-width:980px){.capability-progress{grid-template-columns:minmax(430px,1fr) 165px;gap:8px;padding-inline:8px}.flow-copy small{display:none}.workbench.layout-standard{grid-template-columns:46px 230px 5px minmax(430px,1fr)}.workbench.layout-standard .agent-panel{display:none}.layout-switcher{display:none}}
.test-case-list{grid-column:2;margin:7px 0 1px;padding:5px 0 2px;border-top:1px solid rgba(255,255,255,.08);list-style:none}.test-case-list li{display:flex;gap:7px;padding:5px 0;color:#ff9aa8}.test-case-list li.passed{color:#62d4a5}.test-case-list li>span{width:14px;flex:0 0 14px;font-size:12px;line-height:1.5}.test-case-content{flex:1;min-width:0}.test-case-header{display:flex;align-items:center;justify-content:space-between;gap:6px}.test-case-header b{font-size:10px;color:#c5cfdd}.test-case-header b em{display:inline-block;margin-left:4px;padding:1px 5px;border-radius:4px;color:#ffc0c8;background:#4a2028;font-size:8px;font-style:normal}.test-duration{color:#68768c!important;font-size:8px!important;margin:0!important;padding:0!important;border:0!important}.test-detail{display:block;margin-top:3px;color:#7f8da2;font-size:9px;line-height:1.45}.test-debug-info{margin-top:6px;padding:7px 8px;border:1px solid #2a3850;border-radius:6px;background:#0a111e}.debug-row{margin:3px 0}.debug-row:first-child{margin-top:0}.debug-label{display:inline-block;width:68px;color:#8998ae;font-size:8px;font-weight:600}.debug-row code{display:inline-block;max-width:100%;padding:3px 6px;border-radius:4px;background:#131d2e;color:#bfcbda;font:9px/1.5 'Cascadia Code',Consolas,monospace;white-space:pre-wrap;word-break:break-all;overflow-wrap:anywhere}.debug-row.expected code{color:#57d9a1;background:#0f2620}.debug-row.actual code{color:#ff9aa8;background:#260f14}.test-case-list small.next-action,.test-case-content>small.next-action{margin-top:4px;color:#c8bfff;font-size:9px;display:block}.check-result-item{display:grid!important;grid-template-columns:12px minmax(0,1fr);align-items:start}
.explorer-context-menu{position:fixed;z-index:5000;width:250px;padding:6px;border:1px solid #354157;border-radius:8px;background:#171c26;box-shadow:0 14px 36px rgba(0,0,0,.5)}.explorer-context-menu button{width:100%;height:31px;padding:0 10px;display:flex;align-items:center;justify-content:space-between;border:0;border-radius:5px;color:#d1d7e2;background:transparent;font-size:12px;text-align:left;cursor:pointer}.explorer-context-menu button:hover:not(:disabled){color:#fff;background:#293244}.explorer-context-menu button.danger{color:#ff9aa8}.explorer-context-menu button:disabled{color:#5f6878;cursor:not-allowed}.explorer-context-menu kbd{padding:2px 5px;border:1px solid #3a4352;border-radius:4px;color:#929baa;background:#202632;font:10px 'Cascadia Code',Consolas,monospace}.menu-separator{height:1px;margin:5px -6px;background:#343b48}
.preview-toggle-btn{display:flex;align-items:center;gap:5px;padding:0 11px;border:0;border-left:1px solid var(--line);background:#0e1726;color:#9aa8bc;font-size:11px;cursor:pointer}.preview-toggle-btn:hover,.preview-toggle-btn.active{color:#fff;background:#1b2740}.preview-toggle-btn.active{border-bottom:2px solid #7464ff}.markdown-preview{flex:1;overflow:auto;padding:24px 32px;color:#dce5f4;font-size:13px;line-height:1.8;background:#0b111d}.markdown-preview :deep(h1){font-size:24px;color:#e9eef7;border-bottom:1px solid #243044;padding-bottom:10px;margin:0 0 18px}.markdown-preview :deep(h2){font-size:19px;color:#dce5f4;margin:28px 0 12px}.markdown-preview :deep(h3){font-size:15px;color:#c5cfe0;margin:22px 0 10px}.markdown-preview :deep(p){margin:0 0 12px}.markdown-preview :deep(ul),.markdown-preview :deep(ol){margin:8px 0;padding-left:24px}.markdown-preview :deep(li){margin:4px 0}.markdown-preview :deep(code:not(pre code)){padding:2px 6px;border-radius:4px;color:#9fe0c2;background:#131d2e;font-size:12px}.markdown-preview :deep(pre){background:#080f1b;border:1px solid #243044;border-radius:8px;padding:14px;overflow:auto}.markdown-preview :deep(pre code){font-size:12px;color:#c9d6e7}.markdown-preview :deep(blockquote){margin:12px 0;padding:8px 16px;border-left:3px solid #6d5dfc;background:#111a29;color:#9aa8bc}.markdown-preview :deep(table){border-collapse:collapse;margin:12px 0;width:100%}.markdown-preview :deep(th),.markdown-preview :deep(td){padding:8px 12px;border:1px solid #243044;text-align:left}.markdown-preview :deep(th){background:#111a29;font-weight:600}.markdown-preview :deep(a){color:#7b6eff}.markdown-preview :deep(img){max-width:100%}
</style>
<style>
/* 能力验证 & 关卡评分全局样式 */
.score-ring.low{border-color:#e6a817;color:#b8860b}
.score-dimensions{margin-top:14px;padding:12px;background:#111a29;border-radius:8px;text-align:left}
.dim-row{display:flex;justify-content:space-between;padding:4px 0;font-size:12px;color:#aab6c8}
.dim-row .pass{color:#57d9a1}
.dim-row .ok{color:#e6c35a}
.dim-row .low{color:#e6a817}
.dim-row .skip{color:#68768c}
.capability-choice-form p{font-size:13px;line-height:1.7}
.choice-cards{display:flex;gap:14px}
.choice-card{flex:1;padding:18px;border:1px solid #2a3850;border-radius:10px;background:#111a29;cursor:pointer;text-align:center;transition:all .18s;position:relative}
.choice-card:hover{transform:translateY(-2px)}
.choice-card.recommended:hover{border-color:#6658e9;box-shadow:0 6px 20px rgba(102,88,233,.25)}
.choice-card.skip:hover{border-color:#4b5568;box-shadow:0 6px 20px rgba(75,85,104,.20)}
.choice-icon{font-size:28px;margin-bottom:8px}
.choice-card h4{font-size:14px;color:#e9eef7;margin:0 0 6px}
.choice-card p{font-size:11px;color:#8693a8;line-height:1.55;margin:0}
.choice-tag{display:inline-block;margin-top:10px;padding:3px 10px;border-radius:10px;font-size:10px;font-weight:600}
.choice-tag.recommended{color:#c4bfff;background:#2a2369;border:1px solid #5347c7}
.choice-tag.skip{color:#8794a7;background:#1b2436;border:1px solid #3a4456}
.review-body{display:flex;flex-direction:column;gap:16px}
.review-overview{display:grid;grid-template-columns:88px minmax(0,1fr);align-items:center;gap:16px;padding:14px;border:1px solid #34415a;border-radius:10px;background:linear-gradient(135deg,#101b2d,#151c33)}.review-total-score{width:74px;height:74px;display:flex;align-items:baseline;justify-content:center;border:5px solid #4b5870;border-radius:50%;color:#dce5f4}.review-total-score strong{font-size:25px}.review-total-score span{font-size:10px}.review-total-score.passed{border-color:#51c997;color:#68dcad}.review-total-score.retry{border-color:#d89554;color:#efb46f}.review-overview>div:last-child small,.review-overview>div:last-child b{display:block}.review-overview>div:last-child small{color:#75839a;font-size:9px;letter-spacing:.08em}.review-overview>div:last-child b{margin-top:4px;color:#e2e8f2;font-size:15px}.review-overview p{margin:6px 0 0;color:#8997aa;font-size:10px;line-height:1.5}
.review-card{border:1px solid #2a3850;border-radius:9px;background:#111a29;overflow:hidden}
.review-question-header{display:flex;align-items:flex-start;gap:10px;padding:12px;border-bottom:1px solid #243044;background:#0e1624}
.review-q-num{width:24px;height:24px;display:grid;place-items:center;border-radius:50%;background:#2f3c54;color:#aab6c8;font-size:11px;font-weight:700;flex-shrink:0}
.review-question-header b{display:block;font-size:12px;color:#dce5f4}
.review-question-header small{font-size:10px;color:#75839a}
.review-score-tag{padding:2px 8px;border-radius:8px;font-size:10px;font-weight:700;flex-shrink:0;margin-left:auto}
.review-score-tag.good{color:#57d9a1;background:#122d26;border:1px solid #265443}
.review-score-tag.ok{color:#e6c35a;background:#2a2410;border:1px solid #554c2e}
.review-score-tag.low{color:#ff9aa8;background:#2a181c;border:1px solid #55303a}
.review-compare{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px}
.review-col{min-width:0}
.review-col-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#9aa8bc;margin-bottom:7px;padding:4px 8px;background:#0a111e;border-radius:4px}
.review-col-title.reference{color:#7b6eff;background:#1a1540}
.review-answer{font-size:11px;line-height:1.65;color:#c5d0df;padding:9px;border-radius:6px;background:#0b1321;min-height:60px;white-space:pre-wrap}
.review-answer.user{border-left:3px solid #534c8c}
.review-answer.reference{border-left:3px solid #50b885;max-height:360px;overflow-y:auto}
.review-answer.reference p{margin:0 0 6px}
.review-answer.reference ul,.review-answer.reference ol{margin:4px 0;padding-left:18px}
.review-feedback{margin-top:7px;padding:8px;border-radius:5px;background:#1a1c2a;font-size:10px;color:#9ba8c0;line-height:1.5}
.review-feedback b{display:block;color:#c4bfff;margin-bottom:3px}
.review-points{font-size:9px;padding:5px 8px;margin-top:5px;border-radius:4px;line-height:1.5}
.review-points.hit{color:#57d9a1;background:#0f2620}
.review-points.miss{color:#ff9aa8;background:#260f14}
.review-tip{text-align:center;color:#68768c;font-size:11px;margin:0;padding:8px}
.repair-review-card{padding:14px;border:1px solid #35445d;border-radius:9px;background:#0e1726}.repair-review-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.repair-review-heading small,.repair-review-heading b{display:block}.repair-review-heading small{color:#8391a7;font-size:10px}.repair-review-heading b{margin-top:3px;color:#dbe4f2;font-size:13px}.repair-review-heading>span{color:#65d6a6;font-size:20px;font-weight:800}.repair-score-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}.repair-score-grid>div{padding:9px;border-radius:6px;background:#111f31}.repair-score-grid small,.repair-score-grid b{display:block}.repair-score-grid small{color:#74839a;font-size:9px}.repair-score-grid b{margin-top:4px;color:#cdd7e6;font-size:12px}.repair-review-card p{margin:7px 0 0;color:#9eacc0;font-size:10px;line-height:1.6}.repair-review-card p b{color:#cbd6e5}
.review-next-action{align-self:flex-end;justify-content:center;min-width:190px}
.knowledge-detail-loading{text-align:center;padding:40px;color:#8693a8}
.knowledge-detail-loading .el-icon{font-size:36px;margin-bottom:12px}
/* 变式迁移 */
.variant-form{padding:4px 0}.variant-scenario-card{margin-bottom:14px;padding:14px;border:1px solid #3a4660;border-radius:9px;background:#0f1827}.variant-scenario-card h4{font-size:13px;color:#7b6eff;margin:0 0 10px}.variant-scenario-content{font-size:12px;color:#c5d0df;line-height:1.7}.variant-scenario-content :deep(h3){font-size:14px;color:#dce5f4;margin:0 0 8px}.variant-scenario-content :deep(p){margin:6px 0}.variant-scenario-content :deep(ul),.variant-scenario-content :deep(ol){margin:6px 0;padding-left:20px}.variant-scenario-content :deep(li){margin:3px 0}.variant-scenario-content :deep(code){padding:2px 5px;border-radius:4px;color:#9fe0c2;background:#0b1321;font-size:11px}.variant-scenario-content :deep(pre){padding:10px;border-radius:6px;background:#080f1b;overflow:auto}.variant-scenario-content :deep(pre code){padding:0;background:transparent;font-size:11px}.variant-instruction{margin:12px 0;color:#8998ae;font-size:12px;line-height:1.6}.variant-actions{display:flex;margin-top:16px}
.variant-meta{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:0 0 12px}.variant-meta span{padding:4px 8px;border:1px solid #36435b;border-radius:999px;color:#aab7ca;background:#111c2d;font-size:10px}.variant-meta b{margin-left:auto;color:#9fe0c2;font-size:13px}.variant-result-card{display:grid;gap:6px;padding:13px 14px;border:1px solid #315c4c;border-radius:9px;background:#10241d;color:#c8ded5}.variant-result-card b{color:#8fd7b8;font-size:14px}.variant-result-card span{font-size:12px}.variant-result-card p{margin:0;color:#8fa99e;font-size:11px;line-height:1.6}
.repair-result-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:16px 0}.repair-result-grid>div{display:grid;gap:5px;padding:10px;border:1px solid #313d52;border-radius:8px;background:#0e1725}.repair-result-grid small{color:#77869c;font-size:10px}.repair-result-grid b{color:#d9e2ef;font-size:14px}.repair-choice-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}.repair-choice-actions button{display:flex;align-items:center;justify-content:center;gap:6px}.text-review-button{margin-top:12px;border:0;color:#94a5bd;background:transparent;font-size:11px;cursor:pointer}.text-review-button:hover{color:#cbd6e6}
</style>
