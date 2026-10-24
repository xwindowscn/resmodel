# resmodel.com — 产品站（纯软件）

## 定位
本仓库只承载 **RES Financial Model 软件产品站**。内容范围限定为：产品介绍、功能、定价、下载、常见问题、法务（Terms/Refund/Privacy）、支持。
**不包含**任何咨询、顾问、投资建议类内容，也不链接到集团门户的业务页面。这是 Paddle 域名审查的要求。

## 结构
- `index.html` 首页（产品/功能/定价/下载/FAQ/免责）
- `terms.html` / `refund.html` / `privacy.html` / `support.html`
- `downloads/` 四个平台安装包（3.6.1）
- `CNAME` → resmodel.com

## 发布
GitHub Pages（本仓库 main 分支根目录）。自定义域名通过 `CNAME` 文件 + DNS 指向实现。

## 维护规则
1. 新增内容前先自检：是否属于"软件产品"范畴；不得出现咨询/顾问/投资建议措辞（免责句除外）
2. 不得添加指向 yellowfir.com 等集团业务页面的链接
3. 法务页修改需与法务部确认
4. 定价与计划 ID 必须与 `license.resmodel.com/buy?plan=` 一致
