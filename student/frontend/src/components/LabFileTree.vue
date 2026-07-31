<template>
  <ul :class="['lab-file-tree', { 'lab-file-tree-root': depth === 0 }]" role="tree">
    <li v-for="entry in entries" :key="entry.path" class="lab-tree-item" role="treeitem">
      <button
        :class="[
          'lab-tree-row',
          { directory: entry.is_directory, expanded: entry.is_directory && expanded.has(entry.path),
            virtual: entry.virtual, active: entry.path === activePath },
        ]"
        :aria-expanded="entry.is_directory ? expanded.has(entry.path) : undefined"
        :title="entry.path"
        @click="$emit('activate', entry)"
        @contextmenu.prevent="$emit('contextmenu', $event, entry)"
      >
        <el-icon v-if="entry.is_directory" class="lab-tree-chevron">
          <ArrowDown v-if="expanded.has(entry.path)" /><ArrowRight v-else />
        </el-icon>
        <span v-else class="lab-tree-chevron placeholder">•</span>

        <el-icon v-if="entry.is_directory" class="lab-tree-folder">
          <FolderOpened v-if="expanded.has(entry.path)" /><Folder v-else />
        </el-icon>
        <span v-else :class="['lab-tree-file-icon', fileKind(entry.path)]">{{ fileLabel(entry.path) }}</span>

        <span class="lab-tree-name">{{ entry.name }}</span>
        <span v-if="entry.virtual" class="lab-tree-tag">Python</span>
        <span v-if="dirtyPaths.has(entry.path)" class="lab-tree-dirty" title="未保存">●</span>
      </button>

      <LabFileTree
        v-if="entry.is_directory && expanded.has(entry.path)"
        class="lab-tree-children"
        :entries="children[entry.path] || []"
        :children="children"
        :expanded="expanded"
        :active-path="activePath"
        :dirty-paths="dirtyPaths"
        :depth="depth + 1"
        @activate="entry => $emit('activate', entry)"
        @contextmenu="(event, child) => $emit('contextmenu', event, child)"
      />
    </li>
  </ul>
</template>

<script setup>
defineProps({
  entries: { type: Array, default: () => [] },
  children: { type: Object, required: true },
  expanded: { type: Object, required: true },
  activePath: { type: String, default: '' },
  dirtyPaths: { type: Object, required: true },
  depth: { type: Number, default: 0 },
})

defineEmits(['activate', 'contextmenu'])

function fileKind(path) {
  if (path.endsWith('.py')) return 'python'
  if (path.endsWith('.md')) return 'markdown'
  if (path.includes('.env')) return 'env'
  if (path.endsWith('.json')) return 'json'
  if (path.endsWith('.yml') || path.endsWith('.yaml')) return 'yaml'
  return 'text'
}

function fileLabel(path) {
  return {
    python: 'Py', markdown: 'M↓', env: '⚙', json: '{}', yaml: 'Y', text: '•',
  }[fileKind(path)]
}
</script>

<style>
.lab-file-tree{list-style:none;margin:0;padding:0;color:#b8c2d1;font-size:12px}.lab-file-tree-root{padding:4px 5px 10px}.lab-tree-item{position:relative;margin:0;padding:0}.lab-tree-row{position:relative;width:100%;height:30px;padding:0 7px;display:flex;align-items:center;gap:6px;border:0;border-radius:4px;color:inherit;background:transparent;text-align:left;cursor:pointer}.lab-tree-row:hover{background:#1b2637}.lab-tree-row.active{color:#fff;background:#293448}.lab-tree-row.virtual{color:#9ad8b7}.lab-tree-chevron{width:13px;min-width:13px;color:#7f8b9e;font-size:12px}.lab-tree-chevron.placeholder{display:grid;place-items:center;color:#3f4a5a;font-size:12px}.lab-tree-folder{width:17px;min-width:17px;color:#c4cedf;font-size:17px}.lab-tree-row.expanded>.lab-tree-folder{color:#d5b46d}.lab-tree-file-icon{width:17px;min-width:17px;font-size:9px;font-weight:800;text-align:center}.lab-tree-file-icon.python{color:#50b8d8}.lab-tree-file-icon.markdown{color:#69aaf7}.lab-tree-file-icon.env{color:#e8bd58}.lab-tree-file-icon.json{color:#e3a45c}.lab-tree-file-icon.yaml{color:#a98be5}.lab-tree-file-icon.text{color:#596477}.lab-tree-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.lab-tree-tag{margin-left:auto;padding:1px 5px;border:1px solid #315c4b;border-radius:8px;color:#75c9a3;font-size:8px}.lab-tree-dirty{margin-left:auto;color:#8b7cff;font-size:9px}.lab-tree-children{position:relative;margin-left:20px;padding-left:9px;border-left:1px solid #334052}.lab-tree-children>.lab-tree-item>.lab-tree-row::before{content:"";position:absolute;left:-10px;top:15px;width:9px;border-top:1px solid #334052}.lab-tree-children>.lab-tree-item:last-child::after{content:"";position:absolute;left:-10px;top:16px;bottom:0;border-left:2px solid #101827}
</style>
