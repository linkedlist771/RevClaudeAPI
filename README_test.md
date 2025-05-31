# API密钥创建测试脚本

这个独立的测试脚本用于测试各种类型的API密钥创建功能，包括Claude镜像、逆向代理、续费码等。

## 安装依赖

```bash
pip install -r requirements_test.txt
```

## 运行脚本

```bash
python test_api_key_creation.py
```

## 功能说明

### 测试选项

1. **只创建Claude镜像密钥** - 创建API密钥并添加到Claude后端系统
2. **只创建逆向代理密钥** - 创建API密钥但不添加到后端，用于逆向代理
3. **创建续费码** - 创建Claude账号池续费码
4. **测试完整流程** - 测试所有功能
5. **自定义测试** - 自定义参数进行测试

### 主要功能

- **Claude API密钥创建**: 通过API创建Claude密钥
- **后端系统集成**: 将创建的密钥添加到Claude后端管理系统
- **续费码生成**: 创建用于账号续费的代码
- **密钥删除**: 批量删除不需要的API密钥
- **完整工作流测试**: 模拟真实的创建和使用流程

### 配置说明

脚本中的主要配置项：

```python
# API服务器配置
BASE_URL = "http://54.254.143.80:1145"
CLAUDE_BACKEND_API_BASE_URL = "https://clauai.qqyunsd.com/adminapi"
API_CLAUDE35_URL = "https://api.claude35.585dg.com/api/v1"

# 认证信息
CLAUDE_BACKEND_API_APIAUTH = "ccccld"
```

### 输出日志

- 控制台输出：实时显示测试进度和结果
- 日志文件：`api_key_test.log` - 详细的操作日志，按天轮换

### 使用示例

#### 快速测试创建1个API密钥
```bash
python test_api_key_creation.py
# 选择选项 1 (只创建Claude镜像密钥)
```

#### 自定义测试
```bash
python test_api_key_creation.py
# 选择选项 5 (自定义测试)
# 输入参数: plus类型, 3个密钥, 2小时过期时间
```

### 注意事项

1. **网络连接**: 确保能访问相关的API服务器
2. **认证信息**: 确保配置中的认证信息正确
3. **超时设置**: 默认HTTP超时为3600秒，可根据需要调整
4. **日志记录**: 所有操作都会记录到日志文件中，便于问题排查

### 错误处理

脚本包含完善的错误处理机制：
- API请求失败时会记录详细错误信息
- 网络超时会自动处理
- 参数验证确保输入有效性

### 扩展功能

如需添加新的测试功能，可以：
1. 在`APIKeyTester`类中添加新的测试方法
2. 在`main()`函数中添加新的选项
3. 更新`test_full_workflow()`方法支持新的工作流程 