<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import {
  BarChart3,
  BookOpenCheck,
  Database,
  FileUp,
  LogIn,
  LogOut,
  RotateCcw,
  Server,
  UserRound,
  WandSparkles
} from "lucide-vue-next";

import { authMe, guestSession, login, logout, register } from "./api";
import type { AuthState } from "./types";

const route = useRoute();

const navItems = [
  { path: "/dashboard", label: "概览", icon: BarChart3 },
  { path: "/questions", label: "题库", icon: Database },
  { path: "/practice", label: "刷题", icon: BookOpenCheck },
  { path: "/review", label: "复盘", icon: RotateCcw },
  { path: "/ai-generate", label: "AI 出题", icon: WandSparkles },
  { path: "/import", label: "导入", icon: FileUp }
];

const currentTitle = computed(() => String(route.meta.title ?? "题库"));
const auth = ref<AuthState>({ authenticated: false });
const authDialog = ref(false);
const authMode = ref<"login" | "register">("login");
const authLoading = ref(false);
const form = reactive({
  username: "",
  password: "",
  email: "",
  display_name: ""
});

const authLabel = computed(() => {
  if (auth.value.authenticated && auth.value.user) return auth.value.user.display_name || auth.value.user.username;
  if (auth.value.guest_session_id) return "访客";
  return "未登录";
});

async function loadAuth() {
  try {
    auth.value = await authMe();
  } catch {
    auth.value = { authenticated: false };
  }
}

async function startGuest() {
  authLoading.value = true;
  try {
    auth.value = await guestSession();
    authDialog.value = false;
    ElMessage.success("已进入访客模式");
  } finally {
    authLoading.value = false;
  }
}

async function submitAuth() {
  if (!form.username.trim() || !form.password.trim()) {
    ElMessage.warning("请填写用户名和密码");
    return;
  }
  authLoading.value = true;
  try {
    auth.value =
      authMode.value === "login"
        ? await login({ username: form.username, password: form.password })
        : await register({
            username: form.username,
            password: form.password,
            email: form.email || undefined,
            display_name: form.display_name || undefined
          });
    authDialog.value = false;
    ElMessage.success(authMode.value === "login" ? "已登录" : "已注册");
  } finally {
    authLoading.value = false;
  }
}

async function doLogout() {
  await logout();
  auth.value = { authenticated: false };
  ElMessage.success("已退出");
}

onMounted(loadAuth);
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
          <span>多科目练习台</span>
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
          <p class="eyebrow">RK Question Bank</p>
          <h1>{{ currentTitle }}</h1>
        </div>
        <div class="top-actions">
          <el-tag effect="plain">
            <UserRound :size="14" />
            {{ authLabel }}
          </el-tag>
          <el-button v-if="auth.authenticated || auth.guest_session_id" :icon="LogOut" @click="doLogout">退出</el-button>
          <el-button v-else type="primary" :icon="LogIn" @click="authDialog = true">登录 / 访客</el-button>
          <el-link href="http://127.0.0.1:8000/docs" target="_blank" underline="never">Swagger</el-link>
        </div>
      </header>

      <router-view />
    </main>

    <el-dialog v-model="authDialog" width="420px" title="账号">
      <el-tabs v-model="authMode">
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>
      <el-form label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <template v-if="authMode === 'register'">
          <el-form-item label="邮箱">
            <el-input v-model="form.email" />
          </el-form-item>
          <el-form-item label="昵称">
            <el-input v-model="form.display_name" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <div class="dialog-actions">
          <el-button @click="startGuest" :loading="authLoading">访客继续</el-button>
          <el-button type="primary" @click="submitAuth" :loading="authLoading">
            {{ authMode === "login" ? "登录" : "注册" }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
