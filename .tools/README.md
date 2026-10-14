# 本地绘图工具

用于 `mydocs` 架构图重绘，未修改 Cortrix 的依赖和业务代码。

- Archify 3.1.0：上游 https://github.com/tt-a1i/archify，commit `c21c31ffb879668900c5487ea24993bf45d89b15`；技能入口 `archify/SKILL.md`。
- Node.js 22.16.0：`node-v22.16.0-linux-x64/bin/node`。
- Chrome headless 155.0.8059.79：`chrome/chrome-headless-shell-linux64/chrome-headless-shell`。
- 浏览器动态库与 Noto Sans CJK 字体安装到当前 Rocky Linux 环境。

三个工具目录通过本目录 `.gitignore` 忽略。交付 HTML 自包含，阅读不需要这些工具；重绘脚本见 `mydocs/tools/render_archify.py`。
