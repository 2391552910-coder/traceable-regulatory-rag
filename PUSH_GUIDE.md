# 待推送文件清单与操作指南（交接文档 v2）

> 本文档用于新对话中的 AI 继续完成 GitHub 推送。仓库本地路径：`/mnt/agents/work/traceable-regulatory-rag`
> GitHub 仓库：`2391552910-coder/traceable-regulatory-rag`，分支 `main`
> 推送方式：仅能通过 GitHub MCP 工具 `push_files`（沙箱内无 git 凭据，已验证）。
> 上次更新：2026-09-30 会话。所有 commit 均在 main 分支。

## 已推送（请勿重复推送）

| 批次 | 文件 | 提交 |
|---|---|---|
| 批 1 | `README.md`、`docs/知识库采集说明.md`、`docs/实验设计与流程.md` | `26a4e910` |
| 批 2 | `scripts/` 5 个采集/构建脚本 | `a4211490` |
| 批 3A | `src/retrieval/router.py`、`src/retrieval/dense.py`、`src/alignment/citation_alignment.py`、`src/generation/llm_client.py`、`tests/test_smoke.py` | `e0ce0025` |
| 批 3B | `data/annotation/retrieval_queries.csv`、`retrieval_queries_for_annotation.csv`、`results/retrieval_eval.csv` | `2617cf1e` |
| 批 4 | `data/knowledge_base/manifest.json`（315篇清单） | `3460149d` |
| 批 10（部分） | 仅 4 个txt：`DOC039`、`DOC040`、`DOC041`、`DOC044`（commit 信息标注有误，实际不含 DOC042/043/045-053） | `4d176b60` |
| 批 11 | `DOC054`-`DOC068`（15 个处罚决定 txt） | `35126686` |
| 批 20 | `DOC154`-`DOC168`（15 个处罚决定 txt） | `1fbbaf46` |

知识库 txt 已推送 34/315。其余 281 个 txt + 3 个 collection_manifest*.json 未推送。

## 续推批次（按此顺序，每批一次 push_files，读完立即推）

- 续批1（2个，约160KB）：DOC005-DOC006
- 续批2（8个，约187KB）：DOC007-DOC014
- 续批3（10个，约175KB）：DOC015-DOC024
- 续批4（7个，约188KB）：DOC025-DOC031
- 续批5（7个，约189KB）：DOC032-DOC038
- 续批6（15个，约158KB）：DOC042-DOC072
- 续批7（15个，约127KB）：DOC073-DOC087
- 续批8（8个，约192KB）：DOC088-DOC096
- 续批9（8个，约143KB）：DOC097-DOC108
- 续批10（6个，约199KB）：DOC110-DOC119
- 续批11（5个，约196KB）：DOC120-DOC129
- 续批12（3个，约53KB）：DOC130-DOC132
- 续批13（1个，约286KB）：DOC133（单独一批，最大文件）
- 续批14（15个，约87KB）：DOC134-DOC153
- 续批15（15个，约70KB）：DOC169-DOC183
- 续批16（15个，约117KB）：DOC184-DOC198
- 续批17（15个，约99KB）：DOC199-DOC213
- 续批18（15个，约75KB）：DOC214-DOC228
- 续批19（15个，约47KB）：DOC229-DOC243
- 续批20（15个，约64KB）：DOC244-DOC258
- 续批21（15个，约98KB）：DOC259-DOC273
- 续批22（15个，约46KB）：DOC274-DOC288
- 续批23（15个，约142KB）：DOC289-DOC303
- 续批24（15个，约43KB）：DOC304-DOC318
- 续批25（15个，约96KB）：DOC319-DOC337
- 续批26（6个，约185KB）：DOC338-DOC343

文件名以 `data/knowledge_base/DOCxxx_*.txt` 为准（精确名单可用
`ls /mnt/agents/work/traceable-regulatory-rag/data/knowledge_base/` 对照 manifest.json 的 file 字段）。
3 个 `collection_manifest*.json` 为采集中间产物，可选推送。

## 降级策略（时间/额度有限时）

优先推小文件批次：续批14、15、17、19、20、22、24（全部处罚决定/通报），
大法规文件（续批1-5、8-13、26）可跳过、由脚本重建（见 README「知识库重建」）。

## 推送注意事项

1. **直接调用 `push_files`，不要先用 shell 打印确认** —— 拿到文件内容后立即调用。
2. `push_files` 参数：owner/repo/branch/message/files，files 为 `[{"path": ..., "content": ...}]`，content 用 UTF-8 原文。
3. 文件读取用绝对路径 `/mnt/agents/work/traceable-regulatory-rag/...`。
4. 每批推送成功后报告 commit SHA，并更新本文件「已推送」表。
5. 单会话上下文有限：每个 txt 内容需经对话两次（读取+推送），一个会话约可完成 4-6 批（60-90 个文件）。推不完就更新本文件后交给下一个对话继续。

## 安全约束（必须遵守）

- 仓库内不得出现任何 API 密钥/密钥串；`LLM_API_KEY` 只能通过环境变量/`.env`（已 gitignore）注入。
