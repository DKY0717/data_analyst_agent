import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import * as echarts from 'echarts'
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
app.use(ElementPlus, { size: 'default' })
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.provide('echarts', echarts)
app.provide('hljs', hljs)
app.mount('#app')
