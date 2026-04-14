# Global Gotchas (跨项目踩坑记录)

## ⚠️ Tool & Environment Pitfalls
<!-- Record cross-project tool/environment pitfalls here -->
- [2026-04-09] qmd (semantic search tool) is a niche project with ecosystem risk. Prefer ripgrep for search, use semantic search as optional enhancement only.
- [2026-04-09] `git pull --rebase --autostash || true` silently ignores conflicts, may cause memory loss. Always implement explicit conflict handling.

## 🐛 Language & Framework Gotchas
<!-- Record language/framework-specific pitfalls that apply across projects -->

## 🔐 Security & Secrets
<!-- Record security-related lessons learned -->
- [2026-04-14] (source: cli) Test gotcha: brain push global write verification
