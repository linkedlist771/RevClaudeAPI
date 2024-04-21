#!/bin/bash

# 指定要格式化的目录，如果要格式化整个项目，请使用"."
# 您也可以指定特定的文件或子目录
TARGET_DIRECTORY="."

# 检查 Black 是否已安装
if ! command -v black &> /dev/null
then
    echo "Black could not be found, installing..."
    pip install black
fi

# 运行 Black 来格式化代码
echo "Running Black on ${TARGET_DIRECTORY}..."
black $TARGET_DIRECTORY

echo "Formatting complete."
