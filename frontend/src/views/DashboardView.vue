<script setup lang="ts">
import * as echarts from "echarts";
import { onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { AlertTriangle, BookMarked, Database, Heart, Tags, UsersRound } from "lucide-vue-next";

import { fetchOverview, fetchQuestionsByYear, fetchStatsByLevel, fetchWrongByTag } from "../api";
import type { LevelStat, OverviewStats, WrongTagStat, YearStat } from "../types";

const loading = ref(false);
const stats = ref<OverviewStats>({
  subjects: 0,
  exams: 0,
  questions: 0,
  usable_questions: 0,
  tags: 0,
  users: 0,
  favorites: 0,
  wrong_records: 0
});
const yearStats = ref<YearStat[]>([]);
const wrongTags = ref<WrongTagStat[]>([]);
const levelStats = ref<LevelStat[]>([]);
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const statItems = [
  { key: "subjects", label: "科目", icon: BookMarked },
  { key: "questions", label: "总题量", icon: Database },
  { key: "usable_questions", label: "可练习", icon: Tags },
  { key: "users", label: "用户", icon: UsersRound },
  { key: "favorites", label: "收藏", icon: Heart },
  { key: "wrong_records", label: "错题记录", icon: AlertTriangle }
] as const;

function drawChart() {
  if (!chartRef.value) return;
  chart?.dispose();
  chart = echarts.init(chartRef.value);
  const sorted = [...yearStats.value].sort((a, b) => a.year - b.year);
  chart.setOption({
    color: ["#2f6f63"],
    grid: { left: 36, right: 16, top: 24, bottom: 28 },
    xAxis: { type: "category", data: sorted.map((item) => String(item.year)), axisTick: { show: false } },
    yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#e8e9e2" } } },
    tooltip: { trigger: "axis" },
    series: [
      {
        type: "bar",
        data: sorted.map((item) => item.question_count),
        barWidth: 28,
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      }
    ]
  });
}

async function load() {
  loading.value = true;
  try {
    const [overview, byYear, wrongByTag, byLevel] = await Promise.all([
      fetchOverview(),
      fetchQuestionsByYear(),
      fetchWrongByTag(),
      fetchStatsByLevel()
    ]);
    stats.value = overview;
    yearStats.value = byYear;
    wrongTags.value = wrongByTag;
    levelStats.value = byLevel;
    drawChart();
  } catch {
    ElMessage.error("读取概览失败");
  } finally {
    loading.value = false;
  }
}

function resizeChart() {
  chart?.resize();
}

onMounted(() => {
  void load();
  window.addEventListener("resize", resizeChart);
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart);
  chart?.dispose();
});
</script>

<template>
  <section v-loading="loading" class="grid">
    <div class="stat-strip">
      <div v-for="item in statItems" :key="item.key" class="stat-item">
        <div class="tag-row">
          <component :is="item.icon" :size="18" />
          <p class="stat-label">{{ item.label }}</p>
        </div>
        <p class="stat-value">{{ stats[item.key] }}</p>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <h2>科目分布</h2>
          <p>按高级 / 中级 / 初级聚合可练习题量</p>
        </div>
      </div>
      <div class="panel-body">
        <el-empty v-if="!levelStats.length" description="暂无数据" />
        <el-table v-else :data="levelStats" size="small">
          <el-table-column prop="level" label="级别" width="90" />
          <el-table-column prop="subject_name" label="科目" />
          <el-table-column prop="question_count" label="题量" width="120" align="right" />
        </el-table>
      </div>
    </div>

    <div class="grid two">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>年份题量</h2>
            <p>仅统计质量状态为 ok 的题</p>
          </div>
          <el-button @click="load">刷新</el-button>
        </div>
        <div class="panel-body">
          <div ref="chartRef" class="chart" />
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>错题标签</h2>
            <p>从答题记录中统计高频标签</p>
          </div>
        </div>
        <div class="panel-body">
          <el-empty v-if="!wrongTags.length" description="暂无错题记录" />
          <el-table v-else :data="wrongTags" size="small">
            <el-table-column prop="tag" label="标签" />
            <el-table-column prop="wrong_count" label="次数" width="100" align="right" />
          </el-table>
        </div>
      </div>
    </div>
  </section>
</template>
