<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Bot, ClipboardCheck, FileJson, SearchCheck, ShieldCheck, Upload } from "lucide-vue-next";

import {
  cleanupApply,
  cleanupPreview,
  confirmSourceImport,
  extractQuestions,
  fetchImportBatches,
  importAiJson,
  importJson,
  previewSource
} from "../api";
import type { CleanupReport, ImportBatch, ImportPayload, ImportResult } from "../types";

const jsonText = ref("");
const sourceText = ref("");
const sourceUrl = ref("");
const aiText = ref("");
const updateExisting = ref(false);
const legalConfirmation = ref(true);
const useReasoning = ref(false);
const loading = ref(false);
const draft = ref<ImportPayload | null>(null);
const result = ref<ImportResult | null>(null);
const cleanup = ref<CleanupReport | null>(null);
const batches = ref<ImportBatch[]>([]);
const preview = ref<null | {
  content_excerpt: string;
  content_length: number;
  truncated: boolean;
  compliance_notice: string;
}>(null);

const examForm = reactive({
  exam_name: "",
  level: "中级",
  year: new Date().getFullYear(),
  season: "模拟",
  paper_type: "模拟考试",
  source_name: "自整理",
  source_url: "",
  is_memory_version: false,
  remark: ""
});

const draftText = computed(() => (draft.value ? JSON.stringify(draft.value, null, 2) : ""));
const cleanupReasons = computed(() => Object.entries(cleanup.value?.by_reason ?? {}).map(([reason, count]) => ({ reason, count })));

function normalizeExam() {
  return {
    ...examForm,
    exam_name: examForm.exam_name || "自定义科目"
  };
}

function parseJsonInput(): ImportPayload | null {
  try {
    return JSON.parse(jsonText.value) as ImportPayload;
  } catch {
    ElMessage.error("JSON 格式不正确");
    return null;
  }
}

async function runJsonImport() {
  const payload = parseJsonInput();
  if (!payload) return;
  loading.value = true;
  try {
    result.value = await importJson(payload, updateExisting.value);
    ElMessage.success("导入完成");
    await loadBatches();
  } catch {
    ElMessage.error("导入失败");
  } finally {
    loading.value = false;
  }
}

async function runPreview() {
  loading.value = true;
  try {
    preview.value = await previewSource({
      text: sourceText.value || undefined,
      url: sourceUrl.value || undefined
    });
    ElMessage.success("预览完成");
  } catch {
    ElMessage.error("预览失败");
  } finally {
    loading.value = false;
  }
}

async function runConfirmImport() {
  loading.value = true;
  try {
    draft.value = await confirmSourceImport({
      text: sourceText.value || undefined,
      url: sourceUrl.value || undefined,
      legal_confirmation: legalConfirmation.value,
      exam: normalizeExam(),
      use_reasoning_model: useReasoning.value
    });
    ElMessage.success("草稿已生成");
  } catch {
    ElMessage.error("AI 结构化失败");
  } finally {
    loading.value = false;
  }
}

async function runAiExtract() {
  if (!aiText.value.trim()) {
    ElMessage.warning("请填写待整理文本");
    return;
  }
  loading.value = true;
  try {
    draft.value = await extractQuestions({
      text: aiText.value,
      exam: normalizeExam(),
      use_reasoning_model: useReasoning.value
    });
    ElMessage.success("草稿已生成");
  } catch {
    ElMessage.error("AI 结构化失败");
  } finally {
    loading.value = false;
  }
}

async function importDraft() {
  if (!draft.value) return;
  loading.value = true;
  try {
    result.value = await importAiJson(draft.value, updateExisting.value);
    ElMessage.success("草稿已导入");
    await loadBatches();
  } catch {
    ElMessage.error("草稿导入失败");
  } finally {
    loading.value = false;
  }
}

async function loadCleanup() {
  cleanup.value = await cleanupPreview();
}

async function applyCleanup(mode: "isolate" | "delete") {
  if (mode === "delete") {
    await ElMessageBox.confirm("会先备份再删除低质量题，确认继续？", "清理确认", { type: "warning" });
  }
  loading.value = true;
  try {
    cleanup.value = await cleanupApply(mode);
    ElMessage.success(mode === "delete" ? "已删除低质量题" : "已隔离低质量题");
  } finally {
    loading.value = false;
  }
}

async function loadBatches() {
  batches.value = await fetchImportBatches();
}

onMounted(async () => {
  await Promise.all([loadCleanup(), loadBatches()]);
});
</script>

<template>
  <section class="split">
    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>导入工作台</h2>
          <p>JSON、来源预览、DeepSeek 结构化与数据清理</p>
        </div>
        <el-switch v-model="updateExisting" active-text="更新重复题" />
      </div>
      <div class="panel-body">
        <el-tabs>
          <el-tab-pane label="JSON">
            <el-input v-model="jsonText" class="editor" type="textarea" :rows="18" placeholder="粘贴后端 ImportPayload JSON" />
            <div class="tag-row" style="margin-top: 14px">
              <el-button type="primary" :icon="Upload" :loading="loading" @click="runJsonImport">导入 JSON</el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="来源">
            <el-form label-position="top">
              <el-form-item label="URL">
                <el-input v-model="sourceUrl" placeholder="https://..." />
              </el-form-item>
              <el-form-item label="文本">
                <el-input v-model="sourceText" type="textarea" :rows="8" placeholder="粘贴合法取得的题目文本" />
              </el-form-item>
              <el-checkbox v-model="legalConfirmation">确认来源为自整理、公开授权或合法取得</el-checkbox>
              <div class="tag-row" style="margin-top: 14px">
                <el-button :icon="SearchCheck" :loading="loading" @click="runPreview">预览</el-button>
                <el-button type="primary" :icon="ClipboardCheck" :loading="loading" @click="runConfirmImport">生成草稿</el-button>
              </div>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="AI 文本">
            <el-form label-position="top">
              <div class="toolbar" style="margin-bottom: 12px">
                <el-input v-model="examForm.exam_name" placeholder="科目名称" />
                <el-select v-model="examForm.level" placeholder="级别">
                  <el-option label="高级" value="高级" />
                  <el-option label="中级" value="中级" />
                  <el-option label="初级" value="初级" />
                </el-select>
                <el-input-number v-model="examForm.year" :min="1990" :max="2100" controls-position="right" />
                <el-select v-model="examForm.season">
                  <el-option label="上半年" value="上半年" />
                  <el-option label="下半年" value="下半年" />
                  <el-option label="模拟" value="模拟" />
                </el-select>
                <el-input v-model="examForm.paper_type" placeholder="试卷类型" />
                <el-switch v-model="useReasoning" active-text="推理模型" />
              </div>
              <el-input v-model="aiText" type="textarea" :rows="12" placeholder="粘贴合法来源文本，AI 只生成未校对草稿" />
              <div class="tag-row" style="margin-top: 14px">
                <el-button type="primary" :icon="Bot" :loading="loading" @click="runAiExtract">AI 结构化</el-button>
              </div>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="清理">
            <div class="tag-row" style="margin-bottom: 14px">
              <el-button :icon="ShieldCheck" @click="loadCleanup">重新预览</el-button>
              <el-button :loading="loading" @click="applyCleanup('isolate')">隔离低质题</el-button>
              <el-button type="danger" :loading="loading" @click="applyCleanup('delete')">备份并删除</el-button>
            </div>
            <el-descriptions v-if="cleanup" :column="2" border>
              <el-descriptions-item label="总题量">{{ cleanup.total_questions }}</el-descriptions-item>
              <el-descriptions-item label="候选清理">{{ cleanup.candidate_count }}</el-descriptions-item>
              <el-descriptions-item label="备份文件" :span="2">{{ cleanup.backup_file || "-" }}</el-descriptions-item>
            </el-descriptions>
            <el-table v-if="cleanupReasons.length" :data="cleanupReasons" size="small" style="margin-top: 12px">
              <el-table-column prop="reason" label="原因" />
              <el-table-column prop="count" label="数量" width="120" align="right" />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>

    <div class="grid">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>草稿</h2>
            <p>{{ draft ? `${draft.questions.length} 道` : "等待输入" }}</p>
          </div>
          <el-button :icon="FileJson" :disabled="!draft" :loading="loading" @click="importDraft">导入草稿</el-button>
        </div>
        <div class="panel-body">
          <div v-if="preview" class="answer-result" style="margin-bottom: 12px">
            <p class="muted">{{ preview.compliance_notice }}</p>
            <p>长度：{{ preview.content_length }} 字，{{ preview.truncated ? "已截断" : "未截断" }}</p>
          </div>
          <pre v-if="draft" class="json-preview">{{ draftText }}</pre>
          <el-empty v-else description="暂无草稿" />
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>导入批次</h2>
            <p>{{ result ? `最新批次 ${result.batch_id}` : "最近记录" }}</p>
          </div>
        </div>
        <div class="panel-body">
          <el-table :data="batches" size="small" height="260">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="source_type" label="类型" width="120" />
            <el-table-column prop="total_count" label="总数" width="80" align="right" />
            <el-table-column prop="success_count" label="成功" width="80" align="right" />
            <el-table-column prop="failed_count" label="失败" width="80" align="right" />
          </el-table>
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
