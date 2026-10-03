"""xhs-cli：匿名免登录采集小红书笔记。

设计约束
--------
- **零登录态**：不读 cookie/env，请求前用 :func:`anonymity.assert_anonymous` 校验。
- **不美化数据**：抓不到首批评论就标 ``partial``，不假装完整。
- **可复现**：相同分享链接 → 相同解析路径 → 相同目录结构。
"""

__version__ = "0.1.0"

__all__ = ["__version__"]