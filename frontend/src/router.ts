import { createRouter, createWebHistory } from "vue-router";

import AiGenerateView from "./views/AiGenerateView.vue";
import DashboardView from "./views/DashboardView.vue";
import ImportView from "./views/ImportView.vue";
import PracticeView from "./views/PracticeView.vue";
import QuestionsView from "./views/QuestionsView.vue";
import ReviewView from "./views/ReviewView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    { path: "/dashboard", component: DashboardView, meta: { title: "概览" } },
    { path: "/questions", component: QuestionsView, meta: { title: "题库" } },
    { path: "/practice", component: PracticeView, meta: { title: "刷题" } },
    { path: "/review", component: ReviewView, meta: { title: "复盘" } },
    { path: "/ai-generate", component: AiGenerateView, meta: { title: "AI 出题" } },
    { path: "/import", component: ImportView, meta: { title: "导入" } }
  ]
});
