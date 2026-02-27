#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Lambda 打包脚本
# 用法: cd careplan-mvp/lambdas && bash build.sh
#
# 打包原理:
#   Lambda 运行环境是 Linux x86_64。
#   如果直接在 Mac 上 pip install，psycopg2 等 C 扩展会是 Mac 版本，
#   传到 Lambda 会报错 "cannot import ... incompatible architecture"。
#   解决方法：pip install 时指定 --platform manylinux2014_x86_64，
#   强制下载 Linux 版本的二进制文件。
#
# 最终产物:
#   dist/create_order.zip
#   dist/generate_careplan.zip
#   dist/get_order.zip
# ═══════════════════════════════════════════════════════════════

set -e   # 任何命令失败就立刻停止脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"
DIST_DIR="$SCRIPT_DIR/dist"
DEPS_DIR="$SCRIPT_DIR/.deps"   # 依赖缓存目录（只需装一次）

echo "📦 开始打包 Lambda..."
echo "   backend 目录: $BACKEND_DIR"
echo "   输出目录: $DIST_DIR"

# 创建输出目录
mkdir -p "$DIST_DIR"

# ── 第一步：安装 Linux 兼容的依赖（只需执行一次）──────────────────────
echo ""
echo "🔧 安装 Linux 兼容依赖..."
pip install \
    --platform manylinux2014_x86_64 \
    --target="$DEPS_DIR" \
    --implementation cp \
    --python-version 3.12 \
    --only-binary=:all: \
    --upgrade \
    -r "$SCRIPT_DIR/requirements.txt"

echo "✅ 依赖安装完成"

# ── 打包函数 ──────────────────────────────────────────────────────────
package_lambda() {
    local LAMBDA_NAME=$1      # 例如 "create_order"
    local HANDLER_FILE=$2     # 例如 "create_order/handler.py"
    local OUTPUT_ZIP="$DIST_DIR/${LAMBDA_NAME}.zip"
    local BUILD_DIR="$SCRIPT_DIR/.build_${LAMBDA_NAME}"

    echo ""
    echo "📦 打包 Lambda: $LAMBDA_NAME"

    # 清理旧的 build 目录
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"

    # 1. 复制依赖
    cp -r "$DEPS_DIR/." "$BUILD_DIR/"

    # 2. 复制 Django 项目代码（backend/ 下所有内容）
    #    Lambda 里 /var/task/ 就相当于 backend/ 目录
    cp -r "$BACKEND_DIR/." "$BUILD_DIR/"

    # 3. 复制对应的 handler.py 到根目录
    #    Lambda 的 Handler 配置是 "handler.handler"（文件名.函数名）
    cp "$SCRIPT_DIR/$HANDLER_FILE" "$BUILD_DIR/handler.py"

    # 4. 删除不需要的文件（减小 zip 体积）
    find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$BUILD_DIR" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find "$BUILD_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
    find "$BUILD_DIR" -name "*.pyc" -delete 2>/dev/null || true
    find "$BUILD_DIR" -name ".DS_Store" -delete 2>/dev/null || true

    # 5. 打 zip 包
    cd "$BUILD_DIR"
    zip -r "$OUTPUT_ZIP" . -q
    cd "$SCRIPT_DIR"

    # 6. 显示 zip 大小
    local SIZE=$(du -sh "$OUTPUT_ZIP" | cut -f1)
    echo "✅ $LAMBDA_NAME.zip 打包完成 ($SIZE)"
}

# ── 打包三个 Lambda ────────────────────────────────────────────────────
package_lambda "create_order"      "create_order/handler.py"
package_lambda "generate_careplan" "generate_careplan/handler.py"
package_lambda "get_order"         "get_order/handler.py"

# ── 清理临时 build 目录 ────────────────────────────────────────────────
rm -rf "$SCRIPT_DIR"/.build_*

echo ""
echo "🎉 全部打包完成！输出文件："
ls -lh "$DIST_DIR/"
echo ""
echo "⬆️  下一步：去 AWS 控制台上传 zip 文件"
echo "   控制台路径：Lambda → 函数 → 代码 → 上传自 → .zip 文件"
