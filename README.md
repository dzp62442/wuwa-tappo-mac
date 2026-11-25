<div align="center">
  <img src="docs/images/app-icon.png" alt="Wuwa Tappo" width="96" height="96">
  <h1>Wuwa Tappo · macOS</h1>
  <p>把鸣潮桌宠带到 Mac 桌面</p>
  <p><strong>1.0.5 · build 18</strong> · Apple Silicon · macOS 13+</p>
  <p><a href="https://github.com/dzp62442/wuwa-tappo-mac/releases/latest">下载安装包</a> · <a href="#使用说明">使用说明</a> · <a href="CHANGELOG.md">更新记录</a></p>
</div>

Wuwa Tappo macOS 是鸣潮桌宠的社区移植版。用键盘、鼠标或手柄让共鸣者在桌面上拍桌子，边玩边积累点击，开宝箱收集角色外观、配件和表情。界面沿用国服素材与布局，输入监听、菜单栏、窗口和会话存储接入 macOS。

## 1.0.5 更新

- **断网恢复后可以重新登录**。网络恢复时，登录窗口会重新检查连接，长时间运行后也能继续打开通行证登录。
- **缩短开宝箱的等待**。背包查询较慢时，开箱动画结束就发送领取请求，随后在后台刷新背包。
- **输入监控授权可随更新保留**。从本版起，发布包使用固定证书签名。同一签名的版本覆盖安装后，macOS 可沿用已授予的输入监控权限。
- 修复联机桌宠拖动。即使 macOS 未授权全局输入监控，也能在自己的屏幕上拖动其他房间成员的桌宠。
- **和朋友一起玩**。创建房间并设为公开，或随机加入公开房间。房主可以移除成员、转让房主。
- **更快找到表情**。在背包里筛选当前角色的表情，也可以把角色、配件和表情存成预设。
- **按场景调整桌宠**。在游戏模式设置中管理始终置顶与指针监控。macOS 14 及以上可选跟随系统游戏模式。
- **重置后继续累计**。重置应用会清理本地设置和登录会话，并保留点击计数。重新登录后恢复该账号的累计值。

设置页、联机和合成页使用统一的暖金色按钮样式，桌宠计数在 WebKit 中按字符复用字体缓存。各构建的完整记录见 [更新记录](CHANGELOG.md)。

<p align="center">
  <img src="docs/images/backpack.png" alt="Wuwa Tappo macOS 1.0.5 的背包界面" width="900">
</p>

## 安装

需要 **Apple Silicon Mac 和 macOS 13 或更新版本**。

从 [1.0.5 发布页](https://github.com/dzp62442/wuwa-tappo-mac/releases/tag/v1.0.5) 下载 `Wuwa-Tappo-mac-1.0.5-arm64.zip`，退出旧版，解压后把 `Wuwa Tappo.app` 拖进「应用程序」。将同页的 `SHA256SUMS.txt` 与 ZIP 放在同一目录，运行 `shasum -a 256 -c SHA256SUMS.txt` 可校验下载。

已安装 1.0.5 build 17 的用户请从发布页下载 build 18 并覆盖安装。build 17 的应用内更新只比较版本号，同为 1.0.5 时不会提示升级。

从此前公开发布的 1.0.4 build 14 升级，首次迁移到新签名时需重新授权一次。如果「输入监控」已开启但桌宠仍未计数，可按[开发指南](docs/开发指南.md#更新后验证输入监控)恢复授权。

安装包未经 Apple 公证。若 macOS 拦截启动，先尝试打开一次，再到「系统设置 → 隐私与安全性」选择「仍要打开」。

## 使用说明

- **启动并计数**。在菜单栏桌宠图标中选择「授权输入监控…」，在「系统设置 → 隐私与安全性 → 输入监控」启用 Wuwa Tappo，回到应用选择「重试监听」。输入监控用于桌宠动作与点击计数。
- **登录和收集**。支持国服通行证及游戏 UID 登录。可以查看账号背包和图鉴，换装、收藏、保存预设、合成、兑换及联机。登录会话保存在系统钥匙串。
- **跟随系统游戏模式**。在「设置 → 游戏模式设置」打开「跟随 macOS 游戏模式」。该功能默认关闭，需要 macOS 14 或更新版本。开启后，桌宠跟随系统状态，桌宠自身的全屏自动切换暂时停用。
- **检查更新**。打开「设置 → 检查更新」，发现新版后可前往 GitHub Release。

<p align="center">
  <img src="docs/images/settings.png" alt="Wuwa Tappo macOS 1.0.5 的游戏模式设置" width="900">
</p>

## 从源码构建

需要 Xcode Command Line Tools、Python 3.9+ 和 Git。素材以 Git 子模块放在 `vendor/wuwa-tappo-assets/`。递归克隆会一并检出项目锁定的素材版本。首次本地构建前请按[开发指南](docs/开发指南.md#版本与签名)配置签名身份。

```sh
git clone --recurse-submodules https://github.com/dzp62442/wuwa-tappo-mac.git
cd wuwa-tappo-mac
python3 scripts/build-macos.py
open 'dist/Wuwa Tappo.app'
```

已有工作副本在普通克隆后，或拉取了更新素材版本的提交后，可在项目根目录运行 `git submodule update --init --recursive`，再执行上面的构建命令。

所需素材已打入应用包，日常运行无需保留源码或子模块。产物为 `dist/Wuwa Tappo.app` 和 `dist/Wuwa-Tappo-mac-arm64.zip`。运行测试另需 Node.js 22+，无需 `npm install`。

## 致谢与许可

感谢 [Wuwa Tappo 国服](https://download-mc-wuwatappo.kurogames-global.com/download/) 的桌宠、角色美术及界面，感谢 [wuwa-tappo-assets](https://github.com/lliooly/wuwa-tappo-assets) 的素材整理与校验。

本项目是社区维护的非官方移植。原创适配代码和文档采用 [MIT](LICENSE)，原作素材、字体及商标保留各自权利。参见 [第三方说明](THIRD_PARTY_NOTICES.md) 和 [非官方声明](DISCLAIMER.md)。
