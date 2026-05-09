<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { Filter, Heart, RefreshCcw, Search } from "lucide-vue-next";

import { addFavorite, fetchGroupedSubjects, fetchQuestions, fetchTags } from "../api";
import type { GroupedSubjects, LevelName, Question, Subject, TagItem } from "../types";

const LEVELS: Array<"全部" | LevelName> = ["全部", "高级", "中级", "初级"];

const loading = ref(false);
const questions = ref<Question[]>([]);
const tags = ref<TagItem[]>([]);
const subjects = ref<GroupedSubjects>({ 高级: [], 中级: [], 初级: [] });
const active = ref<Question | null>(null);
const drawerVisible = ref(false);
const currentLevel = ref<"全部" | LevelName>("全部");

const filters = reactive({
  subject_id: undefined as number | undefined,
  year: undefined as number | undefined,
  season: "",
  paper_type: "",
  knowledge_area: "",
  tag: "",
  difficulty: undefined as number | undefined,
  keyword: "",
  question_type: "",
  is_verified: undefined as boolean | undefined,
  has_answer: true as boolean | undefined,
  quality_status: "ok"
});

const subjectOptions = computed<Subject[]>(() => {
  if (currentLevel.value === "全部") return [...subjects.value.高级, ...subjects.value.中级, ...subjects.value.初级];
  return subjects.value[currentLevel.value] ?? [];
});

watch(currentLevel, () => {
  filters.subject_id = undefined;
  void loadQuestions();
});

watch(
  () => filters.subject_id,
  () => void loadQuestions()
);

async function loadTags() {
  tags.value = await fetchTags();
}

async function loadSubjects() {
  subjects.value = await fetchGroupedSubjects();
}

async function loadQuestions() {
  loading.value = true;
  try {
    questions.value = await fetchQuestions({
      ...filters,
      level: currentLevel.value === "全部" ? undefined : currentLevel.value,
      limit: 200
    });
  } catch {
    ElMessage.error("读取题目失败");
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  currentLevel.value = "全部";
  filters.subject_id = undefined;
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
  filters.quality_status = "ok";
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
  } catch {
    ElMessage.error("收藏失败");
  }
}

function imagesByType(question: Question | null, type: string) {
  return question?.images?.filter((image) => image.image_type === type) ?? [];
}

function stemImages(question: Question | null) {
  return imagesByType(question, "stem");
}

function optionImages(question: Question | null, key: string | number) {
  return imagesByType(question, `option_${String(key)}`);
}

onMounted(async () => {
  await Promise.all([loadTags(), loadSubjects()]);
  await loadQuestions();
});
</script>

<template>
  <section class="grid">
    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>题目筛选</h2>
          <p>默认只显示质量状态 ok 且带答案的题</p>
        </div>
        <div class="tag-row">
          <el-button :icon="RefreshCcw" @click="resetFilters">重置</el-button>
          <el-button type="primary" :icon="Search" @click="loadQuestions">查询</el-button>
        </div>
      </div>
      <div class="panel-body">
        <div class="level-bar">
          <el-radio-group v-model="currentLevel">
            <el-radio-button v-for="level in LEVELS" :key="level" :value="level">{{ level }}</el-radio-button>
          </el-radio-group>
          <el-select v-model="filters.subject_id" clearable filterable placeholder="选择科目" style="width: 240px">
            <el-option v-for="subject in subjectOptions" :key="subject.id" :label="subject.name" :value="subject.id" />
          </el-select>
        </div>

        <div class="toolbar">
          <el-input-number v-model="filters.year" :min="1990" :max="2100" placeholder="年份" controls-position="right" />
          <el-select v-model="filters.season" clearable placeholder="场次">
            <el-option label="上半年" value="上半年" />
            <el-option label="下半年" value="下半年" />
            <el-option label="模拟" value="模拟" />
          </el-select>
          <el-select v-model="filters.paper_type" clearable placeholder="试卷">
            <el-option label="上午综合知识" value="上午综合知识" />
            <el-option label="下午案例分析" value="下午案例分析" />
            <el-option label="模拟考试" value="模拟考试" />
          </el-select>
          <el-select v-model="filters.question_type" clearable placeholder="题型">
            <el-option label="单选" value="single_choice" />
            <el-option label="多选" value="multiple_choice" />
            <el-option label="案例" value="case_study" />
            <el-option label="论文" value="essay" />
            <el-option label="其他" value="other" />
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
          <el-select v-model="filters.quality_status" clearable placeholder="质量状态">
            <el-option label="ok" value="ok" />
            <el-option label="low_quality" value="low_quality" />
            <el-option label="missing_answer" value="missing_answer" />
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
        <el-table-column prop="question_type" label="题型" width="120" />
        <el-table-column label="题干" min-width="360">
          <template #default="{ row }">
            <span class="question-stem">{{ row.stem }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="knowledge_area" label="知识点" width="150" />
        <el-table-column prop="quality_status" label="质量" width="120" />
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
        <div v-if="stemImages(active).length" class="question-media">
          <img v-for="image in stemImages(active)" :key="image.id" :src="image.image_path" :alt="image.caption || '题干图片'" />
        </div>
        <div v-if="active.options_json" class="option-list">
          <div v-for="(value, key) in active.options_json" :key="key" class="answer-result">
            <div>{{ key }}. {{ value }}</div>
            <div v-if="optionImages(active, key).length" class="option-media">
              <img v-for="image in optionImages(active, key)" :key="image.id" :src="image.image_path" :alt="image.caption || `选项 ${key} 图片`" />
            </div>
          </div>
        </div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="答案">{{ active.answer || "-" }}</el-descriptions-item>
          <el-descriptions-item label="解析">
            <span class="question-stem">{{ active.analysis || "-" }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="知识点">{{ active.knowledge_area || "-" }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ active.source_provider || "-" }}</el-descriptions-item>
          <el-descriptions-item label="质量">{{ active.quality_status }}</el-descriptions-item>
          <el-descriptions-item label="校对">{{ active.is_verified ? "已校对" : "未校对" }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </section>
</template>
