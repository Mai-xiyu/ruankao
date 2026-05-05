<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { Filter, Heart, RefreshCcw, Search } from "lucide-vue-next";

import { addFavorite, fetchQuestions, fetchTags } from "../api";
import type { Question, TagItem } from "../types";

const loading = ref(false);
const questions = ref<Question[]>([]);
const tags = ref<TagItem[]>([]);
const active = ref<Question | null>(null);
const drawerVisible = ref(false);

const filters = reactive({
  year: undefined as number | undefined,
  season: "",
  paper_type: "",
  knowledge_area: "",
  tag: "",
  difficulty: undefined as number | undefined,
  keyword: "",
  question_type: "",
  is_verified: undefined as boolean | undefined,
  has_answer: true as boolean | undefined
});

async function loadTags() {
  tags.value = await fetchTags();
}

async function loadQuestions() {
  loading.value = true;
  try {
    questions.value = await fetchQuestions({ ...filters, limit: 200 });
  } catch (error) {
    ElMessage.error("读取题目失败");
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.year = undefined;
  filters.season = "";
  filters.paper_type = "";
  filters.knowledge_area = "";
  filters.tag = "";
  filters.difficulty = undefined;
  filters.keyword = "";
  filters.question_type = "";
  filters.is_verified = undefined;
  filters.has_answer = true;
  void loadQuestions();
}

function openQuestion(row: Question) {
  active.value = row;
  drawerVisible.value = true;
}

async function favorite(row: Question) {
  try {
    await addFavorite(row.id);
    ElMessage.success("已收藏");
  } catch (error) {
    ElMessage.error("收藏失败");
  }
}

onMounted(async () => {
  await Promise.all([loadTags(), loadQuestions()]);
});
</script>

<template>
  <section class="grid">
    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>题目筛选</h2>
          <p>年份、知识点、标签和关键词组合查询</p>
        </div>
        <div class="tag-row">
          <el-button :icon="RefreshCcw" @click="resetFilters">重置</el-button>
          <el-button type="primary" :icon="Search" @click="loadQuestions">查询</el-button>
        </div>
      </div>
      <div class="panel-body">
        <div class="toolbar">
          <el-input-number v-model="filters.year" :min="1990" :max="2100" placeholder="年份" controls-position="right" />
          <el-select v-model="filters.season" clearable placeholder="季节">
            <el-option label="上半年" value="上半年" />
            <el-option label="下半年" value="下半年" />
          </el-select>
          <el-select v-model="filters.paper_type" clearable placeholder="试卷">
            <el-option label="上午综合知识" value="上午综合知识" />
            <el-option label="下午案例分析" value="下午案例分析" />
          </el-select>
          <el-select v-model="filters.question_type" clearable placeholder="题型">
            <el-option label="单选" value="single_choice" />
            <el-option label="多选" value="multiple_choice" />
            <el-option label="案例" value="case" />
            <el-option label="配置题" value="config" />
            <el-option label="计算题" value="calculation" />
          </el-select>
          <el-select v-model="filters.difficulty" clearable placeholder="难度">
            <el-option v-for="level in 5" :key="level" :label="`${level} 星`" :value="level" />
          </el-select>
          <el-select v-model="filters.tag" filterable clearable placeholder="标签">
            <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.name" />
          </el-select>
          <el-input v-model="filters.knowledge_area" clearable placeholder="知识点" />
          <el-select v-model="filters.is_verified" clearable placeholder="校对状态">
            <el-option label="已校对" :value="true" />
            <el-option label="未校对" :value="false" />
          </el-select>
          <el-select v-model="filters.has_answer" clearable placeholder="答案状态">
            <el-option label="有答案" :value="true" />
            <el-option label="无答案" :value="false" />
          </el-select>
          <el-input v-model="filters.keyword" class="wide" clearable placeholder="题干或解析关键词" @keyup.enter="loadQuestions">
            <template #prefix>
              <Filter :size="16" />
            </template>
          </el-input>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>题目列表</h2>
          <p>当前 {{ questions.length }} 条</p>
        </div>
      </div>
      <el-table v-loading="loading" :data="questions" height="560" row-key="id" @row-dblclick="openQuestion">
        <el-table-column prop="question_no" label="题号" width="90" />
        <el-table-column prop="question_type" label="题型" width="130" />
        <el-table-column label="题干" min-width="360">
          <template #default="{ row }">
            <span class="question-stem">{{ row.stem }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="knowledge_area" label="知识点" width="150" />
        <el-table-column label="标签" width="220">
          <template #default="{ row }">
            <div class="tag-row">
              <el-tag v-for="tag in row.tags_json" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="difficulty" label="难度" width="90" align="center" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openQuestion(row)">查看</el-button>
            <el-button size="small" :icon="Heart" circle @click="favorite(row)" />
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="drawerVisible" size="46%" title="题目详情">
      <template v-if="active">
        <p class="question-stem">{{ active.stem }}</p>
        <div v-if="active.options_json" class="option-list">
          <el-tag v-for="(value, key) in active.options_json" :key="key" effect="plain">
            {{ key }}. {{ value }}
          </el-tag>
        </div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="答案">{{ active.answer || "-" }}</el-descriptions-item>
          <el-descriptions-item label="解析">
            <span class="question-stem">{{ active.analysis || "-" }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="知识点">{{ active.knowledge_area || "-" }}</el-descriptions-item>
          <el-descriptions-item label="校对">{{ active.is_verified ? "已校对" : "未校对" }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </section>
</template>
