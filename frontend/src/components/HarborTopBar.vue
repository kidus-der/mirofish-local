<template>
  <header class="hb-topbar hb-surface-navy">
    <RouterLink class="brand" :to="{ name: 'Home' }">
      <svg class="logo" viewBox="30 22 196 196" width="32" height="32" aria-hidden="true">
        <circle class="logo-ring" cx="128" cy="120" r="90" />
        <path class="logo-fish" d="M78 120 49 95q11 25 0 50z" />
        <path class="logo-fish" d="M73 120c22-37 78-40 111 0-33 40-89 37-111 0z" />
        <path class="logo-net" d="M101 124l25-21 21 24-26 12zM126 103l-5 36" />
        <g class="logo-nodes">
          <circle cx="101" cy="124" r="8" />
          <circle cx="126" cy="103" r="8" />
          <circle cx="147" cy="127" r="8" />
          <circle cx="121" cy="139" r="8" />
        </g>
      </svg>
      <span>MiroFish <em>Local</em></span>
    </RouterLink>

    <nav class="nav" :aria-label="$t('nav.mainNavigation')">
      <ul class="hb-list">
        <li v-for="link in links" :key="link.label">
          <RouterLink :to="link.to">{{ link.label }}</RouterLink>
        </li>
      </ul>
    </nav>

    <div v-if="$slots.status" class="status"><slot name="status" /></div>

    <LanguageSwitcher class="language" />
  </header>
</template>

<script setup>
import LanguageSwitcher from './LanguageSwitcher.vue'

defineProps({
  links: { type: Array, default: () => [] }
})
</script>

<style scoped>
.hb-topbar {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  min-height: var(--hb-topbar);
  padding-left: 18px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: var(--hb-topbar);
  margin-right: 26px;
  color: inherit;
  font: 700 1.3125rem / 1.25 var(--hb-font-serif);
  text-decoration: none;
  white-space: nowrap;
}

.brand em {
  color: var(--hb-water);
  font-weight: 500;
}

.logo-ring {
  fill: none;
  stroke: var(--hb-water);
  stroke-width: 7;
  stroke-dasharray: 20 15;
}

.logo-fish {
  fill: var(--hb-paper);
}

.logo-net {
  fill: none;
  stroke: var(--hb-navy);
  stroke-width: 5;
}

.logo-nodes {
  fill: var(--hb-navy);
}

.nav {
  min-width: 0;
}

.nav ul {
  display: flex;
  height: 100%;
}

.nav a {
  display: flex;
  align-items: center;
  height: 100%;
  min-height: var(--hb-topbar);
  padding: 0 15px;
  color: inherit;
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.nav a:hover {
  background: var(--hb-navy-hover);
}

.nav a[aria-current] {
  background: var(--hb-paper);
  color: var(--hb-navy);
  font-weight: 700;
}

.nav a:focus-visible,
.brand:focus-visible {
  outline-offset: -3px;
}

.status {
  display: flex;
  align-items: center;
  margin-left: auto;
  padding-left: var(--hb-space-5);
  color: var(--hb-water);
  font-size: var(--hb-text-sm);
  white-space: nowrap;
}

.status :deep(> * + *) {
  margin-left: 10px;
  padding-left: 10px;
  border-left: 1px solid rgba(191, 224, 230, 0.5);
}

.status :deep(b) {
  color: var(--hb-paper);
  font-weight: 700;
}

.language {
  display: flex;
  align-items: center;
  margin: 0 14px 0 18px;
}

.nav + .language {
  margin-left: auto;
}

@media (max-width: 1080px) {
  .status {
    order: 4;
    flex: 1 0 calc(100% + 18px);
    min-height: 32px;
    margin-left: -18px;
    padding: 0 18px;
    border-top: 1px solid rgba(191, 224, 230, 0.35);
  }

  .language {
    margin-left: auto;
  }
}

@media (max-width: 620px) {
  .brand {
    margin-right: var(--hb-space-3);
  }

  .nav {
    order: 3;
    flex: 1 0 calc(100% + 18px);
    margin-left: -18px;
    overflow-x: auto;
    border-top: 1px solid rgba(191, 224, 230, 0.35);
  }

  .nav a {
    min-height: 40px;
  }

  .status {
    flex-wrap: wrap;
    row-gap: 2px;
    padding-block: 6px;
    white-space: normal;
  }
}
</style>
