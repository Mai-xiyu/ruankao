<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { DatabaseZap, FileJson, WandSparkles } from "lucide-vue-next";

import { generateQuestions, importAiGenerated } from "../api";
import type { ImportPayload, ImportResult } from "../types";

const loading = ref(false);
const importing = ref(false);
const updateExisting = ref(false);
const useReasoning = ref(false);
const draft = ref<ImportPayload | null>(null);
const result = ref<ImportResult | null>(null);

const form = reactive({
  subject_name: "",
  level: "中级",
  year: new Date().getFullYear(),
  season: "模拟",
  paper_type: "模拟练习",
  question_count: 5,
  question_types: ["single_choice"],
  difficulty: 3,
  knowledge_areas: "TCP/IP\n路由协议\n网络安全",
  tags: "网络基础, IPv4",
  source_text: "",
  extra_requirements: ""
});

const exam = computed<ImportPayload["exam"]>(() => ({
  exam_name: form.subject_name || "自定义科目",
  level: form.level,
  year: form.year,
  season: form.season,
  paper_type: form.paper_type,
  source_name: "DeepSeek AI 生成",
  source_url: "",
  is_memory_version: false,
  remark: "AI 生成模拟练习题，非历年真题，需人工校对"
}));

const draftText = computed(() => (draft.value ? JSON.stringify(draft.value, null, 2) : ""));

function splitTokens(value: string) {
  return value
    .replace(/，/g, ",")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function runGenerate() {
  loading.value = true;
  result.value = null;
  try {
    draft.value = await generateQuestions({
      exam: exam.value,
      question_count: form.question_count,
      question_types: form.question_types,
      difficulty: form.difficulty,
      knowledge_areas: splitTokens(form.knowledge_areas),
      tags: splitTokens(form.tags),
      source_text: form.source_text.trim() || undefined,
      extra_requirements: form.extra_requirements.trim() || undefined,
      use_reasoning_model: useReasoning.value
    });
    ElMessage.success("已生成草稿");
  } catch {
    ElMessage.error("AI 出题失败");
  } finally {
    loading.value = false;
  }
}

async function importDraft() {
  if (!draft.value) return;
  importing.value = true;
  try {
    result.value = await importAiGenerated(draft.value, updateExisting.value);
    ElMessage.success("已导入题库");
  } catch {
    ElMessage.error("导入失败");
  } finally {
    importing.value = false;
  }
}
</script>

<template>
  <section class="split ai-generate">
    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>AI 出题</h2>
          <p>生成模拟练习草稿，入库后默认未校对</p>
        </div>
        <el-switch v-model="useReasoning" active-text="推理模型" />
      </div>
      <div class="panel-body">
        <el-form label-position="top">
          <div class="toolbar">
            <el-input v-model="form.subject_name" placeholder="科目名称" />
            <el-select v-model="form.level">
              <el-option label="高级" value="高级" />
              <el-option label="中级" value="中级" />
              <el-option label="初级" value="初级" />
            </el-select>
            <el-input-number v-model="form.year" :min="1990" :max="2100" controls-position="right" />
            <el-select v-model="form.season">
              <el-option label="上半年" value="上半年" />
              <el-option label="下半年" value="下半年" />
              <el-option label="模拟" value="模拟" />
            </el-select>
            <el-input v-model="form.paper_type" placeholder="试卷类型" />
            <el-input-number v-model="form.question_count" :min="1" :max="30" controls-position="right" />
            <el-select v-model="form.difficulty">
              <el-option v-for="level in 5" :key="level" :label="`${level} 星`" :value="level" />
            </el-select>
            <el-select v-model="form.question_types" multiple collapse-tags collapse-tags-tooltip class="wide">
              <el-option label="单选" value="single_choice" />
              <el-option label="多选" value="multiple_choice" />
              <el-option label="填空" value="fill_blank" />
              <el-option label="案例" value="case_study" />
              <el-option label="计算" value="calculation" />
            </el-select>
          </div>

          <div class="grid two" style="margin-top: 14px">
            <el-form-item label="知识点">
              <el-input v-model="form.knowledge_areas" type="textarea" :rows="5" />
            </el-form-item>
            <el-form-item label="标签">
              <el-input v-model="form.tags" type="textarea" :rows="5" />
            </el-form-item>
          </div>

          <el-form-item label="参考文本">
            <el-input v-model="form.source_text" type="textarea" :rows="8" />
          </el-form-item>

          <el-form-item label="额外要求">
            <el-input v-model="form.extra_requirements" type="textarea" :rows="4" />
          </el-form-item>

          <div class="tag-row">
            <el-button type="primary" :icon="WandSparkles" :loading="loading" @click="runGenerate">生成草稿</el-button>
            <el-switch v-model="updateExisting" active-text="更新重复题" />
          </div>
        </el-form>
      </div>
    </div>

    <div class="grid">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>草稿</h2>
            <p>{{ draft ? `${draft.questions.length} 道` : "暂无" }}</p>
          </div>
          <el-button :icon="DatabaseZap" :disabled="!draft" :loading="importing" @click="importDraft">入库</el-button>
        </div>
        <div class="panel-body">
          <el-empty v-if="!draft" description="暂无草稿" />
          <div v-else class="grid">
            <div v-for="item in draft.questions" :key="item.question_no" class="answer-result">
              <div class="tag-row" style="justify-content: space-between">
                <el-tag effect="plain">{{ item.question_type }}</el-tag>
                <el-rate :model-value="item.difficulty" disabled />
              </div>
              <p class="question-stem">{{ item.question_no }}. {{ item.stem }}</p>
              <div v-if="item.options" class="option-list compact">
                <span v-for="(value, key) in item.options" :key="key">{{ key }}. {{ value }}</span>
              </div>
              <p class="muted">答案：{{ item.answer || "-" }}</p>
            </div>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>JSON</h2>
            <p>{{ result ? `批次 ${result.batch_id}` : "待导入" }}</p>
          </div>
          <FileJson :size="20" />
        </div>
        <div class="panel-body">
          <pre v-if="draft" class="json-preview">{{ draftText }}</pre>
          <el-empty v-else description="暂无 JSON" />
          <el-descriptions v-if="result" class="import-result" :column="2" border>
            <el-descriptions-item label="新增">{{ result.success_count }}</el-descriptions-item>
            <el-descriptions-item label="更新">{{ result.updated_count }}</el-descriptions-item>
            <el-descriptions-item label="跳过">{{ result.skipped_count }}</el-descriptions-item>
            <el-descriptions-item label="失败">{{ result.failed_count }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </div>
  </section>
</template>
