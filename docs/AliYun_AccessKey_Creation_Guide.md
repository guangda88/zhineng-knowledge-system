# 阿里云 AccessKey 创建指南

**目的**: 为调用听悟API创建访问密钥（AccessKey）

---

## ⚠️ 安全警告

> **重要**: 阿里云强烈建议**使用RAM用户创建AccessKey**，而不是主账号！

### 为什么使用RAM用户？

| 特性 | 主账号AccessKey | RAM用户AccessKey |
|------|----------------|-----------------|
| **安全性** | ❌ 风险高（拥有所有权限） | ✅ 风险低（可限制权限） |
| **权限控制** | ❌ 无法限制 | ✅ 可精确控制 |
| **审计追踪** | ❌ 难以区分 | ✅ 可区分操作者 |
| **泄露影响** | ❌ 影响整个账号 | ✅ 仅影响该用户 |
| **推荐使用** | ❌ **不推荐** | ✅ **强烈推荐** |

---

## 🎯 推荐方案：为RAM用户创建AccessKey

### 步骤1: 创建RAM用户

```
1. 登录阿里云控制台
   https://ram.console.aliyun.com/

2. 左侧导航栏 → 人员管理 → 用户

3. 点击"创建用户"

4. 填写用户信息:
   - 用户名: lingzhi-tingwu (示例)
   - 显示名称: 灵知系统听悟服务
   - 访问方式: ✓ OpenAPI调用访问

5. 点击"确定"完成创建
```

### 步骤2: 添加权限

```
1. 在用户列表中，找到刚创建的用户

2. 点击用户名进入详情页

3. 点击"添加权限"

4. 选择权限:
   - 系统搜索: 搜索"tingwu"
   - 选择: AliyunTingwuFullAccess (听悟完整权限)
   - 或者根据需要选择更精细的权限

5. 点击"确定"
```

### 步骤3: 创建AccessKey

```
1. 在用户详情页，找到"认证管理"标签页

2. 点击"创建AccessKey"按钮

3. 阅读安全提示:
   ☐ 我确认已知晓云账号AccessKey安全风险
   ☐ 建议使用RAM用户AccessKey以降低风险

4. 点击"确认"

5. ⚠️ 重要! 此时会显示AccessKey信息:
   - AccessKey ID: LTAI5tXXXXXXXXXXXX
   - AccessKey Secret: YYYYYYYYYYYYYYYYYYYYY

   **⚠️ 这是唯一一次能看到Secret的机会！**
   **请立即复制保存！**
```

### 步骤4: 保存AccessKey

创建完成后，立即保存到安全位置：

```bash
# 方式1: 环境变量（推荐）
export ALIYUN_ACCESS_KEY_ID="LTAI5tXXXXXXXXXXXX"
export ALIYUN_ACCESS_KEY_SECRET="YYYYYYYYYYYYYYYYYYYY"

# 方式2: 配置文件
# ~/.aliyun/credentials
[default]
access_key_id = LTAI5tXXXXXXXXXXXX
access_key_secret = YYYYYYYYYYYYYYYYYYYYY

# 方式3: 项目配置文件
# config/aliyun.yaml
aliyun:
  access_key_id: "LTAI5tXXXXXXXXXXXX"
  access_key_secret: "YYYYYYYYYYYYYYYYYYYY"
```

---

## 🚫 不推荐方案：主账号AccessKey（仅作参考）

如果您坚持使用主账号AccessKey（不推荐）：

### 步骤

```
1. 登录阿里云控制台
   https://ram.console.aliyun.com/

2. 鼠标移动到右上角头像

3. 选择"AccessKey"

4. 阅读风险提示:
   ☐ 我确认知晓云账号AccessKey安全风险

5. 点击"继续使用云账号AccessKey"

6. 查看或创建AccessKey
```

---

## 🔐 安全最佳实践

### 1. 权限最小化原则

```python
# 仅授予听悟服务所需权限
permissions = [
    "tingwu:SubmitTask",      # 提交转写任务
    "tingwu:GetTaskDetail",   # 获取任务详情
    "tingwu:ListTasks",       # 列出任务
    "tingwu:DeleteTask"       # 删除任务
]
```

### 2. 使用环境变量存储

```python
# ❌ 不推荐：硬编码
ACCESS_KEY_ID = "LTAI5tXXXXXXXXXXXX"
ACCESS_KEY_SECRET = "YYYYYYYYYYYYYYYYYYYY"

# ✅ 推荐：环境变量
import os
ACCESS_KEY_ID = os.environ.get("ALIYUN_ACCESS_KEY_ID")
ACCESS_KEY_SECRET = os.environ.get("ALIYUN_ACCESS_KEY_SECRET")
```

### 3. 定期轮换

```bash
# 建议每3-6个月轮换一次AccessKey
# 步骤：
# 1. 创建新的AccessKey
# 2. 测试新Key是否可用
# 3. 更新应用配置
# 4. 禁用旧的AccessKey
```

### 4. 禁用不需要的AccessKey

```bash
# 在RAM控制台
# 1. 找到用户
# 2. 进入"认证管理"
# 3. 找到不需要的AccessKey
# 4. 点击"禁用"
```

### 5. 使用STS临时凭证（高级）

```python
# 对于生产环境，建议使用STS临时凭证
# 优点：
# - 临时有效（自动过期）
# - 动态权限
# - 更安全

from aliyunsdkcore.client import AcsClient
from aliyunsdksts.request.v20150401 import AssumeRoleRequest

def get_sts_token():
    client = AcsClient(
        os.environ.get("ALIYUN_ACCESS_KEY_ID"),
        os.environ.get("ALIYUN_ACCESS_KEY_SECRET"),
        "cn-hangzhou"
    )

    request = AssumeRoleRequest.AssumeRoleRequest()
    request.set_RoleArn("acs:ram::xxxx:role/tingwu-role")
    request.set_RoleSessionName("tingwu-session")
    request.set_DurationSeconds(3600)  # 1小时

    response = client.do_action_with_exception(request)
    return response
```

---

## 🧪 验证AccessKey

创建后，立即验证是否可用：

### 方法1: 使用阿里云CLI

```bash
# 安装阿里云CLI
pip install aliyun-cli

# 配置
aliyun configure

# 测试
aliyun tingwu GetTaskDetail --TaskId your_task_id
```

### 方法2: 使用Python SDK

```python
# scripts/test_access_key.py
from alibabacloud_tingwu20230930.client import Client as TingwuClient
from alibabacloud_core.models import Config
import os

def test_access_key():
    """测试AccessKey是否可用"""
    try:
        config = Config(
            access_key_id=os.environ.get("ALIYUN_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIYUN_ACCESS_KEY_SECRET"),
            region_id='cn-hangzhou'
        )

        client = TingwuClient(config)

        # 测试API调用
        response = client.list_tasks(
            page_size=1
        )

        print("✅ AccessKey验证成功！")
        print(f"账号ID: {response.body.account_id}")

        return True

    except Exception as e:
        print(f"❌ AccessKey验证失败: {e}")
        return False

if __name__ == "__main__":
    test_access_key()
```

运行测试：

```bash
export ALIYUN_ACCESS_KEY_ID="your_access_key_id"
export ALIYUN_ACCESS_KEY_SECRET="your_access_key_secret"

python scripts/test_access_key.py
```

---

## 📝 记录AccessKey信息

创建完成后，请记录以下信息：

```markdown
# 阿里云AccessKey信息

## RAM用户信息
- 用户名: lingzhi-tingwu
- 显示名称: 灵知系统听悟服务
- 创建时间: 2026-03-31

## AccessKey信息
- AccessKey ID: LTAI5tXXXXXXXXXXXX
- AccessKey Secret: YYYYYYYYYYYYYYYYYYYYY
- 创建时间: 2026-03-31 10:00:00
- 状态: 启用

## 权限配置
- 策略: AliyunTingwuFullAccess
- 权限范围: 听悟服务完整权限

## 使用范围
- 项目: 灵知系统
- 用途: 调用听悟API获取音频和转录文字
- 环境: 开发/生产

## 轮换计划
- 创建日期: 2026-03-31
- 轮换周期: 6个月
- 下次轮换: 2026-09-30
```

---

## ⚠️ 常见问题

### Q1: 忘记保存AccessKey Secret怎么办？

**A**: 无法找回！AccessKey Secret只在创建时显示一次。解决方案：
- 删除当前AccessKey
- 重新创建新的AccessKey
- 更新所有使用该Key的应用

### Q2: AccessKey泄露怎么办？

**A**: 立即采取以下措施：
1. 禁用泄露的AccessKey
2. 删除泄露的AccessKey
3. 创建新的AccessKey
4. 更新应用配置
5. 审计日志，检查异常操作

### Q3: AccessKey权限不足怎么办？

**A**: 检查并添加权限：
1. 进入RAM控制台
2. 找到对应的RAM用户
3. 添加需要的权限策略
4. 等待权限生效（通常1-5分钟）

### Q4: 如何限制AccessKey的使用范围？

**A**: 创建自定义权限策略：
```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "tingwu:GetTaskDetail",
        "tingwu:ListTasks"
      ],
      "Resource": "*",
      "Condition": {
        "IpAddress": {
          "acs:SourceIp": ["192.168.1.0/24"]
        }
      }
    }
  ]
}
```

---

## 🎯 下一步

AccessKey创建完成后：

1. ✅ 配置环境变量
2. ✅ 测试AccessKey是否可用
3. ✅ 运行听悟API调用脚本
4. ✅ 导入数据到灵知系统

---

## 📚 相关文档

- [阿里云RAM快速入门](https://help.aliyun.com/zh/ram/product-overview/quick-start-create-and-use-accesskey-pairs-for-programmatic-calls)
- [创建RAM用户AccessKey](https://help.aliyun.com/zh/ram/user-guide/create-an-accesskey-pair)
- [AccessKey安全最佳实践](https://help.aliyun.com/zh/kms/key-management-service/user-guide/manage-and-use-ram-secrets)
- [听悟API文档](https://help.aliyun.com/zh/tingwu)

---

**文档状态**: ✅ 完成

**最后更新**: 2026-03-31

**安全提醒**: 请妥善保管AccessKey，不要泄露给他人！
