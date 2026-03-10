# Search OpenClaw

> Search infrastructure and CLI scaffolding for OpenClaw.  
> Focused on `Web Search`, provider selection, multi-search fallback, and practical agent-friendly search workflows.

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Docs](https://img.shields.io/badge/docs-English%20%2B%20Chinese-blue)
![Topic](https://img.shields.io/badge/OpenClaw-Web%20Search-orange)

English · [中文](#中文版) · [Web Search](./docs/web-search.md) · [Search Routes](./docs/search-routes.md) · [Contributing](./CONTRIBUTING.md)

## English

Search OpenClaw helps you set up the search layer for OpenClaw instead of treating search as an afterthought.

It currently includes:

- a CLI to configure providers such as Brave, Tavily, Exa, Perplexity, GitHub, and iFlow
- `doctor` checks for your current search stack
- `doctor --fix` to install the skill and auto-detect local integrations
- direct search commands
- iFlow reuse from your local OpenClaw config
- one-command wrappers around the local `x_search_aggregator` repo for X and Zhihu keyword scraping

### Quick Start

```bash
search-openclaw install
search-openclaw doctor --fix
search-openclaw search "latest AI developments"
search-openclaw search "OpenClaw search setup" --provider iflow --stream
search-openclaw scrape-social "AI Agent" --platform both
```

### Why this repo exists

Most agent users do not fail because the model is weak. They fail because the search layer is badly configured:

- no reliable web search
- poor result structure
- no fallback provider
- weak handling of time-sensitive information

Search OpenClaw is built to make that layer explicit and usable.

### Provider Guidance

- If you have a card and want the safest default, start with `Brave`
- If you want lower friction and no card, start with `Tavily`
- If you want semantic search or lower cost experiments, add `Exa`
- If you already run OpenClaw with `iFlow`, Search OpenClaw can reuse that local key automatically
- If you care about resilience, combine at least two providers

### Social Search Wrappers

If you already have the local repo [`x_search_aggregator`](https://github.com/hhchhchhchhc/x_search_aggregator), Search OpenClaw can wrap it directly:

- `search-openclaw login-x`
- `search-openclaw scrape-social "AI Agent" --platform x`
- `search-openclaw scrape-social "AI Agent" --platform zhihu`
- `search-openclaw scrape-social "AI Agent" --platform both`

### Notes

- `iFlow` is currently used as a research-brief / structured-summary route, not a traditional web search engine
- Zhihu scraping still requires a valid cookie
- X scraping still requires a valid logged-in browser state

---

## 中文版

## CLI 快速开始

这个仓库现在不只是资料仓，也带了一套搜索层 CLI 脚手架，形态上参考了 `agent-reach`，但收敛到了搜索配置本身。

```bash
search-openclaw install
search-openclaw configure tavily_api_key <YOUR_KEY>
search-openclaw doctor
search-openclaw doctor --fix
search-openclaw search "latest AI developments"
search-openclaw search "OpenClaw 搜索配置建议" --provider iflow
search-openclaw scrape-social "AI Agent" --platform both
```

目前内置的能力包括：

- `install`：安装 Search OpenClaw skill
- `configure`：写入 Brave / Tavily / Exa / Perplexity / iFlow / GitHub 配置
- `doctor`：检查当前搜索层是否就绪
- `search`：直接调用已配置的搜索 provider
- `doctor --fix`：自动安装 skill 并检测本机 OpenClaw / x_search_aggregator 配置
- `login-x`：调用本地 `x_search_aggregator` 的登录脚本保存 X 登录态
- `scrape-social`：一键抓取 `x.com` / 知乎关键词结果
- `version`：查看版本

## 为什么需要 Search OpenClaw？

很多人第一次用 OpenClaw，都会有一种错觉：

“模型已经这么强了，搜索应该只是顺手就能搞定的事。”

真正开始跑任务以后，问题就出来了：

- “帮我查一下这个观点是不是最新的” -> 搜索源太弱，结果时效性差
- “帮我核实一下这条信息有没有别的来源” -> 只有单一搜索源，交叉验证能力差
- “帮我找几个高质量资料继续读” -> 结果结构太乱，Agent 不容易提炼
- “帮我持续跟踪这个主题最近一周的变化” -> 搜索稳定性不够，容易漏信息
- “帮我低成本配一个能长期用的搜索方案” -> 不知道该选 Brave、Tavily 还是多引擎

讨论到最后，结论其实很明确：

**搜索配置会显著影响 Agent 查资料、核实信息和跟踪时效信息的能力。**

配置对了，OpenClaw 才更像一个“会搜、会判、会引用”的执行代理，而不只是一个会续写的聊天模型。

Search OpenClaw 想做的，就是把这件事讲清楚。

## 仓库导航

- [Web Search](./docs/web-search.md)：为什么搜索层会直接影响 Agent 表现
- [搜索路线](./docs/search-routes.md)：Brave、Tavily、Exa、You.com、iFlow 的取舍
- [FAQ](./docs/faq.md)：常见问题、适用场景和选型建议
- [Contributing](./CONTRIBUTING.md)：如何补充经验、修正文档、提交新路线

## 这个仓库解决什么问题

这个仓库不是新的搜索引擎，也不是 OpenClaw 插件商店。

它更像一份围绕 `OpenClaw + Web Search` 的实战选型手册，重点解决几件事：

- 哪些搜索 API 更适合 Agent，而不只是适合人类网页浏览
- 没卡怎么开始，有卡怎么少踩坑
- 免费优先时，哪条路线最值得先试
- 什么时候该上多引擎，什么时候单引擎就够了
- 如何从“能搜”走到“搜得稳、搜得准、搜得省”

## 快速结论

如果你现在只想先拿一个能用的结论：

- **有卡且追求兼容性：优先 Brave Search API**
- **不想绑卡、零门槛开跑：优先 Tavily**
- **继续压低成本：试 Exa、You.com、iFlow**
- **想做容灾和补盲：上多搜索源组合**

一句话说完：

**给 OpenClaw 配搜索，不是比“谁更全”，而是比“谁更适合 Agent”。**

## 关键配置

### Web Search

`Web Search` 是 OpenClaw 里最容易被低估、但对实际效果影响最大的一层配置。

很多看起来像“模型不够聪明”的问题，本质上都出在搜索层：

- 没配搜索，Agent 只能依赖已有上下文回答
- 搜索源质量一般，结果噪音高、时效差
- 搜索结果结构不友好，Agent 很难稳定提炼重点
- 缺少多引擎兜底，一旦单点失效就直接掉线

对 Agent 来说，搜索不是附属能力，而是基础能力。

一个真正能干活的 OpenClaw，至少要能做到：

- 搜到最新信息，而不是只复述训练数据
- 交叉验证多个来源，而不是抓到一条就当真
- 提取结构化网页信息，而不是把整页噪音直接喂给模型
- 在单一搜索源不稳定时自动切换

如果你的目标是研究、信息收集、内容整理、竞品跟踪、热点分析，那么先把 `Web Search` 配好，收益通常比换模型更直接。

更多解释见：[docs/web-search.md](./docs/web-search.md)

## 搜索 API

### 默认优先

如果你有卡，且追求兼容性、稳定性和社区验证程度，**优先 Brave Search API**。

原因很简单：

- 接入讨论多，资料相对好找
- 结果结构适合 Agent 消费
- 速度和稳定性通常都比较好
- 很多人已经拿它跑过实际任务，踩坑成本更低

这是最接近“少折腾，先跑起来”的路线。

### 零门槛优先

如果你不想绑卡，只想尽快用起来，**优先 Tavily**。

它的优势主要在于：

- 注册和接入门槛低
- 对 Agent 使用场景比较友好
- 社区里常被当作开箱即用的搜索 API
- 免费额度对个人测试比较够用

对刚开始折腾 OpenClaw 的用户，Tavily 往往是最省心的起点。

### 进一步降成本

如果你已经把基本搜索跑通，接下来可以考虑继续压低成本或增强覆盖面：

- `Exa`
- `You.com`
- `iFlow`
- 多引擎并行 / 回退方案

这类路线更适合已经明确自己需求的人，比如：

- 希望把成本压到更低
- 想增强语义搜索能力
- 希望降低单一供应商风险
- 想做多源交叉验证

### 备注

这里提到的免费额度，主要来自社区讨论中的常见说法，适合做选型参考，**不建议把配额当长期承诺**。

搜索服务的定价、免费层和风控策略都可能随时间变化。真正上线到生产环境前，建议你以官方控制台和文档为准。

## 免费优先

### 最值得先试的几条搜索路线

下面这几条路线，各自适合不同约束。

| 路线 | 社区常见认知 | 适合谁 | 备注 |
| --- | --- | --- | --- |
| Brave | 每月约 `2000` 次免费，通常要绑卡 | 有卡、想少折腾的人 | 结构化结果好，兼容性强 |
| Tavily | 每月约 `1000` 次免费，不绑卡 | 刚入门、想低门槛开跑的人 | 对 Agent 友好，开箱即用 |
| Exa / You.com | 更偏语义搜索和赠送额度思路 | 想继续压低成本的人 | 适合补充检索能力 |
| iFlow | 复用当前 OpenClaw key 的研究增强路线 | 已经在本机使用 OpenClaw 的人 | 适合减少重复配置 |
| multi-search-engine | 多搜索源组合 | 想做容灾、补盲、交叉验证的人 | 降低单点故障风险 |

## 组合使用建议

如果你不想花太多时间选型，可以直接按下面的思路走：

### 方案 A：最省心

- 主搜索：`Brave`
- 备用：`Tavily`

适合大多数希望稳定跑任务的人。

### 方案 B：完全免费优先

- 主搜索：`Tavily`
- 补充：`Exa` 或 `You.com`

适合个人体验、学习和轻度使用。

### 方案 C：稳定性优先

- 主搜索：`Brave`
- 备用：`Tavily`
- 容灾：多搜索源组合

适合信息收集、研究、持续监控类任务。

### 方案 D：进阶折腾流

- 主搜索：`Brave` 或 `Tavily`
- 研究增强：`iFlow`
- 多源补盲：多搜索源组合

适合已经熟悉 OpenClaw、想进一步增强效果的人。

更完整说明见：[docs/search-routes.md](./docs/search-routes.md)

## 推荐阅读顺序

如果你第一次看这个仓库，建议按这个顺序读：

1. 先看 [Web Search](./docs/web-search.md)，理解为什么搜索层比想象中更关键
2. 再看 [搜索路线](./docs/search-routes.md)，确定你当前适合哪条方案
3. 最后按自己的约束选择：有卡走 Brave，没卡走 Tavily，需要更稳就加多引擎

## 适合谁

这个仓库比较适合下面几类人：

- 刚开始用 OpenClaw，不知道搜索该怎么配
- 希望低成本把 Agent 搜索能力跑通
- 做研究、资料收集、热点跟踪，比较依赖时效信息
- 想做多搜索源组合，减少单点故障
- 想先把基础设施搭好，再往上叠工作流

## Contributing

欢迎补充：

- 新的搜索 API 路线
- 免费额度变化
- OpenClaw 里的实际配置经验
- 多搜索源组合方案
- 踩坑记录和规避建议

提交前建议先看 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 为什么值得 Star

如果你正在用 OpenClaw，或者准备让 Agent 真正承担资料检索和信息核实的工作，这类基础设施会比表面上更重要。

Star 这个仓库的理由很简单：

- 以后你要重新配置搜索时，能更快找到一份现成的选型参考
- 免费额度、推荐路线、组合方案会持续变化，集中整理比零散翻帖子更省时间
- 很多看似“模型不行”的问题，本质上是搜索层没搭好，这类知识值得沉淀

## 常见问题 / FAQ

### OpenClaw 的 Web Search 为什么这么关键？

因为它直接决定 Agent 能不能拿到最新信息、能不能做交叉验证、能不能稳定引用外部资料。

### 第一次配置，应该先选哪个？

- 有卡：先试 `Brave`
- 没卡：先试 `Tavily`

### 完全免费能不能用？

可以。对大多数个人测试和轻度使用来说，免费优先路线是能跑通的。但免费额度和策略可能变化，不建议把免费配额当长期承诺。

### 什么时候该上多搜索源？

当你开始做持续监控、热点跟踪、研究分析，或者明显感觉单一搜索源有漏检、偏科、偶发失效时，就值得上多搜索源组合。

### 这个仓库是代码仓还是资料仓？

目前是资料仓，重点在选型、路线、经验总结和文档沉淀，不是新的搜索 SDK。

更完整 FAQ 见：[docs/faq.md](./docs/faq.md)

## About

Search OpenClaw 是一个围绕 `OpenClaw + Web Search` 的中文资料仓，目标不是重新发明搜索，而是帮更多人用更低成本把搜索层搭对。

## License

MIT
