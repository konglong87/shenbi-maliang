# 🖌️ 神笔马良 · 写作DNA蒸馏

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> 把你自己写成代码。将公众号/小红书/X/Twitter 的文章蒸馏成专属于你的「写作基因包」，让 AI 写出真正像你的文字。

---

## 为什么需要这个？

用 AI 写文章，输出永远是那个"AI 味"——满嘴「首先、其次、总而言之」，冷静平整得像块玻璃。

**写作DNA蒸馏**解决的就是这件事：读你几十篇文章，从中萃取出你的句式习惯、论证套路、情绪调性、选题偏好，甚至你的思维盲区。最后生成一个 DNA 档案——AI 拿着它就能写出几乎分不清是你写的还是它写的文字。

不是 prompt engineering，是一次完整的写作范式萃取。

---

## 核心流程

```
文章样本 → 文本预处理 → 七维并行采集 → 三重验证降噪
                                    ↓
                               硬规则/软范式分类
                                    ↓
                               写作DNA档案
                                    ↓
                             AI 按你风格写作
```

### 七维采集器

从七个维度独立并行分析你的文章，各自提取碎片化特征：

| 维度 | 采集内容 |
|------|----------|
| **表达范式** | 句式习惯、标志性词汇、口头禅、修辞手法 |
| **思维逻辑** | 论证套路、推理路径、因果链条 |
| **知识体系** | 高频话题、类比素材库、知识边界 |
| **情感决策** | 读者关系定位、情绪调性、共情策略 |
| **选题视角** | 话题切入角度、标题命名规律 |
| **节奏控制** | 句长分布、段落节奏、留白风格 |
| **反模式** ⚠️ | 思维盲区、逻辑漏洞、表达短板、刻意回避 |

### 三重验证

原始特征中混有大量偶然发挥，只保留**稳定、可信、有代表性**的特征：

1. **频次验证** — 同一特征至少在 N 篇不同文章中出现（默认 ≥3 篇）
2. **语境一致性验证** — 在不同话题、不同情绪的文章中表现稳定
3. **逻辑自洽验证** — 多条特征之间无矛盾

### 双轨输出

- 🔴 **硬规则**（Hard Rules）：口头禅、禁忌话题、固定句式模板 → AI 直接执行
- 🔵 **软范式**（Soft Paradigms）：思维框架、情感调性、论证模式 → Few-shot 引导

---

## 项目结构

```
shenbi-maliang/
├── writing-dna/
│   ├── SKILL.md                              # 技能定义（WorkBuddy 入口）
│   ├── config.yaml                           # 验证阈值与采集规则配置
│   ├── references/
│   │   ├── writing-dna-framework.md          # 七维分析框架详细指南
│   │   ├── dna-template.md                   # DNA档案输出模板
│   │   └── my-writing-dna.md                 # 你的个人DNA档案（自动生成）
│   ├── scripts/
│   │   └── distill_writing_dna.py            # 批量蒸馏 + 三重验证 + 增量更新
│   └── assets/                               # 资源文件
└── README.md
```

---

## 快速开始

克隆仓库：

```bash
git clone git@github.com:konglong87/shenbi-maliang.git
cd shenbi-maliang
```

### WorkBuddy

原生支持，直接安装即可使用全部命令。

1. 将 `writing-dna` 目录放入 WorkBuddy skills 目录
2. 提供文章样本，说：**「蒸馏文章」**
3. 查看DNA档案：**「DNA档案」**
4. 用你的风格写新文章：**「按我风格写 [主题]」**

### Claude Code

将写作DNA框架注入 Claude Code，让它理解并复刻你的风格。

**方法一：作为项目指令**

将 `writing-dna/SKILL.md` 的核心内容追加到项目 `CLAUDE.md`：

```bash
cat writing-dna/SKILL.md >> CLAUDE.md
```

在 Claude Code 对话中直接说「蒸馏我的文章」，它会按七维框架分析。

**方法二：DNA档案作为风格参考**

蒸馏完成后，将生成的 `my-writing-dna.md` 内容添加到 `CLAUDE.md` 的用户风格部分。之后 Claude Code 在写作时会自动匹配你的风格。

### Cursor

**方法一：Rules 注入**

将写作DNA框架添加为 Cursor Rule：

1. 打开 Cursor → Settings → Rules
2. 新建 Rule，将 `writing-dna/SKILL.md` 内容粘贴进去
3. 设置为 `always` 或 `agent-requested`

**方法二：.cursorrules**

```bash
cp writing-dna/references/writing-dna-framework.md .cursorrules
```

蒸馏出的 DNA 档案可追加到此文件末尾，Cursor 在写作任务中会参考。

### OpenCode

OpenCode 支持自定义 Workspace Rules，将写作DNA框架注册为项目规则：

1. 打开 OpenCode → Workspace Settings → Instructions
2. 将 `writing-dna/SKILL.md` 内容添加为 Project Instructions
3. 蒸馏完成后，把 DNA 档案也添加进去

对话中直接说「按我风格写一篇关于 X 的文章」，OpenCode 会加载规则生成。

### Codex (OpenAI)

Codex CLI 支持通过 `AGENTS.md` 或 `CODEX.md` 注入系统指令：

```bash
# 方法一：通过 AGENTS.md（Codex 自动加载）
cat writing-dna/SKILL.md >> AGENTS.md

# 方法二：通过 CODEX.md
cp writing-dna/SKILL.md CODEX.md
```

也可以在 Codex 会话中手动指定：

```bash
codex exec "加载写作DNA框架: writing-dna/SKILL.md，然后按我的风格写..."
```

### 命令行独立运行

如果只想跑蒸馏脚本，不需要任何 AI 工具：

```bash
cd writing-dna/scripts

# 完整蒸馏
python3 distill_writing_dna.py --input ./samples/ --output ../references/

# 增量更新（只处理新文章）
python3 distill_writing_dna.py --input ./samples/ --mode incremental
```

---

## 命令速查

| 命令 | 效果 |
|------|------|
| `蒸馏文章` / `distill` | 分析文章，生成或更新DNA档案 |
| `增量更新` / `update dna` | 只分析新文章，合并入已有档案 |
| `DNA档案` / `show dna` | 展示当前写作DNA全貌 |
| `硬规则` / `hard rules` | 只展示可直接执行的规则 |
| `软范式` / `soft paradigms` | 只展示风格示例 |
| `反模式` / `anti patterns` | 展示写作盲区与禁忌 |
| `按我风格写 [主题]` | 加载DNA，创作新内容 |
| `重置DNA` | 清空当前档案，重新蒸馏 |

---

## 配置说明

编辑 `config.yaml` 调整蒸馏严格程度：

- `frequency_threshold: 3` — 特征需在至少 3 篇文章中出现才被采纳
- `confidence.high_threshold: 5` — 出现 5 篇以上升级为硬规则
- `incremental.enabled: true` — 支持增量蒸馏，无需全量重跑

完整配置项见 [config.yaml](writing-dna/config.yaml)。

---

## 核心原则

- **忠实优先** — 宁可保留「不完美」也不擅自优化，原汁原味复刻
- **稳定特征优先** — 只蒸馏反复出现的特征，一次性灵感不入库
- **来源可溯** — 每条规则标注出处，出错可回溯
- **DNA 是活的** — 文章越多越准确，支持增量迭代
- **反模式同权重** — 盲区和禁忌与优点同等重要

---

## 理念来源

借鉴认知蒸馏（Cognitive Distillation）方法论，将隐性的个人写作风格转化为 AI 可直接执行的显性规则。本质是**人文本范式的萃取与固化**。

---

## License

MIT © 2026
