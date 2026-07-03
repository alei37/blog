/*!
 * math-dblclick.js
 * 给 LoveIt 主题的 KaTeX 公式加双击复制 LaTeX 源码功能
 * 依赖：KaTeX 渲染的 DOM（.katex-mathml annotation）
 */
(function () {
  'use strict';

  /**
   * 从 KaTeX DOM 中提取 LaTeX 源码
   * KaTeX 会把 LaTeX 放在 <annotation encoding="application/x-tex"> 里
   */
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

  /**
   * 复制到剪贴板（带 fallback）
   */
  function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    // 旧浏览器兜底
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

  /**
   * 弹"Copied!"小提示
   */
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

  /**
   * 给所有 .katex 元素绑定双击事件（已绑过的跳过）
   */
  function bind() {
    var katexNodes = document.querySelectorAll('.katex:not([data-dblclick-bound])');
    katexNodes.forEach(function (el) {
      el.setAttribute('data-dblclick-bound', '1');
      el.addEventListener('dblclick', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var tex = extractLatex(el);
        if (!tex) return;
        copyToClipboard(tex)
          .then(function () { showTip(e.clientX, e.clientY); })
          .catch(function (err) { console.error('[dblclick-copy] failed:', err); });
      });
    });
  }

  // 首次绑定（DOM ready 后）
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }

  // 兜底：KaTeX 异步渲染/动态加载情况下再绑一次
  setTimeout(bind, 500);
  setTimeout(bind, 1500);
})();
