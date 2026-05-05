<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { BarChart3, BookOpenCheck, Database, FileUp, RotateCcw, Server, WandSparkles } from "lucide-vue-next";

const route = useRoute();

const navItems = [
  { path: "/dashboard", label: "概览", icon: BarChart3 },
  { path: "/questions", label: "题库", icon: Database },
  { path: "/practice", label: "刷题", icon: BookOpenCheck },
  { path: "/ai-generate", label: "AI 出题", icon: WandSparkles },
  { path: "/import", label: "导入", icon: FileUp },
  { path: "/review", label: "复盘", icon: RotateCcw }
];

const currentTitle = computed(() => String(route.meta.title ?? "题库"));
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <Server :size="22" />
        </div>
        <div>
          <strong>软考题库</strong>
          <span>网络工程师</span>
        </div>
      </div>

      <el-menu :default-active="route.path" router class="side-menu">
        <el-menu-item v-for="item in navItems" :key="item.path" :index="item.path">
          <component :is="item.icon" :size="18" />
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <div>
          <p class="eyebrow">RK Network Engineer Bank</p>
          <h1>{{ currentTitle }}</h1>
        </div>
        <div class="top-actions">
          <el-tag type="success" effect="plain">API /api</el-tag>
          <el-link href="http://127.0.0.1:8000/docs" target="_blank" underline="never">Swagger</el-link>
        </div>
      </header>

      <router-view />
    </main>
  </div>
</template>
