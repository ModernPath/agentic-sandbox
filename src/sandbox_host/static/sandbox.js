/* Sandbox shared kit: request helper, safe rendering, sign-out. Loaded by the home page and agent pages. */
(function (global) {
  'use strict';

  var HEADER = 'X-Sandbox-Request';

  function safeHref(value) {
    if (typeof value !== 'string') return null;
    if (value.charAt(0) === '/' && value.charAt(1) !== '/' && value.indexOf('\\') === -1) return value;
    if (/^https?:\/\//i.test(value)) return value;
    return null;
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (key === 'className') node.className = attrs[key];
      else if (key === 'text') node.textContent = attrs[key];
      else node.setAttribute(key, attrs[key]);
    });
    (children || []).forEach(function (child) {
      if (child === null || child === undefined) return;
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    });
    return node;
  }

  function link(href, label, className) {
    var safe = safeHref(href);
    if (!safe) return document.createTextNode(label);
    return el('a', { href: safe, text: label, className: className || '',
      rel: /^https?:/i.test(safe) ? 'noopener noreferrer' : null,
      target: /^https?:/i.test(safe) ? '_blank' : null });
  }

  function api(method, path, body) {
    var options = { method: method, headers: {}, credentials: 'same-origin' };
    options.headers[HEADER] = '1';
    if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    return fetch(path, options).then(function (response) {
      if (response.status === 401) {
        global.location.assign('/login?next=' + encodeURIComponent(global.location.pathname));
        throw new Error('Sign in required');
      }
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) {
          var detail = data.detail;
          if (Array.isArray(detail)) detail = detail.map(function (d) { return String(d.msg).replace(/^Value error, /, ''); }).join('; ');
          throw new Error(detail || data.error || ('Request failed (' + response.status + ')'));
        }
        return data;
      });
    });
  }

  function signOut() {
    return api('POST', '/api/auth/logout').catch(function () { return null; }).then(function () {
      global.location.assign('/login');
    });
  }

  function banner(text, isError) {
    return el('p', { className: 'banner ' + (isError ? 'error' : 'ok'), role: 'status', text: text });
  }

  function itemList(items, emptyText) {
    if (!items || !items.length) return el('p', { className: 'empty', text: emptyText || 'Nothing yet.' });
    return el('ul', { className: 'items' }, items.map(function (item) {
      return el('li', {}, [
        link(item.href, item.title || '(untitled)'),
        item.meta ? el('div', { className: 'item-meta', text: item.meta }) : null,
      ]);
    }));
  }

  function renderPanel(panel) {
    var children = [el('h2', { text: panel.title || '' })];
    if (panel.metric) {
      children.push(el('div', { className: 'metric-label', text: panel.metric.label || '' }));
      children.push(el('div', { className: 'metric', text: String(panel.metric.value) }));
    }
    children.push(itemList(panel.items, panel.empty));
    if (panel.action) children.push(el('p', {}, [link(panel.action.href, panel.action.label, 'button secondary')]));
    return el('section', { className: 'card' }, children);
  }

  global.Sandbox = {
    api: api,
    el: el,
    link: link,
    safeHref: safeHref,
    signOut: signOut,
    banner: banner,
    itemList: itemList,
    renderPanel: renderPanel,
  };
})(window);
