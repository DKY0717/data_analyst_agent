import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ElButton, ElButtonGroup } from 'element-plus/es/components/button/index.mjs'
import { ElIcon } from 'element-plus/es/components/icon/index.mjs'
import { ElInput } from 'element-plus/es/components/input/index.mjs'
import { ElPagination } from 'element-plus/es/components/pagination/index.mjs'
import { ElSwitch } from 'element-plus/es/components/switch/index.mjs'
import { ElTable, ElTableColumn } from 'element-plus/es/components/table/index.mjs'
import { ElTag } from 'element-plus/es/components/tag/index.mjs'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import { Download, Document, CopyDocument, Sunny, Moon } from '@element-plus/icons-vue'
import hljs from 'highlight.js/lib/core'
import sql from 'highlight.js/lib/languages/sql'
import 'highlight.js/styles/github-dark-dimmed.css'
import App from './App.vue'
import router from './router'
import './styles/main.css'

hljs.registerLanguage('sql', sql)

const app = createApp(App)
app.use(createPinia())
app.use(router)
for (const component of [
  ElButton,
  ElButtonGroup,
  ElIcon,
  ElInput,
  ElPagination,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
]) {
  app.use(component)
}
for (const [key, component] of Object.entries({ Download, Document, CopyDocument, Sunny, Moon })) {
  app.component(key, component)
}
app.provide('hljs', hljs)
app.mount('#app')
