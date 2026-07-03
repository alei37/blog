---
title: "Hello, Hugo!"
date: 2026-07-03T11:55:00+08:00
draft: false
description: "我的第一篇 Hugo 博客文章，介绍基本语法"
categories: ["计算机学习"]
tags: ["hugo", "博客", "入门"]
---

## 前言

这是博客的第一篇文章！🎉

用来测试一下 Hugo + LoveIt 主题的基本功能。

## 代码高亮测试

Python 代码块：

```python
def hello(name: str) -> str:
    return f"Hello, {name}!"

print(hello("alei"))
```

Bash 命令：

```bash
hugo server -D
```

## 公式测试

行内公式：爱因斯坦场方程 $G_{\mu\nu} = 8\pi G T_{\mu\nu}$。

块级公式：

$$
\frac{\partial u}{\partial t} = \nu \nabla^2 u
$$

## 表格测试

| 列1 | 列2 | 列3 |
|---|---|---|
| A | B | C |
| 1 | 2 | 3 |

## 任务列表

- [x] 搭建 Hugo 博客
- [x] 配置 GitHub Actions 自动部署
- [x] 启用 GitHub Pages
- [ ] 写更多文章
- [ ] 配置 Giscus 评论
