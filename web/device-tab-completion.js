/* Keyboard command completion for the native desktop's simulated consoles.
   Tab changes the edit buffer only; command execution always requires Enter. */
(() => {
  'use strict';

  const pcCommands = ['ipconfig', 'arp -a', 'ping', 'tracert', 'traceroute', 'help'];
  const agentCommands = [
    'help', 'capabilities', 'show', 'show interfaces', 'show routes',
    'show topology', 'show links', 'show vlans', 'show arp',
    'show spanning-tree', 'show json', 'add', 'add-model', 'connect',
    'disconnect', 'remove', 'rename', 'duplicate', 'move', 'ip',
    'gateway', 'ospf', 'ios', 'ping', 'traceroute', 'reset',
    'save', 'load', 'undo', 'redo', 'note', 'sample', 'physical',
    'workspace-tool', 'device-config', 'show packet-events'
  ];

  function localComplete(text, cursor, words, deviceNames = []) {
    const left = text.slice(0, cursor);
    const match = /\S+$/.exec(left);
    const start = match ? match.index : cursor;
    const typed = left.slice(start).toLowerCase();
    const context = left.slice(0, start).trim().split(/\s+/).filter(Boolean);
    let end = cursor;
    while (end < text.length && !/\s/.test(text[end])) end++;
    const candidates = new Set();
    for (const phrase of words) {
      const parts = phrase.split(/\s+/);
      if (parts.length <= context.length) continue;
      if (!context.every((word, i) => parts[i].toLowerCase().startsWith(word.toLowerCase()))) continue;
      const next = parts[context.length];
      if (next.toLowerCase().startsWith(typed)) candidates.add(next);
    }
    if (deviceNames.length && context.length === 1 &&
        ['show', 'ios', 'ping', 'traceroute', 'remove'].includes(context[0].toLowerCase())) {
      for (const device of deviceNames) {
        if (device.toLowerCase().startsWith(typed)) candidates.add(device);
      }
    }
    const matches = [...candidates].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
    let replacement = left.slice(start);
    if (matches.length === 1) {
      replacement = matches[0];
    } else if (matches.length > 1) {
      const first = matches[0];
      let count = 0;
      while (count < first.length &&
             matches.every(value => value[count]?.toLowerCase() === first[count]?.toLowerCase())) count++;
      if (count > typed.length) replacement = first.slice(0, count);
    }
    return {
      start, end, replacement, candidates: matches,
      changed: replacement !== text.slice(start, end)
    };
  }

  function hint(input, message) {
    const form = input.closest('form');
    if (!form) return;
    let node = form.nextElementSibling;
    if (!node?.classList.contains('pt-cli-completions')) {
      node = document.createElement('div');
      node.className = 'pt-cli-completions';
      node.setAttribute('role', 'status');
      node.setAttribute('aria-live', 'polite');
      form.after(node);
    }
    node.textContent = message;
    node.hidden = !message;
  }

  document.addEventListener('input', event => {
    if (event.target?.matches('#deviceCliIn,#pcCmdIn,#termIn')) hint(event.target, '');
  }, true);

  document.addEventListener('keydown', async event => {
    if (event.key !== 'Tab' || event.shiftKey || event.ctrlKey ||
        event.metaKey || event.altKey || event.isComposing) return;
    const input = event.target;
    const kind = input?.id;
    if (kind !== 'deviceCliIn' && kind !== 'pcCmdIn' && kind !== 'termIn') return;

    // The browser must not move to the next control instead of completing.
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const value = input.value;
    const cursor = input.selectionStart;
    if (!value.trim() || cursor === null) return;
    const selectedDevice = kind === 'deviceCliIn' ? selected : null;
    let result;
    try {
      if (kind === 'deviceCliIn') {
        const response = await fetch('/api/ios/complete', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ device: selectedDevice, text: value, cursor })
        });
        result = await response.json();
        if (!response.ok || !result.ok) throw Error(result.error || 'Completion unavailable');
      } else if (kind === 'pcCmdIn') {
        result = localComplete(value, cursor, pcCommands);
      } else {
        const deviceNames = Object.keys(state.devices || {});
        result = localComplete(value, cursor, agentCommands, deviceNames);
      }
    } catch (error) {
      if (input.isConnected) hint(input, error.message);
      return;
    }

    // Ignore stale asynchronous results after typing, moving the cursor,
    // selecting another device, or switching console tabs.
    if (!input.isConnected || document.activeElement !== input ||
        input.value !== value || input.selectionStart !== cursor ||
        (kind === 'deviceCliIn' && selected !== selectedDevice)) return;

    if (result.changed && Number.isInteger(result.start) &&
        Number.isInteger(result.end) && typeof result.replacement === 'string') {
      input.setRangeText(result.replacement, result.start, result.end, 'end');
    }
    const options = result.candidates || [];
    if (options.length > 1) {
      const shown = options.slice(0, 12);
      hint(input, shown.join('    ') +
           (options.length > shown.length ? '    (+' + (options.length - shown.length) + ' more)' : ''));
    } else {
      hint(input, '');
    }
  }, true);
})();
