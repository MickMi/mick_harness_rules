# CI/CD Pipeline 模板库

本文档提供常用 CI/CD 平台的 Pipeline 模板。项目初始化时，根据实际技术栈选择对应模板，复制到项目根目录使用。

---

## 模板 A：GitHub Actions (通用)

文件路径：`.github/workflows/ci.yml`

```yaml
name: CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  lint:
    name: 🧹 Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup runtime
        # TODO: 根据技术栈选择 setup action
        # Node.js: uses: actions/setup-node@v4
        # Python:  uses: actions/setup-python@v5
        run: echo "请替换为实际的 setup step"
      - name: Install dependencies
        run: echo "请替换为实际的 install 命令 (npm ci / pip install / etc.)"
      - name: Run linter
        run: echo "请替换为实际的 lint 命令 (eslint . / ruff check . / etc.)"

  test:
    name: 🧪 Test
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - name: Setup runtime
        run: echo "请替换为实际的 setup step"
      - name: Install dependencies
        run: echo "请替换为实际的 install 命令"
      - name: Run tests
        run: echo "请替换为实际的 test 命令 (jest / pytest / etc.)"
      - name: Upload coverage
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage/

  security:
    name: 🔒 Security Scan
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - name: Run dependency audit
        run: echo "请替换为实际的 audit 命令 (npm audit / pip audit / etc.)"

  build:
    name: 📦 Build
    runs-on: ubuntu-latest
    needs: [test, security]
    steps:
      - uses: actions/checkout@v4
      - name: Setup runtime
        run: echo "请替换为实际的 setup step"
      - name: Install dependencies
        run: echo "请替换为实际的 install 命令"
      - name: Build
        run: echo "请替换为实际的 build 命令 (npm run build / etc.)"
      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: build-output
          path: dist/
```

---

## 模板 B：GitHub Actions (Docker 构建 + 推送)

文件路径：`.github/workflows/docker.yml`

```yaml
name: Docker Build & Push

on:
  push:
    tags: ['v*']

permissions:
  contents: read
  packages: write

jobs:
  docker:
    name: 🐳 Docker
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          # TODO: 替换为实际的 registry (ghcr.io / docker.io / 等)
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## 模板 C：GitLab CI (通用)

文件路径：`.gitlab-ci.yml`

```yaml
stages:
  - lint
  - test
  - security
  - build
  - deploy

variables:
  # TODO: 根据技术栈设置变量
  NODE_VERSION: "20"

lint:
  stage: lint
  script:
    - echo "请替换为实际的 lint 命令"

test:
  stage: test
  script:
    - echo "请替换为实际的 test 命令"
  coverage: '/All files[^|]*\|[^|]*\s+([\d\.]+)/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura-coverage.xml

security:
  stage: security
  script:
    - echo "请替换为实际的 audit 命令"
  allow_failure: false

build:
  stage: build
  script:
    - echo "请替换为实际的 build 命令"
  artifacts:
    paths:
      - dist/

deploy_staging:
  stage: deploy
  script:
    - echo "请替换为实际的部署命令"
  environment:
    name: staging
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy_production:
  stage: deploy
  script:
    - echo "请替换为实际的部署命令"
  environment:
    name: production
  rules:
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/
  when: manual
```

---

## PR 模板

文件路径：`.github/PULL_REQUEST_TEMPLATE.md`

```markdown
## What (做了什么)
<!-- 简述本次变更的内容 -->

## Why (为什么)
<!-- 说明变更的业务背景或技术原因 -->

## How to Test (如何测试)
<!-- 描述验证步骤，或说明已通过的自动化测试 -->

## Checklist
- [ ] 代码遵循项目 `.cursorrules` 中的编码规范
- [ ] 已编写/更新对应的测试用例
- [ ] 已更新相关文档 (architecture.md / MEMORY.md / TODO.md)
- [ ] 无新增 Lint 错误
- [ ] 已通过 Reviewer Agent 审查（或已提交审查请求）

## Related
<!-- 关联的 Issue / TODO 项 / 其他 PR -->
```

---

## Commitlint 配置模板

文件路径：`commitlint.config.js`（或 `.commitlintrc.yml`）

```javascript
// commitlint.config.js
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'style', 'refactor', 'perf', 'test', 'chore', 'ci', 'build', 'revert'],
    ],
    'subject-max-length': [2, 'always', 72],
    'body-max-line-length': [1, 'always', 100],
  },
};
```
