<template>
  <label class="language-switcher">
    <span class="hb-vh">{{ $t('nav.language') }}</span>
    <select class="hb-select" :value="locale" @change="switchLocale($event.target.value)">
      <option v-for="loc in availableLocales" :key="loc.key" :value="loc.key">
        {{ loc.label }}
      </option>
    </select>
  </label>
</template>

<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { availableLocales } from '@/i18n/index.js'

const { locale } = useI18n()

const switchLocale = (key) => {
  locale.value = key
  localStorage.setItem('locale', key)
  document.documentElement.lang = key
}

onMounted(() => {
  document.documentElement.lang = locale.value
})
</script>

<style scoped>
.language-switcher {
  position: relative;
  display: inline-flex;
}
</style>
