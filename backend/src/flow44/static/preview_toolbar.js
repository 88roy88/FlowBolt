// Element-picker toolbar, injected into dev preview pages by api/preview.py.
// Sends picked elements, and prompts written next to them, to the builder via postMessage
// (window.parent in the iframe, window.opener in a new tab).
(function () {
  'use strict';
  if (window.__BUILDAPP_TOOLBAR__) return;
  window.__BUILDAPP_TOOLBAR__ = true;

  var match = location.pathname.match(/^\/api\/preview\/([^/]+)\/proxy\//);
  if (!match) return;
  var projectId = decodeURIComponent(match[1]);

  var SOURCE = 'buildapp-toolbar';
  var BUILDER_SOURCE = 'buildapp-builder';
  var COLLAPSED_KEY = 'buildapp-toolbar-collapsed';
  var HELLO_TIMEOUT_MS = 500;
  var HELLO_THROTTLE_MS = 1000;
  var PROMPT_TIMEOUT_MS = 3000;
  var MAX_COMPONENTS = 4;
  var IGNORED_COMPONENTS =
    /^(BrowserRouter|HashRouter|MemoryRouter|Router|Routes|Route|RenderedRoute|Outlet|Suspense|StrictMode|Fragment|ErrorBoundary)$|(Provider|Consumer|Context|Boundary)$/;

  var ICON_PICK =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3a2 2 0 0 0-2 2"/><path d="M19 3a2 2 0 0 1 2 2"/><path d="m12 12 4 10 1.7-4.3L22 16Z"/><path d="M5 21a2 2 0 0 1-2-2"/><path d="M9 3h1"/><path d="M9 21h2"/><path d="M14 3h1"/><path d="M3 9v1"/><path d="M21 9v2"/><path d="M3 14v1"/></svg>';
  // ICON_PICK with a plus in place of its top-right corner.
  var ICON_PICK_MORE =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3a2 2 0 0 0-2 2"/><path d="M19 2v6"/><path d="M16 5h6"/><path d="m12 12 4 10 1.7-4.3L22 16Z"/><path d="M5 21a2 2 0 0 1-2-2"/><path d="M9 3h1"/><path d="M9 21h2"/><path d="M3 9v1"/><path d="M3 14v1"/></svg>';
  var ICON_DOWN =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
  var ICON_SEND =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>';
  var ICON_CLOSE =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';
  var ICON_UP =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>';

  var STYLES = [
    ':host{all:initial}',
    '*{box-sizing:border-box;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}',
    '.bar{position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:2147483647;display:flex;align-items:center;gap:4px;padding:4px;border-radius:999px;background:#1e1e2e;color:#cdd6f4;font-size:12px;line-height:1;box-shadow:0 4px 16px rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.08);max-width:calc(100vw - 24px)}',
    'button{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;color:inherit;white-space:nowrap}',
    'button:hover{background:rgba(255,255,255,.08)}',
    'button:focus-visible{outline:2px solid #89b4fa;outline-offset:1px}',
    'button.active{background:#0090A3;color:#fff}',
    'button.icon{padding:6px}',
    'button:disabled{opacity:.4;cursor:default;background:none}',
    'button.send{background:#0090A3;color:#fff}',
    'button.send:hover:not(:disabled){background:#007a8a}',
    'button.send:disabled{background:#0090A3}',
    '.hint{padding:6px 10px;color:#a6adc8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.count{padding:3px 8px;border-radius:999px;background:rgba(137,180,250,.15);color:#89b4fa;font-weight:600;white-space:nowrap}',
    '.tab{position:fixed;left:50%;bottom:0;transform:translateX(-50%);z-index:2147483647;padding:2px 14px;border-radius:8px 8px 0 0;background:#1e1e2e;color:#cdd6f4;opacity:.75;box-shadow:0 -2px 8px rgba(0,0,0,.2)}',
    '.tab:hover{opacity:1;background:#1e1e2e}',
    '.toast{position:fixed;left:50%;bottom:56px;transform:translateX(-50%);z-index:2147483647;padding:6px 12px;border-radius:999px;background:#1e1e2e;color:#a6e3a1;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.25);pointer-events:none;white-space:nowrap}',
    '.box{position:fixed;z-index:2147483646;pointer-events:none;border:2px solid #0090A3;background:rgba(0,144,163,.12);border-radius:3px;display:none}',
    '.prompt{position:fixed;z-index:2147483647;width:360px;max-width:calc(100vw - 16px);padding:6px;border-radius:12px;background:#1e1e2e;color:#cdd6f4;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.08);flex-direction:column;gap:4px}',
    '.prompt .row{display:flex;align-items:center;gap:4px}',
    'textarea{all:unset;box-sizing:border-box;flex:1;min-width:0;max-height:120px;overflow-y:auto;padding:6px 8px;border-radius:8px;color:#cdd6f4;font-size:13px;line-height:1.4;white-space:pre-wrap;overflow-wrap:anywhere}',
    'textarea::placeholder{color:#7f849c}',
    'textarea:disabled{opacity:.6}',
    '.prompt .error{padding:0 8px 4px;color:#f38ba8}',
    '.label{position:fixed;z-index:2147483646;pointer-events:none;padding:2px 6px;border-radius:3px;background:#0090A3;color:#fff;font:11px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap;display:none;max-width:60vw;overflow:hidden;text-overflow:ellipsis}',
  ].join('\n');

  var host = window.parent !== window ? window.parent : window.opener;
  var state = {
    status: 'pending', // 'pending' | 'connected' | 'readonly' | 'disconnected'
    count: 0,
    picking: false,
    collapsed: readCollapsed(),
    // The disconnected state always starts collapsed.
    expandedWhileDisconnected: false,
    toast: '',
    // The prompt box next to the picked elements: { anchors, sending, error, selectingMore } or null.
    prompt: null,
  };
  var helloTimer = null;
  var lastHello = 0;
  var toastTimer = null;
  var hovered = null;
  var lastPicked = null;
  var promptTimer = null;

  function readCollapsed() {
    try {
      return localStorage.getItem(COLLAPSED_KEY) === '1';
    } catch (e) {
      return false;
    }
  }

  function writeCollapsed(value) {
    try {
      localStorage.setItem(COLLAPSED_KEY, value ? '1' : '0');
    } catch (e) {
      /* storage unavailable */
    }
  }

  function isCollapsed() {
    if (state.status === 'connected') return state.collapsed;
    return !state.expandedWhileDisconnected;
  }

  function send(msg) {
    if (!host || host.closed) return false;
    msg.source = SOURCE;
    msg.projectId = projectId;
    try {
      host.postMessage(msg, location.origin);
      return true;
    } catch (e) {
      return false;
    }
  }

  function hello() {
    var now = Date.now();
    if (now - lastHello < HELLO_THROTTLE_MS) return;
    lastHello = now;
    clearTimeout(helloTimer);
    if (!send({ type: 'hello' })) {
      setStatus('disconnected');
      return;
    }
    helloTimer = setTimeout(function () {
      setStatus('disconnected');
    }, HELLO_TIMEOUT_MS);
  }

  function setStatus(status) {
    if (state.status === status) return;
    state.status = status;
    if (status !== 'connected') {
      stopPicking();
      closePrompt();
    }
    render();
  }

  window.addEventListener('message', function (event) {
    var data = event.data;
    if (event.origin !== location.origin || event.source !== host) return;
    if (!data || data.source !== BUILDER_SOURCE) return;
    if (data.type === 'ready') {
      clearTimeout(helloTimer);
      var count = data.count || 0;
      var status = data.canWrite ? 'connected' : 'readonly';
      if (count === state.count && status === state.status) return;
      state.count = count;
      state.status = status;
      if (status !== 'connected') {
        stopPicking();
        closePrompt();
      }
      render();
    } else if (data.type === 'count') {
      state.count = data.count || 0;
      var picked = data.added && lastPicked && lastPicked.isConnected ? lastPicked : null;
      lastPicked = null;
      if (state.prompt) {
        if (picked) state.prompt.anchors.push(picked);
        showPromptAgain();
      } else if (picked) {
        openPrompt(picked);
      }
      // The prompt box is the confirmation; only toast when there's no box to show.
      if (!data.added) showToast('Max elements reached');
      else if (!picked && !state.prompt) showToast('Added to chat \u2713');
    } else if (data.type === 'prompt-result') {
      if (!state.prompt) return;
      clearTimeout(promptTimer);
      state.count = data.count || 0;
      if (data.ok) {
        closePrompt();
        showToast('Sent to chat \u2713');
      } else {
        failPrompt(PROMPT_ERRORS[data.reason] || 'Could not send the prompt');
      }
    }
  });

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') hello();
  });
  window.addEventListener('focus', hello);

  function clip(value, max) {
    value = value || '';
    return value.length > max ? value.slice(0, max - 1) + '\u2026' : value;
  }

  function classesOf(el) {
    return (el.getAttribute('class') || '').replace(/\s+/g, ' ').trim();
  }

  function segment(el) {
    if (el.id && /^[A-Za-z][\w-]*$/.test(el.id)) return '#' + el.id;
    var tag = el.tagName.toLowerCase();
    var seg = tag;
    var cls = classesOf(el)
      .split(' ')
      .filter(function (c) {
        return c && !/[:[\]/]/.test(c);
      })[0];
    if (cls) seg += '.' + CSS.escape(cls);
    var parent = el.parentElement;
    if (parent) {
      var same = Array.prototype.filter.call(parent.children, function (c) {
        return c.tagName === el.tagName;
      });
      if (same.length > 1) seg += ':nth-of-type(' + (same.indexOf(el) + 1) + ')';
    }
    return seg;
  }

  function selectorOf(el) {
    var parts = [];
    for (var node = el; node && node !== document.body && node !== document.documentElement && parts.length < 5; node = node.parentElement) {
      var seg = segment(node);
      parts.unshift(seg);
      if (seg.charAt(0) === '#') break;
    }
    return parts.join(' > ');
  }

  function componentName(type) {
    if (!type || typeof type === 'string') return null;
    if (typeof type === 'function') return type.displayName || type.name || null;
    // forwardRef / memo wrappers
    if (type.displayName) return type.displayName;
    var inner = type.render || type.type;
    return inner ? componentName(inner) : null;
  }

  function componentsOf(el) {
    try {
      var fiber = null;
      for (var node = el; node && !fiber; node = node.parentElement) {
        for (var key in node) {
          if (key.indexOf('__reactFiber$') === 0) {
            fiber = node[key];
            break;
          }
        }
      }
      var names = [];
      for (var f = fiber; f && names.length < MAX_COMPONENTS; f = f.return) {
        var name = componentName(f.type);
        if (!name || !/^[A-Z]/.test(name) || IGNORED_COMPONENTS.test(name)) continue;
        if (names.indexOf(name) === -1) names.push(name);
      }
      return names;
    } catch (e) {
      return [];
    }
  }

  function describe(el) {
    return {
      tag: el.tagName.toLowerCase(),
      selector: selectorOf(el),
      text: clip((el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(), 120),
      classes: clip(classesOf(el), 200),
      html: clip(el.outerHTML, 600),
      components: componentsOf(el),
    };
  }

  var BLOCKED_EVENTS = ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'dblclick', 'contextmenu', 'submit'];
  var cursorStyle = null;

  function isOwn(target) {
    return target === hostEl;
  }

  function pickable(target) {
    return (
      target instanceof Element &&
      !isOwn(target) &&
      target !== document.body &&
      target !== document.documentElement
    );
  }

  function onMove(e) {
    hovered = pickable(e.target) ? e.target : null;
    positionBox();
  }

  function onBlocked(e) {
    if (isOwn(e.target)) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    if (e.type === 'click' && pickable(e.target)) {
      var element = describe(e.target);
      stopPicking();
      lastPicked = e.target;
      send({ type: 'element-picked', element: element });
    }
  }

  function onLeave() {
    hovered = null;
    positionBox();
  }

  // Outlines `target` with `el`; returns its rect, or null when there's nothing to outline.
  function placeBox(el, target) {
    if (!target || !target.isConnected) {
      el.style.display = 'none';
      return null;
    }
    var r = target.getBoundingClientRect();
    el.style.display = 'block';
    el.style.left = r.left + 'px';
    el.style.top = r.top + 'px';
    el.style.width = r.width + 'px';
    el.style.height = r.height + 'px';
    return r;
  }

  function positionBox() {
    var anchors = state.prompt ? state.prompt.anchors : [];
    var last = anchors[anchors.length - 1];
    anchors.forEach(function (anchor, i) {
      if (!anchorBoxes[i]) {
        anchorBoxes[i] = document.createElement('div');
        anchorBoxes[i].className = 'box';
        shadow.insertBefore(anchorBoxes[i], box);
      }
      placeBox(anchorBoxes[i], anchor);
    });
    for (var i = anchors.length; i < anchorBoxes.length; i++) anchorBoxes[i].style.display = 'none';
    placeBox(box, hovered);

    var target = hovered || last;
    var r = target && target.isConnected ? target.getBoundingClientRect() : null;
    if (!r) {
      label.style.display = 'none';
    } else {
      label.textContent = segment(target).replace(/\\/g, '');
      label.style.display = 'block';
      label.style.left = Math.max(0, r.left) + 'px';
      var labelTop = r.top - 20;
      label.style.top = (labelTop < 0 ? r.bottom + 2 : labelTop) + 'px';
    }
    if (state.prompt && !state.prompt.selectingMore && last && last.isConnected) {
      positionPrompt(last.getBoundingClientRect());
    }
  }

  // Below the element, or above it when there's no room, kept inside the viewport.
  function positionPrompt(r) {
    var gap = 8;
    var w = promptEl.offsetWidth;
    var h = promptEl.offsetHeight;
    var top = r.bottom + gap;
    if (top + h > window.innerHeight - gap) top = r.top - h - gap;
    top = Math.min(Math.max(gap, top), window.innerHeight - h - gap);
    var left = Math.min(Math.max(gap, r.left), window.innerWidth - w - gap);
    promptEl.style.top = top + 'px';
    promptEl.style.left = left + 'px';
  }

  function startPicking() {
    if (state.picking || state.status !== 'connected') return;
    state.picking = true;
    state.collapsed = false;
    window.addEventListener('mousemove', onMove, true);
    window.addEventListener('scroll', positionBox, true);
    window.addEventListener('resize', positionBox);
    document.documentElement.addEventListener('mouseleave', onLeave);
    BLOCKED_EVENTS.forEach(function (type) {
      window.addEventListener(type, onBlocked, true);
    });
    cursorStyle = document.createElement('style');
    cursorStyle.textContent = '*{cursor:crosshair !important}';
    document.head.appendChild(cursorStyle);
    render();
  }

  function stopPicking() {
    if (!state.picking) return;
    state.picking = false;
    hovered = null;
    window.removeEventListener('mousemove', onMove, true);
    window.removeEventListener('scroll', positionBox, true);
    window.removeEventListener('resize', positionBox);
    document.documentElement.removeEventListener('mouseleave', onLeave);
    BLOCKED_EVENTS.forEach(function (type) {
      window.removeEventListener(type, onBlocked, true);
    });
    if (cursorStyle) cursorStyle.remove();
    cursorStyle = null;
    positionBox();
    render();
  }

  // With a prompt box open, picking adds to its elements instead of starting over.
  function pick() {
    if (state.prompt) selectMore();
    else startPicking();
  }

  // Cancelling a "select more" pick brings the box back rather than dismissing it.
  function cancelPicking() {
    stopPicking();
    if (state.prompt) showPromptAgain();
  }

  window.addEventListener(
    'keydown',
    function (e) {
      if (e.key === 'Escape' && state.picking) {
        e.preventDefault();
        e.stopPropagation();
        cancelPicking();
      } else if (e.key === 'Escape' && state.prompt) {
        e.preventDefault();
        e.stopPropagation();
        dismissPrompt();
      } else if (e.altKey && e.shiftKey && e.code === 'KeyS' && state.status === 'connected') {
        e.preventDefault();
        if (state.picking) cancelPicking();
        else pick();
      }
    },
    true,
  );

  var hostEl = document.createElement('buildapp-toolbar');
  var shadow = hostEl.attachShadow({ mode: 'closed' });
  var style = document.createElement('style');
  style.textContent = STYLES;
  var ui = document.createElement('div');
  var box = document.createElement('div');
  box.className = 'box';
  var label = document.createElement('div');
  label.className = 'label';
  var anchorBoxes = [];
  shadow.append(style, box, label, ui);

  function button(className, html, title, onClick) {
    var b = document.createElement('button');
    if (className) b.className = className;
    b.innerHTML = html;
    b.title = title;
    b.addEventListener('click', function (e) {
      e.stopPropagation();
      onClick();
    });
    return b;
  }

  function showToast(text) {
    state.toast = text;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      state.toast = '';
      render();
    }, 1800);
    render();
  }

  var PROMPT_ERRORS = {
    busy: 'BuildApp is busy, try again when it finishes',
    readonly: 'You have view-only access to this project',
    empty: 'Write a prompt first',
  };

  // Lives outside `ui` so re-renders don't drop the typed text or focus.
  var promptEl = document.createElement('div');
  promptEl.className = 'prompt';
  promptEl.style.display = 'none';
  var promptInput = document.createElement('textarea');
  promptInput.rows = 1;
  promptInput.placeholder = 'Ask for a change to this element\u2026';
  var sendButton = button('icon send', ICON_SEND, 'Send to chat (Enter)', submitPrompt);
  var promptRow = document.createElement('div');
  promptRow.className = 'row';
  promptRow.append(
    button('icon', ICON_PICK_MORE, 'Select more elements (Alt+Shift+S)', selectMore),
    promptInput,
    sendButton,
    button('icon', ICON_CLOSE, 'Close and remove the selection (Esc)', dismissPrompt),
  );
  var promptError = document.createElement('div');
  promptError.className = 'error';
  promptEl.append(promptRow, promptError);
  shadow.insertBefore(promptEl, ui);

  promptInput.addEventListener('input', function () {
    renderPrompt();
    positionBox();
  });
  // Keep the preview app's own hotkeys from firing while typing.
  ['keydown', 'keyup', 'keypress'].forEach(function (type) {
    promptInput.addEventListener(type, function (e) {
      e.stopPropagation();
      if (type === 'keydown' && e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        submitPrompt();
      }
    });
  });

  function onOutsidePointer(e) {
    // A "select more" click is a pick, not a dismissal.
    if (state.picking) return;
    if (e.composedPath().indexOf(hostEl) === -1) dismissPrompt();
  }

  // Separate from picking's positionBox listeners, which come and go while the box stays open.
  function onPromptViewport() {
    positionBox();
  }

  function openPrompt(anchor) {
    state.prompt = { anchors: [anchor], sending: false, error: '', selectingMore: false };
    promptInput.value = '';
    window.addEventListener('scroll', onPromptViewport, true);
    window.addEventListener('resize', onPromptViewport);
    window.addEventListener('pointerdown', onOutsidePointer, true);
    render();
    promptInput.focus();
  }

  function selectMore() {
    if (!state.prompt || state.prompt.sending) return;
    state.prompt.selectingMore = true;
    startPicking();
  }

  function showPromptAgain() {
    state.prompt.selectingMore = false;
    render();
    promptInput.focus();
  }

  function closePrompt() {
    if (!state.prompt) return;
    state.prompt = null;
    clearTimeout(promptTimer);
    window.removeEventListener('scroll', onPromptViewport, true);
    window.removeEventListener('resize', onPromptViewport);
    window.removeEventListener('pointerdown', onOutsidePointer, true);
    positionBox();
    render();
  }

  // Closing the box drops the selection; only a sent prompt keeps (and consumes) it.
  function dismissPrompt() {
    if (!state.prompt) return;
    send({ type: 'clear-elements' });
    state.count = 0;
    closePrompt();
  }

  function submitPrompt() {
    if (!state.prompt || state.prompt.sending) return;
    var content = promptInput.value.trim();
    if (!content) return;
    state.prompt.sending = true;
    state.prompt.error = '';
    if (!send({ type: 'send-prompt', content: content })) {
      failPrompt('Open this preview from BuildApp to send prompts');
      return;
    }
    clearTimeout(promptTimer);
    promptTimer = setTimeout(function () {
      failPrompt('BuildApp did not respond, try again');
    }, PROMPT_TIMEOUT_MS);
    render();
  }

  function failPrompt(message) {
    clearTimeout(promptTimer);
    if (!state.prompt) return;
    state.prompt.sending = false;
    state.prompt.error = message;
    render();
    promptInput.focus();
  }

  function renderPrompt() {
    if (!state.prompt || state.prompt.selectingMore) {
      promptEl.style.display = 'none';
      return;
    }
    promptEl.style.display = 'flex';
    promptInput.placeholder =
      state.prompt.anchors.length > 1 ? 'Ask for a change to these elements\u2026' : 'Ask for a change to this element\u2026';
    promptInput.disabled = state.prompt.sending;
    sendButton.disabled = state.prompt.sending || !promptInput.value.trim();
    promptError.textContent = state.prompt.error;
    promptError.style.display = state.prompt.error ? 'block' : 'none';
    // Grow with the text, or the placeholder when empty, instead of scrolling (up to max-height).
    promptInput.style.height = 'auto';
    promptInput.style.height = Math.min(promptInput.scrollHeight, 120) + 'px';
  }

  function setCollapsed(value) {
    if (state.status === 'connected') {
      state.collapsed = value;
      writeCollapsed(value);
    } else {
      state.expandedWhileDisconnected = !value;
    }
    if (!value) hello();
    render();
  }

  function hintText() {
    if (state.status === 'readonly') return 'You have view-only access to this project';
    return 'Open this preview from BuildApp to select elements for chat';
  }

  function render() {
    ui.textContent = '';
    renderPrompt();
    if (state.prompt) positionBox();
    if (state.status === 'pending') return;

    if (state.toast) {
      var toast = document.createElement('div');
      toast.className = 'toast';
      toast.textContent = state.toast;
      ui.appendChild(toast);
    }

    if (isCollapsed()) {
      ui.appendChild(button('tab', ICON_UP, 'Show BuildApp toolbar', function () {
        setCollapsed(false);
      }));
      return;
    }

    var bar = document.createElement('div');
    bar.className = 'bar';
    bar.addEventListener('mouseenter', function () {
      if (!state.picking) hello();
    });

    if (state.status !== 'connected') {
      var hint = document.createElement('span');
      hint.className = 'hint';
      hint.textContent = hintText();
      bar.appendChild(hint);
    } else if (state.picking) {
      var picking = document.createElement('span');
      picking.className = 'hint';
      picking.textContent =
        state.prompt ? 'Click another element \u00b7 Esc to go back' : 'Click an element \u00b7 Esc to cancel';
      bar.appendChild(picking);
      bar.appendChild(button('active', 'Cancel', 'Stop selecting (Esc)', cancelPicking));
    } else {
      bar.appendChild(button('', ICON_PICK + '<span>Select element</span>', 'Select an element to add to the chat (Alt+Shift+S)', pick));
      if (state.count > 0) {
        var count = document.createElement('span');
        count.className = 'count';
        count.textContent = state.count + ' attached';
        bar.appendChild(count);
      }
    }

    if (!state.picking) {
      bar.appendChild(button('icon', ICON_DOWN, 'Hide toolbar', function () {
        setCollapsed(true);
      }));
    }
    ui.appendChild(bar);
  }

  function mount() {
    document.body.appendChild(hostEl);
    // Re-attach if the app replaces body content.
    new MutationObserver(function () {
      if (!hostEl.isConnected) document.body.appendChild(hostEl);
    }).observe(document.body, { childList: true });
    hello();
  }

  if (document.body) mount();
  else document.addEventListener('DOMContentLoaded', mount);
})();
