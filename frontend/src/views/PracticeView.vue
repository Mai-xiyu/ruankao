<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { CheckCircle2, Clock3, Play, RotateCcw, Send } from "lucide-vue-next";

import {
  fetchGroupedSubjects,
  fetchQuestionsByTag,
  fetchRandomQuestions,
  fetchTags,
  fetchWrongPractice,
  submitAnswer
} from "../api";
import type { GroupedSubjects, LevelName, PracticeResult, Question, Subject, TagItem } from "../types";

const LEVELS: LevelName[] = ["高级", "中级", "初级"];

const loading = ref(false);
const mode = ref<"random" | "tag" | "wrong">("random");
const tag = ref("");
const tags = ref<TagItem[]>([]);
const subjects = ref<GroupedSubjects>({ 高级: [], 中级: [], 初级: [] });
const currentLevel = ref<LevelName | "">("");
const subjectId = ref<number | undefined>(undefined);
const questions = ref<Question[]>([]);
const index = ref(0);
const answer = ref("");
const startedAt = ref(Date.now());
const result = ref<PracticeResult | null>(null);

const current = computed(() => questions.value[index.value] ?? null);
const progressText = computed(() => {
  if (!questions.value.length) return "0 / 0";
  return `${index.value + 1} / ${questions.value.length}`;
});
const subjectOptions = computed<Subject[]>(() => {
  if (!currentLevel.value) return [...subjects.value.高级, ...subjects.value.中级, ...subjects.value.初级];
  return subjects.value[currentLevel.value] ?? [];
});

watch(currentLevel, () => {
  subjectId.value = undefined;
  void loadPractice();
});

async function loadBaseData() {
  const [tagList, grouped] = await Promise.all([fetchTags(), fetchGroupedSubjects()]);
  tags.value = tagList;
  subjects.value = grouped;
}

async function loadPractice() {
  loading.value = true;
  result.value = null;
  answer.value = "";
  try {
    if (mode.value === "tag") {
      if (!tag.value) {
        questions.value = [];
        return;
      }
      questions.value = await fetchQuestionsByTag(tag.value, 20);
    } else if (mode.value === "wrong") {
      questions.value = await fetchWrongPractice(20);
    } else {
      questions.value = await fetchRandomQuestions(10, subjectId.value, currentLevel.value || undefined);
    }
    index.value = 0;
    startedAt.value = Date.now();
  } catch {
    ElMessage.error("加载题目失败");
  } finally {
    loading.value = false;
  }
}

function chooseOption(key: string) {
  answer.value = key;
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

async function submit() {
  if (!current.value) return;
  if (!answer.value.trim()) {
    ElMessage.warning("请先填写答案");
    return;
  }
  try {
    const duration = Math.max(0, Math.round((Date.now() - startedAt.value) / 1000));
    result.value = await submitAnswer(current.value.id, answer.value, duration);
  } catch {
    ElMessage.error("提交失败");
  }
}

function nextQuestion() {
  if (index.value < questions.value.length - 1) {
    index.value += 1;
    answer.value = "";
    result.value = null;
    startedAt.value = Date.now();
  } else {
    ElMessage.info("本组题目已完成");
  }
}

onMounted(async () => {
  await loadBaseData();
  await loadPractice();
});
</script>

<template>
  <section class="grid two">
    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>刷题台</h2>
          <p>{{ progressText }}</p>
        </div>
        <el-button type="primary" :icon="Play" @click="loadPractice">换一组</el-button>
      </div>

      <div class="panel-body">
        <div class="level-bar">
          <el-select v-model="currentLevel" clearable placeholder="级别" style="width: 110px">
            <el-option v-for="level in LEVELS" :key="level" :label="level" :value="level" />
          </el-select>
          <el-select v-model="subjectId" clearable filterable placeholder="科目" style="width: 220px" @change="loadPractice">
            <el-option v-for="subject in subjectOptions" :key="subject.id" :label="subject.name" :value="subject.id" />
          </el-select>
          <el-radio-group v-model="mode" @change="loadPractice">
            <el-radio-button value="random">随机</el-radio-button>
            <el-radio-button value="tag">按标签</el-radio-button>
            <el-radio-button value="wrong">错题</el-radio-button>
          </el-radio-group>
          <el-select v-if="mode === 'tag'" v-model="tag" filterable placeholder="选择标签" style="width: 220px" @change="loadPractice">
            <el-option v-for="item in tags" :key="item.id" :label="item.name" :value="item.name" />
          </el-select>
        </div>

        <el-skeleton v-if="loading" :rows="6" animated />
        <el-empty v-else-if="!current" description="暂无可练习题" />
        <template v-else>
          <div class="tag-row" style="margin-bottom: 12px">
            <el-tag effect="plain">{{ current.question_type }}</el-tag>
            <el-tag type="info" effect="plain">{{ current.knowledge_area || "未分类" }}</el-tag>
            <el-tag type="warning" effect="plain">{{ current.difficulty }} 星</el-tag>
          </div>
          <p class="question-stem">{{ current.question_no }}. {{ current.stem }}</p>
          <div v-if="stemImages(current).length" class="question-media">
            <img v-for="image in stemImages(current)" :key="image.id" :src="image.image_path" :alt="image.caption || '题干图片'" />
          </div>

          <div v-if="current.options_json" class="option-list">
            <el-button
              v-for="(value, key) in current.options_json"
              :key="key"
              class="option-button"
              :type="answer === key ? 'primary' : 'default'"
              plain
              @click="chooseOption(String(key))"
            >
              <span>{{ key }}. {{ value }}</span>
              <span v-if="optionImages(current, key).length" class="option-media">
                <img
                  v-for="image in optionImages(current, key)"
                  :key="image.id"
                  :src="image.image_path"
                  :alt="image.caption || `选项 ${key} 图片`"
                />
              </span>
            </el-button>
          </div>
          <el-input v-else v-model="answer" type="textarea" :rows="4" placeholder="填写答案" />

          <div class="tag-row" style="margin-top: 16px">
            <el-button type="primary" :icon="Send" @click="submit">提交</el-button>
            <el-button :icon="RotateCcw" @click="nextQuestion">下一题</el-button>
          </div>
        </template>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>答题结果</h2>
          <p>提交后显示答案与解析</p>
        </div>
      </div>
      <div class="panel-body">
        <el-empty v-if="!result" description="尚未提交" />
        <div v-else class="answer-result">
          <div class="tag-row">
            <CheckCircle2 v-if="result.is_correct" :size="20" color="#2f6f63" />
            <Clock3 v-else :size="20" color="#a84848" />
            <strong>{{ result.is_correct ? "回答正确" : "需要复盘" }}</strong>
          </div>
          <el-divider />
          <p><strong>正确答案：</strong>{{ result.correct_answer || "-" }}</p>
          <p class="question-stem"><strong>解析：</strong>{{ result.analysis || "-" }}</p>
          <div class="tag-row">
            <el-tag v-for="item in result.tags" :key="item" effect="plain">{{ item }}</el-tag>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
