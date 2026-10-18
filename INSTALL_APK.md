# Pi Calculator APK 安装说明

## 文件

- `dist/picalc-1.0-arm64-v8a-debug.apk` —— 19.0 MB
- SHA256：`bb1a74807caaa8f5ae2934acbaf5ff50195dcecff93f9a84bec9b9cec4e90c8f`
- 架构：`arm64-v8a`（覆盖绝大多数现代安卓机，不含 32 位 armeabi-v7a）
- 最低系统：Android 7.0（API 24）及以上
- 类型：debug 包（未签名发布版，安装时手机可能提示"未知来源"）

## 在线下载（公开永久链接）

<https://github.com/ljx20162025/pi-calculator/releases/download/v1.0-9/picalc-1.0-arm64-v8a-debug.apk>

## 安装步骤

1. 把 APK 传到手机（微信/QQ 文件传输、USB 拷贝、或直接手机浏览器打开上面的链接下载）
2. 手机上点开该 APK
3. 若提示"未知来源应用"，按提示允许一次即可（这是所有非应用商店 APK 的正常流程）
4. 安装完成后桌面出现 **Pi Calculator** 图标

> 若用微信/QQ 传文件后点不开安装界面，改用"文件管理"里找到该 APK 再点，
> 或直接用手机浏览器打开上面的链接下载。

## 应用用法

打开后界面从上到下是：

- **算法选择**（下拉框）
  - `递推版（推荐）` —— 每轮只做十几次小整数乘除，位数大时快几十倍
  - `阶乘版` —— 每轮重算阶乘，公式直观但慢
  - `两者对比` —— 同时跑两个算法，校验结果一致并给出耗时对比
- **位数输入** —— 默认 20，可填到几万（位数越大耗时越长）
- **开始计算** —— 计算在后台线程跑，界面不会卡死
- **结果区** —— 可上下滚动查看，超过 64 位会自动分块排版

## 已知限制

- 只含 `arm64-v8a`，很老的 32 位机型装不了
- debug 包首次启动会比 release 包慢一点（解压 Python 运行时）
- 手机上算几万位仍需要几秒到十几秒，属正常

## 想重新构建

推代码到 `main` 分支的 `android/**` 或 `.github/workflows/build-apk.yml` 会自动触发云端构建，
完成后 APK 会同时出现在 Actions 的 Artifacts 和新的 GitHub Release 里。
仓库：<https://github.com/ljx20162025/pi-calculator>
