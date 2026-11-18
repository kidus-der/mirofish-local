import { createApp } from 'vue'
// First, so component styles can override the shared foundation.
import './styles/harbor.css'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
// Fonts are bundled (no Google Fonts request): this fork is local-only.
import '@fontsource/alegreya/400.css'
import '@fontsource/alegreya/500.css'
import '@fontsource/alegreya/500-italic.css'
import '@fontsource/alegreya/700.css'
import '@fontsource/alegreya-sans/400.css'
import '@fontsource/alegreya-sans/400-italic.css'
import '@fontsource/alegreya-sans/500.css'
import '@fontsource/alegreya-sans/700.css'
import '@fontsource/alegreya-sans/800.css'
import '@fontsource/alegreya-sans-sc/500.css'
import '@fontsource/alegreya-sans-sc/700.css'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/700.css'
import '@fontsource/space-grotesk/400.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/700.css'

const app = createApp(App)

app.use(router)
app.use(i18n)

app.mount('#app')
