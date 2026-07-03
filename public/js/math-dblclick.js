/*!
 * math-dblclick.js
 * 给 LoveIt 主题的 KaTeX 公式加双击复制 LaTeX 源码功能
 *
 * 关键点：LoveIt 主题调用 KaTeX auto-render 时没有指定 output 选项，
 * 默认只输出 HTML（无 MathML），找不到 .katex-mathml annotation 标签。
 * 所以这里 monkey-patch renderMathInElement，强制输出 htmlAndMathml。
 */
(function () {
  'use strict';

  // ========== 步骤 1：让 KaTeX 同时输出 MathML ==========
  // 必须放在 IIFE 顶部，并尽早执行（在 theme.js 调 renderMathInElement 之前）
  if (typeof window.renderMathInElement === 'function') {
    var _origRender = window.renderMathInElement;
    window.renderMathInElement = function (elem, options) {
      var newOpts = Object.assign({}, options || {}, { output: 'htmlAndMathml' });
      return _origRender.call(this, elem, newOpts);
    };
  }

  // ========== 步骤 2：从 KaTeX DOM 提取 LaTeX 源码 ==========
  function extractLatex(katexEl) {
    var annotation = katexEl.querySelector('.katex-mathml annotation');
    if (!annotation) return null;
    var tex = annotation.textContent.trim();
    // 去掉 KaTeX annotation 自动加的 $...$ 或 $$...$$ 包裹
    if (tex.startsWith('$$') && tex.endsWith('$$')) {
      tex = tex.slice(2, -2).trim();
    } else if (tex.startsWith('$') && tex.endsWith('$')) {
      tex = tex.slice(1, -1).trim();
    }
    return tex;
  }

  // ========== 步骤 3：复制到剪贴板（带 fallback） ==========
  function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy') ? resolve() : reject();
      } catch (e) {
        reject(e);
      }
      document.body.removeChild(ta);
    });
  }

  // ========== 步骤 4：弹"Copied!"小提示 ==========
  function showTip(x, y) {
    var tip = document.createElement('div');
    tip.textContent = '✓ Copied!';
    tip.style.cssText =
      'position:fixed;left:' + x + 'px;top:' + y + 'px;' +
      'background:rgba(50,50,50,0.9);color:#fff;' +
      'padding:4px 10px;border-radius:4px;font-size:12px;' +
      'z-index:99999;pointer-events:none;' +
      'transform:translate(-50%,-130%);opacity:1;' +
      'transition:opacity 0.4s';
    document.body.appendChild(tip);
    setTimeout(function () { tip.style.opacity = '0'; }, 800);
    setTimeout(function () { document.body.removeChild(tip); }, 1300);
  }

  // ========== 步骤 5：给所有 .katex 元素绑定 dblclick ==========
  function bind() {
    var nodes = document.querySelectorAll('.katex:not([data-dblclick-bound])');
    nodes.forEach(function (el) {
      el.setAttribute('data-dblclick-bound', '1');
      el.addEventListener('dblclick', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var tex = extractLatex(el);
        if (!tex) {
          console.warn('[dblclick-copy] 未找到 LaTeX 源码（MathML 输出未开启？）');
          return;
        }
        copyToClipboard(tex)
          .then(function () { showTip(e.clientX, e.clientY); })
          .catch(function (err) { console.error('[dblclick-copy] 复制失败:', err); });
      });
    });
  }

  // DOM ready 后绑定
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      // 多绑几次，应对 KaTeX 异步/分批渲染
      bind();
      setTimeout(bind, 200);
      setTimeout(bind, 800);
      setTimeout(bind, 2000);
    });
  } else {
    bind();
  }
})();
