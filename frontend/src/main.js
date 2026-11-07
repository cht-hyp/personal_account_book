import { createApp } from 'vue'
import App from './App.vue'
import './styles/base.css'

// 入口只负责挂载根组件与全局样式；导航、类别加载、刷新协调都在 App.vue 内完成。
createApp(App).mount('#app')
