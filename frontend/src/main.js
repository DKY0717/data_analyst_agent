import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/main.css'
import App from './App.vue'

const app = createApp(App)

// 使用 Pinia 统一管理问数状态，后续组件只消费 store，避免跨组件传递混乱。
app.use(createPinia())
app.use(ElementPlus)
app.mount('#app')
