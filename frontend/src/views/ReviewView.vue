<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { CheckCheck, HeartOff, RefreshCcw } from "lucide-vue-next";

import { fetchFavorites, fetchWrongRecords, markReviewed, removeFavorite } from "../api";
import type { FavoriteItem, WrongRecord } from "../types";

const loading = ref(false);
const wrongRecords = ref<WrongRecord[]>([]);
const favorites = ref<FavoriteItem[]>([]);

async function load() {
  loading.value = true;
  try {
    const [wrong, favoriteList] = await Promise.all([fetchWrongRecords(), fetchFavorites()]);
    wrongRecords.value = wrong;
    favorites.value = favoriteList;
  } catch {
    ElMessage.error("读取复盘数据失败");
  } finally {
    loading.value = false;
  }
}

async function reviewed(recordId: number) {
  try {
    await markReviewed(recordId);
    ElMessage.success("已标记复习");
    await load();
  } catch {
    ElMessage.error("操作失败");
  }
}

async function unfavorite(questionId: number) {
  try {
    await removeFavorite(questionId);
    ElMessage.success("已取消收藏");
    await load();
  } catch {
    ElMessage.error("操作失败");
  }
}

onMounted(load);
</script>

<template>
  <section class="grid two" v-loading="loading">
    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>错题本</h2>
          <p>{{ wrongRecords.length }} 条记录</p>
        </div>
        <el-button :icon="RefreshCcw" @click="load">刷新</el-button>
      </div>
      <div class="panel-body">
        <el-empty v-if="!wrongRecords.length" description="暂无错题" />
        <el-table v-else :data="wrongRecords" height="620">
          <el-table-column label="题目" min-width="320">
            <template #default="{ row }">
              <p class="question-stem">{{ row.question?.stem || "-" }}</p>
              <div class="tag-row">
                <el-tag v-for="tag in row.question?.tags_json || []" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="user_answer" label="作答" width="100" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.reviewed ? 'success' : 'warning'" effect="plain">
                {{ row.reviewed ? "已复习" : "待复习" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button size="small" :icon="CheckCheck" circle @click="reviewed(row.record_id)" />
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>收藏题</h2>
          <p>{{ favorites.length }} 道</p>
        </div>
      </div>
      <div class="panel-body">
        <el-empty v-if="!favorites.length" description="暂无收藏" />
        <el-table v-else :data="favorites" height="620">
          <el-table-column label="题目" min-width="300">
            <template #default="{ row }">
              <p class="question-stem">{{ row.question?.stem || "-" }}</p>
              <div class="tag-row">
                <el-tag v-for="tag in row.question?.tags_json || []" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button size="small" :icon="HeartOff" circle @click="unfavorite(row.question_id)" />
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </section>
</template>
